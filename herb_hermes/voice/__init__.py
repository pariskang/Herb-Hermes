"""语音交互 (v0.3): pluggable ASR (FireRedASR2S) and TTS (CosyVoice3) backends.

The heavy neural backends load lazily and only when their model directories are
configured (env ``HERB_HERMES_ASR_MODEL_DIR`` / ``HERB_HERMES_TTS_MODEL_DIR``),
so importing this package never pulls in torch. On a GPU host the backends run
exactly as in the reference Colab notebooks; elsewhere the API reports them as
unavailable and the web UI falls back to the browser Web Speech API.
"""

from .service import (
    VoiceUnavailable,
    get_asr,
    get_tts,
    voice_status,
)

__all__ = ["VoiceUnavailable", "get_asr", "get_tts", "voice_status"]
