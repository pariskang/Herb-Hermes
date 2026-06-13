"""Herb-Hermes command-line interface.

Examples:
    python -m herb_hermes.cli build
    python -m herb_hermes.cli stats
    python -m herb_hermes.cli herb 黃芪
    python -m herb_hermes.cli trace 當歸
    python -m herb_hermes.cli search 強筋骨 補肝腎
    python -m herb_hermes.cli pairs --herb 黃芪
    python -m herb_hermes.cli hypothesis 黃芪 --partner 當歸 --disease 骨质疏松
    python -m herb_hermes.cli graph 黃芪
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import DEFAULT_CORPUS_DIR, KB_PATH
from .discovery.hypothesis import build_hypothesis_card
from .discovery.sourcing import trace_herb
from .store import KnowledgeBase


def _load_kb() -> KnowledgeBase:
    if not KB_PATH.exists():
        print(f"[info] no prebuilt KB at {KB_PATH}; building from corpus …", file=sys.stderr)
        kb = KnowledgeBase.build(DEFAULT_CORPUS_DIR)
        kb.save()
        return kb
    return KnowledgeBase.load(KB_PATH)


def _print_json(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def cmd_build(args) -> int:
    kb = KnowledgeBase.build(Path(args.corpus))
    kb.save()
    _print_json(kb.stats)
    return 0


def cmd_stats(args) -> int:
    _print_json(_load_kb().stats)
    return 0


def cmd_herb(args) -> int:
    kb = _load_kb()
    entries = kb.get_entries(args.name)
    if not entries:
        norm = kb.normalizer.normalize(args.name)
        if norm.ambiguous:
            print(f"『{args.name}』为歧义名物：{norm.note}")
            return 0
        print(f"未找到结构化条目：{args.name}（可尝试 `trace` 做全文溯源）")
        return 0
    for e in entries:
        print(f"== 《{e.book_title}》 {e.name} ==")
        for label, val in [("性味", e.nature_flavor), ("归经", e.meridians),
                           ("功用", e.functions), ("主治", e.indications),
                           ("禁忌", e.contraindications), ("炮製", e.processing),
                           ("配伍", e.compatibility)]:
            if val:
                print(f"  {label}: {val.strip()[:200]}")
        print()
    return 0


def cmd_trace(args) -> int:
    kb = _load_kb()
    res = trace_herb(kb, args.name)
    if res.ambiguous:
        print(f"『{res.herb}』为歧义名物：{res.ambiguity_note}")
        return 0
    print(f"# 本草溯源：{res.herb}")
    if res.aliases:
        print(f"  异名：{'、'.join(res.aliases)}")
    print(f"  历代著录（{len(res.dynasty_timeline)} 部）：")
    for tb in res.dynasty_timeline:
        print(f"    [{tb['dynasty'] or '—'}] 《{tb['book']}》 {tb['author']}  提及×{tb['mentions']}")
    print(f"  证据样例（{len(res.evidence)}）：")
    for ev in res.evidence[: args.limit]:
        print(f"    {ev.citation}\n      {ev.snippet}")
    return 0


def cmd_search(args) -> int:
    kb = _load_kb()
    hits = kb.bm25.search(" ".join(args.query), top_k=args.limit)
    if not hits:
        print("无匹配。")
        return 0
    for p, score in hits:
        print(f"[{score:.2f}] {p.citation}")
        print(f"      {p.text.strip()[:120].replace(chr(10), ' ')}…")
    return 0


def cmd_pairs(args) -> int:
    kb = _load_kb()
    if args.herb:
        pairs = kb.pairs_for(args.herb, top_k=args.limit)
    else:
        pairs = kb.pairs[: args.limit]
    for p in pairs:
        print(f"  {p.herb_a}–{p.herb_b}  count={p.count} pmi={p.pmi}  例：{'、'.join(p.example_books[:3])}")
    return 0


def cmd_hypothesis(args) -> int:
    kb = _load_kb()
    card = build_hypothesis_card(kb, args.herb, partner=args.partner, disease=args.disease)
    _print_json(card.to_dict())
    return 0


def cmd_formula(args) -> int:
    kb = _load_kb()
    g = kb.genealogy.genealogy(args.name)
    if not g.get("found"):
        print(f"未找到方剂：{args.name}")
        return 0
    p = g["primary"]
    print(f"# 方剂谱系：{args.name}")
    print(f"  代表出处：《{p['book']}》{p['dynasty']} {p['author']}  类目：{p['category']}")
    print(f"  组成：{'、'.join(p['composition_herbs'])}")
    if p["indications"]:
        print(f"  主治：{p['indications']}")
    print(f"  历代出现（{len(g['occurrences'])} 处）：" +
          "、".join(f"《{o['book']}》" for o in g["occurrences"][:10]))
    if g["ancestors"]:
        print("  祖方/源流：" + " ← ".join(a["name"] for a in g["ancestors"]))
    if g["descendants"]:
        print("  衍生方：" + "、".join(d["name"] for d in g["descendants"][:12]))
    if g["derivations"]:
        print("  加減記載：" + "；".join(f"{d['relation']}{''.join(d['herbs'])}→{d['target']}"
                                         for d in g["derivations"][:6]))
    if g["similar"]:
        print("  类方（组成相似）：" + "、".join(f"{s['name']}({s['jaccard']})"
                                                for s in g["similar"][:8]))
    a = kb.analyze_formula(args.name)
    if a and a["composition"]:
        print(f"  君臣佐使 + 剂量折算（{a['dynasty']}制，1兩≈{a['liang_grams']}g，"
              f"合计≈{a['total_grams']}g）：")
        for it in a["composition"]:
            g_ = f"{it['grams']}g" if it.get("grams") is not None else (it.get("count_unit") or "—")
            print(f"    [{it['role']}] {it['herb']}　{it.get('dose_raw','') or ''}　≈{g_}　（{it['reason']}）")
        print(f"    註：{a['note']}")
    return 0


def cmd_formulas_with(args) -> int:
    kb = _load_kb()
    canonical = kb.normalizer.normalize(args.herb).canonical
    hits = kb.genealogy.formulas_with_herb(canonical, limit=args.limit)
    print(f"含『{canonical}』的方剂（{len(hits)}，按组成精简度排序）：")
    for f in hits:
        print(f"  《{f.book_title}》{f.name}：{'、'.join(f.composition_herbs[:8])}")
    return 0


def cmd_graph(args) -> int:
    kb = _load_kb()
    nbrs = kb.graph.neighbors(kb.normalizer.normalize(args.name).canonical)
    if not nbrs:
        print(f"图谱中无 {args.name} 的邻接节点。")
        return 0
    grouped = {}
    for n in nbrs:
        grouped.setdefault(n["relation"], []).append(n["label"])
    for rel, labels in grouped.items():
        print(f"  {rel}: {'、'.join(labels)}")
    return 0


def cmd_report(args) -> int:
    from .report import herb_dossier_markdown
    md = herb_dossier_markdown(_load_kb(), args.name, disease=args.disease)
    if args.out:
        Path(args.out).write_text(md, encoding="utf-8")
        print(f"报告已导出 -> {args.out}")
    else:
        print(md)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="herb_hermes", description="Herb-Hermes 本草证据操作系统 CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("build", help="从语料构建知识库")
    sp.add_argument("--corpus", default=str(DEFAULT_CORPUS_DIR))
    sp.set_defaults(func=cmd_build)

    sub.add_parser("stats", help="知识库统计").set_defaults(func=cmd_stats)

    sp = sub.add_parser("herb", help="查看单味药结构化条目")
    sp.add_argument("name")
    sp.set_defaults(func=cmd_herb)

    sp = sub.add_parser("trace", help="本草溯源（跨书跨代）")
    sp.add_argument("name")
    sp.add_argument("--limit", type=int, default=10)
    sp.set_defaults(func=cmd_trace)

    sp = sub.add_parser("search", help="引文可溯的全文检索 (BM25)")
    sp.add_argument("query", nargs="+")
    sp.add_argument("--limit", type=int, default=8)
    sp.set_defaults(func=cmd_search)

    sp = sub.add_parser("pairs", help="药对共现挖掘")
    sp.add_argument("--herb", default=None)
    sp.add_argument("--limit", type=int, default=20)
    sp.set_defaults(func=cmd_pairs)

    sp = sub.add_parser("hypothesis", help="生成科研假设卡")
    sp.add_argument("herb")
    sp.add_argument("--partner", default=None)
    sp.add_argument("--disease", default="骨质疏松")
    sp.set_defaults(func=cmd_hypothesis)

    sp = sub.add_parser("graph", help="知识图谱邻接查询")
    sp.add_argument("name")
    sp.set_defaults(func=cmd_graph)

    sp = sub.add_parser("formula", help="方剂谱系（源流/衍生/类方/加減）")
    sp.add_argument("name")
    sp.set_defaults(func=cmd_formula)

    sp = sub.add_parser("formulas-with", help="检索含某味药的方剂")
    sp.add_argument("herb")
    sp.add_argument("--limit", type=int, default=30)
    sp.set_defaults(func=cmd_formulas_with)

    sp = sub.add_parser("report", help="一键导出本草档案报告 (Markdown)")
    sp.add_argument("name")
    sp.add_argument("--disease", default="骨质疏松")
    sp.add_argument("--out", default=None, help="输出文件路径；缺省则打印到 stdout")
    sp.set_defaults(func=cmd_report)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
