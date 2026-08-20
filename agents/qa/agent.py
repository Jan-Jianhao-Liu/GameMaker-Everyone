"""qa（测试）子图。

调用 godot-mcp run_headless_test，收集报错与截图，产出缺陷报告。
- 有缺陷 → current_role = "coder" 退回（defects 累加）
- 无缺陷 → status = "paused_human"（发布确认卡点），人工确认后转 release
"""

from __future__ import annotations

from collections.abc import Callable

from agents.common.deps import AgentDeps
from agents.common.state import AgentState
from agents.team_config import RoleConfig
from plugins.executor import ChainExecutor


def make_qa_node(
    deps: AgentDeps, role_config: RoleConfig | None = None,
) -> Callable[[AgentState], dict]:
    """构造 qa 节点函数。"""

    def qa_node(state: AgentState) -> dict:
        task_id = state.get("task_id", "unknown")
        key = deps.key_for("qa")
        build = state.get("build_result", {})
        build_path = build.get("path", "")

        ok, result = _run_test(deps, build_path, key, role_config)
        if not ok:
            deps.repo.save_task_memory("qa", task_id, "test", "error", str(result))
            return {"errors": [f"测试执行失败: {result}"], "current_role": "qa"}

        defects = result.get("defects", [])
        deps.repo.save_task_memory(
            "qa", task_id, "test", "ok" if not defects else "fail", f"发现 {len(defects)} 个缺陷"
        )

        if defects:
            return {"defects": defects, "current_role": "coder"}

        build = dict(state.get("build_result", {}))
        if build.get("status") == "pending_release":
            build["status"] = "release"
            deps.repo.save_task_memory("qa", task_id, "release", "ok", "已发布")
            return {"build_result": build, "status": "completed", "current_role": "qa"}

        build["status"] = "pending_release"
        return {
            "build_result": build,
            "defects": [],
            "status": "paused_human",
            "human_feedback": (
                f"构建包 {build_path} 测试通过，待确认发布（draft → release）。\n\n"
                "请确认是否发布：\n"
                "  • 点「确认」→ 构建包转为 release 状态，流水线完成\n"
                "  • 点「拒绝」→ 退回修改"
            ),
        }

    return qa_node


def _run_test(
    deps: AgentDeps, build_path: str, key: str,
    role_config: RoleConfig | None,
) -> tuple[bool, dict]:
    """执行测试。优先插件链，回退硬编码。返回 (ok, result_dict)。"""
    if deps.plugins is not None and role_config and role_config.plugin and role_config.chain:
        executor = ChainExecutor()
        r = executor.execute(
            deps.plugins, role_config.plugin, role_config.chain,
            "qa", key, deps.gateway,
            {"build_path": build_path},
        )
        if r["status"] == "ok":
            return True, r.get("result", {})
        return False, {"error": r.get("error", "")}

    r = deps.gateway.call("qa", key, "run_headless_test", {"build_path": build_path})
    if r.get("status") == "ok":
        return True, r.get("result", {})
    return False, {"error": r.get("error", "")}
