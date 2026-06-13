"""Provider-agnostic LLM client built on litellm (lazy), plus an offline mock.

litellm gives one interface to OpenAI / Anthropic (Claude) / Azure / local
(Ollama, vLLM) and 100+ providers. The model is chosen via
``HERB_HERMES_LLM_MODEL`` (e.g. ``gpt-4o-mini``, ``claude-sonnet-4-6``,
``ollama/qwen2.5``). Nothing here imports litellm at module load.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class LLMResponse:
    content: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    raw: Any = None

    def assistant_message(self) -> Dict[str, Any]:
        """Reconstruct the OpenAI-style assistant message for the next turn."""
        msg: Dict[str, Any] = {"role": "assistant", "content": self.content or ""}
        if self.tool_calls:
            msg["tool_calls"] = [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.name, "arguments": json.dumps(tc.arguments, ensure_ascii=False)}}
                for tc in self.tool_calls
            ]
        return msg


DEFAULT_MODEL_ENV = "HERB_HERMES_LLM_MODEL"


def _detect_model() -> Optional[str]:
    m = os.environ.get(DEFAULT_MODEL_ENV)
    if m:
        return m
    # convenience defaults if a provider key is present
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "claude-sonnet-4-6"
    if os.environ.get("OPENAI_API_KEY"):
        return "gpt-4o-mini"
    return None


def llm_status() -> Dict[str, Any]:
    """Report whether the LLM layer is usable (no network calls)."""
    try:
        import litellm  # noqa: F401
        have_litellm = True
    except Exception:
        have_litellm = False
    model = _detect_model()
    return {
        "litellm_installed": have_litellm,
        "model": model,
        "configured": bool(have_litellm and model),
        "providers_detected": [k.split("_")[0].lower() for k in
                               ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "AZURE_API_KEY",
                                "GEMINI_API_KEY", "GROQ_API_KEY")
                               if os.environ.get(k)],
    }


class LLMClient:
    """Thin wrapper over ``litellm.completion`` with tool-calling support."""

    def __init__(self, model: Optional[str] = None, temperature: float = 0.2,
                 max_tokens: int = 1024) -> None:
        self.model = model or _detect_model()
        self.temperature = temperature
        self.max_tokens = max_tokens

    @property
    def available(self) -> bool:
        try:
            import litellm  # noqa: F401
        except Exception:
            return False
        return bool(self.model)

    def complete(self, messages: List[Dict[str, Any]],
                 tools: Optional[List[Dict]] = None) -> LLMResponse:
        if not self.model:
            raise RuntimeError(
                "未配置 LLM 模型。请设置 HERB_HERMES_LLM_MODEL 及对应 API Key。")
        import litellm
        kwargs: Dict[str, Any] = {
            "model": self.model, "messages": messages,
            "temperature": self.temperature, "max_tokens": self.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        resp = litellm.completion(**kwargs)
        msg = resp.choices[0].message
        calls: List[ToolCall] = []
        for tc in (getattr(msg, "tool_calls", None) or []):
            try:
                args = json.loads(tc.function.arguments or "{}")
            except Exception:
                args = {}
            calls.append(ToolCall(id=getattr(tc, "id", "") or f"call_{len(calls)}",
                                  name=tc.function.name, arguments=args))
        return LLMResponse(content=getattr(msg, "content", "") or "", tool_calls=calls, raw=resp)


class MockLLMClient:
    """Offline client driven by a scripted policy — for tests and demos.

    ``policy`` is called as ``policy(messages, tools) -> LLMResponse`` so tests
    can simulate an agent that calls tools then answers, with zero network.
    """

    def __init__(self, policy: Callable[[List[Dict], Optional[List[Dict]]], LLMResponse],
                 model: str = "mock") -> None:
        self.policy = policy
        self.model = model

    @property
    def available(self) -> bool:
        return True

    def complete(self, messages: List[Dict[str, Any]],
                 tools: Optional[List[Dict]] = None) -> LLMResponse:
        return self.policy(messages, tools)
