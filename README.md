# Herb-Hermes 本草—方剂—机制—发现 证据操作系统 (MVP v0.5)

Herb-Hermes 是面向中医药经典本草与方剂演变的科学发现系统。本仓库实现了设计
草案的**可运行闭环**：从古籍原文出发，完成本草结构化、药名归一与名物考订、
本草溯源、**方剂谱系重建**、**君臣佐使推断**、**剂量古今换算**、引文可溯检索、
知识图谱构建、药对共现挖掘，自动生成**引文落地的科研假设卡**，提供**「研究驾驶舱」
Web 前端**将全部功能可视化，支持**语音交互**（FireRedASR2S / CosyVoice3），
并通过 **litellm 接入大语言模型 + 自主智能体**让大模型在真实古籍证据上推理作答，
**新增 MiniMax-M3 等模型一键接入、SSE 流式推理与浏览器端模型配置面板**，
亦可作为 **MCP 工具服务**接入 Claude Code / Codex 等智能体客户端。

> **规则 × 大模型 × 智能体**：确定性数据挖掘提供可溯源证据，大模型负责语义综合与
> 问答，工具调用把两者耦合——模型只能引用工具检索到的古籍内容，显著降低幻觉。

> MVP 主题切入：**补益类本草 + 骨质疏松 / 骨伤修复**（与设计草案第九节一致）。

核心管线**仅依赖 Python 标准库**，离线即可运行；HTTP API 层使用可选的 FastAPI；
前端为零构建的静态页面（ECharts CDN），由 API 直接托管。LLM / 语音 / MCP 均为
**可选、惰性加载**，未安装不影响核心系统。

---

## 数据底座

语料为「中醫笈成」`book-20180111` 的**本草**与**方書**分类包，已置于
`data/raw/`：

| 指标 | 数量 |
| --- | --- |
| 本草古籍 | 57 部（《神農本草經》《本草綱目》《證類本草》《本草備要》…） |
| 方書古籍 | 88 部（《湯頭歌訣》《祖劑》《太平惠民和劑局方》《醫方集解》…） |
| 章节段落 (passages) | 约 49,700 |
| 结构化单味药条目 | 709（来自「條列版」本草） |
| 方剂记录 / 唯一方名 | 约 25,900 / 19,600 |
| 谱系（结构父子）/ 类方相似边 | 约 2,480 / 20,400 |
| 知识图谱 节点 / 边 | 约 690 / 3,200 |

原始来源：<https://jicheng.tw/files/jcw/book-20180111.7z>（开放古籍数据库）。

---

## 快速开始

```bash
# 1) 构建知识库（解析本草+方書 -> data/processed/herb_hermes_kb.json，约 75s）
python -m herb_hermes.index_build

# 2) 启动「研究驾驶舱」前端（推荐）
pip install fastapi uvicorn
uvicorn herb_hermes.api.server:app --port 8000
# 打开 http://127.0.0.1:8000/  —— 首次启动会载入知识库（约 40s）
# API 文档： http://127.0.0.1:8000/docs

# 3) CLI 探索
python -m herb_hermes.cli stats
python -m herb_hermes.cli herb 黃芪                  # 单味药结构化条目
python -m herb_hermes.cli trace 當歸                 # 本草溯源（跨书跨代时间线）
python -m herb_hermes.cli formula 桂枝湯             # 方剂谱系 + 君臣佐使 + 剂量古今换算
python -m herb_hermes.cli formulas-with 杜仲         # 含某味药的方剂
python -m herb_hermes.cli search 強筋骨 補肝腎        # 引文可溯的全文检索 (BM25)
python -m herb_hermes.cli pairs --herb 黃芪           # 药对共现挖掘
python -m herb_hermes.cli hypothesis 黃芪 --partner 當歸 --disease 骨质疏松
python -m herb_hermes.cli report 杜仲 --out 杜仲.md   # 一键导出 Markdown 报告

# 4) 端到端 Demo（骨质疏松知识发现）
python scripts/demo_osteoporosis.py
```

> 构建产物 `data/processed/herb_hermes_kb.json`（约 130MB）已被 `.gitignore`
> 排除，请在本地用上面的命令重建。持久化只存段落文本，BM25 索引在加载时重建，
> 故启动需数十秒。

---

## 接入大语言模型 + 自主智能体（以 MiniMax-M3 为例）

Herb-Hermes 通过 **litellm** 统一接入 OpenAI / Anthropic / 本地（Ollama）/
**MiniMax** 等 100+ 模型。下面以 **MiniMax-M3**（1M 上下文，支持思考分离）为示例。

### 方式一：环境变量（服务端全局）

```bash
pip install litellm
export MINIMAX_API_KEY=your-minimax-key
export HERB_HERMES_LLM_MODEL=minimax/MiniMax-M3
uvicorn herb_hermes.api.server:app --port 8000
# 重启后，研究驾驶舱「智能问答」页即可用 MiniMax-M3 推理
```

### 方式二：浏览器端配置面板（无需重启，推荐）

打开研究驾驶舱 → 右上角 **⚙ 模型配置** → 选择 **MiniMax** → 模型选 **MiniMax-M3** →
填入 **API Key** → 应用设置。Key 仅存于浏览器 `localStorage`，每次请求直接转发，
不落盘到服务端。

### 方式三：Python 代码

```python
from herb_hermes.store import KnowledgeBase
from herb_hermes.llm.client import LLMClient
from herb_hermes.llm.agent import HerbAgent

kb = KnowledgeBase.load()
client = LLMClient(
    model="minimax/MiniMax-M3",
    api_key="your-minimax-key",        # 或用环境变量 MINIMAX_API_KEY
    # api_base 默认 https://api.minimaxi.com/v1，可省略
)

# 流式思考过程 + 工具调用全程可见
def on_thinking(t): print("【思考】", t[:80])
def on_step(s):     print(f"【工具】{s.tool} {s.arguments}")

agent = HerbAgent(kb, client, max_steps=6, on_step=on_step, on_thinking=on_thinking)
result = agent.ask("杜仲补肝肾强筋骨的古籍依据与配伍规律？")
print("回答：", result.answer)
print("引文：", result.citations[:3])
```

MiniMax 调用会**自动附加 `reasoning_split=True`**，把模型的「思考过程」与最终
答案分离，并在前端以可折叠卡片实时展示。完整示例（流式 / litellm 底层 /
Anthropic SDK 兼容入口）见 [`docs/minimax.md`](docs/minimax.md)。

### 支持的 MiniMax 模型

| 模型 | 上下文 | 思考分离 |
| --- | --- | --- |
| **MiniMax-M3** | 1M tokens | ✦ |
| MiniMax-M2.7 / -highspeed | 204.8K | ✦ |
| MiniMax-M2.5 / -highspeed | 204.8K | ✦ |
| MiniMax-M2.1 / -highspeed | 204.8K | ✦ |
| MiniMax-M2 | 204.8K | ✦ |

> 其它 provider 同理：`HERB_HERMES_LLM_MODEL=gpt-4o-mini`（OpenAI）、
> `claude-sonnet-4-6`（Anthropic）、`ollama/qwen2.5`（本地），配相应 API Key 即可。
> 未配置任何模型时，「智能问答」页自动回退到**规则检索**（BM25 + 方剂谱系 + 本草溯源）。

### 作为 MCP 工具接入 Claude Code / Codex（可选）

```bash
pip install "mcp[cli]"
claude mcp add herb-hermes -- python -m herb_hermes.mcp_server
```

之后在 Claude Code / Codex 中即可让其调用 `trace_herb`、`formula_genealogy`、
`analyze_formula`、`search_corpus`、`generate_hypothesis` 等工具，获得带古籍引文的结果。

---

## 研究驾驶舱前端

`frontend/`（`index.html` + `styles.css` + `app.js`，零构建）由 FastAPI 在 `/`
直接托管，包含七个模块：**概览驾驶舱、本草溯源、方剂谱系、药对配伍、古籍检索、
科研假设、智能问答**。可视化采用 ECharts：历代著录时间线、功效/配伍力导图、
方剂谱系树、类方相似网络、药对网络、君臣佐使色谱柱状图等，节点可点击下钻。

前端亮点（v0.5）：

- **⚙ 模型配置面板**：Provider（MiniMax / OpenAI / Anthropic / Ollama / 自定义）、
  模型选择、API Key、API Base URL，存浏览器 `localStorage`，随请求覆盖服务端配置。
- **流式智能问答**：SSE 边推理边渲染——工具调用步骤逐条出现，MiniMax 思考内容
  以可折叠 `<details>` 实时累积，最后给出带引文的综合回答。
- **规则化回退**：未接入 LLM 时，智能问答自动执行 BM25 检索 + 方剂谱系 + 本草溯源
  并内联展示，仍能给出有价值的可溯源结果。
- **语音交互**：🎤 语音检索（FireRedASR2S / 浏览器识别）+ 🔊 朗读（CosyVoice3 / 浏览器合成）。

---

## API 端点一览

| 端点 | 方法 | 说明 |
| --- | --- | --- |
| `/health`、`/stats` | GET | 健康检查 / 语料统计 |
| `/herb/{name}` | GET | 单味药结构化条目 + 图谱邻居 |
| `/trace/{name}` | GET | 本草溯源（朝代时间线 + 引文证据） |
| `/search?q=` | GET | BM25 引文检索 |
| `/pairs?herb=` | GET | 药对共现挖掘（PMI） |
| `/formula/{name}` | GET | 方剂谱系 + 君臣佐使 + 剂量换算 |
| `/analyze/{name}` | GET | 单方君臣佐使与剂量折算 |
| `/formulas?herb=` | GET | 含某味药的方剂 |
| `/hypothesis?herb=` | GET | 科研假设卡 |
| `/report/{name}` | GET | Markdown 报告 |
| `/voice/status`、`/voice/asr`、`/voice/tts` | GET/POST | 语音状态 / 识别 / 合成 |
| `/llm/status` | GET | LLM 是否就绪、选用模型、已探测 provider |
| **`/llm/models`** | GET | 分组模型目录（供前端选择器） |
| **`/agent/ask`** | POST | 智能体问答（非流式）；接受 `model`/`api_key`/`api_base` 覆盖 |
| **`/agent/stream`** | POST | 智能体问答（SSE 流式）；事件 `thinking`/`tool`/`done`/`error` |

`/agent/stream` 流式调用示例：

```bash
curl -N -X POST http://localhost:8000/agent/stream \
  -H "Content-Type: application/json" \
  -d '{"question": "桂枝汤的君臣佐使与衍生方？", "model": "minimax/MiniMax-M3", "api_key": "your-key"}'
```

---

## 已实现的设计模块

| 设计草案模块 | 本仓库实现 |
| --- | --- |
| Corpus / Normalization 层 | `corpus/`（解析 `<book>` 元数据、章节、`<code>` 条列字段）、`normalize/`（异名归一 + 名物歧义） |
| 本草演变 / 溯源 | `discovery/sourcing.py`：按朝代排序的跨书著录时间线与引文证据 |
| **方剂谱系重建** | `corpus/formula_loader.py` + `genealogy/`：从标题层级（祖劑/湯頭）重建源方→衍生方，解析组成/主治/煎服，识别「加X名Y / 去X名Y」加減线索，类方网络（组成 Jaccard），跨书同名演变 |
| 检索层 (BM25 + 引文) | `retrieval/`：古文友好的字/双字分词 + 纯 Python BM25，覆盖本草与方書，命中即带《书·篇（朝代·作者）》引文 |
| 知识图谱层 | `kg/graph.py`：herb / 歸經 / 性味 / 功效 节点 + 配伍边，导出 node-link JSON 与 DOT |
| 配伍规律发现 (药对) | `discovery/cooccurrence.py`：配伍字段 + 段落共现，PMI 评分 |
| **君臣佐使推断** | `formula_analysis/roles.py`：综合剂量权重、方名命名、功能词典、位置，推断君/臣/佐/使并给依据与置信度 |
| **剂量古今换算** | `formula_analysis/dosage.py`：解析古代剂量（兩/錢/分/銖/升/枚…），按朝代因子折算现代克数 |
| 科研假设 Agent | `discovery/hypothesis.py`：模板化、引文落地的 Hypothesis Card（现代机制明确标注为「待验证假设」） |
| **语音交互 Agent** | `voice/`：FireRedASR2S（ASR）+ CosyVoice3（TTS）可插拔后端，浏览器 Web Speech API 零依赖回退 |
| **大模型 + 自主智能体** | `llm/`：litellm 统一客户端（含 **MiniMax** 接入 + `reasoning_split` 思考分离 + 流式）+ 接地工具注册表 + ReAct 智能体（每条事实带引文、强约束防幻觉）；`MockLLMClient` 离线可测 |
| **MCP 工具服务** | `mcp_server.py`：把全部工具暴露给 Claude Code / Codex / 任意 MCP 客户端 |
| 安全红线 | 假设卡、报告、智能体回答均声明「现代机制为待验证假设，不构成临床处方建议」 |
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
python -m pytest -q          # 49 passed（在毫秒级合成语料上端到端验证）
```

测试不依赖原始语料：`tests/conftest.py` 内置微型合成本草与方書，覆盖解析、
归一、BM25（含序列化往返）、图谱、溯源、药对、假设卡、方剂层级解析、谱系
重建（结构父子 + 加減线索 + 类方）、知识库存取，以及智能体闭环
（用 `MockLLMClient` 离线脚本化驱动「调用工具 → 综合作答」，无需联网或 API Key）。

---

## 目录结构

```text
herb_hermes/
  corpus/        语料解析与加载（元数据 / 章节 / 条列字段 / 方剂层级解析）
  normalize/     药名归一 + 名物歧义表
  retrieval/     古文分词 + BM25（带引文）
  kg/            知识图谱构建与查询
  genealogy/     方剂谱系：源流/衍生/类方/演变
  formula_analysis/ 君臣佐使推断 + 剂量古今换算
  voice/         语音交互：FireRedASR2S (ASR) + CosyVoice3 (TTS) 可插拔后端
  llm/           大模型接入(litellm，含 MiniMax) + 接地工具 + 自主智能体(流式)
  mcp_server.py  MCP 工具服务（Claude Code / Codex 接入）
  discovery/     溯源 / 药对 / 假设卡
  store.py       KnowledgeBase：构建·持久化·查询的中枢
  index_build.py 构建知识库入口
  report.py      Markdown 报告导出
  cli.py         命令行界面
  api/server.py  FastAPI 层（含前端托管 + 语音 + 智能体 + 流式 + 模型目录端点）
frontend/        研究驾驶舱（index.html + styles.css + app.js，ECharts + 语音 +
                 智能问答 + 模型配置面板 + SSE 流式）
notebooks/       语音服务 GPU 部署 notebook
data/raw/本草/   本草语料底座
data/raw/方書/   方書语料底座
scripts/         端到端 Demo
tests/           pytest 测试（49 项）
docs/            设计与路线说明（architecture / genealogy / dosage_roles /
                 voice / agent / minimax / roadmap）
```

更多内容见 [`docs/architecture.md`](docs/architecture.md)、
[`docs/agent.md`](docs/agent.md)、[`docs/minimax.md`](docs/minimax.md) 与
[`docs/roadmap.md`](docs/roadmap.md)。

---

## 边界与免责声明

- 现阶段是**离线证据闭环**：现代药理 / 组学（TCMSP、HERB、ETCM、GEO、KEGG）
  以**接口占位**呈现，机制链与通路均明确标注为「假设，待外部数据验证」。
- 系统面向**科研与知识发现**，**不生成临床处方、不替代执业医师判断**。
- 语料为传统字古籍，归一表为人工冷启动种子，非穷尽本体。
- API Key 安全：前端配置面板中的 Key 仅存浏览器 `localStorage`，请求时直接转发至
  对应 Provider，不经 Herb-Hermes 服务端持久化。
