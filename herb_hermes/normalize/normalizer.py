"""Resolve a raw herb token to a canonical name (with ambiguity flags)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from .aliases import ALIAS_TABLE, AMBIGUOUS_TOKENS, CONFUSABLE_GROUPS

# A tiny simplified -> traditional bridge for the handful of characters that
# appear in user queries against this traditional-character corpus.
_S2T = {
    "黄": "黃", "芪": "芪", "归": "歸", "术": "朮", "参": "參", "芎": "芎",
    "续": "續", "断": "斷", "补": "補", "灵": "靈", "苍": "蒼", "药": "藥",
    "当": "當", "干": "乾", "地": "地", "丹": "丹", "枣": "棗", "贝": "貝",
}


def to_traditional(text: str) -> str:
    return "".join(_S2T.get(ch, ch) for ch in text)


@dataclass
class NormalizedName:
    raw: str
    canonical: str
    aliases: List[str]
    ambiguous: bool
    note: str = ""


class HerbNormalizer:
    """Maps aliases to canonical names and flags ambiguous tokens.

    Built from the seed :data:`ALIAS_TABLE`, optionally extended with the set
    of herb names actually observed in the corpus so corpus-attested names are
    treated as canonical even when not in the seed table.
    """

    def __init__(self, extra_canonical: Optional[List[str]] = None) -> None:
        self._alias_to_canonical: Dict[str, str] = {}
        self._canonical_to_aliases: Dict[str, List[str]] = {}
        for canonical, aliases in ALIAS_TABLE.items():
            self._register(canonical, aliases)
        if extra_canonical:
            for name in extra_canonical:
                self._canonical_to_aliases.setdefault(name, [])
                self._alias_to_canonical.setdefault(name, name)

    def _register(self, canonical: str, aliases: List[str]) -> None:
        self._canonical_to_aliases.setdefault(canonical, [])
        self._alias_to_canonical[canonical] = canonical
        for a in aliases:
            if a not in self._canonical_to_aliases[canonical]:
                self._canonical_to_aliases[canonical].append(a)
            self._alias_to_canonical[a] = canonical

    def normalize(self, raw: str) -> NormalizedName:
        token = to_traditional(raw.strip())
        if token in AMBIGUOUS_TOKENS:
            return NormalizedName(raw, token, [], True, AMBIGUOUS_TOKENS[token])
        canonical = self._alias_to_canonical.get(token, token)
        aliases = self.aliases_of(canonical)
        note = self._confusable_note(canonical)
        return NormalizedName(raw, canonical, aliases, False, note)

    def aliases_of(self, canonical: str) -> List[str]:
        return list(self._canonical_to_aliases.get(canonical, []))

    def canonical_of(self, token: str) -> str:
        """Map any surface form to its canonical name (identity if unknown)."""
        return self._alias_to_canonical.get(to_traditional(token), to_traditional(token))

    def surface_to_canonical(self) -> Dict[str, str]:
        """Every known surface form (canonical names, aliases, corpus names)
        mapped to its canonical name. Used to match herbs inside free text."""
        return dict(self._alias_to_canonical)

    def all_surface_forms(self, canonical: str) -> List[str]:
        """Canonical name plus every alias — used to match across the corpus."""
        forms = [canonical] + self.aliases_of(canonical)
        seen, out = set(), []
        for f in forms:
            if f and f not in seen:
                seen.add(f)
                out.append(f)
        return out

    def _confusable_note(self, canonical: str) -> str:
        for group in CONFUSABLE_GROUPS:
            if canonical in group:
                others = "、".join(sorted(group - {canonical}))
                return f"易與 {others} 混淆，注意區分。"
        return ""
