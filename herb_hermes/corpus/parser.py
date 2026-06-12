"""Low-level parsers for the 中醫笈成 text format.

Observed layout (per book directory):

* ``index.txt`` opens with a heading ``======書名======`` then a ``<book>``
  metadata block of ``key=value`` lines, then prose sections delimited by
  ``=====章節=====``.
* Multi-file books additionally have numbered ``N.txt`` files and a
  ``menu.txt`` (``<menu> N|title </menu>``).
* Itemized (條列版) books store one herb per section inside a ``<code> ...
  </code>`` block, with fields like ``藥名：``, ``性味：``, ``主治：``.

These helpers are deliberately small and pure so they are easy to unit test.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

# A heading line is a run of '=' around a title, e.g. =====人參===== .
_HEADING_RE = re.compile(r"^\s*=+\s*(.+?)\s*=+\s*$")

# Known structured field keys found inside <code> blocks of itemized books.
# Mapped to canonical HerbEntry attribute names.
FIELD_KEY_MAP: Dict[str, str] = {
    "藥名": "name",
    "名稱": "name",
    "編號": "code",
    "序號": "code2",
    "別名": "aliases",
    "性味": "nature_flavor",
    "性": "nature",
    "味": "flavor",
    "氣味": "nature_flavor",
    "歸經": "meridians",
    "功用": "functions",
    "功能": "functions",
    "功效": "functions",
    "主治": "indications",
    "禁忌": "contraindications",
    "品類": "category2",
    "品種": "category2",
    "炮製": "processing",
    "製法": "processing",
    "配伍": "compatibility",
    "十劑": "category",
    "類別": "category",
    "其他": "notes",
    "註": "notes",
    "按": "notes",
}

# Line that begins a known field, e.g. "性味：甘、微寒" (full or half width colon).
_FIELD_RE = re.compile(
    r"^\s*(?P<key>[一-鿿]{1,3})\s*[：:]\s*(?P<val>.*)$"
)


def parse_metadata_block(text: str) -> Dict[str, str]:
    """Extract the ``<book>`` ``key=value`` metadata block.

    Returns a dict with normalized english-ish keys when recognized, plus the
    raw chinese keys. Missing block -> empty dict.
    """
    m = re.search(r"<book>(.*?)</book>", text, re.DOTALL)
    if not m:
        return {}
    out: Dict[str, str] = {}
    key_map = {
        "書名": "title",
        "作者": "author",
        "朝代": "dynasty",
        "年份": "year",
        "分類": "category",
        "品質": "quality",
    }
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip()
        if not k:
            continue
        out[key_map.get(k, k)] = v
    return out


def split_sections(text: str) -> List[Tuple[str, str]]:
    """Split book text into ``(heading, body)`` sections by ``=...=`` lines.

    The ``<book>`` metadata block is stripped first. Text appearing before the
    first heading is returned under an empty heading.
    """
    text = re.sub(r"<book>.*?</book>", "", text, flags=re.DOTALL)
    sections: List[Tuple[str, str]] = []
    cur_head = ""
    cur_lines: List[str] = []

    def flush() -> None:
        body = "\n".join(cur_lines).strip()
        if body or cur_head:
            sections.append((cur_head, body))

    for line in text.splitlines():
        m = _HEADING_RE.match(line)
        if m and set(line.strip()) >= {"="} and line.strip().count("=") >= 4:
            # New heading: flush the previous section.
            flush()
            cur_head = m.group(1).strip()
            cur_lines = []
        else:
            cur_lines.append(line)
    flush()
    return sections


def extract_code_block(body: str) -> str:
    """Return the text inside a ``<code>...</code>`` block, or '' if absent."""
    m = re.search(r"<code>(.*?)</code>", body, re.DOTALL)
    return m.group(1).strip() if m else ""


def parse_code_fields(code_text: str) -> Dict[str, str]:
    """Parse an itemized ``<code>`` block into ``{chinese_key: value}``.

    Multi-line values are joined until the next recognized field key. Only keys
    in :data:`FIELD_KEY_MAP` start a new field; everything else continues the
    current field's value.
    """
    fields: Dict[str, str] = {}
    cur_key: str | None = None
    cur_val: List[str] = []

    def flush() -> None:
        if cur_key is not None:
            val = "\n".join(cur_val).strip()
            if cur_key in fields and val:
                fields[cur_key] = fields[cur_key] + "\n" + val
            else:
                fields[cur_key] = val

    for line in code_text.splitlines():
        m = _FIELD_RE.match(line)
        if m and m.group("key") in FIELD_KEY_MAP:
            flush()
            cur_key = m.group("key")
            cur_val = [m.group("val")]
        else:
            if cur_key is None:
                # Pre-field prose (e.g. a序). Park it under a sentinel key.
                cur_key = "_preamble"
                cur_val = [line]
            else:
                cur_val.append(line)
    flush()
    fields.pop("_preamble", None)
    return fields


def is_itemized_book(title: str, sample_bodies: List[str]) -> bool:
    """Heuristic: does this book store structured per-herb ``<code>`` entries?

    True when the title flags it (條列版) or several sections carry ``<code>``
    blocks with recognized field keys.
    """
    if "條列" in title:
        return True
    hits = 0
    for body in sample_bodies:
        code = extract_code_block(body)
        if code and any(k in code for k in ("藥名：", "名稱：", "性味：", "主治：", "功用：", "功能：")):
            hits += 1
    return hits >= 2
