"""Tests for formula extraction and genealogy (v0.2)."""

from herb_hermes.corpus.parser import split_sections_leveled
from herb_hermes.corpus.formula_loader import load_formula_corpus
from herb_hermes.genealogy.genealogy import FormulaGenealogy
from herb_hermes.normalize.normalizer import HerbNormalizer


def _surface_map():
    n = HerbNormalizer(extra_canonical=[
        "人參", "白朮", "茯苓", "甘草", "半夏", "陳皮", "桂枝", "芍藥", "生薑", "大棗",
    ])
    return n.surface_to_canonical()


def test_split_sections_leveled_depth():
    text = "======書======\n=====門=====\n本\n====方名====\n組成\n===子方===\n子"
    secs = split_sections_leveled(text)
    levels = {h: lv for lv, h, b in secs}
    assert levels["門"] == 5
    assert levels["方名"] == 4
    assert levels["子方"] == 3


def test_formula_extraction(mini_formula_corpus):
    books, formulas = load_formula_corpus(mini_formula_corpus, _surface_map())
    names = {f.name for f in formulas}
    assert {"四君子湯", "六君子湯", "桂枝湯"} <= names
    sjz = next(f for f in formulas if f.name == "四君子湯")
    assert set(["人參", "白朮", "茯苓", "甘草"]) <= set(sjz.composition_herbs)
    assert sjz.category == "補益之劑"


def test_formula_structural_parent(mini_formula_corpus):
    _, formulas = load_formula_corpus(mini_formula_corpus, _surface_map())
    by_name = {f.name: f for f in formulas}
    # 六君子湯 is nested (level 3) under 四君子湯 (level 4)
    child = by_name["六君子湯"]
    assert child.parent_id == by_name["四君子湯"].formula_id


def test_inline_derivation_cue(mini_formula_corpus):
    _, formulas = load_formula_corpus(mini_formula_corpus, _surface_map())
    sjz = next(f for f in formulas if f.name == "四君子湯")
    targets = {d.target for d in sjz.derivations}
    assert "六君子湯" in targets


def test_genealogy_query(mini_formula_corpus):
    _, formulas = load_formula_corpus(mini_formula_corpus, _surface_map())
    g = FormulaGenealogy(formulas).build_similarity()
    view = g.genealogy("四君子湯")
    assert view["found"]
    assert "六君子湯" in {d["name"] for d in view["descendants"]}
    # 桂枝湯 composition resolved
    gz = g.genealogy("桂枝湯")
    assert set(["桂枝", "芍藥", "甘草"]) <= set(gz["primary"]["composition_herbs"])


def test_similarity_network(mini_formula_corpus):
    _, formulas = load_formula_corpus(mini_formula_corpus, _surface_map())
    g = FormulaGenealogy(formulas).build_similarity()
    # 四君子湯 and 六君子湯 share 4 herbs -> should be 类方
    view = g.genealogy("四君子湯")
    sim_names = {s["name"] for s in view["similar"]}
    assert "六君子湯" in sim_names


def test_formulas_with_herb(mini_formula_corpus):
    _, formulas = load_formula_corpus(mini_formula_corpus, _surface_map())
    g = FormulaGenealogy(formulas)
    hits = g.formulas_with_herb("人參")
    assert any(f.name == "四君子湯" for f in hits)
