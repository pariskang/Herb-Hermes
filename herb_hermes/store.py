"""The KnowledgeBase: the in-memory hub that other modules query.

Holds book metadata, the structured herb registry, formula genealogy, all
passages (本草 + 方書), the BM25 index, the herb knowledge graph, the herb
vocabulary, precomputed 药对, and a normalizer. Builds from the raw corpora and
round-trips to a single JSON file.

Persistence stores passage *text* (not the BM25 postings) and rebuilds the
index on load — this keeps the JSON an order of magnitude smaller and makes it
human-inspectable, at the cost of a few seconds of index construction at load.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

from .config import (BM25_B, BM25_K1, DEFAULT_CORPUS_DIR, DEFAULT_FORMULA_DIR,
                     KB_PATH)
from .corpus.loader import load_corpus
from .corpus.formula_loader import load_formula_corpus
from .genealogy.genealogy import FormulaGenealogy
from .kg.graph import HerbGraph
from .models import BookMeta, Formula, HerbEntry, HerbPair, Passage
from .normalize.normalizer import HerbNormalizer
from .retrieval.bm25 import BM25Index


def _formula_passages(formulas: List[Formula]) -> List[Passage]:
    """Turn formulas into retrievable passages (so search/sourcing/药对 see them)."""
    out: List[Passage] = []
    for f in formulas:
        text = "\n".join(x for x in [f.indications, f.composition_raw, f.text] if x)
        out.append(Passage(
            passage_id=f"FX::{f.formula_id}",
            book_title=f.book_title, dynasty=f.dynasty, author=f.author,
            section=f.name, text=text, source_file=f.source_file,
        ))
    return out


class KnowledgeBase:
    def __init__(self) -> None:
        self.books: List[BookMeta] = []
        self.passages: List[Passage] = []
        self.herb_entries: List[HerbEntry] = []
        self.bm25: BM25Index = BM25Index(k1=BM25_K1, b=BM25_B)
        self.graph: HerbGraph = HerbGraph()
        self.normalizer: HerbNormalizer = HerbNormalizer()
        self.registry: Dict[str, List[HerbEntry]] = defaultdict(list)
        self.herb_vocab: List[str] = []
        self.pairs: List[HerbPair] = []
        self.genealogy: FormulaGenealogy = FormulaGenealogy([])

    # ---- build ---------------------------------------------------------
    @classmethod
    def build(cls, corpus_dir: Path = DEFAULT_CORPUS_DIR,
              formula_dir: Optional[Path] = DEFAULT_FORMULA_DIR,
              index_passages: bool = True) -> "KnowledgeBase":
        kb = cls()
        kb.books, kb.passages, kb.herb_entries = load_corpus(corpus_dir)

        raw_names = {e.name for e in kb.herb_entries if len(e.name) >= 2}
        kb.normalizer = HerbNormalizer(extra_canonical=sorted(raw_names))
        kb.herb_vocab = sorted({kb.normalizer.canonical_of(n) for n in raw_names})
        for e in kb.herb_entries:
            kb.registry[kb.normalizer.canonical_of(e.name)].append(e)

        surface_map = kb.normalizer.surface_to_canonical()
        kb.graph = HerbGraph()
        for e in kb.herb_entries:
            kb.graph.add_herb(e, surface_map)

        # 方書 / formula genealogy.
        if formula_dir and Path(formula_dir).exists():
            fbooks, formulas = load_formula_corpus(Path(formula_dir), surface_map)
            kb.books.extend(fbooks)
            kb.passages.extend(_formula_passages(formulas))
            kb.genealogy = FormulaGenealogy(formulas).build_similarity()

        if index_passages:
            kb.bm25 = BM25Index(k1=BM25_K1, b=BM25_B)
            for p in kb.passages:
                if p.text.strip():
                    kb.bm25.add(p)
            kb.bm25.build()

        # Precompute 药对 once (now also over formula compositions).
        from .discovery.cooccurrence import mine_pairs
        kb.pairs = mine_pairs(kb)
        return kb

    # ---- persistence ---------------------------------------------------
    def save(self, path: Path = KB_PATH) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 2,
            "books": [b.to_dict() for b in self.books],
            "herb_entries": [e.to_dict() for e in self.herb_entries],
            "herb_vocab": self.herb_vocab,
            "graph": self.graph.to_node_link(),
            "pairs": [p.to_dict() for p in self.pairs],
            "passages": [p.to_dict() for p in self.passages],
            "genealogy": self.genealogy.to_dict(),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path = KB_PATH) -> "KnowledgeBase":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        kb = cls()
        kb.books = [BookMeta.from_dict(b) for b in data["books"]]
        kb.herb_entries = [HerbEntry.from_dict(e) for e in data["herb_entries"]]
        raw_names = {e.name for e in kb.herb_entries if len(e.name) >= 2}
        kb.normalizer = HerbNormalizer(extra_canonical=sorted(raw_names))
        kb.herb_vocab = data["herb_vocab"]
        for e in kb.herb_entries:
            kb.registry[kb.normalizer.canonical_of(e.name)].append(e)
        kb.pairs = [HerbPair(**p) for p in data.get("pairs", [])]
        kb.genealogy = FormulaGenealogy.from_dict(data.get("genealogy", {}))

        kb.passages = [Passage.from_dict(p) for p in data.get("passages", [])]
        kb.bm25 = BM25Index(k1=BM25_K1, b=BM25_B)
        for p in kb.passages:
            if p.text.strip():
                kb.bm25.add(p)
        kb.bm25.build()

        surface_map = kb.normalizer.surface_to_canonical()
        kb.graph = HerbGraph()
        for e in kb.herb_entries:
            kb.graph.add_herb(e, surface_map)
        return kb

    # ---- convenience ---------------------------------------------------
    def get_entries(self, herb: str) -> List[HerbEntry]:
        canonical = self.normalizer.normalize(herb).canonical
        return self.registry.get(canonical, [])

    def pairs_for(self, herb: str, top_k: int = 20) -> List[HerbPair]:
        canonical = self.normalizer.normalize(herb).canonical
        hits = [p for p in self.pairs if canonical in (p.herb_a, p.herb_b)]
        return hits[:top_k]

    @property
    def stats(self) -> Dict[str, int]:
        return {
            "books": len(self.books),
            "passages": len(self.passages),
            "herb_entries": len(self.herb_entries),
            "unique_herbs": len(self.herb_vocab),
            **{f"graph_{k}": v for k, v in self.graph.stats.items()},
            **{f"formula_{k}": v for k, v in self.genealogy.stats.items()},
        }
