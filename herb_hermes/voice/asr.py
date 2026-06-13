"""FireRedASR2S (FireRedASR2-AED) speech-to-text backend.

Mirrors the official inference path: decode audio to 16 kHz mono PCM wav via
ffmpeg, then run ``FireRedAsr2.transcribe``. All heavy imports are deferred to
:meth:`load` so this module imports cleanly without torch or the model.
"""

from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path
from typing import Dict, List, Optional


class FireRedASRBackend:
    def __init__(self, model_dir: str, use_gpu: Optional[bool] = None,
                 beam_size: int = 3, return_timestamp: bool = True) -> None:
        self.model_dir = model_dir
        self.use_gpu = use_gpu
        self.beam_size = beam_size
        self.return_timestamp = return_timestamp
        self._model = None

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def load(self) -> "FireRedASRBackend":
        if self._model is not None:
            return self
        import torch  # deferred
        from fireredasr2s.fireredasr2 import FireRedAsr2, FireRedAsr2Config

        use_gpu = torch.cuda.is_available() if self.use_gpu is None else self.use_gpu
        config = FireRedAsr2Config(
            use_gpu=use_gpu, use_half=False, beam_size=self.beam_size,
            nbest=1, decode_max_len=0, softmax_smoothing=1.25,
            aed_length_penalty=0.6, eos_penalty=1.0,
            return_timestamp=self.return_timestamp,
        )
        self._model = FireRedAsr2.from_pretrained("aed", self.model_dir, config)
        return self

    @staticmethod
    def _to_16k_wav(audio_path: str) -> str:
        out_path = f"/tmp/herb_hermes_asr_{uuid.uuid4().hex}.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-i", audio_path, "-ar", "16000", "-ac", "1",
             "-acodec", "pcm_s16le", "-f", "wav", out_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
        )
        return out_path

    def transcribe(self, audio_path: str) -> Dict:
        if self._model is None:
            self.load()
        wav = self._to_16k_wav(audio_path)
        try:
            uttid = Path(audio_path).stem or "utt"
            results = self._model.transcribe([uttid], [wav])
            r = results[0]
            timestamp: List = r.get("timestamp", []) or []
            return {
                "text": r.get("text", ""),
                "confidence": r.get("confidence"),
                "duration_s": r.get("dur_s"),
                "rtf": r.get("rtf"),
                "timestamp": [list(t) if isinstance(t, (list, tuple)) else t for t in timestamp],
            }
        finally:
            try:
                os.remove(wav)
            except OSError:
                pass
