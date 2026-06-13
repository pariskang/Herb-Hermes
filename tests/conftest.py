"""Shared fixtures: a tiny synthetic 本草 corpus so tests run in milliseconds."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ITEMIZED_BOOK = """\
======測試本草條列版======

<book>
書名=測試本草
作者=測試
朝代=清
年份=1700
分類=本草
品質=0%
</book>

=====黃耆=====
<code>
編號：草部001
藥名：黃耆
性味：甘、微溫。
功用：補氣固表，托毒生肌，利水消腫。
主治：治氣虛血虛，癰疽久敗瘡，強筋骨。
配伍：得當歸則補血，得防風則固表。配當歸、防風。
炮製：蜜炙用。
禁忌：表實邪盛者禁用。
</code>

=====當歸=====
<code>
編號：草部002
藥名：當歸
性味：甘、辛、溫。
功用：補血活血，養血。
主治：治血虛諸證，強筋骨，續筋接骨。
配伍：得黃耆則補氣生血。配黃耆、川芎。
炮製：酒洗用。
</code>
"""

PROSE_BOOK = """\
======測試方書======

<book>
書名=測試方書
作者=某甲
朝代=明
年份=1500
分類=本草
品質=0%
</book>

=====補氣方=====
黃耆四兩，當歸二錢，防風一錢，共治氣虛血瘀，強筋骨，補肝腎。
"""


FORMULA_BOOK = """\
======測試方書譜======

<book>
書名=測試方書譜
作者=測試
朝代=宋
年份=1100
分類=方書
品質=0%
</book>

=====補益之劑=====

====四君子湯====

治氣虛諸證。人參　白朮　茯苓　甘草（各等分）。上為末，每服二錢。
加半夏陳皮名六君子湯。

===六君子湯===

治氣虛有痰。人參　白朮　茯苓　甘草　半夏　陳皮。上為末。

=====祛風之劑=====

====桂枝湯====

治太陽中風。桂枝　芍藥　生薑　大棗　甘草。上五味，水煎服。
"""


@pytest.fixture
def mini_corpus(tmp_path: Path) -> Path:
    books = tmp_path / "本草" / "書籍"
    b1 = books / "測試本草條列版"
    b1.mkdir(parents=True)
    (b1 / "index.txt").write_text(ITEMIZED_BOOK, encoding="utf-8")
    b2 = books / "測試方書"
    b2.mkdir(parents=True)
    (b2 / "index.txt").write_text(PROSE_BOOK, encoding="utf-8")
    return tmp_path / "本草"


@pytest.fixture
def mini_formula_corpus(tmp_path: Path) -> Path:
    books = tmp_path / "方書" / "書籍"
    b = books / "測試方書譜"
    b.mkdir(parents=True)
    (b / "index.txt").write_text(FORMULA_BOOK, encoding="utf-8")
    return tmp_path / "方書"
