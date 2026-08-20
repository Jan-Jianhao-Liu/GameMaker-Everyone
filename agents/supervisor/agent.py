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
from agents.common.state import AgentState
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


def make_supervisor_node(deps: AgentDeps) -> Callable[[AgentState], dict]:
    """构造 supervisor 节点函数。"""

    def supervisor_node(state: AgentState) -> dict:
        task_id = state.get("task_id", "unknown")
        errors = _validate_all(state)
        retries = dict(state.get("retries", {}))

        if not errors:
            deps.repo.save_task_memory(
                "supervisor", task_id, "review_contracts", "ok", "三份契约全部通过"
            )
            return {
                "errors": [],
                "current_role": "artist3d",
                "retries": retries,
            }

        count = retries.get("designer", 0) + 1
        retries["designer"] = count
        deps.repo.save_task_memory(
            "supervisor",
            task_id,
            "review_contracts",
            "reject",
            f"第 {count} 轮退回 designer: {errors}",
        )
        if count >= deps.max_retries:
            error_lines = "\n".join(f"  • {e}" for e in errors)
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
