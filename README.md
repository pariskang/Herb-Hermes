# Herb-Hermes 本草—方剂—机制—发现 证据操作系统 (MVP v0.1)

Herb-Hermes 是面向中医药经典本草演变的科学发现系统。本仓库实现了设计草案
v0.1 的**可运行最小闭环 (MVP)**：从古籍原文出发，完成本草结构化、药名归一与
名物考订、本草溯源、引文可溯检索、知识图谱构建、药对共现挖掘，并自动生成
**引文落地的科研假设卡**。

> MVP 主题切入：**补益类本草 + 骨质疏松 / 骨伤修复**（与设计草案第九节一致）。

核心管线**仅依赖 Python 标准库**，离线即可运行；HTTP API 层使用可选的 FastAPI。

---

## 数据底座

语料为「中醫笈成」`book-20180111` 的**本草**分类包，已置于 `data/raw/本草/`：

| 指标 | 数量 |
| --- | --- |
| 本草古籍 | 57 部（《神農本草經》《本草綱目》《證類本草》《本草備要》…） |
| 章节段落 (passages) | 约 23,000 |
| 结构化单味药条目 | 709（来自「條列版」本草） |
| 归一后唯一药名 | 约 575 |
| 知识图谱 节点 / 边 | 约 690 / 3,200 |

原始来源：<https://jicheng.tw/files/jcw/book-20180111.7z>（开放古籍数据库）。

---

## 快速开始

```bash
# 1) 构建知识库（解析语料 -> data/processed/herb_hermes_kb.json，约 20s）
python -m herb_hermes.index_build

# 2) CLI 探索
python -m herb_hermes.cli stats
python -m herb_hermes.cli herb 黃芪                 # 单味药结构化条目
python -m herb_hermes.cli trace 當歸                # 本草溯源（跨书跨代时间线）
python -m herb_hermes.cli search 強筋骨 補肝腎       # 引文可溯的全文检索 (BM25)
python -m herb_hermes.cli pairs --herb 黃芪          # 药对共现挖掘
python -m herb_hermes.cli graph 黃芪                 # 知识图谱邻接
python -m herb_hermes.cli hypothesis 黃芪 --partner 當歸 --disease 骨质疏松
python -m herb_hermes.cli report 杜仲 --out 杜仲.md  # 一键导出 Markdown 报告

# 3) 端到端 Demo（骨质疏松知识发现）
python scripts/demo_osteoporosis.py

# 4) 可选 HTTP API
pip install fastapi uvicorn
uvicorn herb_hermes.api.server:app --reload          # http://127.0.0.1:8000/docs
```

> 构建产物 `data/processed/herb_hermes_kb.json`（约 150MB）已被 `.gitignore`
> 排除，请在本地用上面的命令重建。

---

## 已实现的设计模块

| 设计草案模块 | 本仓库实现 |
| --- | --- |
| Corpus / Normalization 层 | `corpus/`（解析 `<book>` 元数据、章节、`<code>` 条列字段）、`normalize/`（异名归一 + 名物歧义） |
| 本草演变 / 溯源 | `discovery/sourcing.py`：按朝代排序的跨书著录时间线与引文证据 |
| 检索层 (BM25 + 引文) | `retrieval/`：古文友好的字/双字分词 + 纯 Python BM25，命中即带《书·篇（朝代·作者）》引文 |
| 知识图谱层 | `kg/graph.py`：herb / 歸經 / 性味 / 功效 节点 + 配伍边，导出 node-link JSON 与 DOT |
| 配伍规律发现 (药对) | `discovery/cooccurrence.py`：配伍字段 + 段落共现，PMI 评分 |
| 科研假设 Agent | `discovery/hypothesis.py`：模板化、引文落地的 Hypothesis Card（现代机制明确标注为「待验证假设」） |
| 安全红线 | 假设卡与报告均声明「现代机制为待验证假设，不构成临床处方建议」 |
| 应用层 | `cli.py`、`api/server.py`、`report.py`（一键报告） |

### 名物考订（设计草案的核心壁垒）

`朮`、`桂`、`芍藥`、`地黃` 等**不强行归一**，而是标记为歧义并给出判断依据
（朝代 / 主治 / 性味 / 配伍）。例如：

```text
$ python -m herb_hermes.cli trace 朮
『朮』为歧义名物：宋以前『朮』多未嚴格區分白朮與蒼朮，需依朝代、主治、性味與配伍判斷。
```

---

## 测试

```bash
pip install pytest
python -m pytest -q          # 21 passed（在毫秒级合成语料上端到端验证）
```

测试不依赖 28MB 原始语料：`tests/conftest.py` 内置微型合成本草，覆盖解析、
归一、BM25（含序列化往返）、图谱、溯源、药对、假设卡与知识库存取。

---

## 目录结构

```text
herb_hermes/
  corpus/        语料解析与加载（元数据 / 章节 / 条列字段）
  normalize/     药名归一 + 名物歧义表
  retrieval/     古文分词 + BM25（带引文）
  kg/            知识图谱构建与查询
  discovery/     溯源 / 药对 / 假设卡
  store.py       KnowledgeBase：构建·持久化·查询的中枢
  index_build.py 构建知识库入口
  report.py      Markdown 报告导出
  cli.py         命令行界面
  api/server.py  可选 FastAPI 层
data/raw/本草/   语料底座
scripts/         端到端 Demo
tests/           pytest 测试
docs/            设计与路线说明
```

更多内容见 [`docs/architecture.md`](docs/architecture.md) 与
[`docs/roadmap.md`](docs/roadmap.md)。

---

## 边界与免责声明

- 现阶段是**离线证据闭环**：现代药理 / 组学（TCMSP、HERB、ETCM、GEO、KEGG）
  以**接口占位**呈现，机制链与通路均明确标注为「假设，待外部数据验证」。
- 系统面向**科研与知识发现**，**不生成临床处方、不替代执业医师判断**。
- 语料为传统字古籍，归一表为人工冷启动种子，非穷尽本体。
