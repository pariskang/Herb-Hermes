"""Expose Herb-Hermes capabilities as grounded, LLM-callable tools.

Every tool runs against the real knowledge base and returns compact,
citation-bearing results — so an agent's answer is anchored in古籍证据 rather
than the model's parametric memory. The same registry backs the HTTP agent and
the MCP server.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List

from ..discovery.hypothesis import build_hypothesis_card
from ..discovery.sourcing import trace_herb


def _trim(s: str, n: int = 160) -> str:
    s = (s or "").strip().replace("\n", " ")
    return s[:n] + ("…" if len(s) > n else "")


class ToolRegistry:
    """Holds tool JSON-schemas and dispatches calls against a KnowledgeBase."""

    def __init__(self, kb) -> None:
        self.kb = kb
        self._handlers: Dict[str, Callable[..., Dict]] = {
            "search_corpus": self._search_corpus,
            "trace_herb": self._trace_herb,
            "herb_info": self._herb_info,
            "herb_pairs": self._herb_pairs,
            "formula_genealogy": self._formula_genealogy,
            "analyze_formula": self._analyze_formula,
            "formulas_with_herb": self._formulas_with_herb,
            "generate_hypothesis": self._generate_hypothesis,
        }

    # ---- specs (OpenAI / litellm tool format) --------------------------
    @property
    def specs(self) -> List[Dict]:
        S = lambda name, desc, props, req: {
            "type": "function",
            "function": {"name": name, "description": desc,
                         "parameters": {"type": "object", "properties": props, "required": req}},
        }
        herb = {"name": {"type": "string", "description": "药名，如 黃芪、杜仲"}}
        return [
            S("search_corpus", "在本草与方書古籍全文中检索（BM25），返回带《书·篇（朝代·作者）》引文的片段。用于查找原文依据。",
              {"query": {"type": "string", "description": "中文检索词，如 強筋骨 補肝腎"},
               "limit": {"type": "integer", "description": "返回条数，默认 8"}}, ["query"]),
            S("trace_herb", "本草溯源：某药的异名、历代著录时间线与引文证据。歧义名物会被标记。", herb, ["name"]),
            S("herb_info", "某药的结构化条目（性味/归经/功用/主治/禁忌/炮製/配伍）。", herb, ["name"]),
            S("herb_pairs", "某药的高频药对（配伍+共现，PMI 量化）。", herb, ["name"]),
            S("formula_genealogy", "方剂谱系：组成、历代演变、源流、衍生方、加減、类方网络。",
              {"name": {"type": "string", "description": "方名，如 桂枝湯、六味地黃丸"}}, ["name"]),
            S("analyze_formula", "方剂的君臣佐使推断与剂量古今换算（含依据与置信度）。",
              {"name": {"type": "string", "description": "方名"}}, ["name"]),
            S("formulas_with_herb", "检索含某味药的方剂。", herb, ["name"]),
            S("generate_hypothesis", "基于古籍证据生成可验证的科研假设卡（现代机制标注待验证）。",
              {"herb": {"type": "string"}, "partner": {"type": "string", "description": "可选药对伙伴"},
               "disease": {"type": "string", "description": "疾病方向，默认 骨质疏松"}}, ["herb"]),
        ]

    @property
    def tool_names(self) -> List[str]:
        return list(self._handlers)

    def dispatch(self, name: str, args: Dict[str, Any]) -> Dict:
        handler = self._handlers.get(name)
        if handler is None:
            return {"error": f"unknown tool: {name}"}
        try:
            return handler(**(args or {}))
        except TypeError as e:
            return {"error": f"bad arguments for {name}: {e}"}
        except Exception as e:  # pragma: no cover - defensive
            return {"error": f"{type(e).__name__}: {e}"}

    # ---- handlers ------------------------------------------------------
    def _search_corpus(self, query: str, limit: int = 8) -> Dict:
        hits = self.kb.bm25.search(query, top_k=min(int(limit), 20))
        return {"query": query, "results": [
            {"citation": p.citation, "snippet": _trim(p.text, 180), "score": round(s, 2)}
            for p, s in hits]}

    def _trace_herb(self, name: str) -> Dict:
        r = trace_herb(self.kb, name, max_evidence=12)
        if r.ambiguous:
            return {"herb": r.herb, "ambiguous": True, "note": r.ambiguity_note}
        return {
            "herb": r.herb, "aliases": r.aliases, "ambiguous": False,
            "timeline": [{"dynasty": t["dynasty"], "book": t["book"], "mentions": t["mentions"]}
                         for t in r.dynasty_timeline[:14]],
            "evidence": [{"citation": e.citation, "snippet": _trim(e.snippet, 140)}
                         for e in r.evidence[:8]],
        }

    def _herb_info(self, name: str) -> Dict:
        entries = self.kb.get_entries(name)
        norm = self.kb.normalizer.normalize(name)
        if not entries:
            return {"herb": norm.canonical, "ambiguous": norm.ambiguous,
                    "note": norm.note, "structured_entry": None}
        e = entries[0]
        return {"herb": norm.canonical, "aliases": norm.aliases, "source_book": e.book_title,
                "nature_flavor": e.nature_flavor, "meridians": e.meridians,
                "functions": _trim(e.functions, 200), "indications": _trim(e.indications, 200),
                "contraindications": _trim(e.contraindications, 120),
                "processing": _trim(e.processing, 120), "compatibility": _trim(e.compatibility, 160)}

    def _herb_pairs(self, name: str) -> Dict:
        pairs = self.kb.pairs_for(name, top_k=12)
        return {"herb": self.kb.normalizer.normalize(name).canonical,
                "pairs": [{"with": p.herb_b if p.herb_a == self.kb.normalizer.normalize(name).canonical else p.herb_a,
                           "count": p.count, "pmi": p.pmi} for p in pairs]}

    def _formula_genealogy(self, name: str) -> Dict:
        g = self.kb.genealogy.genealogy(name)
        if not g.get("found"):
            return {"formula": name, "found": False}
        return {
            "formula": name, "found": True,
            "composition": g["primary"]["composition_herbs"],
            "source": f"《{g['primary']['book']}》{g['primary']['dynasty']}",
            "indications": _trim(g["primary"]["indications"], 120),
            "occurrence_books": [o["book"] for o in g["occurrences"][:10]],
            "descendants": [d["name"] for d in g["descendants"][:12]],
            "derivations": [{"relation": d["relation"], "herbs": d["herbs"], "target": d["target"]}
                            for d in g["derivations"][:8]],
            "similar": [{"name": s["name"], "jaccard": s["jaccard"]} for s in g["similar"][:8]],
        }

    def _analyze_formula(self, name: str) -> Dict:
        a = self.kb.analyze_formula(name)
        if not a:
            return {"formula": name, "found": False}
        return {"formula": name, "found": True, "dynasty": a["dynasty"],
                "liang_grams": a["liang_grams"], "total_grams": a["total_grams"],
                "note": a["note"],
                "composition": [{"role": it["role"], "herb": it["herb"],
                                 "dose": it.get("dose_raw"), "grams": it.get("grams"),
                                 "reason": it["reason"]} for it in a["composition"]]}

    def _formulas_with_herb(self, name: str) -> Dict:
        canon = self.kb.normalizer.normalize(name).canonical
        hits = self.kb.genealogy.formulas_with_herb(canon, limit=20)
        return {"herb": canon, "count": len(hits),
                "formulas": [{"name": f.name, "book": f.book_title,
                              "herbs": f.composition_herbs[:8]} for f in hits[:15]]}

    def _generate_hypothesis(self, herb: str, partner: str = "", disease: str = "骨质疏松") -> Dict:
        card = build_hypothesis_card(self.kb, herb, partner=partner or None, disease=disease)
        return card.to_dict()
