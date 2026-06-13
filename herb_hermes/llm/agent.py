"""HerbAgent: an autonomous, tool-using agent grounded in古籍证据.

The agent reasons in a function-calling loop: the LLM decides which Herb-Hermes
tools to call, the registry executes them against the real knowledge base, and
the model synthesizes a final answer that must cite the retrieved evidence. A
full transcript of tool calls is returned for transparency in the UI.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .client import LLMResponse
from .tools import ToolRegistry

SYSTEM_PROMPT = """你是 Herb-Hermes 的中医药研究助手，专长本草溯源、方剂谱系、君臣佐使、剂量考证与科研假设。

铁律：
1. 你对古籍内容的所有断言都必须来自工具返回的证据；优先调用工具，不要凭记忆杜撰古籍原文、出处或数据。
2. 回答须给出《书名（朝代·作者）》等引文支撑；无证据时如实说明「语料中未见」。
3. 现代药理/机制属于假设，必须标注「待验证假设」，不得当作既成事实。
4. 不提供临床处方、剂量医嘱或诊疗建议；剂量换算与君臣佐使均为研究性推断，需说明其启发式性质。
5. 用简洁的中文作答，结构清晰；必要时分点。

可用工具：本草溯源、结构化条目、药对、方剂谱系、君臣佐使+剂量、含药方剂检索、全文检索、科研假设生成。
先用工具收集证据，再综合作答。"""


@dataclass
class AgentStep:
    tool: str
    arguments: Dict[str, Any]
    result: Dict[str, Any]

    def to_dict(self) -> Dict:
        return {"tool": self.tool, "arguments": self.arguments, "result": self.result}


@dataclass
class AgentResult:
    question: str
    answer: str
    steps: List[AgentStep] = field(default_factory=list)
    citations: List[str] = field(default_factory=list)
    model: str = ""

    def to_dict(self) -> Dict:
        return {"question": self.question, "answer": self.answer,
                "steps": [s.to_dict() for s in self.steps],
                "citations": self.citations, "model": self.model}


def _collect_citations(steps: List[AgentStep]) -> List[str]:
    out, seen = [], set()
    for s in steps:
        for blob in (s.result.get("results"), s.result.get("evidence")):
            for item in (blob or []):
                c = item.get("citation")
                if c and c not in seen:
                    seen.add(c)
                    out.append(c)
    return out


class HerbAgent:
    def __init__(self, kb, llm, max_steps: int = 6) -> None:
        self.kb = kb
        self.llm = llm
        self.registry = ToolRegistry(kb)
        self.max_steps = max_steps

    def ask(self, question: str, history: Optional[List[Dict]] = None) -> AgentResult:
        messages: List[Dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages += history or []
        messages.append({"role": "user", "content": question})

        steps: List[AgentStep] = []
        answer = ""
        for _ in range(self.max_steps):
            resp: LLMResponse = self.llm.complete(messages, tools=self.registry.specs)
            if resp.tool_calls:
                messages.append(resp.assistant_message())
                for tc in resp.tool_calls:
                    result = self.registry.dispatch(tc.name, tc.arguments)
                    steps.append(AgentStep(tc.name, tc.arguments, result))
                    messages.append({
                        "role": "tool", "tool_call_id": tc.id, "name": tc.name,
                        "content": json.dumps(result, ensure_ascii=False),
                    })
                continue
            answer = resp.content
            break
        else:
            # ran out of steps: ask once more for a final synthesis, no tools
            messages.append({"role": "user", "content": "请基于以上证据给出最终答复。"})
            answer = self.llm.complete(messages).content

        return AgentResult(
            question=question, answer=answer, steps=steps,
            citations=_collect_citations(steps),
            model=getattr(self.llm, "model", ""),
        )
