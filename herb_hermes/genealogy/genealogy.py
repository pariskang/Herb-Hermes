"""Reconstruct formula lineage from structural nesting, inline 加減 cues and
composition similarity (类方网络), plus cross-book 演变 of same-named formulas.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from ..models import Formula

# Candidate generation seeds from each formula's rarest herbs (most
# discriminative), so even formulas built from common herbs find their 类方.
_SIM_SEED_HERBS = 3           # how many rarest herbs to seed candidates from
_SIM_SEED_DF_CAP = 3000       # skip a seed scanning more than this many formulas
_SIM_TOP_K = 8
_SIM_MIN_JACCARD = 0.5
_SIM_MIN_SHARED = 3

# Reject mis-detected "formulas" (chapter headings, descriptive/symptom titles).
_BAD_NAME = re.compile(r"[第卷論]|療法|应用|應用|諸方|治法|雜|方論|歌|訣")
# Canonical formulas are named after a dosage form; require such a suffix so
# symptom-titled entries (白帶/自汗) don't pollute the 类方 network.
_FORM_SUFFIX = re.compile(r"(湯|散|丸|飲|膏|丹|煎|錠|餅|酒|茶|圓|飲子)$")


def _formula_like(name: str) -> bool:
    n = _norm_name(name)
    if not (2 <= len(n) <= 9) or _BAD_NAME.search(n):
        return False
    return bool(_FORM_SUFFIX.search(n))


_STRIP_CHARS = " 　【】（）()「」『』《》〔〕[]"


def _norm_name(name: str) -> str:
    for ch in _STRIP_CHARS:
        name = name.replace(ch, "")
    return name.strip()


class FormulaGenealogy:
    def __init__(self, formulas: List[Formula]) -> None:
        self.formulas = formulas
        self.by_id: Dict[str, Formula] = {f.formula_id: f for f in formulas}
        self.by_name: Dict[str, List[Formula]] = defaultdict(list)
        self.children: Dict[str, List[str]] = defaultdict(list)
        for f in formulas:
            self.by_name[_norm_name(f.name)].append(f)
            if f.parent_id:
                self.children[f.parent_id].append(f.formula_id)
        # similarity edges: fid -> [(other_fid, jaccard, shared_count)]
        self.similar: Dict[str, List[Tuple[str, float, int]]] = {}

    # ---- similarity (类方) ------------------------------------------------
    def build_similarity(self) -> "FormulaGenealogy":
        herb_index: Dict[str, List[str]] = defaultdict(list)
        for f in self.formulas:
            for h in set(f.composition_herbs):
                herb_index[h].append(f.formula_id)
        df = {h: len(ids) for h, ids in herb_index.items()}

        for f in self.formulas:
            fs = set(f.composition_herbs)
            if len(fs) < 3 or not _formula_like(f.name):
                continue
            cand_counts: Dict[str, int] = defaultdict(int)
            # seed from the rarest (most discriminative) herbs of this formula
            seeds = sorted(fs, key=lambda h: df.get(h, 0))[:_SIM_SEED_HERBS]
            for h in seeds:
                if df.get(h, 0) > _SIM_SEED_DF_CAP:
                    continue
                for oid in herb_index[h]:
                    if oid != f.formula_id:
                        cand_counts[oid] += 1
            scored: List[Tuple[str, float, int]] = []
            for oid, shared in cand_counts.items():
                if shared < _SIM_MIN_SHARED:
                    continue
                other = self.by_id[oid]
                if not _formula_like(other.name) or _norm_name(other.name) == _norm_name(f.name):
                    continue
                os_ = set(other.composition_herbs)
                union = len(fs | os_)
                jac = len(fs & os_) / union if union else 0.0
                if jac >= _SIM_MIN_JACCARD:
                    scored.append((oid, round(jac, 3), len(fs & os_)))
            scored.sort(key=lambda x: (x[1], x[2]), reverse=True)
            if scored:
                self.similar[f.formula_id] = scored[:_SIM_TOP_K]
        return self

    # ---- queries ---------------------------------------------------------
    def lookup(self, name: str) -> List[Formula]:
        return self.by_name.get(_norm_name(name), [])

    def ancestors(self, fid: str, max_depth: int = 8) -> List[Formula]:
        out, seen = [], set()
        cur = self.by_id.get(fid)
        while cur and cur.parent_id and cur.parent_id not in seen and max_depth > 0:
            seen.add(cur.parent_id)
            parent = self.by_id.get(cur.parent_id)
            if not parent:
                break
            out.append(parent)
            cur = parent
            max_depth -= 1
        return out

    def descendants(self, fid: str) -> List[Formula]:
        return [self.by_id[c] for c in self.children.get(fid, []) if c in self.by_id]

    def similar_to(self, fid: str, top_k: int = _SIM_TOP_K) -> List[Tuple[Formula, float, int]]:
        out = []
        for oid, jac, shared in self.similar.get(fid, [])[:top_k]:
            if oid in self.by_id:
                out.append((self.by_id[oid], jac, shared))
        return out

    def formulas_with_herb(self, herb: str, limit: int = 50) -> List[Formula]:
        hits = [f for f in self.formulas if herb in f.composition_herbs]
        hits.sort(key=lambda f: len(f.composition_herbs))
        return hits[:limit]

    def _representative(self, copies: List[Formula]) -> Formula:
        """Pick the copy with the modal composition (robust to a few bad
        extractions); tie-break toward a richer, non-empty herb set."""
        from collections import Counter
        sigs = Counter(frozenset(f.composition_herbs) for f in copies if f.composition_herbs)
        if sigs:
            best_sig, _ = max(sigs.items(), key=lambda kv: (kv[1], len(kv[0])))
            for f in copies:
                if frozenset(f.composition_herbs) == best_sig:
                    return f
        return max(copies, key=lambda f: len(f.composition_herbs))

    def representative_formula(self, name: str):
        """The representative :class:`Formula` object for a name (or None)."""
        copies = self.lookup(name)
        return self._representative(copies) if copies else None

    def representative_group(self, name: str) -> List[Formula]:
        """Copies sharing the representative (modal) composition — same formula,
        different book editions. Used to find a dose-bearing edition without
        drifting onto an unrelated same-named variant."""
        copies = self.lookup(name)
        if not copies:
            return []
        rep = self._representative(copies)
        sig = frozenset(rep.composition_herbs)
        kin = [f for f in copies if frozenset(f.composition_herbs) == sig]
        return kin or [rep]

    def genealogy(self, name: str) -> Dict:
        """Full genealogy view for a formula name (across all its book copies)."""
        copies = self.lookup(name)
        if not copies:
            return {"name": name, "found": False}

        primary = self._representative(copies)
        occurrences = [
            {"book": f.book_title, "dynasty": f.dynasty, "author": f.author,
             "category": f.category, "herbs": f.composition_herbs,
             "indications": f.indications, "formula_id": f.formula_id}
            for f in sorted(copies, key=lambda f: f.dynasty)
        ]

        ancestors, descendants, similar, derivations = [], [], [], []
        seen_sim = set()
        for f in copies:
            for a in self.ancestors(f.formula_id):
                ancestors.append({"name": a.name, "book": a.book_title, "herbs": a.composition_herbs})
            for d in self.descendants(f.formula_id):
                descendants.append({"name": d.name, "book": d.book_title,
                                    "herbs": d.composition_herbs, "indications": d.indications})
            for s, jac, shared in self.similar_to(f.formula_id):
                key = _norm_name(s.name)
                if key not in seen_sim and key != _norm_name(name):
                    seen_sim.add(key)
                    similar.append({"name": s.name, "book": s.book_title,
                                    "jaccard": jac, "shared": shared, "herbs": s.composition_herbs})
            for dv in f.derivations:
                derivations.append({"relation": dv.relation, "herbs": dv.herbs,
                                    "target": dv.target, "from_book": f.book_title})

        similar.sort(key=lambda x: x["jaccard"], reverse=True)
        return {
            "name": name,
            "found": True,
            "primary": {
                "book": primary.book_title, "dynasty": primary.dynasty,
                "author": primary.author, "category": primary.category,
                "composition_herbs": primary.composition_herbs,
                "composition_raw": primary.composition_raw,
                "indications": primary.indications, "preparation": primary.preparation,
            },
            "occurrences": occurrences,
            "ancestors": ancestors,
            "descendants": descendants[:40],
            "derivations": derivations,
            "similar": similar[:12],
        }

    @property
    def stats(self) -> Dict[str, int]:
        return {
            "formulas": len(self.formulas),
            "unique_formula_names": len(self.by_name),
            "with_parent": sum(1 for f in self.formulas if f.parent_id),
            "with_derivation": sum(1 for f in self.formulas if f.derivations),
            "similarity_edges": sum(len(v) for v in self.similar.values()),
        }

    # ---- serialization ---------------------------------------------------
    def to_dict(self) -> Dict:
        return {
            "formulas": [f.to_dict() for f in self.formulas],
            "similar": {k: v for k, v in self.similar.items()},
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "FormulaGenealogy":
        g = cls([Formula.from_dict(x) for x in d.get("formulas", [])])
        g.similar = {k: [tuple(t) for t in v] for k, v in d.get("similar", {}).items()}
        return g
