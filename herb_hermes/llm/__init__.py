"""大语言模型接入层 (v0.4): litellm 统一客户端 + 工具 + 自主智能体.

设计原则：
* **接地 (grounded)**：智能体只能通过工具获取事实，每个工具都回传古籍引文；
  系统提示强约束「只依据工具证据作答、必须引用、不编造、现代机制标注待验证」。
* **零依赖可降级**：未安装 litellm 或未配置 API Key 时，核心系统照常运行；
  智能体接口返回明确指引。
* **可离线验证**：``LLMClient`` 与 ``MockLLMClient`` 同接口，单元测试用 mock
  脚本驱动完整的工具调用闭环，无需联网。
"""

from .client import LLMClient, MockLLMClient, LLMResponse, ToolCall, llm_status
from .tools import ToolRegistry
from .agent import HerbAgent

__all__ = [
    "LLMClient", "MockLLMClient", "LLMResponse", "ToolCall", "llm_status",
    "ToolRegistry", "HerbAgent",
]
