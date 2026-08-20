"""通用工具链执行器 — 从插件获取 ToolChain 模板，占位符替换后通过 gateway 执行。

用法:
    executor = ChainExecutor()
    result = executor.execute(
        registry, plugin_id="blender", chain_name="produce_model",
        role="artist3d", key="k", gateway=gw,
        context={"asset_id": "model_hero", "out_path": "game/assets/models/model_hero.fbx"},
    )
    # result = {"status": "ok"} 或 {"status": "error", "error": "...", "tool": "..."}

占位符规则:
    - "{key}" 完全匹配 → 直接替换为 context[key]（保持原类型：list/dict/int 等）
    - "prefix_{key}_suffix" 部分匹配 → str.format 字符串替换
    - 未匹配的 {key} 保留原样
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from plugins.registry import PluginRegistry

_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


def _resolve_value(value: Any, context: dict[str, Any]) -> Any:
    """递归替换占位符。"""
    if isinstance(value, str):
        full = _PLACEHOLDER_RE.fullmatch(value)
        if full and full.group(1) in context:
            return context[full.group(1)]
        for ck, cv in context.items():
            value = value.replace(f"{{{ck}}}", str(cv))
        return value
    if isinstance(value, dict):
        return {k: _resolve_value(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_value(v, context) for v in value]
    return value


def resolve_params(params: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """替换 params 中所有占位符。"""
    return {k: _resolve_value(v, context) for k, v in params.items()}


class ChainExecutor:
    """通用工具链执行器。"""

    def execute(
        self,
        registry: PluginRegistry,
        plugin_id: str,
        chain_name: str,
        role: str,
        key: str,
        gateway: Any,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """执行插件工具链。

        Returns:
            {"status": "ok"} 或 {"status": "error", "error": str, "tool": str}
        """
        plugin = registry.get(plugin_id)
        if plugin is None:
            return {"status": "error", "error": f"插件 {plugin_id} 未加载"}
        chain = plugin.get_chain(chain_name)
        if chain is None:
            return {"status": "error", "error": f"工具链 {chain_name} 不存在于插件 {plugin_id}"}

        for step in chain.steps:
            tool = step["tool"]
            params = resolve_params(step.get("params", {}), context)
            r = gateway.call(role, key, tool, params)
            if r.get("status") != "ok":
                return {"status": "error", "error": f"{tool}: {r.get('error')}", "tool": tool}
        return {"status": "ok", "result": r.get("result", {})}

    def execute_steps(
        self,
        steps: list[dict[str, Any]],
        role: str,
        key: str,
        gateway: Any,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """执行显式步骤列表（不从插件读取，但做占位符替换）。

        用于 agent 需要追加自定义步骤（如 commit_asset）的场景。
        """
        for step in steps:
            tool = step["tool"]
            params = resolve_params(step.get("params", {}), context)
            r = gateway.call(role, key, tool, params)
            if r.get("status") != "ok":
                return {"status": "error", "error": f"{tool}: {r.get('error')}", "tool": tool}
        return {"status": "ok"}
