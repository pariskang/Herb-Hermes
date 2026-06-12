"""The KnowledgeBase: the in-memory hub that other modules query.

Holds book metadata, the structured herb registry, all passages, the BM25
index, the herb knowledge graph, the herb vocabulary, and a normalizer. Builds
from a raw corpus directory and round-trips to a single JSON file.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

from .config import BM25_B, BM25_K1, DEFAULT_CORPUS_DIR, KB_PATH
from .corpus.loader import load_corpus
from .kg.graph import HerbGraph
from .models import BookMeta, HerbEntry, HerbPair, Passage
from .normalize.normalizer import HerbNormalizer
from .retrieval.bm25 import BM25Index


class KnowledgeBase:
    def __init__(self) -> None:
        self.books: List[BookMeta] = []
        self.passages: List[Passage] = []
        self.herb_entries: List[HerbEntry] = []
        self.bm25: BM25Index = BM25Index(k1=BM25_K1, b=BM25_B)
        self.graph: HerbGraph = HerbGraph()
        self.normalizer: HerbNormalizer = HerbNormalizer()
        # canonical herb name -> list of HerbEntry across books
        self.registry: Dict[str, List[HerbEntry]] = defaultdict(list)
        self.herb_vocab: List[str] = []
        # precomputed herb pairs (药对), strongest first
        self.pairs: List[HerbPair] = []

    # ---- build ---------------------------------------------------------
    @classmethod
    def build(cls, corpus_dir: Path = DEFAULT_CORPUS_DIR,
              index_passages: bool = True) -> "KnowledgeBase":
        kb = cls()
        kb.books, kb.passages, kb.herb_entries = load_corpus(corpus_dir)

        raw_names = {e.name for e in kb.herb_entries if len(e.name) >= 2}
        kb.normalizer = HerbNormalizer(extra_canonical=sorted(raw_names))
        # Canonical vocabulary (aliases collapsed onto canonical names).
        kb.herb_vocab = sorted({kb.normalizer.canonical_of(n) for n in raw_names})

        for e in kb.herb_entries:
            kb.registry[kb.normalizer.canonical_of(e.name)].append(e)

        surface_map = kb.normalizer.surface_to_canonical()
        kb.graph = HerbGraph()
        for e in kb.herb_entries:
            kb.graph.add_herb(e, surface_map)

        if index_passages:
            kb.bm25 = BM25Index(k1=BM25_K1, b=BM25_B)
            for p in kb.passages:
                if p.text.strip():
                    kb.bm25.add(p)
            kb.bm25.build()

        # Precompute 药对 once (the corpus scan is too slow to run per request).
        from .discovery.cooccurrence import mine_pairs  # local import avoids cycle
        kb.pairs = mine_pairs(kb)
        return kb

    # ---- persistence ---------------------------------------------------
    def save(self, path: Path = KB_PATH) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "books": [b.to_dict() for b in self.books],
            "herb_entries": [e.to_dict() for e in self.herb_entries],
            "herb_vocab": self.herb_vocab,
            "graph": self.graph.to_node_link(),
            "pairs": [p.to_dict() for p in self.pairs],
            "bm25": self.bm25.to_dict(),
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
        kb.bm25 = BM25Index.from_dict(data["bm25"])
        kb.passages = kb.bm25.passages
        # Rebuild the graph from entries (cheap, keeps adjacency consistent).
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
        """Cached 药对 lookup for one herb (no corpus rescan)."""
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
        }
