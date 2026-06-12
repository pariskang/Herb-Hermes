"""Demo: 从经典本草到科研假设 —— 补肾活血类方药治疗骨质疏松的知识发现。

Runs the MVP end-to-end on the bundled 本草 corpus and prints a compact,
citation-grounded walk-through for the osteoporosis theme from the design doc.

    python scripts/demo_osteoporosis.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herb_hermes.config import KB_PATH
from herb_hermes.store import KnowledgeBase
from herb_hermes.discovery.sourcing import trace_herb
from herb_hermes.discovery.hypothesis import build_hypothesis_card

HERBS = ["杜仲", "續斷", "骨碎補", "淫羊藿", "熟地黃", "黃芪", "當歸", "牛膝"]


def main() -> int:
    kb = KnowledgeBase.load(KB_PATH) if KB_PATH.exists() else KnowledgeBase.build()
    print("# Herb-Hermes 骨质疏松知识发现 Demo\n")
    print("## 1. 语料底座")
    for k, v in kb.stats.items():
        print(f"   {k:16s}{v}")

    print("\n## 2. 补肾强骨类本草 —— 古籍证据检索（强筋骨 / 补肝肾）")
    for p, score in kb.bm25.search("強筋骨 補肝腎 續筋接骨", top_k=5):
        print(f"   [{score:5.1f}] {p.citation}")
        print(f"           {p.text.strip()[:70].replace(chr(10),' ')}…")

    print("\n## 3. 单味药溯源时间线（杜仲）")
    src = trace_herb(kb, "杜仲")
    for tb in src.dynasty_timeline[:8]:
        print(f"   [{tb['dynasty'] or '—'}] 《{tb['book']}》 提及×{tb['mentions']}")

    print("\n## 4. 高频药对（黃芪 / 當歸 方向）")
    for p in kb.pairs_for("黃芪", top_k=6):
        other = p.herb_b if p.herb_a == "黃芪" else p.herb_a
        print(f"   黃芪–{other}: count={p.count} pmi={p.pmi}")

    print("\n## 5. 自动科研假设卡")
    card = build_hypothesis_card(kb, "黃芪", partner="當歸", disease="骨质疏松")
    print(f"   {card.hypothesis_id}: {card.research_question}")
    print(f"   证据等级: {card.evidence_score}")
    print(f"   机制轴: {card.mechanism_chain['axis']}")
    print(f"   候选通路: {', '.join(card.mechanism_chain['pathways'])}")
    print(f"   古籍证据条数: {len(card.classical_evidence)}")

    print("\n（提示：`python -m herb_hermes.cli report 杜仲 --out 杜仲.md` 导出完整报告）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
