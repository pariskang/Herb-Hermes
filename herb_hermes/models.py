"""Core data models for Herb-Hermes.

Plain dataclasses (no third-party dependency) with explicit ``to_dict`` /
``from_dict`` so the whole knowledge base round-trips through JSON.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class BookMeta:
    """Metadata for one classical book, parsed from its ``<book>`` block."""

    title: str
    author: str = ""
    dynasty: str = ""
    year: str = ""
    category: str = ""
    quality: str = ""
    book_id: str = ""
    n_passages: int = 0
    n_herb_entries: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BookMeta":
        return cls(**{k: d.get(k, "") for k in cls.__dataclass_fields__ if k not in ("n_passages", "n_herb_entries")},
                   n_passages=d.get("n_passages", 0),
                   n_herb_entries=d.get("n_herb_entries", 0))


@dataclass
class Passage:
    """A retrievable chunk of text with a precise classical citation."""

    passage_id: str
    book_title: str
    dynasty: str
    author: str
    section: str
    text: str
    source_file: str = ""

    @property
    def citation(self) -> str:
        bits = [self.book_title]
        if self.section and self.section != self.book_title:
            bits.append(self.section)
        meta = "·".join(b for b in [self.dynasty, self.author] if b)
        head = "·".join(bits)
        return f"《{head}》" + (f"（{meta}）" if meta else "")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Passage":
        return cls(**{k: d.get(k, "") for k in cls.__dataclass_fields__})


@dataclass
class HerbEntry:
    """A structured per-herb record parsed from an itemized (條列版) book.

    Fields mirror the classical itemized layout. ``raw_fields`` keeps every
    field exactly as parsed so nothing is silently dropped.
    """

    name: str
    book_title: str
    dynasty: str = ""
    author: str = ""
    code: str = ""
    aliases: List[str] = field(default_factory=list)
    nature_flavor: str = ""      # 性味 / 性 / 味
    meridians: str = ""          # 歸經
    functions: str = ""          # 功用 / 功能
    indications: str = ""        # 主治
    contraindications: str = ""  # 禁忌
    processing: str = ""         # 炮製
    compatibility: str = ""      # 配伍
    category: str = ""           # 十劑 / 類別
    notes: str = ""              # 其他 / 註
    source_file: str = ""
    raw_fields: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "HerbEntry":
        return cls(**{k: d.get(k, cls.__dataclass_fields__[k].default
                               if cls.__dataclass_fields__[k].default is not None else "")
                      for k in cls.__dataclass_fields__})


@dataclass
class Evidence:
    """One piece of classical evidence backing a claim, fully attributable."""

    book_title: str
    dynasty: str
    author: str
    section: str
    snippet: str
    passage_id: str = ""

    @property
    def citation(self) -> str:
        meta = "·".join(b for b in [self.dynasty, self.author] if b)
        head = self.book_title + (f"·{self.section}" if self.section and self.section != self.book_title else "")
        return f"《{head}》" + (f"（{meta}）" if meta else "")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SourcingResult:
    """本草溯源: how a single herb is attested across books and dynasties."""

    herb: str
    aliases: List[str] = field(default_factory=list)
    ambiguous: bool = False
    ambiguity_note: str = ""
    evidence: List[Evidence] = field(default_factory=list)
    dynasty_timeline: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["evidence"] = [e.to_dict() if isinstance(e, Evidence) else e for e in self.evidence]
        return d


@dataclass
class HerbPair:
    """A mined herb pair (药对) with co-occurrence statistics."""

    herb_a: str
    herb_b: str
    count: int
    pmi: float
    example_books: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HypothesisCard:
    """A templated, citation-grounded research-hypothesis card."""

    hypothesis_id: str
    research_question: str
    classical_evidence: List[str] = field(default_factory=list)
    modern_evidence: List[str] = field(default_factory=list)
    mechanism_chain: Dict[str, Any] = field(default_factory=dict)
    validation_plan: List[str] = field(default_factory=list)
    risk_and_counterevidence: List[str] = field(default_factory=list)
    evidence_score: str = "C"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
