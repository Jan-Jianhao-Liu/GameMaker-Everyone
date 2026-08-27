"""gaf CLI：Prompt-to-Pipeline 入口。

用法：
  python -m gaf make-game "做一个跳跃游戏"
  python -m gaf make-game --resume <task_id>
  python -m gaf make-game "..." --api-key sk-xxx --cloud-provider glm

流程：意图解析 → GDD 草案展示 → 用户确认 → Prompt 5 五角色流水线 → 汇总。
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path
from typing import Any

from agents.common.deps import AgentDeps
from agents.common.hooks import HookEngine
from agents.common.llm import HybridLLM
from agents.orchestrator import build_graph, build_graph_with_checkpointer, make_checkpointer
from gateway.auth import RoleAuth
from gateway.http_forwarder import HttpMcpForwarder, MultiForwarder
from gateway.rate_limit import RateLimiter
from gateway.sandbox import Sandbox
from gateway.server import AuditDB, Gateway
from plugins.registry import PluginRegistry
from storage.sqlite_repo import SQLiteRepo

_ROOT = Path(__file__).resolve().parents[1]
_CHECKPOINT_DIR = _ROOT / "logs" / "checkpoints"
_REPO_DIR = _ROOT / "logs"

_ROLE_KEYS = {
    "designer": "key-designer",
    "supervisor": "key-supervisor",
    "artist3d": "key-artist3d",
    "artist2d": "key-artist2d",
    "coder": "key-coder",
    "qa": "key-qa",
}


def _build_default_deps(
    api_keys: dict[str, str] | None = None,
    forwarder: Any = None,
    effort: str = "high",
) -> AgentDeps:
    """构造默认 deps。forwarder 为 None 时用占位（实机由 Prompt 7 注入真实转发）。

    Args:
        effort: AI-effort 滑块 ("low"/"medium"/"high")，控制工具列表裁剪。
    """
    repo = SQLiteRepo(_REPO_DIR / "gaf.db")
    keys = api_keys or _ROLE_KEYS
    auth = RoleAuth({v: k for k, v in keys.items()}, effort=effort)
    sandbox = Sandbox([_ROOT / "game", _ROOT / "sandbox"])
    rate = RateLimiter(_REPO_DIR / "rate.db")
    audit = AuditDB(_REPO_DIR / "audit.db")

    registry = PluginRegistry()
    registry.load()

    hooks = HookEngine()
    hooks.add_post_tool(
        "audit_log", "*",
        lambda role, tool, params, result: None,
    )

    if forwarder is None:
        multi = MultiForwarder()

        godot_ai_plugin = registry.get("godot_ai")
        if godot_ai_plugin is not None:
            endpoint = godot_ai_plugin.config.get(
                "endpoint", "http://127.0.0.1:8001/mcp",
            )
            multi.register("godot_ai", HttpMcpForwarder(endpoint))

        def _stub_forwarder(server: str, tool: str, params: dict) -> dict:
            return {"status": "error", "error": f"forwarder 未配置（server={server}）"}

        multi.set_fallback(_stub_forwarder)
        gw_forwarder = multi.dispatch
    else:
        gw_forwarder = forwarder

    gw = Gateway(auth, sandbox, rate, audit, gw_forwarder, hooks=hooks)
    llm = HybridLLM()
    return AgentDeps(
        llm=llm, gateway=gw, repo=repo, api_keys=keys,
        plugins=registry, hooks=hooks, effort=effort,
    )


def _stream_pipeline(
    deps: AgentDeps,
    state: dict[str, Any],
    config: dict,
    checkpoint_db: Path | None = None,
    stream: Any = None,
) -> dict[str, Any]:
    """用 stream 模式跑流水线，逐节点输出进度。返回最终状态。"""
    from gaf.progress import checkpoint as ckpt_alert
    from gaf.progress import error as err_alert
    from gaf.progress import role_event

    def _process_chunk(chunk, final_state):
        for node, update in chunk.items():
            if update is None:
                continue
            role = update.get("current_role", node)
            role_event(role, f"节点 {node} 完成", str(update.keys()), stream)
            final_state.update(update)
            if update.get("status") == "paused_human":
                ckpt_alert(update.get("human_feedback", ""), stream)
            elif update.get("status") == "failed":
                err_alert(update.get("errors", ["未知错误"])[0], stream)

    final_state: dict[str, Any] = dict(state)
    if checkpoint_db is not None:
        saver = make_checkpointer(checkpoint_db)
        try:
            graph = build_graph_with_checkpointer(deps, saver)
            for chunk in graph.stream(state, config=config, stream_mode="updates"):
                _process_chunk(chunk, final_state)
        finally:
            saver.conn.close()
    else:
        graph = build_graph(deps)
        for chunk in graph.stream(state, config=config, stream_mode="updates"):
            _process_chunk(chunk, final_state)
    return final_state


def make_game(
    request: str,
    deps: AgentDeps | None = None,
    api_key: str | None = None,
    cloud_provider: str | None = None,
    resume_task_id: str | None = None,
    auto_confirm: bool = False,
    stream: Any = None,
    effort: str = "high",
) -> dict[str, Any]:
    """make-game 核心逻辑。

    Args:
        request: 用户需求文本（resume 模式可传空）
        deps: 智能体依赖；None 则用默认构造
        api_key: 云端 API key（覆盖环境变量）
        cloud_provider: glm/deepseek/qwen
        resume_task_id: 非空则从 checkpointer 恢复
        auto_confirm: 跳过用户确认（测试用）
        stream: 输出流（测试用）
        effort: AI-effort 滑块 ("low"/"medium"/"high")

    Returns:
        最终状态 dict。
    """
    from gaf import progress
    from gaf.intent import parse_intent, prompt_confirm
    from gaf.summary import summarize

    if api_key:
        os.environ["LLM_CLOUD_API_KEY"] = api_key
    if cloud_provider:
        os.environ["LLM_CLOUD_PROVIDER"] = cloud_provider

    deps = deps or _build_default_deps(effort=effort)
    _CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    if resume_task_id:
        progress.info(f"恢复任务 {resume_task_id}", stream)
        checkpoint_db = _CHECKPOINT_DIR / f"{resume_task_id}.db"
        config = {"configurable": {"thread_id": resume_task_id}}
        saver = make_checkpointer(checkpoint_db)
        try:
            graph = build_graph_with_checkpointer(deps, saver)
            final = graph.invoke(None, config=config)
        finally:
            saver.conn.close()
        summarize(final, stream)
        return final

    task_id = f"task-{uuid.uuid4().hex[:8]}"
    progress.info(f"启动新任务 {task_id}", stream)

    intent = parse_intent(deps.llm, request)
    progress.info("意图解析完成", stream)

    if not auto_confirm:
        if not prompt_confirm(intent, stream):
            progress.info("用户取消，退出", stream)
            return {"status": "cancelled", "task_id": task_id}

    state: dict[str, Any] = {
        "task_id": task_id,
        "user_request": request,
        "current_role": "designer",
        "status": "running",
        "retries": {},
        "produced_assets": [],
        "defects": [],
        "errors": [],
    }
    config = {"configurable": {"thread_id": task_id}}
    checkpoint_db = _CHECKPOINT_DIR / f"{task_id}.db"

    final = _stream_pipeline(deps, state, config, checkpoint_db, stream)
    summarize(final, stream)
    return final


def main(argv: list[str] | None = None) -> int:
    """CLI 主入口。返回退出码。"""
    parser = argparse.ArgumentParser(
        prog="gaf",
        description="game-agent-factory: 一句话启动游戏开发流水线",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    mk = sub.add_parser("make-game", help="启动游戏开发流水线")
    mk.add_argument("request", nargs="?", default="", help="游戏需求描述")
    mk.add_argument("--resume", dest="resume_task_id", help="恢复指定任务 ID")
    mk.add_argument("--api-key", dest="api_key", help="云端 LLM API key")
    mk.add_argument(
        "--cloud-provider", dest="cloud_provider",
        choices=["glm", "deepseek", "qwen"], help="云端 LLM 提供商",
    )
    mk.add_argument(
        "--effort", dest="effort",
        choices=["low", "medium", "high"], default="high",
        help="AI-effort 滑块: low=核心工具, medium=标准集, high=全部工具",
    )

    args = parser.parse_args(argv)

    if args.command == "make-game":
        if args.resume_task_id:
            make_game(
                request="",
                resume_task_id=args.resume_task_id,
                api_key=args.api_key,
                cloud_provider=args.cloud_provider,
                effort=args.effort,
            )
        elif args.request:
            make_game(
                request=args.request,
                api_key=args.api_key,
                cloud_provider=args.cloud_provider,
                effort=args.effort,
            )
        else:
            parser.error("make-game 需要需求文本或 --resume <task_id>")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
