"""药对 mining: herb-pair co-occurrence with PMI scoring.

Two complementary signals are combined:

1. The 配伍 (compatibility) field of structured herb entries — a near-direct
   statement of which herbs pair with which.
2. Co-occurrence of herb names within the same corpus passage.

Pairs are scored by raw count and pointwise mutual information (PMI).
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from itertools import combinations
from typing import Dict, List, Optional

from ..config import MIN_PAIR_COUNT
from ..models import HerbPair
from ..store import KnowledgeBase


def _bucket_surface(surface_map: Dict[str, str]) -> Dict[str, List[str]]:
    """Group surface forms (len>=2) by first char for fast scanning."""
    buckets: Dict[str, List[str]] = defaultdict(list)
    for surface in surface_map:
        if len(surface) >= 2:
            buckets[surface[0]].append(surface)
    return buckets


def _herbs_in_text(text: str, buckets: Dict[str, List[str]],
                   surface_map: Dict[str, str]) -> set:
    """Return the set of canonical herb names present in ``text``."""
    present_chars = set(text)
    found = set()
    for ch in present_chars:
        for surface in buckets.get(ch, ()):
            if surface in text:
                found.add(surface_map[surface])
    return found


def mine_pairs(kb: KnowledgeBase, min_count: int = MIN_PAIR_COUNT,
               top_k: Optional[int] = None) -> List[HerbPair]:
    """Mine the strongest herb pairs across the corpus."""
    surface_map = kb.normalizer.surface_to_canonical()
    buckets = _bucket_surface(surface_map)

    herb_doc = Counter()
    pair_doc = Counter()
    pair_books: Dict[frozenset, set] = defaultdict(set)
    n_docs = 0

    # Signal 1: compatibility fields (counted as their own "documents").
    for e in kb.herb_entries:
        if not e.compatibility:
            continue
        self_canon = surface_map.get(e.name, e.name)
        partners = _herbs_in_text(e.compatibility, buckets, surface_map)
        partners.discard(self_canon)
        herbs = partners | {self_canon}
        if len(herbs) < 2:
            continue
        n_docs += 1
        for h in herbs:
            herb_doc[h] += 1
        for a, b in combinations(sorted(herbs), 2):
            pair_doc[(a, b)] += 1
            pair_books[frozenset((a, b))].add(e.book_title)

    # Signal 2: passage co-occurrence (prose context).
    for p in kb.passages:
        if not p.text or len(p.text) > 6000:
            continue
        herbs = _herbs_in_text(p.text, buckets, surface_map)
        if len(herbs) < 2:
            continue
        n_docs += 1
        for h in herbs:
            herb_doc[h] += 1
        for a, b in combinations(sorted(herbs), 2):
            pair_doc[(a, b)] += 1
            pair_books[frozenset((a, b))].add(p.book_title)

    pairs: List[HerbPair] = []
    n = max(n_docs, 1)
    for (a, b), c in pair_doc.items():
        if c < min_count:
            continue
        pa, pb = herb_doc[a] / n, herb_doc[b] / n
        pab = c / n
        pmi = math.log(pab / (pa * pb)) if pa > 0 and pb > 0 else 0.0
        pairs.append(HerbPair(
            herb_a=a, herb_b=b, count=c, pmi=round(pmi, 3),
            example_books=sorted(pair_books[frozenset((a, b))])[:5],
        ))

    pairs.sort(key=lambda p: (p.count, p.pmi), reverse=True)
    return pairs[:top_k] if top_k else pairs


def pairs_for_herb(kb: KnowledgeBase, herb: str, min_count: int = 2,
                   top_k: int = 20) -> List[HerbPair]:
    """All mined pairs involving ``herb``, strongest first."""
    canonical = kb.normalizer.normalize(herb).canonical
    all_pairs = mine_pairs(kb, min_count=min_count)
    hits = [p for p in all_pairs if canonical in (p.herb_a, p.herb_b)]
    hits.sort(key=lambda p: (p.count, p.pmi), reverse=True)
    return hits[:top_k]
