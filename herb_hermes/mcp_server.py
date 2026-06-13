"""MCP server exposing Herb-Hermes tools to agent clients (Claude Code, Codex…).

Run:
    pip install "mcp[cli]"
    python -m herb_hermes.mcp_server

Register with Claude Code:
    claude mcp add herb-hermes -- python -m herb_hermes.mcp_server

Any MCP-compatible client can then call the grounded tools (本草溯源 / 方剂谱系 /
君臣佐使 / 剂量换算 / 药对 / 全文检索 / 科研假设), each returning古籍引文。
"""

from __future__ import annotations

import sys


def _build_server():
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception as exc:  # pragma: no cover - requires mcp
        raise SystemExit(
            "需要 MCP SDK。请安装： pip install \"mcp[cli]\"\n"
            f"（导入失败：{exc}）"
        ) from exc

    from .config import KB_PATH
    from .store import KnowledgeBase
    from .llm.tools import ToolRegistry

    kb = KnowledgeBase.load(KB_PATH) if KB_PATH.exists() else KnowledgeBase.build()
    reg = ToolRegistry(kb)
    mcp = FastMCP("herb-hermes")

    @mcp.tool(description="在本草与方書古籍全文检索（BM25），返回带《书·篇（朝代·作者）》引文的片段。")
    def search_corpus(query: str, limit: int = 8) -> dict:
        return reg.dispatch("search_corpus", {"query": query, "limit": limit})

    @mcp.tool(description="本草溯源：某药的异名、历代著录时间线与引文证据；歧义名物会被标记。")
    def trace_herb(name: str) -> dict:
        return reg.dispatch("trace_herb", {"name": name})

    @mcp.tool(description="某药的结构化条目（性味/归经/功用/主治/禁忌/炮製/配伍）。")
    def herb_info(name: str) -> dict:
        return reg.dispatch("herb_info", {"name": name})

    @mcp.tool(description="某药的高频药对（配伍+共现，PMI 量化）。")
    def herb_pairs(name: str) -> dict:
        return reg.dispatch("herb_pairs", {"name": name})

    @mcp.tool(description="方剂谱系：组成、历代演变、源流、衍生方、加減、类方网络。")
    def formula_genealogy(name: str) -> dict:
        return reg.dispatch("formula_genealogy", {"name": name})

    @mcp.tool(description="方剂的君臣佐使推断与剂量古今换算（含依据与置信度）。")
    def analyze_formula(name: str) -> dict:
        return reg.dispatch("analyze_formula", {"name": name})

    @mcp.tool(description="检索含某味药的方剂。")
    def formulas_with_herb(name: str) -> dict:
        return reg.dispatch("formulas_with_herb", {"name": name})

    @mcp.tool(description="基于古籍证据生成可验证的科研假设卡（现代机制标注待验证）。")
    def generate_hypothesis(herb: str, partner: str = "", disease: str = "骨质疏松") -> dict:
        return reg.dispatch("generate_hypothesis", {"herb": herb, "partner": partner, "disease": disease})

    return mcp


def main() -> int:
    server = _build_server()
    print("[herb-hermes] MCP server ready (stdio).", file=sys.stderr)
    server.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
