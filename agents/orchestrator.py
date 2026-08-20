"""LangGraph 编排器：五角色流水线。

图结构：
  START → designer → route
  supervisor / artist3d / artist2d / coder / qa → route（条件边）

route 根据 state.current_role 路由到对应节点；
status == paused_human / completed / failed → END（人工卡点暂停或终态）。

--resume 由 SqliteSaver checkpointer 承担（按 thread_id = task_id 恢复）。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from agents.artist2d.agent import make_artist2d_node
from agents.artist3d.agent import make_artist3d_node
from agents.coder.agent import make_coder_node
from agents.common.deps import AgentDeps
from agents.common.state import AgentState
from agents.designer.agent import make_designer_node
from agents.qa.agent import make_qa_node
from agents.supervisor.agent import make_supervisor_node

_NODE_NAMES = {"designer", "supervisor", "artist3d", "artist2d", "coder", "qa"}
_TERMINAL_STATUSES = {"paused_human", "completed", "failed"}


def _route(state: AgentState) -> str:
    """条件边路由函数。返回下一节点名或 END。"""
    if state.get("status") in _TERMINAL_STATUSES:
        return END
    role = state.get("current_role", "")
    if role in _NODE_NAMES:
        return role
    return END


def build_graph(deps: AgentDeps) -> Any:
    """构造编译后的 StateGraph。

    所有节点通过 deps 注入依赖，便于测试替换 mock。
    """
    graph = StateGraph(AgentState)
    graph.add_node("designer", make_designer_node(deps))
    graph.add_node("supervisor", make_supervisor_node(deps))
    graph.add_node("artist3d", make_artist3d_node(deps))
    graph.add_node("artist2d", make_artist2d_node(deps))
    graph.add_node("coder", make_coder_node(deps))
    graph.add_node("qa", make_qa_node(deps))

    graph.add_edge(START, "designer")
    for node in _NODE_NAMES:
        graph.add_conditional_edges(node, _route)
    return graph.compile()


def make_checkpointer(db_path: Path) -> SqliteSaver:
    """构造 SQLite checkpointer（--resume 用）。"""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    return SqliteSaver(conn)


def run_pipeline(
    deps: AgentDeps,
    task_id: str,
    user_request: str,
    checkpoint_db: Path | None = None,
    initial_state: dict[str, Any] | None = None,
) -> AgentState:
    """运行流水线。

    Args:
        deps: 智能体依赖
        task_id: 任务 ID（对应 LangGraph thread_id，--resume 按此恢复）
        user_request: 用户需求文本
        checkpoint_db: checkpointer 数据库路径；None 则不用 checkpointer
        initial_state: 恢复时注入的初始状态增量（如金样本确认后填入 gold_samples）

    Returns:
        最终状态。
    """
    graph = build_graph(deps)
    config = {"configurable": {"thread_id": task_id}}
    state: AgentState = {
        "task_id": task_id,
        "user_request": user_request,
        "current_role": "designer",
        "status": "running",
        "retries": {},
        "produced_assets": [],
        "defects": [],
        "errors": [],
    }
    if initial_state:
        state.update(initial_state)

    if checkpoint_db is not None:
        saver = make_checkpointer(checkpoint_db)
        try:
            graph_checkpointed = build_graph_with_checkpointer(deps, saver)
            return graph_checkpointed.invoke(state, config=config)
        finally:
            saver.conn.close()
    return graph.invoke(state, config=config)


def build_graph_with_checkpointer(deps: AgentDeps, checkpointer: Any) -> Any:
    """构造带 checkpointer 的编译图（--resume 用）。"""
    graph = StateGraph(AgentState)
    graph.add_node("designer", make_designer_node(deps))
    graph.add_node("supervisor", make_supervisor_node(deps))
    graph.add_node("artist3d", make_artist3d_node(deps))
    graph.add_node("artist2d", make_artist2d_node(deps))
    graph.add_node("coder", make_coder_node(deps))
    graph.add_node("qa", make_qa_node(deps))

    graph.add_edge(START, "designer")
    for node in _NODE_NAMES:
        graph.add_conditional_edges(node, _route)
    return graph.compile(checkpointer=checkpointer)


def resume_pipeline(
    deps: AgentDeps,
    task_id: str,
    checkpoint_db: Path,
    initial_state: dict[str, Any] | None = None,
) -> AgentState:
    """从 checkpointer 恢复流水线（--resume）。

    Args:
        deps: 智能体依赖
        task_id: 要恢复的任务 ID
        checkpoint_db: checkpointer 数据库路径
        initial_state: 注入的状态增量（如人工确认后的 gold_samples / human_feedback）
    """
    config = {"configurable": {"thread_id": task_id}}
    saver = make_checkpointer(checkpoint_db)
    try:
        graph = build_graph_with_checkpointer(deps, saver)
        resume_input = {"status": "running"}
        if initial_state:
            resume_input.update(initial_state)
        return graph.invoke(resume_input, config=config)
    finally:
        saver.conn.close()
