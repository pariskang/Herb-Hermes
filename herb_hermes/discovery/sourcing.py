"""本草溯源: trace how one herb is attested across books and dynasties."""

from __future__ import annotations

from collections import defaultdict
from typing import List, Optional

from ..models import Evidence, SourcingResult
from ..store import KnowledgeBase

# Rough chronological ordering of dynasties for timeline sorting.
_DYNASTY_ORDER = {
    "先秦": 0, "秦": 1, "漢": 2, "魏": 3, "晉": 4, "南北朝": 5, "隋": 6,
    "唐": 7, "五代": 8, "宋": 9, "金": 10, "元": 11, "明": 12, "清": 13,
    "民國": 14, "近代": 15, "現代": 16, "": 99,
}


def _dynasty_key(d: str) -> int:
    for name, order in _DYNASTY_ORDER.items():
        if name and name in d:
            return order
    return _DYNASTY_ORDER.get(d, 99)


def _snippet(text: str, term: str, width: int = 60) -> str:
    pos = text.find(term)
    if pos < 0:
        return text[:width].replace("\n", " ")
    start = max(0, pos - width // 2)
    end = min(len(text), pos + len(term) + width // 2)
    return ("…" if start > 0 else "") + text[start:end].replace("\n", " ") + ("…" if end < len(text) else "")


def trace_herb(kb: KnowledgeBase, herb: str, max_evidence: int = 40) -> SourcingResult:
    """Collect dated evidence for a herb across the whole corpus."""
    norm = kb.normalizer.normalize(herb)
    if norm.ambiguous:
        return SourcingResult(herb=norm.canonical, ambiguous=True,
                              ambiguity_note=norm.note)

    forms = kb.normalizer.all_surface_forms(norm.canonical)
    evidence: List[Evidence] = []
    by_book = set()
    timeline_books: dict = {}

    for p in kb.passages:
        if not p.text:
            continue
        matched = next((f for f in forms if f and f in p.text), None)
        if not matched:
            continue
        key = (p.book_title, p.section)
        if key in by_book:
            continue
        by_book.add(key)
        evidence.append(Evidence(
            book_title=p.book_title, dynasty=p.dynasty, author=p.author,
            section=p.section, snippet=_snippet(p.text, matched), passage_id=p.passage_id,
        ))
        tb = timeline_books.setdefault(p.book_title, {
            "book": p.book_title, "dynasty": p.dynasty, "author": p.author, "mentions": 0})
        tb["mentions"] += 1

    evidence.sort(key=lambda e: (_dynasty_key(e.dynasty), e.book_title))
    timeline = sorted(timeline_books.values(), key=lambda t: (_dynasty_key(t["dynasty"]), t["book"]))

    return SourcingResult(
        herb=norm.canonical,
        aliases=norm.aliases,
        ambiguous=False,
        ambiguity_note=norm.note,
        evidence=evidence[:max_evidence],
        dynasty_timeline=timeline,
    )
