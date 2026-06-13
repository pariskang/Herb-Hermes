"""Seed alias and ambiguity tables for materia-medica names.

This is a hand-curated cold-start table, not an exhaustive ontology. Each
canonical herb maps to a list of historical/variant names (异名). Ambiguous
tokens are names that must NOT be force-normalized because their referent
depends on dynasty, context, paired herbs, or flavor — exactly the kind of
名物考订 problem the design calls out.

The tables use traditional characters to match the 中醫笈成 corpus, with a
small simplified<->traditional bridge applied at runtime by the normalizer.
"""

from __future__ import annotations

from typing import Dict, List

# canonical -> historical aliases / 异名
ALIAS_TABLE: Dict[str, List[str]] = {
    "黃芪": ["黃耆", "黄芪", "黄耆", "戴糝", "戴椹", "獨椹", "蜀脂", "綿芪", "綿黃芪", "箭芪"],
    "甘草": ["國老", "美草", "蜜甘", "粉草", "炙甘草"],
    "人參": ["人参", "神草", "人銜", "鬼蓋", "黃參", "血參", "地精"],
    "當歸": ["当归", "乾歸", "山蘄", "白蘄"],
    "熟地黃": ["熟地", "熟地黄"],
    "生地黃": ["生地", "乾地黃", "地髓"],
    "白朮": ["白术", "於朮", "于术", "山薊", "山精"],
    "蒼朮": ["苍术", "赤朮", "山精"],
    "白芍": ["白芍藥", "金芍藥"],
    "赤芍": ["赤芍藥", "木芍藥"],
    "肉桂": ["桂", "桂心", "牡桂", "紫桂", "玉桂"],
    "桂枝": ["柳桂"],
    "茯苓": ["茯菟", "伏靈", "雲苓", "松腴"],
    "川芎": ["芎藭", "芎窮", "撫芎", "京芎"],
    "牛膝": ["牛茎", "百倍", "懷牛膝", "川牛膝"],
    "杜仲": ["思仲", "思仙", "木綿", "石思仙"],
    "續斷": ["续断", "屬折", "接骨", "龍豆", "南草"],
    "骨碎補": ["骨碎补", "猴薑", "胡猻薑", "石毛薑"],
    "淫羊藿": ["仙靈脾", "剛前", "三枝九葉草", "放杖草"],
    "附子": ["附子", "黑附子", "熟附子"],
    "半夏": ["守田", "水玉", "地文", "和姑"],
    "牡丹皮": ["丹皮", "丹根", "牡丹根皮"],
    "山茱萸": ["山萸肉", "萸肉", "棗皮", "蜀棗"],
    "山藥": ["薯蕷", "懷山藥", "淮山"],
    "澤瀉": ["水瀉", "澤芝"],
}

# tokens that look like a herb name but are genuinely ambiguous.
# value = note explaining the disambiguation hinge.
AMBIGUOUS_TOKENS: Dict[str, str] = {
    "朮": "宋以前『朮』多未嚴格區分白朮與蒼朮，需依朝代、主治、性味與配伍判斷。",
    "术": "同『朮』；可能指白朮或蒼朮。",
    "桂": "可指桂枝、肉桂或桂心，依方劑與功效定位判斷。",
    "芍": "可指白芍或赤芍；古方多作『芍藥』通稱。",
    "芍藥": "古籍『芍藥』未必對應現代單一白芍/赤芍。",
    "地黃": "需區分生地黃與熟地黃，炮製不同則功效相反。",
    "烏頭": "與附子同源（川烏/附子），毒性與炮製差異大。",
}

# canonical groups whose members are easily conflated; surfaced as warnings.
CONFUSABLE_GROUPS = [
    {"白朮", "蒼朮"},
    {"白芍", "赤芍"},
    {"桂枝", "肉桂"},
    {"生地黃", "熟地黃"},
    {"川牛膝", "懷牛膝"},
]
