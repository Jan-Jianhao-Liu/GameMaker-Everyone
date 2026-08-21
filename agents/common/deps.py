"""智能体共享依赖容器。

把 LLM / Gateway / Repo / API Keys 打包成一个对象，
各角色节点工厂函数接收 AgentDeps 注入，便于测试 mock。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agents.common.llm import HybridLLM
    from agents.common.thought_bus import ThoughtBus
    from gateway.server import Gateway
    from plugins.registry import PluginRegistry
    from storage.sqlite_repo import SQLiteRepo


@dataclass
class AgentDeps:
    """智能体运行时依赖。"""

    llm: HybridLLM
    gateway: Gateway
    repo: SQLiteRepo
    api_keys: dict[str, str] = field(default_factory=dict)
    max_retries: int = 3
    plugins: PluginRegistry | None = None
    thought_bus: ThoughtBus | None = None

    def key_for(self, role: str) -> str:
        """取角色对应的 API Key（用于网关调用）。"""
        return self.api_keys.get(role, "")
