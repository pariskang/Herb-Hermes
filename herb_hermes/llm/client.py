"""Provider-agnostic LLM client built on litellm (lazy), plus an offline mock.

litellm gives one interface to OpenAI / Anthropic / Azure / local (Ollama,
vLLM) and 100+ providers. The model is chosen via HERB_HERMES_LLM_MODEL (e.g.
``gpt-4o-mini``, ``claude-sonnet-4-6``, ``ollama/qwen2.5``, ``minimax/MiniMax-M3``).

MiniMax integration:
  Set HERB_HERMES_LLM_MODEL=minimax/MiniMax-M3 and MINIMAX_API_KEY=<key>.
  Or pass model/api_key/api_base directly to LLMClient().
  reasoning_split=True is sent automatically for MiniMax models so the
  thinking content is returned separately in reasoning_details.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Generator, List, Optional


# ---------------------------------------------------------------------------
# MiniMax constants
# ---------------------------------------------------------------------------
MINIMAX_MODELS = [
    "MiniMax-M3",
    "MiniMax-M2.7",
    "MiniMax-M2.7-highspeed",
    "MiniMax-M2.5",
    "MiniMax-M2.5-highspeed",
    "MiniMax-M2.1",
    "MiniMax-M2.1-highspeed",
    "MiniMax-M2",
]
MINIMAX_API_BASE = "https://api.minimaxi.com/v1"
MINIMAX_API_KEY_ENV = "MINIMAX_API_KEY"

DEFAULT_MODEL_ENV = "HERB_HERMES_LLM_MODEL"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class ToolCall:
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class LLMResponse:
    content: str = ""
    thinking: str = ""        # MiniMax reasoning_split or chain-of-thought
    tool_calls: List[ToolCall] = field(default_factory=list)
    raw: Any = None

    def assistant_message(self) -> Dict[str, Any]:
        """Reconstruct the OpenAI-style assistant message for the next turn."""
        msg: Dict[str, Any] = {"role": "assistant", "content": self.content or ""}
        if self.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id, "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                    },
                }
                for tc in self.tool_calls
            ]
        return msg


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _is_minimax(model: str) -> bool:
    return model.startswith("minimax/") or any(
        model == m or model == f"openai/{m}" for m in MINIMAX_MODELS
    )


def _canonical_minimax_model(model: str) -> str:
    """Strip any prefix to get the bare MiniMax model name."""
    for prefix in ("minimax/", "openai/"):
        if model.startswith(prefix):
            return model[len(prefix):]
    return model


def _detect_model() -> Optional[str]:
    m = os.environ.get(DEFAULT_MODEL_ENV)
    if m:
        return m
    if os.environ.get(MINIMAX_API_KEY_ENV):
        return "minimax/MiniMax-M3"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "claude-sonnet-4-6"
    if os.environ.get("OPENAI_API_KEY"):
        return "gpt-4o-mini"
    return None


def _available_models() -> Dict[str, Any]:
    """Return grouped model catalogue for the /llm/models endpoint."""
    return {
        "providers": [
            {
                "name": "MiniMax",
                "env_key": MINIMAX_API_KEY_ENV,
                "api_base": MINIMAX_API_BASE,
                "prefix": "minimax/",
                "models": [
                    {
                        "id": f"minimax/{m}",
                        "label": m,
                        "context": "1M" if m == "MiniMax-M3" else "204.8K",
                        "reasoning": True,
                    }
                    for m in MINIMAX_MODELS
                ],
            },
            {
                "name": "OpenAI",
                "env_key": "OPENAI_API_KEY",
                "prefix": "",
                "api_base": "",
                "models": [
                    {"id": "gpt-4o", "label": "GPT-4o", "context": "128K", "reasoning": False},
                    {"id": "gpt-4o-mini", "label": "GPT-4o Mini", "context": "128K", "reasoning": False},
                    {"id": "o3", "label": "o3", "context": "200K", "reasoning": True},
                    {"id": "o4-mini", "label": "o4-mini", "context": "200K", "reasoning": True},
                ],
            },
            {
                "name": "Anthropic",
                "env_key": "ANTHROPIC_API_KEY",
                "prefix": "",
                "api_base": "",
                "models": [
                    {"id": "claude-fable-5", "label": "Claude Fable 5", "context": "200K", "reasoning": True},
                    {"id": "claude-opus-4-8", "label": "Claude Opus 4.8", "context": "200K", "reasoning": True},
                    {"id": "claude-sonnet-4-6", "label": "Claude Sonnet 4.6", "context": "200K", "reasoning": False},
                    {"id": "claude-haiku-4-5-20251001", "label": "Claude Haiku 4.5", "context": "200K", "reasoning": False},
                ],
            },
            {
                "name": "Ollama (本地)",
                "env_key": None,
                "prefix": "ollama/",
                "api_base": "http://localhost:11434",
                "models": [
                    {"id": "ollama/qwen2.5", "label": "Qwen 2.5", "context": "128K", "reasoning": False},
                    {"id": "ollama/llama3.2", "label": "LLaMA 3.2", "context": "128K", "reasoning": False},
                    {"id": "ollama/deepseek-r1", "label": "DeepSeek R1", "context": "128K", "reasoning": True},
                    {"id": "ollama/mistral", "label": "Mistral", "context": "32K", "reasoning": False},
                ],
            },
        ]
    }


def llm_status() -> Dict[str, Any]:
    """Report whether the LLM layer is usable (no network calls)."""
    try:
        import litellm  # noqa: F401
        have_litellm = True
    except Exception:
        have_litellm = False
    model = _detect_model()
    providers: List[str] = []
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "AZURE_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY"):
        if os.environ.get(k):
            providers.append(k.split("_")[0].lower())
    if os.environ.get(MINIMAX_API_KEY_ENV):
        providers.append("minimax")
    return {
        "litellm_installed": have_litellm,
        "model": model,
        "configured": bool(have_litellm and model),
        "providers_detected": providers,
        "minimax_available": bool(os.environ.get(MINIMAX_API_KEY_ENV)),
    }


# ---------------------------------------------------------------------------
# LLMClient
# ---------------------------------------------------------------------------
class LLMClient:
    """Thin litellm wrapper with tool-calling and MiniMax reasoning_split support.

    Parameters
    ----------
    model:    model string; if None, inferred from env vars.
    api_key:  per-instance key override (e.g. from UI settings panel).
    api_base: per-instance base URL override (e.g. ``https://api.minimaxi.com/v1``).
    """

    def __init__(
        self,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
    ) -> None:
        self.model = model or _detect_model()
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._api_key = api_key
        self._api_base = api_base

    @property
    def available(self) -> bool:
        try:
            import litellm  # noqa: F401
        except Exception:
            return False
        return bool(self.model)

    def _build_kwargs(
        self, messages: List[Dict], tools: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        model = self.model or ""
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        # MiniMax: route through litellm OpenAI-compatible path
        if _is_minimax(model):
            bare = _canonical_minimax_model(model)
            kwargs["model"] = f"openai/{bare}"
            kwargs["api_base"] = (
                self._api_base or os.environ.get("MINIMAX_API_BASE") or MINIMAX_API_BASE
            )
            kwargs["api_key"] = (
                self._api_key
                or os.environ.get(MINIMAX_API_KEY_ENV)
                or os.environ.get("OPENAI_API_KEY", "")
            )
            kwargs["extra_body"] = {"reasoning_split": True}
        else:
            # Apply per-instance overrides for any provider (e.g. custom Ollama endpoint)
            if self._api_base:
                kwargs["api_base"] = self._api_base
            if self._api_key:
                kwargs["api_key"] = self._api_key

        return kwargs

    @staticmethod
    def _extract_thinking(msg: Any) -> str:
        """Pull thinking/reasoning text out of a litellm message object."""
        thinking = ""
        # MiniMax reasoning_split=True → reasoning_details list
        rd = getattr(msg, "reasoning_details", None) or []
        for item in rd:
            if isinstance(item, dict) and item.get("type") == "thinking":
                thinking += item.get("thinking", "")
        # Fallback: provider_specific_fields
        if not thinking:
            pf = getattr(msg, "provider_specific_fields", None) or {}
            thinking = pf.get("reasoning_content", "") or ""
        return thinking

    def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict]] = None,
    ) -> LLMResponse:
        if not self.model:
            raise RuntimeError(
                "未配置 LLM 模型。请设置 HERB_HERMES_LLM_MODEL 及对应 API Key。"
            )
        import litellm

        resp = litellm.completion(**self._build_kwargs(messages, tools))
        msg = resp.choices[0].message
        calls: List[ToolCall] = []
        for tc in getattr(msg, "tool_calls", None) or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except Exception:
                args = {}
            calls.append(
                ToolCall(
                    id=getattr(tc, "id", "") or f"call_{len(calls)}",
                    name=tc.function.name,
                    arguments=args,
                )
            )
        return LLMResponse(
            content=getattr(msg, "content", "") or "",
            thinking=self._extract_thinking(msg),
            tool_calls=calls,
            raw=resp,
        )

    def stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict]] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """Streaming completion — yields dicts: {type, content}.

        Event types: ``thinking`` (MiniMax reasoning), ``token`` (text delta),
        ``done``, ``error``.
        """
        if not self.model:
            raise RuntimeError("未配置 LLM 模型")
        import litellm

        kwargs = self._build_kwargs(messages, tools)
        kwargs["stream"] = True
        try:
            for chunk in litellm.completion(**kwargs):
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                # Thinking (MiniMax reasoning_split)
                for item in getattr(delta, "reasoning_details", None) or []:
                    if isinstance(item, dict) and item.get("type") == "thinking":
                        yield {"type": "thinking", "content": item.get("thinking", "")}
                # Regular token
                c = getattr(delta, "content", None)
                if c:
                    yield {"type": "token", "content": c}
                if chunk.choices[0].finish_reason == "stop":
                    yield {"type": "done", "content": ""}
        except Exception as e:
            yield {"type": "error", "content": str(e)}


# ---------------------------------------------------------------------------
# MockLLMClient
# ---------------------------------------------------------------------------
class MockLLMClient:
    """Offline client driven by a scripted policy — for tests and demos.

    ``policy(messages, tools) -> LLMResponse`` lets tests simulate a full
    tool-calling loop with zero network access.
    """

    def __init__(
        self,
        policy: Callable[[List[Dict], Optional[List[Dict]]], LLMResponse],
        model: str = "mock",
    ) -> None:
        self.policy = policy
        self.model = model

    @property
    def available(self) -> bool:
        return True

    def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict]] = None,
    ) -> LLMResponse:
        return self.policy(messages, tools)

    def stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict]] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        resp = self.policy(messages, tools)
        if resp.thinking:
            yield {"type": "thinking", "content": resp.thinking}
        yield {"type": "token", "content": resp.content}
        yield {"type": "done", "content": ""}
