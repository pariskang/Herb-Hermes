# 大模型与自主智能体 (v0.4)

把 v0.1–v0.3 的确定性、带引文的能力（溯源 / 谱系 / 君臣佐使 / 剂量 / 药对 /
假设）升级为**接地的智能体层**：大模型负责推理与编排，但每一条事实都来自一个
回传古籍引文的工具。两个集成方向：

```text
出站 (litellm) ── Herb-Hermes ── 入站 (MCP)
GPT / Claude / 本地模型           Claude Code / Codex / 任意 MCP 客户端
        │                                  │
        └────── 同一套接地工具 ToolRegistry ──┘
```

## 出站：litellm 接入任意模型 (`llm/`)

- `client.py`：`LLMClient` 基于 litellm（**惰性导入**），由 `HERB_HERMES_LLM_MODEL`
  选择模型（`gpt-4o-mini` / `claude-sonnet-4-6` / `ollama/qwen2.5` …）。
  `MockLLMClient` 同接口，用于离线测试与演示。
- `tools.py`：`ToolRegistry` 把 KB 能力封装为函数调用工具（OpenAI/litellm schema），
  每个工具回传精简、带《书·篇（朝代·作者）》引文的结果。
- `agent.py`：`HerbAgent` 函数调用循环（ReAct）。系统提示强约束：
  **只依据工具证据作答、必须引用、不编造、现代机制标注「待验证」、不提供处方**。
  返回 `answer + steps(工具调用全记录) + citations`，前端逐步可溯。

### 配置
```bash
pip install litellm
export HERB_HERMES_LLM_MODEL=claude-sonnet-4-6     # 或 gpt-4o-mini / ollama/qwen2.5
export ANTHROPIC_API_KEY=...                        # 或 OPENAI_API_KEY 等
uvicorn herb_hermes.api.server:app --port 8000
```
未配置时核心系统照常运行，`/agent/ask` 返回 503，前端「智能问答」页给出指引并
引导改用规则化模块。

### API
- `GET /llm/status` — 是否安装 litellm、选用模型、已探测到的 provider
- `POST /agent/ask` — `{question, history?, max_steps?}` → `{answer, steps[], citations[], model}`

## 入站：MCP 服务（Claude Code / Codex / …）

`herb_hermes/mcp_server.py` 用 MCP SDK 暴露同一套工具，任何 MCP 兼容客户端均可调用：

```bash
pip install "mcp[cli]"
python -m herb_hermes.mcp_server
# 注册到 Claude Code：
claude mcp add herb-hermes -- python -m herb_hermes.mcp_server
```
之后在 Claude Code / Codex 中即可让其调用 `trace_herb`、`formula_genealogy`、
`analyze_formula`、`search_corpus`、`generate_hypothesis` 等工具，并获得带古籍引文的
结果——把本草方剂的专业检索能力接入通用编码/研究智能体。

## 规则 × 大模型：为什么接地很重要

- **数据挖掘（规则）**给出可复现、可溯源的结构化证据（PMI 药对、Jaccard 类方、
  剂量折算、君臣佐使推断、朝代时间线）。
- **大模型**负责语义理解、跨证据综合、自然语言问答与假设阐述。
- 通过工具把两者耦合：模型不能凭记忆杜撰古籍，只能引用工具检索到的内容，
  从而显著降低幻觉、保证学术可追溯——这正是中医药文献研究的硬要求。

## 离线可验证

`tests/test_agent.py` 用 `MockLLMClient` 脚本化驱动「调用工具 → 综合作答」的完整
闭环（单/多工具），在合成语料上断言工具被正确调用、结果接地、答复非空——无需联网
或 API Key 即可验证智能体编排逻辑。
