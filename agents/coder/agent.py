"""coder（程序）子图。

拉取已交付资产 + GDD，经网关调用 godot-mcp：
import_asset（每个资产）→ create_scene → attach_script（含 InputAdapter）→
set_level_data（从 GDD levels 驱动）→ build_export（Windows 桌面）。

build_export 产出默认 draft 状态（发布确认卡点由 qa 通过后触发）。
完成后 current_role = "qa"。
"""

from __future__ import annotations

from collections.abc import Callable

from agents.common.deps import AgentDeps
from agents.common.state import AgentState
from agents.team_config import RoleConfig
from plugins.executor import ChainExecutor

_BUILD_OUTPUT = "game/build/windows"


def make_coder_node(
    deps: AgentDeps, role_config: RoleConfig | None = None,
) -> Callable[[AgentState], dict]:
    """构造 coder 节点函数。"""

    def coder_node(state: AgentState) -> dict:
        task_id = state.get("task_id", "unknown")
        key = deps.key_for("coder")
        produced = state.get("produced_assets", [])
        gdd = state.get("gdd", {})

        existing_build = state.get("build_result", {})
        if existing_build.get("status") in ("pending_release", "release"):
            return {"current_role": "qa"}

        for asset in produced:
            r = deps.gateway.call(
                "coder", key, "import_asset", {"asset_id": asset["asset_id"], "path": asset["path"]}
            )
            if r.get("status") != "ok":
                deps.repo.save_task_memory(
                    "coder", task_id, "import_asset", "error", str(r.get("error"))
                )
                return {
                    "errors": [f"导入资产 {asset['asset_id']} 失败: {r.get('error')}"],
                    "current_role": "coder",
                }

        if not _run_build_chain(deps, gdd, key, task_id, role_config):
            return {"errors": ["构建失败"], "current_role": "coder"}

        deps.repo.save_task_memory("coder", task_id, "build", "ok", "构建完成（draft）")
        return {
            "build_result": {"path": _BUILD_OUTPUT, "status": "draft"},
            "current_role": "qa",
            "errors": [],
        }

    return coder_node


def _run_build_chain(
    deps: AgentDeps, gdd: dict, key: str, task_id: str,
    role_config: RoleConfig | None,
) -> bool:
    """执行构建步骤。优先插件链，回退硬编码。"""
    build_output = (role_config.build_output if role_config and role_config.build_output
                    else _BUILD_OUTPUT)
    levels = gdd.get("levels", [])

    if deps.plugins is not None and role_config and role_config.plugin and role_config.chain:
        executor = ChainExecutor()
        r = executor.execute(
            deps.plugins, role_config.plugin, role_config.chain,
            "coder", key, deps.gateway,
            {"levels": levels, "build_output": build_output},
        )
        if r["status"] != "ok":
            deps.repo.save_task_memory(
                "coder", task_id, r.get("tool", "build"), "error", r["error"],
            )
            return False
        return True

    steps = [
        ("create_scene", {"scene_name": "Main", "template": "scene_3d"}),
        ("attach_script", {"node": "Player", "script_template": "character"}),
        ("set_level_data", {"levels": levels}),
        ("build_export", {"platform": "windows", "output_path": build_output}),
    ]
    for tool, params in steps:
        r = deps.gateway.call("coder", key, tool, params)
        if r.get("status") != "ok":
            deps.repo.save_task_memory("coder", task_id, tool, "error", str(r.get("error")))
            return False
    return True
