"""qa（测试）子图。

调用 godot-mcp run_headless_test 或 godot-ai editor_screenshot + logs_read，
收集报错与截图，产出缺陷报告。
- 有缺陷 → current_role = "coder" 退回（defects 累加）
- 无缺陷 → status = "paused_human"（发布确认卡点），人工确认后转 release
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agents.common.deps import AgentDeps
from agents.common.state import AgentState
from agents.common.thought_bus import get_bus
from agents.team_config import RoleConfig
from plugins.executor import ChainExecutor


def make_qa_node(
    deps: AgentDeps, role_config: RoleConfig | None = None,
) -> Callable[[AgentState], dict]:
    """构造 qa 节点函数。"""

    def qa_node(state: AgentState) -> dict:
        bus = get_bus()
        task_id = state.get("task_id", "unknown")
        key = deps.key_for("qa")
        build = state.get("build_result", {})
        build_path = build.get("path", "")

        use_godot_ai = _has_godot_ai(deps)
        if bus:
            mode = "godot-ai 视觉验证" if use_godot_ai else "无头测试"
            bus.think("qa", f"测试构建包: {build_path}（{mode}）")

        if use_godot_ai:
            ok, result = _run_visual_test(deps, key, bus)
        else:
            ok, result = _run_test(deps, build_path, key, role_config)
        if not ok:
            if bus:
                bus.error("qa", f"测试执行失败: {result}")
            deps.repo.save_task_memory("qa", task_id, "test", "error", str(result))
            return {"errors": [f"测试执行失败: {result}"], "current_role": "qa"}

        defects = result.get("defects", [])
        if bus:
            bus.result("qa", f"测试完成，发现 {len(defects)} 个缺陷")
        deps.repo.save_task_memory(
            "qa", task_id, "test", "ok" if not defects else "fail", f"发现 {len(defects)} 个缺陷"
        )

        if defects:
            if bus:
                bus.act("qa", f"退回 coder 修复 {len(defects)} 个缺陷")
            return {"defects": defects, "current_role": "coder"}

        build = dict(state.get("build_result", {}))
        if build.get("status") == "pending_release":
            build["status"] = "release"
            if bus:
                bus.result("qa", "构建包已发布（release）")
            deps.repo.save_task_memory("qa", task_id, "release", "ok", "已发布")
            return {"build_result": build, "status": "completed", "current_role": "qa"}

        build["status"] = "pending_release"
        if bus:
            bus.act("qa", "测试通过，等待发布确认")
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


def _has_godot_ai(deps: AgentDeps) -> bool:
    """检查 godot-ai 插件是否已加载。"""
    if deps.plugins is None:
        return False
    return deps.plugins.get("godot_ai") is not None


def _run_visual_test(
    deps: AgentDeps, key: str, bus: Any,
) -> tuple[bool, dict]:
    """使用 godot-ai editor_screenshot + logs_read 做视觉验证。"""
    gw = deps.gateway
    defects: list[dict] = []

    if bus:
        bus.act("qa", "editor_screenshot: 3D 视口截图")
    r = gw.call("qa", key, "editor_screenshot", {"viewport": "3d"})
    if r.get("status") != "ok":
        return False, {"error": r.get("error", "截图失败")}
    screenshot = r.get("result", {})
    if bus:
        bus.result("qa", f"截图完成: {screenshot.get('path', 'unknown')}")

    if bus:
        bus.act("qa", "logs_read: 读取错误日志")
    r = gw.call("qa", key, "logs_read", {"level": "error"})
    if r.get("status") != "ok":
        return False, {"error": r.get("error", "日志读取失败")}
    log_result = r.get("result", {})
    error_logs = log_result.get("logs", [])
    if error_logs:
        for log_entry in error_logs:
            defects.append({
                "type": "error_log",
                "message": log_entry if isinstance(log_entry, str) else str(log_entry),
                "severity": "high",
            })

    if bus:
        bus.act("qa", "scene_get_hierarchy: 验证场景结构")
    r = gw.call("qa", key, "scene_get_hierarchy", {})
    if r.get("status") == "ok":
        hierarchy = r.get("result", {})
        nodes = hierarchy.get("nodes", [])
        node_names = [n.get("name", "") for n in nodes] if isinstance(nodes, list) else []
        if not node_names:
            defects.append({
                "type": "empty_scene",
                "message": "场景为空或无节点",
                "severity": "high",
            })
        elif "Player" not in node_names:
            defects.append({
                "type": "missing_player",
                "message": "场景缺少 Player 节点",
                "severity": "high",
            })

    return True, {"defects": defects, "screenshot": screenshot}


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
