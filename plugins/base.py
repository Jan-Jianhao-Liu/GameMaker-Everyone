"""插件抽象基类 + 工具描述。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolDef:
    """工具描述。"""

    name: str
    description: str = ""
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolChain:
    """工具链 — 一组按顺序执行的工具调用模板。"""

    name: str
    steps: list[dict[str, Any]]
    """每步: {"tool": "...", "params": {...}}，params 中可用 {asset_id} 等占位符。"""


class PluginBase(ABC):
    """插件抽象基类。

    子类须实现:
      - tools(): 声明此插件提供的工具
      - call(tool, params): 执行工具调用
      - tool_chains(): 声明预定义工具链（如 Blender 的 "produce_model" 链）

    属性:
      - plugin_id: 唯一标识（如 "blender"）
      - name: 显示名（如 "Blender 4.2"）
      - plugin_type: 类型（"3d_editor"/"2d_editor"/"game_engine"/"vcs"/"custom"）
      - port: MCP server 端口
      - enabled: 是否启用
    """

    plugin_id: str = ""
    name: str = ""
    plugin_type: str = "custom"
    port: int = 0
    enabled: bool = True
    config: dict[str, Any] = field(default_factory=dict)

    @abstractmethod
    def tools(self) -> list[ToolDef]:
        """声明此插件提供的所有工具。"""

    @abstractmethod
    def call(self, tool: str, params: dict[str, Any]) -> dict[str, Any]:
        """执行工具调用，返回 {"status": "ok"/"error", "result": ..., "error": ...}。"""

    def tool_chains(self) -> dict[str, ToolChain]:
        """声明预定义工具链。子类可覆盖。"""
        return {}

    def get_chain(self, chain_name: str) -> ToolChain | None:
        """按名获取工具链。"""
        return self.tool_chains().get(chain_name)

    def tool_names(self) -> list[str]:
        """所有工具名。"""
        return [t.name for t in self.tools()]
