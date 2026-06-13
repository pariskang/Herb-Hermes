"""剂量古今换算: parse classical dose expressions and convert to modern grams.

Conversion is dynasty-dependent and scholarly-contested; we use the most
widely cited figures and always carry the assumption in the result's ``note``.
References: 丘光明《中国历代度量衡考》、柯雪帆《伤寒论》剂量考、
《中国科学技术史·度量衡卷》。

Weight system
-------------
* 漢/魏晉南北朝: 1斤=16兩, 1兩=24銖；1兩≈15.6g（1斤≈250g，柯雪帆/上海中医药）。
* 隋唐: 1兩≈41.3g（1斤≈661g，大制）。
* 宋金元: 1兩≈40g（1斤≈640g）；后世 1兩=10錢, 1錢=10分, 1分=10厘。
* 明: 1兩≈37.0g；清: 1兩≈37.3g。
* 民國（旧市制）: 1兩=31.25g（16兩=500g）；现代（新市制）: 1兩=50g（10兩=500g）。

Volume (漢制经方): 1斗=10升, 1升≈200ml, 1合≈20ml（按容积报告 ml）。
Count units (枚/個/片/條/握/束/杯/盞…): 非定量，原样报告。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple

# grams per 兩 by dynasty (key matched by substring containment).
DYNASTY_LIANG_GRAMS: Dict[str, float] = {
    "漢": 15.6, "魏": 15.6, "晉": 15.6, "南北朝": 15.6,
    "隋": 41.3, "唐": 41.3,
    "宋": 40.0, "金": 40.0, "元": 40.0,
    "明": 37.0, "清": 37.3,
    "民國": 31.25, "民国": 31.25, "近代": 31.25,
    "現代": 50.0, "现代": 50.0, "當代": 50.0,
}
_DEFAULT_LIANG_G = 37.3  # 清制 as a neutral fallback

# ---- Chinese numeral parsing ----------------------------------------
_CN_DIGIT = {"〇": 0, "零": 0, "○": 0, "一": 1, "二": 2, "兩": 2, "两": 2,
             "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_CN_UNIT = {"十": 10, "百": 100, "千": 1000}


def cn_num(s: str) -> Optional[float]:
    """Parse a Chinese/arabic numeral string to a float. 半=0.5. None if empty."""
    s = s.strip()
    if not s:
        return None
    if re.fullmatch(r"\d+(?:\.\d+)?", s):
        return float(s)
    # bare 半
    if s == "半":
        return 0.5
    total = 0.0
    section = 0.0
    matched = False
    i = 0
    while i < len(s):
        ch = s[i]
        if ch in _CN_DIGIT:
            section = _CN_DIGIT[ch]
            matched = True
        elif ch in _CN_UNIT:
            unit = _CN_UNIT[ch]
            section = (section or 1) * unit
            total += section
            section = 0.0
            matched = True
        elif ch == "半":
            section += 0.5
            matched = True
        i += 1
    total += section
    return total if matched else None


# ---- dose token parsing ---------------------------------------------
_WEIGHT_UNITS = {"斤", "兩", "两", "錢", "钱", "分", "銖", "铢", "厘", "釐"}
_VOLUME_UNITS = {"斗", "升", "合", "勺"}
_COUNT_UNITS = {"枚", "個", "个", "片", "條", "条", "握", "束", "杯", "盞", "盏",
                "粒", "丸", "節", "节", "支", "朵", "莖", "茎", "把", "筒", "顆", "颗",
                "字", "錢匕", "刀圭", "方寸匕"}

_NUM = "[半〇零○一二三四五六七八九十百千兩两\\d]"
_UNIT = "(?:斤|兩|两|錢匕|錢|钱|分|銖|铢|厘|釐|斗|升|合|勺|枚|個|个|片|條|条|握|束|杯|盞|盏|粒|丸|節|节|支|朵|莖|茎|把|筒|顆|颗|字|刀圭|方寸匕)"
# e.g. 三兩 / 半斤 / 二兩半 / 十二枚 / 七十個 / 各三錢
DOSE_RE = re.compile(rf"(各)?\s*({_NUM}+)\s*({_UNIT})\s*(半)?")


@dataclass
class Dose:
    raw: str = ""
    value: Optional[float] = None
    unit: str = ""
    each: bool = False           # 各 (shared dose)
    grams: Optional[float] = None
    ml: Optional[float] = None
    count_unit: Optional[str] = None
    note: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)


def parse_dose_token(text: str) -> Optional[Dose]:
    """Parse the first dose expression in ``text`` (a small window)."""
    m = DOSE_RE.search(text)
    if not m:
        return None
    each, num_s, unit, half = m.group(1), m.group(2), m.group(3), m.group(4)
    val = cn_num(num_s)
    if val is None:
        return None
    if half:
        val += 0.5
    unit = {"两": "兩", "钱": "錢", "铢": "銖", "个": "個", "条": "條", "节": "節",
            "盏": "盞", "茎": "莖", "釐": "厘", "颗": "顆"}.get(unit, unit)
    return Dose(raw=m.group(0).strip(), value=val, unit=unit, each=bool(each))


class DoseConverter:
    """Convert a parsed :class:`Dose` to modern grams given a dynasty."""

    def __init__(self, dynasty: str = "") -> None:
        self.dynasty = dynasty
        self.liang_g = self._liang_for(dynasty)

    @staticmethod
    def _liang_for(dynasty: str) -> float:
        for key, g in DYNASTY_LIANG_GRAMS.items():
            if key and key in (dynasty or ""):
                return g
        return _DEFAULT_LIANG_G

    def convert(self, dose: Dose) -> Dose:
        if dose.value is None:
            return dose
        u, v = dose.unit, dose.value
        han = self.liang_g <= 16  # 漢制 uses 銖 and 1斤=16兩
        if u in _WEIGHT_UNITS:
            liang = {
                "斤": 16.0, "兩": 1.0,
                "錢": 0.1, "分": 0.01, "厘": 0.001,
                "銖": 1.0 / 24.0,
            }.get(u)
            if liang is not None:
                dose.grams = round(v * liang * self.liang_g, 2)
                dose.note = f"按{self._era_label()}制 1兩≈{self.liang_g}g 折算"
        elif u in _VOLUME_UNITS:
            ml = {"斗": 2000.0, "升": 200.0, "合": 20.0, "勺": 2.0}.get(u)
            if ml is not None:
                dose.ml = round(v * ml, 1)
                dose.note = "按漢制 1升≈200ml 折算（容量，仅供参考）"
        elif u in _COUNT_UNITS:
            dose.count_unit = u
            if u == "字":
                dose.grams = round(v * 0.65, 2)
                dose.note = "一字≈0.65g（约一钱匕的四分之一），估值"
            else:
                dose.note = "计数单位，无法定量折算"
        return dose

    def _era_label(self) -> str:
        for key in ("漢", "唐", "宋", "明", "清", "民國", "現代"):
            if key in (self.dynasty or ""):
                return key
        return "清"
