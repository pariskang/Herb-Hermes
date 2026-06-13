"""Unit tests for normalizer, tokenizer, BM25, and graph."""

from herb_hermes.models import HerbEntry, Passage
from herb_hermes.normalize.normalizer import HerbNormalizer
from herb_hermes.retrieval.tokenizer import tokenize
from herb_hermes.retrieval.bm25 import BM25Index
from herb_hermes.kg.graph import HerbGraph


def test_normalizer_alias():
    n = HerbNormalizer()
    r = n.normalize("黃耆")
    assert r.canonical == "黃芪"
    assert not r.ambiguous


def test_normalizer_simplified_bridge():
    n = HerbNormalizer()
    assert n.normalize("黄芪").canonical == "黃芪"


def test_normalizer_ambiguous():
    n = HerbNormalizer()
    r = n.normalize("朮")
    assert r.ambiguous
    assert "白朮" in r.note


def test_tokenizer_bigrams():
    toks = tokenize("黃芪補氣")
    assert "黃" in toks and "芪" in toks
    assert "黃芪" in toks and "補氣" in toks


def test_bm25_ranks_relevant_first():
    idx = BM25Index()
    idx.add(Passage("1", "甲書", "清", "", "黃芪", "黃芪補氣固表強筋骨"))
    idx.add(Passage("2", "乙書", "明", "", "桂枝", "桂枝發汗解表"))
    idx.build()
    hits = idx.search("強筋骨")
    assert hits and hits[0][0].passage_id == "1"


def test_bm25_roundtrip():
    idx = BM25Index()
    idx.add(Passage("1", "甲書", "清", "", "黃芪", "黃芪補氣"))
    idx.build()
    restored = BM25Index.from_dict(idx.to_dict())
    assert restored.search("補氣")[0][0].passage_id == "1"


def test_graph_compatibility_edges():
    g = HerbGraph()
    surface = {"黃耆": "黃芪", "當歸": "當歸"}
    e = HerbEntry(name="黃耆", book_title="x", nature_flavor="甘、微溫",
                  functions="補氣固表", compatibility="配當歸。")
    g.add_herb(e, surface)
    labels = {n["label"] for n in g.neighbors("黃芪")}
    assert "當歸" in labels        # partner canonicalized
    assert "補氣" in labels        # function node attached
