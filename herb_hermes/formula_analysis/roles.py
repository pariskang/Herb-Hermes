"""君臣佐使推断 (heuristic monarch–minister–assistant–envoy role inference).

Classical theory:
* 君 (monarch) — addresses the principal disease/syndrome; typically the
  largest dose, and often the herb the formula is named after.
* 臣 (minister) — reinforces the monarch or treats a coexisting syndrome.
* 佐 (assistant) — treats accompanying symptoms, moderates toxicity, or 反佐.
* 使 (envoy) — guides drugs to channels (引经) or harmonizes (调和).

The inference combines dose weight (primary), name-match, position, and a
small functional lexicon. It is explicitly a heuristic: every assignment
carries a rationale and a confidence so a clinician/researcher can audit it.
"""

from __future__ import annotations

from typing import Dict, List, Optional

# 调和诸药 → strong 使 candidates.
_HARMONIZE_ENVOY = {"甘草", "炙甘草"}
# 调和营卫 / 和中 → typically 佐 (assistant) when not the chief herb.
_HARMONIZE_ASSIST = {"生薑", "生姜", "薑", "姜", "大棗", "大枣", "紅棗"}
# 载药 / 引经 → 使 when not the chief herb.
_CHANNEL_GUIDE = {"桔梗", "牛膝", "升麻", "桂枝", "柴胡", "薄荷", "蔥白"}

ROLE_NAMES = {"君": "monarch", "臣": "minister", "佐": "assistant", "使": "envoy"}


def _weight(item: Dict) -> float:
    # Only convertible weights count; count units (枚/個…) carry no dose weight.
    g = item.get("grams")
    if g is not None:
        return float(g)
    if item.get("count_unit") or item.get("ml") is not None:
        return 0.0
    v = item.get("value")
    return float(v) if v is not None and item.get("unit") else 0.0


def infer_roles(composition: List[Dict], formula_name: str = "",
                indications: str = "") -> List[Dict]:
    """Assign 君臣佐使 to each composition item (a list of dicts with at least
    ``herb`` and optionally ``grams`` / ``value``). Returns the same items with
    ``role``, ``role_en``, ``reason`` added, ordered 君→臣→佐→使."""
    if not composition:
        return []
    items = [dict(it) for it in composition]
    for i, it in enumerate(items):
        it["_pos"] = i
        it["_w"] = _weight(it)

    has_doses = any(it.get("grams") is not None for it in items)
    name_matches = [it for it in items if it["herb"] and it["herb"] in formula_name]

    # rank by dose weight, then original position
    ranked = sorted(items, key=lambda it: (-it["_w"], it["_pos"]))
    monarch = name_matches[0] if name_matches else ranked[0]
    monarch_w = monarch["_w"] or (ranked[0]["_w"] or 1.0)

    roles: Dict[int, str] = {}
    reasons: Dict[int, str] = {}
    roles[monarch["_pos"]] = "君"
    reasons[monarch["_pos"]] = (
        "方以此药命名，主病主证" if monarch in name_matches else
        ("用量最重，主病主证" if has_doses else "居首位，主病主证"))

    minister_budget = 2
    core: List[Dict] = []
    for it in ranked:
        if it["_pos"] in roles:
            continue
        herb = it["herb"]
        if herb in _HARMONIZE_ENVOY:
            roles[it["_pos"]] = "使"; reasons[it["_pos"]] = "调和诸药"
        elif herb in _HARMONIZE_ASSIST:
            roles[it["_pos"]] = "佐"; reasons[it["_pos"]] = "调和营卫／和中助运"
        elif herb in _CHANNEL_GUIDE and (not has_doses or it["_w"] < 0.5 * monarch_w):
            roles[it["_pos"]] = "使"; reasons[it["_pos"]] = "引经／载药"
        else:
            core.append(it)

    for k, it in enumerate(core):
        if minister_budget > 0 and (not has_doses and k == 0 or
                                    has_doses and it["_w"] >= 0.5 * monarch_w):
            roles[it["_pos"]] = "臣"
            reasons[it["_pos"]] = "用量次于君药，辅助主治" if has_doses else "辅助君药"
            minister_budget -= 1
        else:
            roles[it["_pos"]] = "佐"
            reasons[it["_pos"]] = "佐助／佐制，兼顾兼证"

    result = []
    for i, it in enumerate(composition):
        r = roles.get(i, "佐")
        clean = {k: v for k, v in it.items() if not k.startswith("_")}
        result.append({**clean, "role": r, "role_en": ROLE_NAMES.get(r, ""),
                       "reason": reasons.get(i, "")})
    order = {"君": 0, "臣": 1, "佐": 2, "使": 3}
    result.sort(key=lambda x: order.get(x["role"], 9))
    confidence = "高" if has_doses else "中"
    for r in result:
        r["confidence"] = confidence
    return result
