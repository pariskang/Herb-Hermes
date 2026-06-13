"""A compact, dependency-free BM25 index with serialization.

Indexes :class:`~herb_hermes.models.Passage` objects and returns ranked hits
together with the passage so every answer carries a classical citation.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Dict, List, Tuple

from ..models import Passage
from .tokenizer import tokenize


class BM25Index:
    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.passages: List[Passage] = []
        self.doc_tokens: List[Counter] = []
        self.doc_len: List[int] = []
        self.df: Dict[str, int] = defaultdict(int)
        self.postings: Dict[str, List[Tuple[int, int]]] = defaultdict(list)
        self.avgdl: float = 0.0
        self._built = False

    def add(self, passage: Passage) -> None:
        toks = tokenize(passage.text)
        tf = Counter(toks)
        idx = len(self.passages)
        self.passages.append(passage)
        self.doc_tokens.append(tf)
        self.doc_len.append(len(toks))
        for term, c in tf.items():
            self.df[term] += 1
            self.postings[term].append((idx, c))
        self._built = False

    def build(self) -> "BM25Index":
        n = len(self.doc_len)
        self.avgdl = (sum(self.doc_len) / n) if n else 0.0
        self._built = True
        return self

    def _idf(self, term: str) -> float:
        n = len(self.passages)
        df = self.df.get(term, 0)
        if df == 0:
            return 0.0
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def search(self, query: str, top_k: int = 10) -> List[Tuple[Passage, float]]:
        if not self._built:
            self.build()
        q_terms = [t for t in tokenize(query) if t in self.df]
        if not q_terms:
            return []
        scores: Dict[int, float] = defaultdict(float)
        for term in set(q_terms):
            idf = self._idf(term)
            if idf <= 0:
                continue
            for doc_id, tf in self.postings[term]:
                dl = self.doc_len[doc_id]
                denom = tf + self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1))
                scores[doc_id] += idf * (tf * (self.k1 + 1)) / (denom or 1)
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
        return [(self.passages[i], s) for i, s in ranked]

    # ---- serialization -------------------------------------------------
    def to_dict(self) -> Dict:
        return {
            "k1": self.k1,
            "b": self.b,
            "passages": [p.to_dict() for p in self.passages],
            "doc_len": self.doc_len,
            "df": dict(self.df),
            "postings": {t: post for t, post in self.postings.items()},
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "BM25Index":
        idx = cls(k1=d.get("k1", 1.5), b=d.get("b", 0.75))
        idx.passages = [Passage.from_dict(p) for p in d["passages"]]
        idx.doc_len = d["doc_len"]
        idx.df = defaultdict(int, d["df"])
        idx.postings = defaultdict(list, {t: [tuple(x) for x in post]
                                          for t, post in d["postings"].items()})
        idx.doc_tokens = [Counter() for _ in idx.passages]
        return idx.build()
