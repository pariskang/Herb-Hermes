"""Lazy singletons and status reporting for the voice backends."""

from __future__ import annotations

import os
from typing import Dict, Optional


class VoiceUnavailable(RuntimeError):
    """Raised when a voice backend is not configured or fails to load."""


_ASR = None
_TTS = None
_ASR_ERR: Optional[str] = None
_TTS_ERR: Optional[str] = None


def get_asr():
    """Return a loaded ASR backend or raise :class:`VoiceUnavailable`."""
    global _ASR, _ASR_ERR
    if _ASR is not None:
        return _ASR
    model_dir = os.environ.get("HERB_HERMES_ASR_MODEL_DIR")
    if not model_dir:
        raise VoiceUnavailable(
            "未配置 ASR 模型。请设置 HERB_HERMES_ASR_MODEL_DIR 指向 FireRedASR2-AED 目录。")
    try:
        from .asr import FireRedASRBackend
        _ASR = FireRedASRBackend(model_dir).load()
        return _ASR
    except Exception as exc:  # pragma: no cover - requires GPU model
        _ASR_ERR = f"{type(exc).__name__}: {exc}"
        raise VoiceUnavailable(f"ASR 后端加载失败：{_ASR_ERR}") from exc


def get_tts():
    """Return a loaded TTS backend or raise :class:`VoiceUnavailable`."""
    global _TTS, _TTS_ERR
    if _TTS is not None:
        return _TTS
    model_dir = os.environ.get("HERB_HERMES_TTS_MODEL_DIR")
    if not model_dir:
        raise VoiceUnavailable(
            "未配置 TTS 模型。请设置 HERB_HERMES_TTS_MODEL_DIR 指向 Fun-CosyVoice3-0.5B 目录。")
    try:
        from .tts import CosyVoiceBackend
        _TTS = CosyVoiceBackend(model_dir).load()
        return _TTS
    except Exception as exc:  # pragma: no cover - requires GPU model
        _TTS_ERR = f"{type(exc).__name__}: {exc}"
        raise VoiceUnavailable(f"TTS 后端加载失败：{_TTS_ERR}") from exc


def voice_status() -> Dict:
    """Report which server-side backends are configured/loaded (no loading)."""
    asr_dir = os.environ.get("HERB_HERMES_ASR_MODEL_DIR")
    tts_dir = os.environ.get("HERB_HERMES_TTS_MODEL_DIR")
    default_prompt = os.environ.get("HERB_HERMES_TTS_PROMPT_WAV")
    return {
        "asr": {
            "backend": "FireRedASR2-AED",
            "configured": bool(asr_dir),
            "loaded": _ASR is not None,
            "error": _ASR_ERR,
        },
        "tts": {
            "backend": "CosyVoice3-0.5B",
            "configured": bool(tts_dir),
            "loaded": _TTS is not None,
            "has_default_prompt": bool(default_prompt),
            "error": _TTS_ERR,
        },
        "browser_fallback": True,
    }
