"""artist3d（3D 美术）子图。

从 manifest 领取 type=model 且未生产的资产（按拓扑序），
经网关调用 blender-mcp 生产：create_primitive → auto_uv → assign_material →
export_fbx → validate_export → commit_asset（git LFS）。

金样本卡点：第一个 model 资产须人工确认后成为金样本，
后续 model 由 supervisor 对照金样本自动校验。
"""

from __future__ import annotations

from collections.abc import Callable

from agents.common.deps import AgentDeps
from agents.common.questioning import check_question
from agents.common.state import AgentState
from agents.common.task_lock import AssetLock, LockError
from agents.common.thought_bus import get_bus
from agents.team_config import RoleConfig
from plugins.executor import ChainExecutor

_ASSET_TYPE = "model"
_OUTPUT_DIR = "game/assets/models"


def _pending_models(state: AgentState) -> list[dict]:
    """返回 manifest 中 type=model 且未在 produced_assets 里的资产。"""
    manifest = state.get("manifest", {})
    produced_ids = {a["asset_id"] for a in state.get("produced_assets", [])}
    return [
        a
        for a in manifest.get("assets", [])
        if a.get("type") == _ASSET_TYPE and a["asset_id"] not in produced_ids
    ]


def _produce_one(
    deps: AgentDeps, asset: dict, task_id: str, role_config: RoleConfig | None = None,
) -> dict | None:
    """生产单个 3D 资产。优先用插件工具链，回退硬编码。"""
    asset_id = asset["asset_id"]
    key = deps.key_for("artist3d")
    out_path = f"{_OUTPUT_DIR}/{asset_id}.fbx"

    try:
        with AssetLock(deps.repo, asset_id, "artist3d"):
            if not _run_produce_chain(deps, asset_id, out_path, key, task_id, role_config):
                return None
            if not _commit_asset(deps, asset_id, out_path, key, task_id):
                return None
            deps.repo.save_task_memory(
                "artist3d", task_id, "produce", "ok", f"{asset_id} 生产完成"
            )
            return {
                "asset_id": asset_id, "type": _ASSET_TYPE,
                "path": out_path, "producer": "artist3d",
            }
    except LockError as e:
        deps.repo.save_task_memory("artist3d", task_id, "lock", "error", str(e))
        return None


def _run_produce_chain(
    deps: AgentDeps, asset_id: str, out_path: str, key: str, task_id: str,
    role_config: RoleConfig | None,
) -> bool:
    """执行生产步骤（不含 commit）。优先插件链，回退硬编码。返回是否成功。"""
    if deps.plugins is not None and role_config and role_config.plugin and role_config.chain:
        executor = ChainExecutor()
        r = executor.execute(
            deps.plugins, role_config.plugin, role_config.chain,
            "artist3d", key, deps.gateway,
            {"asset_id": asset_id, "out_path": out_path},
        )
        if r["status"] != "ok":
            deps.repo.save_task_memory(
                "artist3d", task_id, r.get("tool", "produce"), "error",
                f"{asset_id}: {r['error']}",
            )
            return False
        return True

    steps = [
        ("create_primitive", {
            "prim_type": "CUBE", "name": asset_id, "dimensions": [1, 1, 1],
        }),
        ("auto_uv", {"asset_id": asset_id}),
        ("assign_material", {
            "asset_id": asset_id, "base_color": [0.8, 0.8, 0.8, 1],
            "roughness": 0.5, "metallic": 0.0,
        }),
        ("export_fbx", {"asset_id": asset_id, "path": out_path}),
        ("validate_export", {"path": out_path}),
    ]
    for tool, params in steps:
        r = deps.gateway.call("artist3d", key, tool, params)
        if r.get("status") != "ok":
            deps.repo.save_task_memory(
                "artist3d", task_id, tool, "error", f"{asset_id}: {r.get('error')}"
            )
            return False
    return True


def _commit_asset(
    deps: AgentDeps, asset_id: str, out_path: str, key: str, task_id: str,
) -> bool:
    """提交资产到 VCS（跨插件 git 操作）。"""
    r = deps.gateway.call("artist3d", key, "commit_asset", {
        "asset_id": asset_id, "file_paths": [out_path],
        "message": f"3D 资产 {asset_id} 入库",
    })
    if r.get("status") != "ok":
        deps.repo.save_task_memory(
            "artist3d", task_id, "commit_asset", "error", f"{asset_id}: {r.get('error')}"
        )
        return False
    return True


def make_artist3d_node(
    deps: AgentDeps, role_config: RoleConfig | None = None,
) -> Callable[[AgentState], dict]:
    """构造 artist3d 节点函数。"""

    def artist3d_node(state: AgentState) -> dict:
        bus = get_bus()
        task_id = state.get("task_id", "unknown")
        pending = _pending_models(state)
        if not pending:
            return {"current_role": "artist2d"}

        if bus:
            bus.think("artist3d", f"有 {len(pending)} 个模型资产待生产")

        answered = state.get("answered_questions", [])
        asked_roles = {q.get("role") for q in answered}
        if bus and "artist3d" not in asked_roles:
            q = check_question("artist3d", state)
            if q is not None:
                if bus:
                    bus.think("artist3d", "缺少美术风格指引，向用户追问...")
                return {
                    "status": "paused_question",
                    "pause_type": "question",
                    "current_role": "artist3d",
                    "pending_question": q.to_dict(),
                    "human_feedback": q.question,
                }

        gold = dict(state.get("gold_samples", {}))
        if _ASSET_TYPE not in gold:
            asset_id = pending[0]["asset_id"]
            gold[_ASSET_TYPE] = asset_id
            return {
                "gold_samples": gold,
                "status": "paused_human",
                "current_role": "artist3d",
                "human_feedback": (
                    f"3D美术即将开始生产模型资产。第一个模型「{asset_id}」将作为"
                    "金样本（质量基准样本）。\n\n"
                    "请确认是否开始生产：\n"
                    "  • 点「确认」→ 以此为基准，自动批量生产所有模型资产\n"
                    "  • 点「拒绝」→ 退回修改需求或规范"
                ),
            }

        produced: list[dict] = []
        for asset in pending:
            asset_id = asset["asset_id"]
            if bus:
                bus.act("artist3d", f"生产模型 {asset_id}")
            result = _produce_one(deps, asset, task_id, role_config)
            if result is not None:
                if bus:
                    bus.result("artist3d", f"{asset_id} 生产完成")
                produced.append(result)
            elif bus:
                bus.error("artist3d", f"{asset_id} 生产失败")
        next_role = "artist2d" if _has_pending_2d(state, produced) else "coder"
        if bus:
            bus.result("artist3d", f"共生产 {len(produced)} 个模型，转 {next_role}")
        return {
            "produced_assets": produced,
            "current_role": next_role,
        }

    return artist3d_node


def _has_pending_2d(state: AgentState, just_produced: list[dict]) -> bool:
    """判断是否还有 2D 资产待生产。"""
    manifest = state.get("manifest", {})
    produced_ids = {a["asset_id"] for a in state.get("produced_assets", [])}
    produced_ids |= {a["asset_id"] for a in just_produced}
    return any(
        a.get("type") in ("texture", "ui") and a["asset_id"] not in produced_ids
        for a in manifest.get("assets", [])
    )
