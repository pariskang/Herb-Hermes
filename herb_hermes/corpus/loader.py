"""Walk a 本草 corpus directory tree and materialize structured objects."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterator, List, Tuple

from ..models import BookMeta, HerbEntry, Passage
from .parser import (
    FIELD_KEY_MAP,
    extract_code_block,
    is_itemized_book,
    parse_code_fields,
    parse_metadata_block,
    split_sections,
)

_NUM_RE = re.compile(r"^(\d+)\.txt$")


def iter_book_dirs(corpus_dir: Path) -> Iterator[Path]:
    """Yield each book directory under ``<corpus>/書籍``."""
    books_root = corpus_dir / "書籍"
    if not books_root.exists():
        books_root = corpus_dir
    for child in sorted(books_root.iterdir()):
        if child.is_dir():
            yield child


def _ordered_text_files(book_dir: Path) -> List[Path]:
    """index.txt first, then numbered files in numeric order, then the rest."""
    files = [p for p in book_dir.glob("*.txt") if p.name != "menu.txt"]
    index = [p for p in files if p.name == "index.txt"]
    numbered = sorted((p for p in files if _NUM_RE.match(p.name)),
                      key=lambda p: int(_NUM_RE.match(p.name).group(1)))
    others = [p for p in files if p.name != "index.txt" and not _NUM_RE.match(p.name)]
    return index + numbered + others


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _build_herb_entry(name: str, fields: Dict[str, str], meta: BookMeta,
                      source_file: str) -> HerbEntry:
    attrs: Dict[str, str] = {}
    for cn_key, value in fields.items():
        attr = FIELD_KEY_MAP.get(cn_key)
        if attr in (None, "code2", "category2", "nature", "flavor"):
            continue
        if attr == "aliases":
            continue
        # Accumulate notes from multiple keys.
        if attr == "notes" and attrs.get("notes"):
            attrs["notes"] = attrs["notes"] + "\n" + value
        else:
            attrs[attr] = value

    # Compose 性味 from separate 性 / 味 if no combined field.
    if not attrs.get("nature_flavor"):
        nf = "，".join(v for v in (fields.get("性", ""), fields.get("味", "")) if v)
        if nf:
            attrs["nature_flavor"] = nf

    aliases: List[str] = []
    if fields.get("別名"):
        aliases = [a for a in re.split(r"[、,，;；\s]+", fields["別名"]) if a]

    entry_name = fields.get("藥名") or fields.get("名稱") or name
    return HerbEntry(
        name=entry_name.strip(),
        book_title=meta.title,
        dynasty=meta.dynasty,
        author=meta.author,
        code=fields.get("編號", ""),
        aliases=aliases,
        nature_flavor=attrs.get("nature_flavor", ""),
        meridians=attrs.get("meridians", ""),
        functions=attrs.get("functions", ""),
        indications=attrs.get("indications", ""),
        contraindications=attrs.get("contraindications", ""),
        processing=attrs.get("processing", ""),
        compatibility=attrs.get("compatibility", ""),
        category=attrs.get("category", ""),
        notes=attrs.get("notes", ""),
        source_file=source_file,
        raw_fields=dict(fields),
    )


def load_book(book_dir: Path) -> Tuple[BookMeta, List[Passage], List[HerbEntry]]:
    """Parse one book directory into metadata, passages and herb entries."""
    files = _ordered_text_files(book_dir)
    index_path = book_dir / "index.txt"
    meta_dict = parse_metadata_block(_read(index_path)) if index_path.exists() else {}
    meta = BookMeta(
        title=meta_dict.get("title") or book_dir.name,
        author=meta_dict.get("author", ""),
        dynasty=meta_dict.get("dynasty", ""),
        year=meta_dict.get("year", ""),
        category=meta_dict.get("category", ""),
        quality=meta_dict.get("quality", ""),
        book_id=book_dir.name,
    )

    # First pass: collect all sections (so we can detect itemized books).
    all_sections: List[Tuple[str, str, str]] = []  # (heading, body, source_file)
    for path in files:
        for i, (head, body) in enumerate(split_sections(_read(path))):
            # The opening heading of index.txt equals the book title; keep it
            # only if it has real body text.
            if path.name == "index.txt" and i == 0 and head == meta.title and not body.strip():
                continue
            all_sections.append((head, body, path.name))

    itemized = is_itemized_book(meta.title, [b for _, b, _ in all_sections[:40]])

    passages: List[Passage] = []
    herbs: List[HerbEntry] = []
    for idx, (head, body, src) in enumerate(all_sections):
        section = head or meta.title
        passages.append(Passage(
            passage_id=f"{book_dir.name}#{idx}",
            book_title=meta.title,
            dynasty=meta.dynasty,
            author=meta.author,
            section=section,
            text=body,
            source_file=src,
        ))
        if itemized:
            code = extract_code_block(body)
            if code:
                fields = parse_code_fields(code)
                if any(k in fields for k in ("藥名", "名稱", "性味", "主治", "功用", "功能")):
                    herbs.append(_build_herb_entry(section, fields, meta, src))

    meta.n_passages = len(passages)
    meta.n_herb_entries = len(herbs)
    return meta, passages, herbs


def load_corpus(corpus_dir: Path) -> Tuple[List[BookMeta], List[Passage], List[HerbEntry]]:
    """Load every book under ``corpus_dir`` into flat lists."""
    books: List[BookMeta] = []
    passages: List[Passage] = []
    herbs: List[HerbEntry] = []
    for book_dir in iter_book_dirs(corpus_dir):
        meta, p, h = load_book(book_dir)
        books.append(meta)
        passages.extend(p)
        herbs.extend(h)
    return books, passages, herbs
