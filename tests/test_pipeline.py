"""Integration tests over the synthetic mini corpus end-to-end."""

from herb_hermes.store import KnowledgeBase
from herb_hermes.discovery.sourcing import trace_herb
from herb_hermes.discovery.hypothesis import build_hypothesis_card


def test_build_and_stats(mini_corpus):
    kb = KnowledgeBase.build(mini_corpus)
    assert kb.stats["books"] == 2
    assert kb.stats["herb_entries"] == 2
    assert "黃芪" in kb.herb_vocab        # canonicalized from 黃耆


def test_registry_alias_lookup(mini_corpus):
    kb = KnowledgeBase.build(mini_corpus)
    # querying by canonical name returns the entry stored under alias 黃耆
    assert kb.get_entries("黃芪")
    assert kb.get_entries("黄芪")          # simplified query also resolves


def test_trace_across_books(mini_corpus):
    kb = KnowledgeBase.build(mini_corpus)
    res = trace_herb(kb, "黃芪")
    books = {t["book"] for t in res.dynasty_timeline}
    assert "測試本草" in books and "測試方書" in books
    # timeline sorted oldest dynasty first (明 before 清)
    assert res.dynasty_timeline[0]["dynasty"] == "明"


def test_trace_ambiguous():
    from herb_hermes.store import KnowledgeBase
    kb = KnowledgeBase()  # empty KB still resolves ambiguity from seed table
    res = trace_herb(kb, "桂")
    assert res.ambiguous


def test_pairs_mined(mini_corpus):
    kb = KnowledgeBase.build(mini_corpus)
    pair_set = {frozenset((p.herb_a, p.herb_b)) for p in kb.pairs}
    assert frozenset(("黃芪", "當歸")) in pair_set


def test_hypothesis_card(mini_corpus):
    kb = KnowledgeBase.build(mini_corpus)
    card = build_hypothesis_card(kb, "黃芪", partner="當歸", disease="骨质疏松")
    assert card.hypothesis_id.startswith("HH-HYP-")
    assert "骨质疏松" in card.research_question
    assert card.classical_evidence            # grounded in corpus
    assert card.mechanism_chain["disease"] == "骨质疏松"


def test_save_load_roundtrip(mini_corpus, tmp_path):
    kb = KnowledgeBase.build(mini_corpus)
    path = kb.save(tmp_path / "kb.json")
    kb2 = KnowledgeBase.load(path)
    assert kb2.stats["herb_entries"] == kb.stats["herb_entries"]
    assert kb2.get_entries("黃芪")
    assert kb2.bm25.search("補氣")
