"""Tokenizer tuned for classical Chinese.

Classical Chinese is largely monosyllabic, so CJK characters are emitted as
unigrams plus adjacent bigrams (which capture most bisyllabic herb/term
names). Runs of latin/digits are kept whole. No external segmenter required.
"""

from __future__ import annotations

import re
from typing import List

_CJK = re.compile(r"[一-鿿]")
_ASCII_RUN = re.compile(r"[A-Za-z0-9]+")
_TOKEN_SPLIT = re.compile(r"[一-鿿]|[A-Za-z0-9]+")


def tokenize(text: str, bigrams: bool = True) -> List[str]:
    if not text:
        return []
    units = _TOKEN_SPLIT.findall(text)
    tokens: List[str] = []
    cjk_buf: List[str] = []

    def flush_cjk() -> None:
        if not cjk_buf:
            return
        tokens.extend(cjk_buf)  # unigrams
        if bigrams:
            for i in range(len(cjk_buf) - 1):
                tokens.append(cjk_buf[i] + cjk_buf[i + 1])
        cjk_buf.clear()

    for u in units:
        if _CJK.match(u):
            cjk_buf.append(u)
        else:
            flush_cjk()
            tokens.append(u.lower())
    flush_cjk()
    return tokens
