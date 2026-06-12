# Herb-Hermes 架构说明 (MVP v0.1)

本 MVP 落地设计草案七层架构中**已可离线闭环**的部分，并为外部数据/智能体
预留接口。

## 数据流

```text
data/raw/本草/書籍/<書名>/{index.txt, N.txt, menu.txt}
        │  corpus.parser  (解析 <book> 元数据 / =章节= / <code> 条列字段)
        ▼
corpus.loader  ──►  BookMeta · Passage · HerbEntry
        │
        ▼
store.KnowledgeBase.build
   ├─ normalize.HerbNormalizer   异名→规范名，歧义名物标记
   ├─ registry                   规范名 → [HerbEntry]（跨书）
   ├─ retrieval.BM25Index        段落倒排 + 引文
   ├─ kg.HerbGraph               herb/歸經/性味/功效 节点 + 配伍边
   └─ discovery.mine_pairs       预计算药对 (PMI)
        │ save() / load()  ◄──►  data/processed/herb_hermes_kb.json
        ▼
应用层：cli · api.server · report · discovery.sourcing/hypothesis
```

## 各层与设计草案的对应

| 草案层 | 模块 | 说明 |
| --- | --- | --- |
| 1 Corpus | `corpus/` | 解析三种实际版式：纯散文、多文件章节、條列版结构化 `<code>` |
| 2 Normalization | `normalize/` | 异名归一、简繁桥接、歧义名物（`朮/桂/芍藥/地黃`）不强行归一 |
| 3 Knowledge Graph | `kg/graph.py` | 纯字典邻接，导出 node-link JSON / Graphviz DOT 供 Cytoscape/ECharts/G6 |
| 4 Retrieval | `retrieval/` | 古文字/双字分词 + BM25；可扩展向量/GraphRAG |
| 5 Agent | `discovery/` | 溯源、药对、假设三类「分析型」算子（草案 Analyst 层） |
| 6 Application | `cli.py` `api/server.py` `report.py` | 本草溯源 / 检索 / 药对 / 假设 / 报告导出 |
| 7 Evaluation | `tests/` | 解析/检索/图谱/管线单元与集成测试 |

## 关键设计取舍

- **纯标准库核心**：无需 GPU/联网即可构建与查询；FastAPI 仅在 API 层按需导入。
- **字级分词**：古文以单字为主，字 + 双字 n-gram 对本草术语（多为双字）召回良好，
  且免去外部分词模型依赖。
- **引文优先**：每个 `Passage`/`Evidence` 携带《书·篇（朝代·作者）》引文，
  保证「引文可追溯率」这一草案评估指标。
- **歧义优先于强归一**：名物考订是专业壁垒，错误归一比保留歧义代价更高。
- **假设卡的诚实性**：古籍证据来自语料真实命中；现代机制为种子映射，
  统一标注「待验证」，不伪造既成事实。

## 数据模型

见 `herb_hermes/models.py`：`BookMeta`、`Passage`、`HerbEntry`、`Evidence`、
`SourcingResult`、`HerbPair`、`HypothesisCard`，均可 JSON 往返。
```text
HerbEntry = name + 性味/歸經/功用/主治/禁忌/炮製/配伍/十劑 + raw_fields(原样保留)
```
`raw_fields` 保留解析到的全部原始字段，确保「无静默丢字」。

## 扩展点（已预留接口）

- `discovery/hypothesis.py:DISEASE_MECHANISMS`：疾病→证候/通路/细胞类型种子，
  可替换为 TCMSP/HERB/ETCM/GEO 实时查询。
- `retrieval/`：可加入向量检索 + GraphRAG/LightRAG（草案第四节）。
- `corpus/`：可接入方书分类包以构建方剂谱系（草案创新点 2）。
