"""CosyVoice3 (Fun-CosyVoice3-0.5B) text-to-speech backend.

Mirrors the official inference path: load via ``cosyvoice.cli.cosyvoice.AutoModel``
and synthesize with zero-shot or natural-language-instruct inference, returning
a WAV byte stream. Heavy imports are deferred to :meth:`load`.
"""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path
from typing import Optional


class CosyVoiceBackend:
    def __init__(self, model_dir: str, repo_dir: Optional[str] = None,
                 fp16: Optional[bool] = None) -> None:
        self.model_dir = model_dir
        self.repo_dir = repo_dir or os.environ.get("HERB_HERMES_COSYVOICE_REPO", "")
        self.fp16 = fp16
        self._model = None

    @property
    def loaded(self) -> bool:
        return self._model is not None

    @property
    def sample_rate(self) -> int:
        return getattr(self._model, "sample_rate", 24000)

    def load(self) -> "CosyVoiceBackend":
        if self._model is not None:
            return self
        import torch  # deferred
        if self.repo_dir:
            sys.path.insert(0, self.repo_dir)
            mt = str(Path(self.repo_dir) / "third_party" / "Matcha-TTS")
            if os.path.isdir(mt):
                sys.path.insert(0, mt)
        from cosyvoice.cli.cosyvoice import AutoModel
        fp16 = torch.cuda.is_available() if self.fp16 is None else self.fp16
        self._model = AutoModel(model_dir=self.model_dir, fp16=fp16)
        return self

    def _encode_wav(self, speech_tensor) -> bytes:
        import torchaudio
        buf = io.BytesIO()
        torchaudio.save(buf, speech_tensor.cpu(), self.sample_rate, format="wav")
        return buf.getvalue()

    def synthesize(self, text: str, prompt_wav: str, prompt_text: str = "",
                   instruct: str = "") -> bytes:
        """Synthesize ``text`` cloning the voice in ``prompt_wav``.

        If ``instruct`` is given, uses natural-language-instruct inference;
        otherwise zero-shot cloning with ``prompt_text``.
        """
        if self._model is None:
            self.load()
        if instruct:
            instr = "You are a helpful assistant. " + instruct + "<|endofprompt|>"
            gen = self._model.inference_instruct2(text, instr, prompt_wav, stream=False)
        else:
            prompt = "You are a helpful assistant.<|endofprompt|>" + (prompt_text or "")
            gen = self._model.inference_zero_shot(text, prompt, prompt_wav, stream=False)
        for out in gen:
            return self._encode_wav(out["tts_speech"])
        raise RuntimeError("CosyVoice produced no audio")
