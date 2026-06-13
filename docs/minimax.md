# MiniMax 模型接入指南

Herb-Hermes v0.5 新增 MiniMax 模型支持，通过 litellm 的 OpenAI 兼容路由接入。

## 快速开始

```bash
pip install litellm

# 方式一：环境变量（服务端全局配置）
export MINIMAX_API_KEY=your-api-key
export HERB_HERMES_LLM_MODEL=minimax/MiniMax-M3
uvicorn herb_hermes.api.server:app --port 8000

# 方式二：前端浏览器设置
# 打开研究驾驶舱 → 右上角 ⚙ → 选择 MiniMax → 填入 API Key → 应用设置
```

## 支持的模型

| 模型 | 上下文 | 思考模式 | 适用场景 |
|------|--------|----------|----------|
| MiniMax-M3 | 1M tokens | ✦ 是 | 长文献分析、多轮推理 |
| MiniMax-M2.7 | 204.8K | ✦ 是 | 均衡速度/质量 |
| MiniMax-M2.7-highspeed | 204.8K | ✦ 是 | 快速响应 |
| MiniMax-M2.5 | 204.8K | ✦ 是 | — |
| MiniMax-M2.5-highspeed | 204.8K | ✦ 是 | — |
| MiniMax-M2.1 | 204.8K | ✦ 是 | — |
| MiniMax-M2 | 204.8K | ✦ 是 | — |

API 申请：<https://api.minimaxi.com>

## Python 代码示例

### 非流式调用（使用 LLMClient）

```python
import os
os.environ["MINIMAX_API_KEY"] = "your-api-key"
os.environ["HERB_HERMES_LLM_MODEL"] = "minimax/MiniMax-M3"

from herb_hermes.llm.client import LLMClient

client = LLMClient()
resp = client.complete([
    {"role": "user", "content": "黄芪的主要功效是什么？"}
])
print("思考：", resp.thinking[:200] if resp.thinking else "(无)")
print("回答：", resp.content)
```

### 直接传入 API Key（不依赖环境变量）

```python
from herb_hermes.llm.client import LLMClient

client = LLMClient(
    model="minimax/MiniMax-M3",
    api_key="your-api-key",
    api_base="https://api.minimaxi.com/v1",   # 可选，已内置默认值
)
resp = client.complete([{"role": "user", "content": "六味地黄丸的君臣佐使？"}])
```

### 使用自主智能体

```python
from herb_hermes.store import KnowledgeBase
from herb_hermes.llm.client import LLMClient
from herb_hermes.llm.agent import HerbAgent

kb = KnowledgeBase.load()
client = LLMClient(model="minimax/MiniMax-M3", api_key="your-key")

def on_thinking(thinking):
    print("【思考】", thinking[:100])

def on_step(step):
    print(f"【工具】{step.tool}({step.arguments})")

agent = HerbAgent(kb, client, max_steps=6,
                  on_step=on_step, on_thinking=on_thinking)
result = agent.ask("杜仲补肝肾强筋骨的古籍依据与配伍规律？")
print("回答：", result.answer)
print("引文：", result.citations[:3])
```

### 流式调用

```python
client = LLMClient(model="minimax/MiniMax-M3", api_key="your-key")
messages = [{"role": "user", "content": "桂枝汤的历代演变？"}]

for event in client.stream(messages):
    if event["type"] == "thinking":
        print("思考：", event["content"], end="", flush=True)
    elif event["type"] == "token":
        print(event["content"], end="", flush=True)
    elif event["type"] == "done":
        print()
```

### 直接使用 litellm（底层，不经过 LLMClient）

```python
import litellm

response = litellm.completion(
    model="openai/MiniMax-M3",
    api_base="https://api.minimaxi.com/v1",
    api_key="your-api-key",
    messages=[{"role": "user", "content": "你好"}],
    extra_body={"reasoning_split": True},   # 让思考内容单独返回
)
msg = response.choices[0].message
print("回答：", msg.content)
# 提取 reasoning_details 中的思考内容
for item in getattr(msg, "reasoning_details", []) or []:
    if isinstance(item, dict) and item.get("type") == "thinking":
        print("思考：", item["thinking"])
```

### Anthropic SDK 兼容（可选）

MiniMax 也支持 Anthropic SDK 兼容入口：

```python
import anthropic
import os

client = anthropic.Anthropic(
    api_key="your-minimax-key",
    base_url="https://api.minimaxi.com/anthropic",
)
resp = client.messages.create(
    model="MiniMax-M3",
    max_tokens=1024,
    messages=[{"role": "user", "content": "补肾强骨类方剂的演变？"}],
)
print(resp.content[0].text)
```

## API 端点

启动服务后，可通过以下 API 端点使用 MiniMax：

```bash
# 非流式（阻塞直到完成）
curl -X POST http://localhost:8000/agent/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "杜仲的功效？", "model": "minimax/MiniMax-M3", "api_key": "your-key"}'

# 流式 SSE（边生成边返回）
curl -X POST http://localhost:8000/agent/stream \
  -H "Content-Type: application/json" \
  -d '{"question": "桂枝汤的君臣佐使？", "model": "minimax/MiniMax-M3", "api_key": "your-key"}'
# 返回 text/event-stream，事件类型：thinking / tool / done / error

# 查看模型列表
curl http://localhost:8000/llm/models

# 查看当前服务端配置状态
curl http://localhost:8000/llm/status
```

## 注意事项

- `reasoning_split=True` 由 LLMClient 自动附加，无需手动设置。
- 多轮对话时，`content` 字段中不含 `<think>` 标签（因为启用了 `reasoning_split`），
  litellm 已处理消息序列化，无需特殊处理。
- MiniMax-M3 上下文 1M tokens，适合在同一会话中加载大量古籍段落。
- API Key 安全：前端设置中，Key 只存于浏览器 `localStorage`，
  每次请求直接从前端发往后端转发给 MiniMax，不落盘。
