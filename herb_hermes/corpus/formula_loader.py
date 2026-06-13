"""Extract structured :class:`Formula` records from the 方書 corpus.

Formula books encode genealogy in heading depth — in 祖劑 and 湯頭歌訣 a
derivative formula sits at a shallower heading level *under* its ancestor — and
in inline cues such as ``加半夏陳皮名六君子湯`` / ``除卻半夏名異功散``. This
module turns both signals into ``parent_id`` links and :class:`Derivation`
records, and resolves each formula's herb composition against the herb
vocabulary built from the 本草 corpus.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Tuple

from ..models import BookMeta, Derivation, Formula
from .loader import _ordered_text_files, _read
from .parser import parse_metadata_block, split_sections_leveled

# Headings that are clearly not formulas.
_NON_FORMULA_HEADINGS = {
    "序", "敘", "凡例", "目錄", "目录", "小敘", "自序", "跋", "後序", "前言",
    "卷之一", "卷之二", "卷之三", "卷之四", "卷之五", "卷之六", "卷之七",
}

_DOSE_UNIT = "兩两錢钱分銖铢字枚片條条根握束盞盏匕升合斗丸粒個个克g"
_DOSE_RE = re.compile(rf"[一二三四五六七八九十百千兩半數各\d][{_DOSE_UNIT}]")

# preparation / decoction markers — text from here on is 煎服法, not composition.
_PREP_RE = re.compile(r"(上[一二三四五六七八九十右為右件]|上件|右為|每服|水[一二兩盞]|共為|為末|為粗末|為散|為丸|搗|杵|煎至|水煎)")

# indications usually open with 治 / 主治 / 療.
_INDIC_RE = re.compile(r"(?:主治|治|療|主)[：:]?(.{2,80}?)[。\n]")

# inline 加減 derivation cues.
_ADD_RE = re.compile(r"(?:加|益以|加入)([^\s，。；、]{1,12}?)(?:名|為|曰|名為)([一-鿿]{2,8}[湯散丸飲膏丹])")
_REMOVE_RE = re.compile(r"(?:去|除|除卻|除却|減|减)([^\s，。；、]{1,12}?)(?:名|為|曰|名為)([一-鿿]{2,8}[湯散丸飲膏丹])")


def _bucket(surface_map: Dict[str, str]) -> Dict[str, List[str]]:
    from collections import defaultdict
    b: Dict[str, List[str]] = defaultdict(list)
    for s in surface_map:
        if len(s) >= 2:
            b[s[0]].append(s)
    return b


def _herbs_in(text: str, buckets, surface_map) -> List[str]:
    present = set(text)
    found = []
    seen = set()
    for ch in present:
        for s in buckets.get(ch, ()):
            if s in text:
                canon = surface_map[s]
                if canon not in seen:
                    seen.add(canon)
                    found.append(canon)
    return found


def _looks_like_formula(heading: str, body: str, n_herbs: int) -> bool:
    if not heading or len(heading) > 16 or heading in _NON_FORMULA_HEADINGS:
        return False
    if heading.startswith(("卷", "第", "附")) and not body:
        return False
    # a formula body either lists >=2 known herbs or carries a dose pattern.
    return n_herbs >= 2 or bool(_DOSE_RE.search(body))


def _extract_composition_raw(body: str) -> str:
    """The herb-list span: after the indication sentence, before 煎服法."""
    work = body
    # drop a leading indication sentence
    m = re.match(r"^[（(].*?[)）]\s*", work)
    if m:
        work = work[m.end():]
    if work.startswith(("治", "主治", "療", "主")):
        dot = work.find("。")
        if 0 < dot < 120:
            work = work[dot + 1:]
    prep = _PREP_RE.search(work)
    if prep:
        work = work[: prep.start()]
    return " ".join(work.split())[:200].strip()


def _extract_indications(body: str) -> str:
    m = _INDIC_RE.search(body)
    return m.group(1).strip() if m else ""


def _extract_preparation(body: str) -> str:
    m = _PREP_RE.search(body)
    return " ".join(body[m.start():].split())[:160] if m else ""


def _extract_derivations(body: str, buckets, surface_map) -> List[Derivation]:
    out: List[Derivation] = []
    for rel, rx in (("加", _ADD_RE), ("去", _REMOVE_RE)):
        for mod, target in rx.findall(body):
            target = target.lstrip("為为名曰").strip()
            herbs = _herbs_in(mod, buckets, surface_map)
            out.append(Derivation(relation=rel, herbs=herbs or [mod], target=target))
    return out


def load_formula_book(book_dir: Path, surface_map: Dict[str, str],
                      buckets=None) -> Tuple[BookMeta, List[Formula]]:
    if buckets is None:
        buckets = _bucket(surface_map)
    files = _ordered_text_files(book_dir)
    index_path = book_dir / "index.txt"
    meta_dict = parse_metadata_block(_read(index_path)) if index_path.exists() else {}
    meta = BookMeta(
        title=meta_dict.get("title") or book_dir.name,
        author=meta_dict.get("author", ""),
        dynasty=meta_dict.get("dynasty", ""),
        year=meta_dict.get("year", ""),
        category=meta_dict.get("category", ""),
        book_id=book_dir.name,
    )

    formulas: List[Formula] = []
    # stack of (level, is_formula, formula_id_or_category_heading)
    stack: List[Tuple[int, bool, str]] = []
    counter = 0

    for path in files:
        for level, heading, body in split_sections_leveled(_read(path)):
            if heading == meta.title and not body:
                continue
            herbs = _herbs_in(body, buckets, surface_map) if body else []
            is_formula = _looks_like_formula(heading, body, len(herbs))

            # In this corpus MORE '=' means an OUTER container (book=6 ⊃
            # category=5 ⊃ formula=4 ⊃ derivative=3). Pop siblings/inner
            # entries so the stack holds only enclosing (larger-level) headings.
            while stack and stack[-1][0] <= level:
                stack.pop()

            category = next((h for lv, isf, h in reversed(stack) if not isf), "")
            parent_id = next((h for lv, isf, h in reversed(stack) if isf), "")

            if is_formula:
                counter += 1
                fid = f"{book_dir.name}::F{counter}"
                comp_raw = _extract_composition_raw(body)
                comp_herbs = _herbs_in(comp_raw, buckets, surface_map) or herbs
                formulas.append(Formula(
                    formula_id=fid,
                    name=heading,
                    book_title=meta.title,
                    dynasty=meta.dynasty,
                    author=meta.author,
                    category=category,
                    composition_herbs=comp_herbs,
                    composition_raw=comp_raw,
                    indications=_extract_indications(body),
                    preparation=_extract_preparation(body),
                    parent_id=parent_id,
                    derivations=_extract_derivations(body, buckets, surface_map),
                    source_file=path.name,
                    text=body[:1200],
                ))
                stack.append((level, True, fid))
            else:
                stack.append((level, False, heading))

    meta.n_herb_entries = len(formulas)
    return meta, formulas


def load_formula_corpus(corpus_dir: Path, surface_map: Dict[str, str]
                        ) -> Tuple[List[BookMeta], List[Formula]]:
    from .loader import iter_book_dirs
    buckets = _bucket(surface_map)
    books: List[BookMeta] = []
    formulas: List[Formula] = []
    for book_dir in iter_book_dirs(corpus_dir):
        meta, fs = load_formula_book(book_dir, surface_map, buckets)
        books.append(meta)
        formulas.extend(fs)
    return books, formulas
