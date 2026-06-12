"""Corpus ingestion: parse 中醫笈成 本草 book directories into structured objects."""

from .parser import (
    parse_metadata_block,
    split_sections,
    parse_code_fields,
    is_itemized_book,
)
from .loader import load_corpus, iter_book_dirs, load_book

__all__ = [
    "parse_metadata_block",
    "split_sections",
    "parse_code_fields",
    "is_itemized_book",
    "load_corpus",
    "iter_book_dirs",
    "load_book",
]
