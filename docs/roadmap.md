# Herb-Hermes 路线图

按设计草案「先骨质疏松 MVP → 扩展病种 → 通用平台」推进。

## v0.1（本仓库，已完成）

- [x] 本草语料解析（57 部，2.3 万段落，709 条结构化条目）
- [x] 药名归一 + 名物歧义（朮/桂/芍藥/地黃）
- [x] 本草溯源（跨书跨代时间线 + 引文证据）
- [x] BM25 引文检索
- [x] 本草知识图谱（herb/歸經/性味/功效 + 配伍）
- [x] 药对共现挖掘（PMI）
- [x] 科研假设卡（引文落地，现代机制标注待验证）
- [x] CLI + FastAPI + Markdown 报告导出
- [x] pytest 测试闭环

## v0.2（方剂谱系 + 研究驾驶舱前端，已完成）

- [x] 接入方書分类包（88 部），抽取方剂组成、主治、煎服法
- [x] 方剂谱系重建：标题层级父子（祖劑/湯頭）+ 「加X名Y / 去X名Y」加減线索
- [x] 类方网络（组成 Jaccard 相似）
- [x] 跨书同名方剂演变（历代著录）
- [x] 含某味药的方剂检索；方剂组成纳入 BM25 与药对挖掘
- [x] 「研究驾驶舱」Web 前端（六模块 + ECharts 可视化）

## v0.3（君臣佐使 + 剂量换算 + 语音交互，已完成）

- [x] 剂量古今换算（`formula_analysis/dosage.py`）：中文数字/单位解析，
      朝代换算因子（漢/唐/宋/明/清/民国/现代），重量·容量·计数分治
- [x] 君臣佐使推断（`formula_analysis/roles.py`）：剂量权重 + 方名命名 +
      功能词典 + 位置，输出角色 / 依据 / 置信度（经典方验证一致）
- [x] 语音交互（`voice/`）：FireRedASR2S（ASR）+ CosyVoice3（TTS）可插拔后端，
      浏览器 Web Speech API 零依赖回退；前端 🎤 语音检索 + 🔊 朗读
- [x] GPU 部署 notebook（`notebooks/HerbHermes_Voice_Server.ipynb`）

## v0.3（现代机制映射）

- [ ] TCMSP / HERB / ETCM / SymMap 成分-靶点-疾病接入
- [ ] GEO 差异表达交集验证
- [ ] KEGG/Reactome 通路富集
- [ ] 假设卡自动填充「现代证据」并给出证据分级

## v0.4（大模型 + 自主智能体 + MCP，已完成）

- [x] litellm 统一客户端（出站接 GPT/Claude/本地模型），`MockLLMClient` 离线可测
- [x] 接地工具注册表（`llm/tools.py`）：8 个工具，结果均带古籍引文
- [x] ReAct 自主智能体（`llm/agent.py`）：强约束防幻觉，回答带引文与全程工具调用记录
- [x] MCP 工具服务（`mcp_server.py`）：接入 Claude Code / Codex / 任意 MCP 客户端
- [x] 前端「智能问答」模块：流程可溯、引文卡片、朗读
- [ ] 向量检索 + GraphRAG / LightRAG（待后续）
- [ ] Neo4j/Kùzu 图数据库后端（待后续）

## v0.5（MiniMax 接入 + UI 完整集成，已完成）

- [x] **MiniMax 模型接入**：MiniMax-M3/M2.7/M2.5/M2.1/M2（含 highspeed 变体）通过
      litellm OpenAI 兼容路由接入；自动启用 `reasoning_split=True`，思考内容
      单独返回并在前端实时展示
- [x] **SSE 流式智能体端点**（`POST /agent/stream`）：边推理边返回 thinking / tool / done 事件，
      前端逐步渲染工具调用步骤与思考内容
- [x] **前端模型配置面板**（⚙ 设置）：Provider 选择（MiniMax / OpenAI / Anthropic / Ollama / 自定义）、
      模型选择、API Key、API Base URL，存于浏览器 `localStorage`，
      每次 agent 请求携带 model/api_key/api_base 字段（服务端支持按请求覆盖）
- [x] **规则化回退**：未配置 LLM 时，智能问答自动执行 BM25 检索 + 方剂谱系 + 本草溯源，
      提供有价值的规则检索结果，并引导配置模型
- [x] **`/llm/models` 端点**：返回分组模型目录，供前端动态渲染选择器
- [x] **per-request 模型覆盖**：`/agent/ask` 与 `/agent/stream` 均接受请求体中的
      `model` / `api_key` / `api_base` 字段，优先于服务端环境变量

## v0.5（现代机制 + 审稿/安全智能体，待续）

- [ ] TCMSP / HERB / ETCM / SymMap / GEO / KEGG 真实现代机制接入（填充假设卡现代证据）
- [ ] 反证审稿 Agent、安全审查 Agent（药典 2025 + 十八反十九畏硬约束）
- [ ] 论文/课题草案生成
- [ ] 向量检索 + GraphRAG / LightRAG
- [ ] Neo4j/Kùzu 图数据库后端

## 病种扩展顺序

骨质疏松 / 骨伤修复 → 肺癌骨转移 → 银屑病 / 类风湿 → 慢病康复 → 通用平台
