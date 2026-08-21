"""supervisor（监理）子图。

调用 contracts/validators.py 校验三份契约合规性：
- validate_gdd
- validate_asset_manifest + validate_no_circular_deps（Kahn 检环）
- validate_art_spec

不合规 → 退回 designer 重做，retries["designer"] += 1。
连续 max_retries 轮不通过 → status = "paused_human"（4 个人工卡点之一）。
全部通过 → current_role = "artist3d"（按拓扑序开始生产）。
"""

from __future__ import annotations

from collections.abc import Callable

from jsonschema import ValidationError

from agents.common.deps import AgentDeps
from agents.common.questioning import check_question
from agents.common.state import AgentState
from agents.common.thought_bus import get_bus
from agents.team_config import RoleConfig
from contracts.validators import (
    CircularDependencyError,
    validate_art_spec,
    validate_asset_manifest,
    validate_gdd,
    validate_no_circular_deps,
)


def _validate_all(state: AgentState) -> list[str]:
    """校验三份契约，返回错误信息列表（空表示全部通过）。"""
    errors: list[str] = []
    try:
        validate_gdd(state.get("gdd", {}))
    except ValidationError as e:
        errors.append(f"GDD 不合规: {e.message}")
    try:
        manifest = state.get("manifest", {})
        validate_asset_manifest(manifest)
        validate_no_circular_deps(manifest)
    except ValidationError as e:
        errors.append(f"资产清单不合规: {e.message}")
    except CircularDependencyError as e:
        errors.append(str(e))
    try:
        validate_art_spec(state.get("art_spec", {}))
    except ValidationError as e:
        errors.append(f"美术规范不合规: {e.message}")
    return errors


def make_supervisor_node(
    deps: AgentDeps, role_config: RoleConfig | None = None,
) -> Callable[[AgentState], dict]:
    """构造 supervisor 节点函数。"""

    def supervisor_node(state: AgentState) -> dict:
        bus = get_bus()
        task_id = state.get("task_id", "unknown")
        if bus:
            bus.think("supervisor", "审查三份契约文档...")
        errors = _validate_all(state)
        retries = dict(state.get("retries", {}))

        if not errors:
            if bus:
                bus.result("supervisor", "三份契约全部通过，进入资产生产")
            deps.repo.save_task_memory(
                "supervisor", task_id, "review_contracts", "ok", "三份契约全部通过"
            )
            return {
                "errors": [],
                "current_role": "artist3d",
                "retries": retries,
            }

        if bus:
            bus.think("supervisor", f"发现 {len(errors)} 个问题", errors=errors[:3])

        answered = state.get("answered_questions", [])
        asked_roles = {q.get("role") for q in answered}
        if bus and "supervisor" not in asked_roles:
            q = check_question("supervisor", state)
            if q is not None:
                if bus:
                    bus.think("supervisor", "契约冲突严重，向用户追问...")
                return {
                    "status": "paused_question",
                    "pause_type": "question",
                    "current_role": "supervisor",
                    "pending_question": q.to_dict(),
                    "human_feedback": q.question,
                }

        count = retries.get("designer", 0) + 1
        retries["designer"] = count
        if bus:
            bus.act("supervisor", f"退回 designer 重做（第 {count} 轮）")
        deps.repo.save_task_memory(
            "supervisor",
            task_id,
            "review_contracts",
            "reject",
            f"第 {count} 轮退回 designer: {errors}",
        )
        if count >= deps.max_retries:
            error_lines = "\n".join(f"  • {e}" for e in errors)
            if bus:
                bus.error("supervisor", f"designer 连续 {count} 轮不通过，转人工")
            return {
                "errors": errors,
                "retries": retries,
                "current_role": "supervisor",
                "status": "paused_human",
                "human_feedback": f"designer 连续 {count} 轮不通过，转人工。错误：\n{error_lines}",
            }
        return {
            "errors": errors,
            "retries": retries,
            "current_role": "designer",
        }

    return supervisor_node
