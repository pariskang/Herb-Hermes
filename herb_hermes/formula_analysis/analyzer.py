"""Tie dose parsing + role inference to a concrete :class:`Formula`."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..models import Formula
from .dosage import Dose, DoseConverter, parse_dose_token
from .roles import infer_roles


@dataclass
class FormulaAnalysis:
    name: str
    dynasty: str
    liang_grams: float
    composition: List[Dict] = field(default_factory=list)  # herb+dose+role
    total_grams: Optional[float] = None
    note: str = ""

    def to_dict(self) -> Dict:
        return {
            "name": self.name, "dynasty": self.dynasty,
            "liang_grams": self.liang_grams, "composition": self.composition,
            "total_grams": self.total_grams, "note": self.note,
        }


def _dedup_canonical(herbs: List[str], normalizer) -> List[str]:
    seen, out = set(), []
    for h in herbs:
        c = normalizer.canonical_of(h)
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _herb_positions(herbs: List[str], raw: str, normalizer) -> List[tuple]:
    """(canonical, surface, index) of each herb's first mention in ``raw``."""
    out = []
    for canon in herbs:
        best = None
        for surf in normalizer.all_surface_forms(canon):
            idx = raw.find(surf)
            if idx >= 0 and (best is None or idx < best[1]):
                best = (surf, idx)
        if best:
            out.append((canon, best[0], best[1]))
    out.sort(key=lambda x: x[2])
    return out


def _dose_from_text(canon: str, text: str, normalizer) -> Optional[Dose]:
    """Fallback: find ``<herb>（…dose…）`` anywhere in the fuller formula text."""
    for surf in normalizer.all_surface_forms(canon):
        m = re.search(re.escape(surf) + r"\s*[（(]([^)）]{0,18})[)）]", text)
        if m:
            d = parse_dose_token(m.group(1))
            if d:
                return d
    return None


def analyze_formula(formula: Formula, normalizer) -> FormulaAnalysis:
    raw = formula.composition_raw or formula.text or ""
    full_text = "\n".join(x for x in [formula.composition_raw, formula.text] if x)
    conv = DoseConverter(formula.dynasty)
    herbs = _dedup_canonical(formula.composition_herbs, normalizer)
    positions = _herb_positions(herbs, raw, normalizer)

    comp: List[Dict] = []
    for k, (canon, surf, idx) in enumerate(positions):
        nxt = positions[k + 1][2] if k + 1 < len(positions) else len(raw)
        window = raw[idx + len(surf): max(idx + len(surf), nxt)][:24]
        dose = parse_dose_token(window) or _dose_from_text(canon, full_text, normalizer)
        item: Dict = {"herb": canon}
        if dose:
            conv.convert(dose)
            item.update({"dose_raw": dose.raw, "value": dose.value, "unit": dose.unit,
                         "grams": dose.grams, "ml": dose.ml, "count_unit": dose.count_unit,
                         "each": dose.each, "dose_note": dose.note})
        comp.append(item)

    # propagate 各 (shared) doses backward to herbs lacking a dose
    for k, item in enumerate(comp):
        if item.get("each") and item.get("grams") is not None:
            j = k - 1
            while j >= 0 and "grams" not in comp[j]:
                comp[j].update({"value": item["value"], "unit": item["unit"],
                                "grams": item["grams"], "dose_note": "（承『各』量）"})
                j -= 1

    comp = infer_roles(comp, formula.name, formula.indications)
    total = sum(it["grams"] for it in comp if it.get("grams")) or None
    return FormulaAnalysis(
        name=formula.name, dynasty=formula.dynasty or "（不详）",
        liang_grams=conv.liang_g, composition=comp,
        total_grams=round(total, 1) if total else None,
        note=f"剂量按{conv._era_label()}制折算（1兩≈{conv.liang_g}g）；"
             "古今折算存学派分歧，仅供科研参考，不作处方依据。",
    )
