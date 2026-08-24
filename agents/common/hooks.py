"""Agent Hook 引擎 — pre/post tool 钩子 + before/after turn 钩子。

借鉴 openagentic-sdk-gdscript 的 OAHookEngine 设计：
  pre_tool_use:  工具调用前触发，可修改参数或拒绝调用
  post_tool_use: 工具调用后触发，可修改结果或记录日志
  before_turn:   agent 轮次开始前触发
  after_turn:    agent 轮次结束后触发

用法:
    hooks = HookEngine()
    hooks.add_pre_tool("log_all", "*", lambda role, tool, params: None)
    hooks.add_post_tool("audit", "node_create", lambda role, tool, params, result: None)
"""

from __future__ import annotations

import fnmatch
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Hook:
    """钩子定义。"""

    name: str
    pattern: str
    callback: Callable[..., Any]
    is_async: bool = False


class HookEngine:
    """Agent 钩子引擎。

    支持通配符匹配工具名：
      "*"          匹配所有工具
      "node_*"     匹配 node_create, node_find, ...
      "script_*"   匹配 script_attach, script_create, ...
    """

    def __init__(self) -> None:
        self._pre_tool: list[Hook] = []
        self._post_tool: list[Hook] = []
        self._before_turn: list[Hook] = []
        self._after_turn: list[Hook] = []

    def add_pre_tool(
        self, name: str, tool_pattern: str, callback: Callable[..., Any],
        is_async: bool = False,
    ) -> None:
        self._pre_tool.append(Hook(name, tool_pattern, callback, is_async))

    def add_post_tool(
        self, name: str, tool_pattern: str, callback: Callable[..., Any],
        is_async: bool = False,
    ) -> None:
        self._post_tool.append(Hook(name, tool_pattern, callback, is_async))

    def add_before_turn(
        self, name: str, role_pattern: str, callbackBak: Callable[..., Any],
        is_async: bool = False,
    ) -> None:
        self._before_turn.append(Hook(name, role_pattern, role_pattern, is_async))

    def add_after_turn(
        self, name: str, role_pattern: str, callback: Callable[..., Any],
        is_async: bool = False,
    ) -> None:
        self._after_turn.append(Hook(name, role_pattern, callback, is_async))

    def fire_pre_tool(
        self, role: str, tool: str, params: dict[str, Any],
    ) -> dict[str, Any] | None:
        """触发 pre_tool 钩子。返回 None 表示继续，返回 dict 表示替换参数。"""
        for hook in self._pre_tool:
            if fnmatch.fnmatch(tool, hook.pattern):
                result = hook.callback(role, tool, params)
                if result is not None and isinstance(result, dict):
                    return result
        return None

    def fire_post_tool(
        self, role: str, tool: str, params: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        """触发 post_tool 钩子。可修改结果。"""
        for hook in self._post_tool:
            if fnmatch.fnmatch(tool, hook.pattern):
                modified = hook.callback(role, tool, params, result)
                if modified is not None and isinstance(modified, dict):
                    result = modified
        return result

    def fire_before_turn(self, role: str, state: dict[str, Any]) -> None:
        """触发 before_turn 钩子。"""
        for hook in self._before_turn:
            if fnmatch.fnmatch(role, hook.pattern):
                hook.callback(role, state)

    def fire_after_turn(self, role: str, state: dict[str, Any]) -> None:
        """触发 after_turn 钩子。"""
        for hook in self._after_turn:
            if fnmatch.fnmatch(role, hook.pattern):
                hook.callback(role, state)

    def has_hooks(self) -> bool:
        """是否有任何钩子注册。"""
        return bool(self._pre_tool or self._post_tool or self._before_turn or self._after_turn)