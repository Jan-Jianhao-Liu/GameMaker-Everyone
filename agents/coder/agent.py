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

_BUILD_OUTPUT = "game/build/windows"


def make_coder_node(deps: AgentDeps) -> Callable[[AgentState], dict]:
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

        steps = [
            ("create_scene", {"scene_name": "Main", "template": "scene_3d"}),
            ("attach_script", {"node": "Player", "script_template": "character"}),
            ("set_level_data", {"levels": gdd.get("levels", [])}),
            ("build_export", {"platform": "windows", "output_path": _BUILD_OUTPUT}),
        ]
        for tool, params in steps:
            r = deps.gateway.call("coder", key, tool, params)
            if r.get("status") != "ok":
                deps.repo.save_task_memory("coder", task_id, tool, "error", str(r.get("error")))
                return {"errors": [f"{tool} 失败: {r.get('error')}"], "current_role": "coder"}

        deps.repo.save_task_memory("coder", task_id, "build", "ok", "构建完成（draft）")
        return {
            "build_result": {"path": _BUILD_OUTPUT, "status": "draft"},
            "current_role": "qa",
            "errors": [],
        }

    return coder_node
