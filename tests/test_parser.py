"""Unit tests for the low-level corpus parsers."""

from herb_hermes.corpus.parser import (
    parse_metadata_block,
    split_sections,
    extract_code_block,
    parse_code_fields,
    is_itemized_book,
)
from herb_hermes.corpus.loader import load_book


def test_parse_metadata_block():
    text = "x\n<book>\n書名=神農本草經\n作者=孫星衍\n朝代=清\n年份=1644\n</book>\ny"
    meta = parse_metadata_block(text)
    assert meta["title"] == "神農本草經"
    assert meta["author"] == "孫星衍"
    assert meta["dynasty"] == "清"


def test_parse_metadata_block_missing():
    assert parse_metadata_block("no block here") == {}


def test_split_sections():
    text = "=====序=====\n前言內容\n=====正文=====\n正文內容"
    secs = dict(split_sections(text))
    assert secs["序"].strip() == "前言內容"
    assert secs["正文"].strip() == "正文內容"


def test_parse_code_fields_multiline():
    code = "藥名：貝母\n性味：苦\n辛。\n主治：治虛勞\n咳嗽。\n配伍：反烏頭。"
    fields = parse_code_fields(code)
    assert fields["藥名"] == "貝母"
    assert "辛" in fields["性味"]          # multi-line value joined
    assert "咳嗽" in fields["主治"]
    assert fields["配伍"] == "反烏頭。"


def test_extract_code_block():
    assert extract_code_block("a<code>X\nY</code>b") == "X\nY"
    assert extract_code_block("no code") == ""


def test_is_itemized_by_title():
    assert is_itemized_book("某某條列版", [])


def test_load_book_itemized(mini_corpus):
    meta, passages, herbs = load_book(mini_corpus / "書籍" / "測試本草條列版")
    assert meta.title == "測試本草"
    assert meta.dynasty == "清"
    names = {h.name for h in herbs}
    assert names == {"黃耆", "當歸"}
    hq = next(h for h in herbs if h.name == "黃耆")
    assert "補氣" in hq.functions
    assert "強筋骨" in hq.indications
    assert hq.code == "草部001"
