"""Tests for 剂量古今换算 and 君臣佐使推断 (v0.3)."""

import pytest

from herb_hermes.formula_analysis.dosage import cn_num, parse_dose_token, DoseConverter
from herb_hermes.formula_analysis.roles import infer_roles
from herb_hermes.formula_analysis.analyzer import analyze_formula
from herb_hermes.models import Formula
from herb_hermes.normalize.normalizer import HerbNormalizer


# ---- numeral parsing ----
@pytest.mark.parametrize("s,v", [
    ("三", 3), ("十二", 12), ("二十", 20), ("七十", 70), ("一百", 100),
    ("半", 0.5), ("二兩", 2), ("5", 5),
])
def test_cn_num(s, v):
    assert cn_num(s) == v


def test_parse_dose_token():
    d = parse_dose_token("三兩去皮")
    assert d.value == 3 and d.unit == "兩"
    d2 = parse_dose_token("一兩半")
    assert d2.value == 1.5
    d3 = parse_dose_token("十二枚")
    assert d3.value == 12 and d3.unit == "枚"
    d4 = parse_dose_token("各三錢")
    assert d4.each and d4.value == 3


# ---- conversion ----
def test_converter_dynasty_factors():
    han = DoseConverter("漢")
    d = han.convert(parse_dose_token("一兩"))
    assert d.grams == pytest.approx(15.6, abs=0.1)
    qing = DoseConverter("清")
    d2 = qing.convert(parse_dose_token("一錢"))
    assert d2.grams == pytest.approx(3.73, abs=0.05)


def test_converter_zhu_and_count():
    han = DoseConverter("漢")
    zhu = han.convert(parse_dose_token("二十四銖"))
    assert zhu.grams == pytest.approx(15.6, abs=0.2)   # 24銖 = 1兩
    cnt = han.convert(parse_dose_token("七十個"))
    assert cnt.count_unit == "個" and cnt.grams is None


# ---- role inference ----
def test_infer_roles_by_dose_and_name():
    comp = [
        {"herb": "桂枝", "grams": 120.0}, {"herb": "芍藥", "grams": 120.0},
        {"herb": "生薑", "grams": 120.0}, {"herb": "大棗", "count_unit": "枚", "value": 12},
        {"herb": "甘草", "grams": 80.0},
    ]
    roles = {r["herb"]: r["role"] for r in infer_roles(comp, "桂枝湯")}
    assert roles["桂枝"] == "君"      # name match
    assert roles["甘草"] == "使"      # harmonizer
    assert roles["芍藥"] == "臣"
    assert roles["生薑"] == "佐"
    assert roles["大棗"] == "佐"


def test_infer_roles_count_unit_not_minister():
    comp = [
        {"herb": "麻黃", "grams": 60.0}, {"herb": "桂枝", "grams": 40.0},
        {"herb": "杏仁", "count_unit": "個", "value": 70}, {"herb": "甘草", "grams": 20.0},
    ]
    roles = {r["herb"]: r["role"] for r in infer_roles(comp, "麻黃湯")}
    assert roles["麻黃"] == "君"
    assert roles["桂枝"] == "臣"
    assert roles["杏仁"] == "佐"      # count unit -> not minister
    assert roles["甘草"] == "使"


# ---- end-to-end analyzer ----
def test_analyze_formula_end_to_end():
    nz = HerbNormalizer(extra_canonical=["桂枝", "芍藥", "生薑", "大棗", "甘草"])
    f = Formula(
        formula_id="t1", name="桂枝湯", book_title="測試方書", dynasty="漢",
        composition_herbs=["桂枝", "芍藥", "生薑", "大棗", "甘草"],
        composition_raw="桂枝（三兩去皮） 芍藥（三兩） 生薑（三兩） 大棗（十二枚） 甘草（二兩炙）",
        indications="太陽中風",
    )
    a = analyze_formula(f, nz)
    assert a.liang_grams == pytest.approx(15.6, abs=0.1)
    roles = {it["herb"]: it for it in a.composition}
    assert roles["桂枝"]["role"] == "君"
    assert roles["桂枝"]["grams"] == pytest.approx(46.8, abs=0.5)   # 3 × 15.6
    assert roles["甘草"]["role"] == "使"
    assert a.composition[0]["role"] == "君"   # ordered 君→臣→佐→使
