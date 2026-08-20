"""完成后汇总：构建包路径 + 资产清单表格 + 缺陷报告摘要。"""

from __future__ import annotations

from typing import Any

from agents.common.state import AgentState


def summarize(state: AgentState, stream: Any = None) -> str:
    """输出汇总并返回汇总文本。"""
    from gaf.progress import _emit, error, success

    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("流水线完成")
    lines.append("=" * 60)

    build = state.get("build_result", {})
    if build:
        lines.append(f"构建包路径: {build.get('path', 'N/A')}")
        lines.append(f"构建状态:   {build.get('status', 'N/A')}")
    else:
        lines.append("构建包: 未产出")

    produced = state.get("produced_assets", [])
    if produced:
        lines.append("")
        lines.append(f"资产清单（{len(produced)} 项）:")
        lines.append(f"  {'asset_id':<30} {'type':<10} {'producer':<10} path")
        lines.append(f"  {'-' * 30} {'-' * 10} {'-' * 10} {'-' * 30}")
        for a in produced:
            lines.append(
                f"  {a.get('asset_id', ''):<30} {a.get('type', ''):<10} "
                f"{a.get('producer', ''):<10} {a.get('path', '')}"
            )

    defects = state.get("defects", [])
    if defects:
        lines.append("")
        lines.append(f"缺陷报告（{len(defects)} 项）:")
        for d in defects:
            lines.append(f"  - {d}")

    status = state.get("status", "")
    if status == "paused_human":
        lines.append("")
        lines.append(f"⚠ {state.get('human_feedback', '等待人工确认')}")
    elif status == "failed":
        lines.append("")
        for e in state.get("errors", []):
            lines.append(f"✗ {e}")

    text = "\n".join(lines)
    _emit(text, stream)
    if status == "failed":
        error("流水线失败", stream)
    else:
        success("汇总完成", stream)
    return text
