"""LangGraph 编排器：配置驱动的多角色流水线。

图结构由 config/team.json 动态构建：
  START → first_role → route（条件边按 current_role 路由）
  每个角色节点 → route

route 根据 state.current_role 路由到对应节点；
status == paused_human / completed / failed → END。

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
from agents.team_config import TeamConfig

_NODE_FACTORIES = {
    "designer": make_designer_node,
    "supervisor": make_supervisor_node,
    "artist3d": make_artist3d_node,
    "artist2d": make_artist2d_node,
    "coder": make_coder_node,
    "qa": make_qa_node,
}

_TERMINAL_STATUSES = {"paused_human", "completed", "failed"}


def _make_route(role_ids: set[str]):
    """构造条件边路由函数（闭包绑定角色集合）。"""

    def route(state: AgentState) -> str:
        if state.get("status") in _TERMINAL_STATUSES:
            return END
        role = state.get("current_role", "")
        if role in role_ids:
            return role
        return END

    return route


def _load_team(team_config: TeamConfig | None) -> TeamConfig:
    """加载团队配置：传入则用，否则加载默认。"""
    if team_config is not None:
        return team_config
    team = TeamConfig()
    team.load()
    return team


def _build_graph_impl(
    deps: AgentDeps, team: TeamConfig, checkpointer: Any = None,
) -> Any:
    """图构建核心逻辑（build_graph 和 build_graph_with_checkpointer 共用）。"""
    role_ids = set(team.ids())
    first = team.first_role()
    first_id = first.id if first else "designer"

    graph = StateGraph(AgentState)
    for role in team.roles():
        factory = _NODE_FACTORIES.get(role.id)
        if factory is None:
            continue
        graph.add_node(role.id, factory(deps))

    graph.add_edge(START, first_id)
    route = _make_route(role_ids)
    for role in team.roles():
        if _NODE_FACTORIES.get(role.id) is None:
            continue
        graph.add_conditional_edges(role.id, route)
    if checkpointer is not None:
        return graph.compile(checkpointer=checkpointer)
    return graph.compile()


def build_graph(deps: AgentDeps, team_config: TeamConfig | None = None) -> Any:
    """构造编译后的 StateGraph（配置驱动）。"""
    return _build_graph_impl(deps, _load_team(team_config))


def make_checkpointer(db_path: Path) -> SqliteSaver:
    """构造 SQLite checkpointer（--resume 用）。"""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    return SqliteSaver(conn)


def build_graph_with_checkpointer(
    deps: AgentDeps, checkpointer: Any, team_config: TeamConfig | None = None,
) -> Any:
    """构造带 checkpointer 的编译图（--resume 用，配置驱动）。"""
    return _build_graph_impl(deps, _load_team(team_config), checkpointer)


def run_pipeline(
    deps: AgentDeps,
    task_id: str,
    user_request: str,
    checkpoint_db: Path | None = None,
    initial_state: dict[str, Any] | None = None,
    team_config: TeamConfig | None = None,
) -> AgentState:
    """运行流水线。

    Args:
        deps: 智能体依赖
        task_id: 任务 ID（对应 LangGraph thread_id，--resume 按此恢复）
        user_request: 用户需求文本
        checkpoint_db: checkpointer 数据库路径；None 则不用 checkpointer
        initial_state: 恢复时注入的初始状态增量
        team_config: 团队配置；None 则从 config/team.json 加载默认
    """
    team = _load_team(team_config)
    first = team.first_role()
    first_id = first.id if first else "designer"
    config = {"configurable": {"thread_id": task_id}}
    state: AgentState = {
        "task_id": task_id,
        "user_request": user_request,
        "current_role": first_id,
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
            graph = build_graph_with_checkpointer(deps, saver, team)
            return graph.invoke(state, config=config)
        finally:
            saver.conn.close()
    graph = build_graph(deps, team)
    return graph.invoke(state, config=config)


def resume_pipeline(
    deps: AgentDeps,
    task_id: str,
    checkpoint_db: Path,
    initial_state: dict[str, Any] | None = None,
    team_config: TeamConfig | None = None,
) -> AgentState:
    """从 checkpointer 恢复流水线（--resume）。"""
    config = {"configurable": {"thread_id": task_id}}
    saver = make_checkpointer(checkpoint_db)
    try:
        graph = build_graph_with_checkpointer(deps, saver, team_config)
        resume_input = {"status": "running"}
        if initial_state:
            resume_input.update(initial_state)
        return graph.invoke(resume_input, config=config)
    finally:
        saver.conn.close()
