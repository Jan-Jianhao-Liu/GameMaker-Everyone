"""artist2d（2D 美术）子图。

从 manifest 领取 type in (texture, ui) 且未生产的资产，
经网关调用 krita-mcp 生产：create_canvas → fill_layer →
export_png → validate_export → commit_asset。

金样本卡点：首个 texture 资产须人工确认。
"""

from __future__ import annotations

from collections.abc import Callable

from agents.common.deps import AgentDeps
from agents.common.state import AgentState
from agents.common.task_lock import AssetLock, LockError
from agents.team_config import RoleConfig
from plugins.executor import ChainExecutor

_2D_TYPES = ("texture", "ui")
_OUTPUT_DIR = "game/assets/textures"


def _pending_2d(state: AgentState) -> list[dict]:
    manifest = state.get("manifest", {})
    produced_ids = {a["asset_id"] for a in state.get("produced_assets", [])}
    return [
        a
        for a in manifest.get("assets", [])
        if a.get("type") in _2D_TYPES and a["asset_id"] not in produced_ids
    ]


def _produce_one(
    deps: AgentDeps, asset: dict, task_id: str, role_config: RoleConfig | None = None,
) -> dict | None:
    asset_id = asset["asset_id"]
    key = deps.key_for("artist2d")
    is_ui = asset.get("type") == "ui"
    size = 32 if is_ui else 256
    out_path = f"{_OUTPUT_DIR}/{asset_id}.png"

    try:
        with AssetLock(deps.repo, asset_id, "artist2d"):
            if not _run_produce_chain(deps, asset_id, out_path, size, key, task_id, role_config):
                return None
            if not _commit_asset(deps, asset_id, out_path, key, task_id):
                return None
            deps.repo.save_task_memory(
                "artist2d", task_id, "produce", "ok", f"{asset_id} 生产完成"
            )
            return {
                "asset_id": asset_id, "type": asset.get("type"),
                "path": out_path, "producer": "artist2d",
            }
    except LockError as e:
        deps.repo.save_task_memory("artist2d", task_id, "lock", "error", str(e))
        return None


def _run_produce_chain(
    deps: AgentDeps, asset_id: str, out_path: str, size: int, key: str, task_id: str,
    role_config: RoleConfig | None,
) -> bool:
    """执行生产步骤（不含 commit）。优先插件链，回退硬编码。"""
    if deps.plugins is not None and role_config and role_config.plugin and role_config.chain:
        executor = ChainExecutor()
        r = executor.execute(
            deps.plugins, role_config.plugin, role_config.chain,
            "artist2d", key, deps.gateway,
            {"asset_id": asset_id, "out_path": out_path, "width": size, "height": size},
        )
        if r["status"] != "ok":
            deps.repo.save_task_memory(
                "artist2d", task_id, r.get("tool", "produce"), "error",
                f"{asset_id}: {r['error']}",
            )
            return False
        return True

    steps = [
        ("create_canvas", {
            "width": size, "height": size, "dpi": 72, "color_space": "RGBA8",
        }),
        ("fill_layer", {"layer_name": "background", "color": [200, 200, 200, 255]}),
        ("export_png", {"asset_id": asset_id, "path": out_path}),
        ("validate_export", {"path": out_path}),
    ]
    for tool, params in steps:
        r = deps.gateway.call("artist2d", key, tool, params)
        if r.get("status") != "ok":
            deps.repo.save_task_memory(
                "artist2d", task_id, tool, "error", f"{asset_id}: {r.get('error')}"
            )
            return False
    return True


def _commit_asset(
    deps: AgentDeps, asset_id: str, out_path: str, key: str, task_id: str,
) -> bool:
    r = deps.gateway.call("artist2d", key, "commit_asset", {
        "asset_id": asset_id, "file_paths": [out_path],
        "message": f"2D 资产 {asset_id} 入库",
    })
    if r.get("status") != "ok":
        deps.repo.save_task_memory(
            "artist2d", task_id, "commit_asset", "error", f"{asset_id}: {r.get('error')}"
        )
        return False
    return True


def make_artist2d_node(
    deps: AgentDeps, role_config: RoleConfig | None = None,
) -> Callable[[AgentState], dict]:
    """构造 artist2d 节点函数。"""

    def artist2d_node(state: AgentState) -> dict:
        task_id = state.get("task_id", "unknown")
        pending = _pending_2d(state)
        if not pending:
            return {"current_role": "coder"}

        gold = dict(state.get("gold_samples", {}))
        if "texture" not in gold:
            asset_id = pending[0]["asset_id"]
            gold["texture"] = asset_id
            return {
                "gold_samples": gold,
                "status": "paused_human",
                "current_role": "artist2d",
                "human_feedback": (
                    f"2D美术即将开始生产贴图资产。第一个贴图「{asset_id}」将作为"
                    "金样本（质量基准样本）。\n\n"
                    "请确认是否开始生产：\n"
                    "  • 点「确认」→ 以此为基准，自动批量生产所有贴图资产\n"
                    "  • 点「拒绝」→ 退回修改需求或规范"
                ),
            }

        produced: list[dict] = []
        for asset in pending:
            result = _produce_one(deps, asset, task_id, role_config)
            if result is not None:
                produced.append(result)
        return {
            "produced_assets": produced,
            "current_role": "coder",
        }

    return artist2d_node
