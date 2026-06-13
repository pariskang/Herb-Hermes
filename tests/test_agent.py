"""Tests for the LLM tool registry and the grounded agent (offline, mock LLM)."""

import pytest

from herb_hermes.store import KnowledgeBase
from herb_hermes.llm.tools import ToolRegistry
from herb_hermes.llm.agent import HerbAgent
from herb_hermes.llm.client import MockLLMClient, LLMResponse, ToolCall, llm_status


@pytest.fixture
def kb(mini_corpus, mini_formula_corpus):
    return KnowledgeBase.build(mini_corpus, formula_dir=mini_formula_corpus)


# ---- tool registry ----
def test_registry_specs_and_dispatch(kb):
    reg = ToolRegistry(kb)
    names = {s["function"]["name"] for s in reg.specs}
    assert {"trace_herb", "formula_genealogy", "analyze_formula", "search_corpus"} <= names
    r = reg.dispatch("formula_genealogy", {"name": "四君子湯"})
    assert r["found"] and "人參" in r["composition"]
    r2 = reg.dispatch("trace_herb", {"name": "黃芪"})
    assert r2["herb"] == "黃芪" and "evidence" in r2
    r3 = reg.dispatch("analyze_formula", {"name": "桂枝湯"})
    assert r3["found"] and r3["composition"][0]["role"] == "君"


def test_registry_unknown_and_bad_args(kb):
    reg = ToolRegistry(kb)
    assert "error" in reg.dispatch("nope", {})
    assert "error" in reg.dispatch("trace_herb", {"wrong": 1})


# ---- agent loop with a scripted mock LLM ----
def test_agent_grounded_loop(kb):
    def policy(messages, tools):
        # first turn: ask the agent to call a tool; after tool result: answer
        if any(m.get("role") == "tool" for m in messages):
            return LLMResponse(content="四君子湯出自《測試方書譜》，由人參、白朮、茯苓、甘草组成。")
        return LLMResponse(tool_calls=[ToolCall("c1", "formula_genealogy", {"name": "四君子湯"})])

    agent = HerbAgent(kb, MockLLMClient(policy), max_steps=4)
    res = agent.ask("四君子湯的组成与出处？")
    assert res.steps and res.steps[0].tool == "formula_genealogy"
    assert res.steps[0].result["found"]
    assert "四君子湯" in res.answer
    assert res.model == "mock"


def test_agent_multi_tool(kb):
    calls = {"n": 0}

    def policy(messages, tools):
        tool_msgs = [m for m in messages if m.get("role") == "tool"]
        if len(tool_msgs) == 0:
            return LLMResponse(tool_calls=[ToolCall("a", "trace_herb", {"name": "黃芪"})])
        if len(tool_msgs) == 1:
            return LLMResponse(tool_calls=[ToolCall("b", "herb_pairs", {"name": "黃芪"})])
        return LLMResponse(content="黃芪（《測試本草》）常与當歸配伍。")

    agent = HerbAgent(kb, MockLLMClient(policy), max_steps=5)
    res = agent.ask("黃芪常配伍什么？")
    assert [s.tool for s in res.steps] == ["trace_herb", "herb_pairs"]
    assert res.answer


# ---- status / degradation ----
def test_llm_status_shape():
    s = llm_status()
    assert set(["litellm_installed", "model", "configured"]) <= set(s)


def test_mock_client_available():
    c = MockLLMClient(lambda m, t: LLMResponse(content="ok"))
    assert c.available
