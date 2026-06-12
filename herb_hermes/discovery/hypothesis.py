"""Templated, citation-grounded research-hypothesis cards.

Deterministic and offline: it assembles classical evidence already present in
the knowledge base into the structured Hypothesis Card from the design. Modern
mechanism slots are filled from a small seed mapping and clearly marked as
hypotheses requiring external validation — never fabricated as established
fact.
"""

from __future__ import annotations

import hashlib
from typing import List, Optional

from ..models import HypothesisCard
from ..store import KnowledgeBase
from .sourcing import trace_herb

# Seed disease -> mechanism scaffolding (explicitly hypothesis-level).
DISEASE_MECHANISMS = {
    "骨质疏松": {
        "syndrome": "肾虚血瘀 / 肝肾不足",
        "pathways": ["Wnt/β-catenin", "RANKL/OPG", "HIF-1/VEGF", "PI3K-Akt", "炎症信号"],
        "cell_types": ["成骨细胞", "破骨细胞", "骨髓间充质干细胞", "血管内皮细胞"],
        "axis": "成骨-血管耦合 / 成骨-破骨平衡",
    },
    "骨折": {
        "syndrome": "气滞血瘀 / 肝肾亏虚",
        "pathways": ["BMP/Smad", "Wnt/β-catenin", "VEGF", "TGF-β"],
        "cell_types": ["成骨细胞", "软骨细胞", "骨膜干细胞"],
        "axis": "骨痂形成 / 血管化成骨",
    },
}

DEFAULT_MECHANISM = {
    "syndrome": "（需依证候映射确定）",
    "pathways": ["（待网络药理学补全）"],
    "cell_types": ["（待单细胞定位补全）"],
    "axis": "（待机制链构建）",
}


def _hyp_id(seed: str) -> str:
    h = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:6].upper()
    return f"HH-HYP-{h}"


def build_hypothesis_card(kb: KnowledgeBase, herb: str,
                          partner: Optional[str] = None,
                          disease: str = "骨质疏松") -> HypothesisCard:
    canonical = kb.normalizer.normalize(herb).canonical
    pair_label = canonical + (f"-{kb.normalizer.normalize(partner).canonical}" if partner else "")

    # --- classical evidence from the corpus ---------------------------
    classical: List[str] = []
    src = trace_herb(kb, canonical, max_evidence=6)
    for ev in src.evidence[:6]:
        classical.append(f"{ev.citation}：{ev.snippet}")

    entries = kb.get_entries(canonical)
    if entries:
        e = entries[0]
        if e.functions:
            classical.append(f"《{e.book_title}》功用记载：{e.functions[:60]}")
        if e.indications:
            classical.append(f"《{e.book_title}》主治记载：{e.indications[:60]}")

    if partner:
        pairs = kb.pairs_for(canonical)
        pn = kb.normalizer.normalize(partner).canonical
        hit = next((p for p in pairs if pn in (p.herb_a, p.herb_b)), None)
        if hit:
            books = "、".join(hit.example_books[:3])
            classical.append(f"药对 {pair_label} 在语料中共现 {hit.count} 次（PMI={hit.pmi}），"
                             f"见于：{books}")

    mech = DISEASE_MECHANISMS.get(disease, DEFAULT_MECHANISM)
    question = (f"{pair_label} 药对是否通过调控{mech['axis']}改善{disease}？"
                if partner else
                f"{canonical} 是否通过调控{mech['axis']}改善{disease}？")

    modern_evidence = [
        "成分-靶点（TCMSP / HERB / ETCM）映射 — 待外部数据库接入",
        "GEO 差异表达交集验证 — 待外部数据接入",
        f"通路富集候选：{', '.join(mech['pathways'])}（假设，待验证）",
        f"细胞类型定位候选：{', '.join(mech['cell_types'])}（假设，待 scRNA 验证）",
    ]
    validation = [
        "网络药理学复核成分-靶点-通路",
        f"在 {disease} GEO 数据集中验证候选靶点差异表达",
        "单细胞数据中定位候选靶点的细胞类型",
        "体外（成骨/破骨分化）与动物模型实验验证",
    ]
    risks = [
        "数据库靶点来源不一致，预测靶点缺乏实验验证",
        "成分口服生物利用度与药代动力学可能不足",
        "复方整体作用不能简单等同于单成分靶点叠加",
        "古籍主治与现代疾病映射存在语义偏差",
    ]

    return HypothesisCard(
        hypothesis_id=_hyp_id(pair_label + disease),
        research_question=question,
        classical_evidence=classical or ["（语料中暂未检索到直接证据，建议扩充语料）"],
        modern_evidence=modern_evidence,
        mechanism_chain={
            "disease": disease,
            "syndrome": mech["syndrome"],
            "formula_or_pair": pair_label,
            "pathways": mech["pathways"],
            "cell_types": mech["cell_types"],
            "axis": mech["axis"],
        },
        validation_plan=validation,
        risk_and_counterevidence=risks,
        evidence_score="B-" if classical else "C",
    )
