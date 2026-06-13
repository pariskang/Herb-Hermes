"""Render herb dossiers and hypothesis cards to Markdown (一键导出报告).

Markdown is chosen as the portable target: it renders on GitHub, converts to
Word/PDF via pandoc, and embeds cleanly in a front-end. No dependencies.
"""

from __future__ import annotations

from typing import List

from .discovery.hypothesis import build_hypothesis_card
from .discovery.sourcing import trace_herb
from .models import HypothesisCard
from .store import KnowledgeBase


def hypothesis_to_markdown(card: HypothesisCard) -> str:
    mc = card.mechanism_chain
    lines: List[str] = [
        f"### 科研假设卡 {card.hypothesis_id}",
        "",
        f"**研究问题**：{card.research_question}",
        "",
        f"**证据等级**：{card.evidence_score}",
        "",
        "#### 古籍证据",
    ]
    lines += [f"- {e}" for e in card.classical_evidence]
    lines += ["", "#### 现代证据（待外部数据接入）"]
    lines += [f"- {e}" for e in card.modern_evidence]
    lines += ["", "#### 机制链",
              f"- 疾病：{mc.get('disease','')}",
              f"- 证候：{mc.get('syndrome','')}",
              f"- 方药/药对：{mc.get('formula_or_pair','')}",
              f"- 关键轴：{mc.get('axis','')}",
              f"- 通路：{', '.join(mc.get('pathways', []))}",
              f"- 细胞类型：{', '.join(mc.get('cell_types', []))}",
              "", "#### 验证计划"]
    lines += [f"{i}. {v}" for i, v in enumerate(card.validation_plan, 1)]
    lines += ["", "#### 风险与反证"]
    lines += [f"- {r}" for r in card.risk_and_counterevidence]
    return "\n".join(lines)


def herb_dossier_markdown(kb: KnowledgeBase, herb: str,
                          disease: str = "骨质疏松") -> str:
    canonical = kb.normalizer.normalize(herb).canonical
    out: List[str] = [f"# 本草档案：{canonical}", ""]

    src = trace_herb(kb, canonical)
    if src.aliases:
        out += [f"**异名**：{'、'.join(src.aliases)}", ""]

    entries = kb.get_entries(canonical)
    if entries:
        e = entries[0]
        out += [f"## 结构化条目（《{e.book_title}》）", ""]
        for label, val in [("性味", e.nature_flavor), ("归经", e.meridians),
                           ("功用", e.functions), ("主治", e.indications),
                           ("禁忌", e.contraindications), ("炮製", e.processing),
                           ("配伍", e.compatibility)]:
            if val:
                out.append(f"- **{label}**：{val.strip()}")
        out.append("")

    out += ["## 历代著录时间线", ""]
    for tb in src.dynasty_timeline:
        out.append(f"- [{tb['dynasty'] or '—'}] 《{tb['book']}》 {tb['author']}（提及 {tb['mentions']} 次）")
    out.append("")

    pairs = kb.pairs_for(canonical, top_k=10)
    if pairs:
        out += ["## 高频药对（共现挖掘）", ""]
        for p in pairs:
            other = p.herb_b if p.herb_a == canonical else p.herb_a
            out.append(f"- {canonical}–{other}：共现 {p.count} 次，PMI={p.pmi}")
        out.append("")

    nbrs = kb.graph.neighbors(canonical)
    funcs = [n["label"] for n in nbrs if n["type"] == "function"]
    if funcs:
        out += ["## 功效图谱节点", "", f"- {'、'.join(funcs)}", ""]

    formulas = kb.genealogy.formulas_with_herb(canonical, limit=12)
    if formulas:
        out += ["## 所在经典方剂", ""]
        for f in formulas:
            comp = "、".join(f.composition_herbs[:8])
            out.append(f"- 《{f.book_title}》{f.name}：{comp}")
        out.append("")

    out += ["## 科研假设", ""]
    partner = None
    if pairs:
        partner = pairs[0].herb_b if pairs[0].herb_a == canonical else pairs[0].herb_a
    card = build_hypothesis_card(kb, canonical, partner=partner, disease=disease)
    out.append(hypothesis_to_markdown(card))

    out += ["", "---", "*本报告由 Herb-Hermes 自动生成；现代机制为待验证假设，不构成临床处方建议。*"]
    return "\n".join(out)
