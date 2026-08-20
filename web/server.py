"""FastAPI Web 后端：对话界面 + WebSocket 实时推送 + 流水线后台执行。

路由：
  GET  /                  → index.html
  GET  /static/{file}     → 静态资源
  WS   /ws                → WebSocket 对话端点
  GET  /api/sessions      → 会话列表
  GET  /api/health        → 健康检查

流水线在后台线程跑（graph.stream），事件通过 asyncio.run_coroutine_threadsafe
调度回 event loop 推送 WebSocket。
"""

from __future__ import annotations

import asyncio
import os
import threading
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from agents.common.deps import AgentDeps
from agents.orchestrator import build_graph_with_checkpointer, make_checkpointer
from web.events import (
    ServerEvent,
    checkpoint,
    complete,
    error_event,
    history,
    parse_client,
    progress,
    role_status,
)
from web.session import Session, SessionManager

_STATIC_DIR = Path(__file__).resolve().parent / "static"
_CHECKPOINT_DIR = Path(__file__).resolve().parents[1] / "logs" / "checkpoints"

_CHAT_PROMPT = """你是游戏开发团队的对话窗口。用户说：{text}

请简洁回复（2-3 句话）。如果用户描述了明确的游戏需求（如"做一个XX游戏"），
建议用户点击"启动开发"按钮触发流水线。如果用户在问技术问题，直接回答。"""

_ROLE_LABELS = {
    "designer": "策划", "supervisor": "监理", "artist3d": "3D美术",
    "artist2d": "2D美术", "coder": "程序", "qa": "测试",
}


def _run_pipeline_thread(
    session: Session,
    deps: AgentDeps,
    task_id: str,
    request: str,
    initial_state: dict[str, Any] | None = None,
) -> None:
    """在后台线程跑流水线，事件通过 session.emit 推送。"""
    session.pipeline_running = True
    session.current_task_id = task_id
    session.reset_roles()
    _CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    checkpoint_db = _CHECKPOINT_DIR / f"{task_id}.db"
    config: dict[str, Any] = {"configurable": {"thread_id": task_id}}
    state: dict[str, Any] = {
        "task_id": task_id, "user_request": request,
        "current_role": "designer", "status": "running",
        "retries": {}, "produced_assets": [], "defects": [], "errors": [],
    }
    if initial_state:
        state.update(initial_state)

    saver = make_checkpointer(checkpoint_db)
    try:
        graph = build_graph_with_checkpointer(deps, saver)
        final_state = dict(state)
        for chunk in graph.stream(state, config=config, stream_mode="updates"):
            for node, update in chunk.items():
                if update is None:
                    continue
                final_state.update(update)
                detail = _describe_update(update)
                status = update.get("status", "")
                errors = update.get("errors", [])
                if status not in ("paused_human", "failed") and not errors:
                    session.update_role(node, "done", "完成")
                    session.emit(role_status(node, "done", "完成"))
                elif errors and status != "paused_human":
                    session.update_role(node, "error", detail)
                    session.emit(role_status(node, "error", detail))
                next_role = update.get("current_role", node)
                if next_role != node and status not in ("paused_human", "failed"):
                    session.update_role(next_role, "working", "处理中")
                    session.emit(role_status(next_role, "working", "处理中"))
                session.emit(progress(node, update))
                if status == "paused_human":
                    session.emit(checkpoint(task_id, update.get("human_feedback", "")))
                    session.pipeline_running = False
                    return
                if status == "failed":
                    errs = errors or ["未知错误"]
                    session.emit(error_event(errs[0] if errs else "未知错误"))
                    session.pipeline_running = False
                    return
        session.emit(complete(task_id, _summarize(final_state)))
        for r in _ROLE_LABELS:
            session.update_role(r, "idle")
    except Exception as e:  # noqa: BLE001
        session.emit(error_event(f"流水线异常: {e}"))
    finally:
        try:
            saver.conn.close()
        except Exception:  # noqa: BLE001
            pass
        session.pipeline_running = False


def _describe_update(update: dict[str, Any]) -> str:
    if "gdd" in update:
        return "生成契约文档"
    if "produced_assets" in update and update["produced_assets"]:
        return f"生产 {len(update['produced_assets'])} 个资产"
    if "build_result" in update:
        return "构建完成"
    if "defects" in update and update["defects"]:
        return f"发现 {len(update['defects'])} 个缺陷"
    if "errors" in update and update["errors"]:
        return "校验失败"
    return "处理中"


def _role_statuses_from_update(update: dict[str, Any]) -> dict[str, tuple[str, str]]:
    """从节点更新推断角色状态变化。"""
    result: dict[str, tuple[str, str]] = {}
    role = update.get("current_role", "")
    if role:
        result[role] = ("working", _describe_update(update))
    return result


def _summarize(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "build_result": state.get("build_result", {}),
        "produced_assets": state.get("produced_assets", []),
        "defects": state.get("defects", []),
        "status": state.get("status", ""),
    }


def create_app(
    deps_factory: Callable[[], AgentDeps] | None = None,
) -> FastAPI:
    """构造 FastAPI 应用。

    Args:
        deps_factory: 智能体依赖工厂；None 则用默认构造（gaf.cli._build_default_deps）。
    """
    from gaf.cli import _build_default_deps

    app = FastAPI(title="game-agent-factory Web")
    manager = SessionManager()
    _deps_factory = deps_factory or _build_default_deps

    if _STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(str(_STATIC_DIR / "index.html"))

    @app.get("/api/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/api/sessions")
    async def list_sessions() -> dict:
        return {"sessions": manager.all_ids()}

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        loop = asyncio.get_event_loop()
        pending_checkpoints: dict[str, dict[str, Any]] = {}

        def emit(event: ServerEvent) -> None:
            asyncio.run_coroutine_threadsafe(
                websocket.send_json(event.to_dict()), loop
            )

        session = manager.create(emit)
        await websocket.send_json(history(session.history_dict()).to_dict())

        try:
            while True:
                raw = await websocket.receive_json()
                event = parse_client(raw)

                if event.type == "chat":
                    session.add_message("user", event.text)
                    await _handle_chat(session, event.text, _deps_factory, loop)

                elif event.type == "make_game":
                    session.add_message("user", f"🚀 启动开发：{event.request}")
                    task_id = f"task-{uuid.uuid4().hex[:8]}"
                    deps = _deps_factory()
                    t = threading.Thread(
                        target=_run_pipeline_thread,
                        args=(session, deps, task_id, event.request),
                        daemon=True,
                    )
                    t.start()
                    session.reply(f"已启动任务 {task_id}，智能体团队开始工作...")

                elif event.type == "checkpoint_response":
                    tid = event.task_id
                    if event.accept:
                        initial = pending_checkpoints.pop(tid, {})
                        if event.feedback:
                            initial["human_feedback"] = event.feedback
                        deps = _deps_factory()
                        t = threading.Thread(
                            target=_resume_pipeline_thread,
                            args=(session, deps, tid, initial),
                            daemon=True,
                        )
                        t.start()
                        session.reply("已确认，继续执行...")
                    else:
                        session.reply(f"已拒绝。反馈：{event.feedback or '无'}")

                elif event.type == "resume":
                    deps = _deps_factory()
                    t = threading.Thread(
                        target=_resume_pipeline_thread,
                        args=(session, deps, event.task_id, {}),
                        daemon=True,
                    )
                    t.start()
                    session.reply(f"恢复任务 {event.task_id}...")

                elif event.type == "set_config":
                    if event.api_key:
                        os.environ["LLM_CLOUD_API_KEY"] = event.api_key
                    if event.cloud_provider:
                        os.environ["LLM_CLOUD_PROVIDER"] = event.cloud_provider
                    if event.base_url:
                        os.environ["LLM_CLOUD_BASE_URL"] = event.base_url
                    from web.events import config_saved

                    session.emit(config_saved(
                        api_key_set=bool(os.getenv("LLM_CLOUD_API_KEY")),
                        cloud_provider=os.getenv("LLM_CLOUD_PROVIDER", ""),
                    ))
                    session.reply(
                        f"配置已保存（服务商: {event.cloud_provider or '未变'}, "
                        f"API Key: {'已设置' if event.api_key else '未变'}）"
                    )

                elif event.type == "test_connection":
                    await _handle_test_connection(session, event)

                elif event.type == "get_ollama_status":
                    await _handle_ollama_status(session)

        except WebSocketDisconnect:
            pass

    return app


async def _handle_test_connection(session: Session, event: Any) -> None:
    """测试云端 API 连接：调 /models 端点。"""
    import httpx

    from web.events import connection_test_result

    base_url = event.base_url.rstrip("/")
    api_key = event.api_key
    provider_id = event.provider_id or "custom"
    try:
        resp = await asyncio.to_thread(
            lambda: httpx.get(
                f"{base_url}/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10.0,
            )
        )
        if resp.status_code == 200:
            models = [m.get("id", "") for m in resp.json().get("data", [])]
            session.emit(connection_test_result(provider_id, True, models))
        else:
            session.emit(connection_test_result(
                provider_id, False, error=f"HTTP {resp.status_code}"
            ))
    except Exception as e:  # noqa: BLE001
        session.emit(connection_test_result(provider_id, False, error=str(e)))


async def _handle_ollama_status(session: Session) -> None:
    """查询本地 Ollama 状态。"""
    import socket

    from web.events import ollama_status

    port = int(os.getenv("OLLAMA_PORT", "11434"))
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            pass
        import subprocess

        result = await asyncio.to_thread(
            lambda: subprocess.run(
                ["ollama", "list"], capture_output=True, text=True, timeout=5
            )
        )
        if result.returncode == 0:
            lines = [ln.strip() for ln in result.stdout.strip().split("\n") if ln.strip()]
            models = [ln.split()[0] for ln in lines[1:] if ln] if len(lines) > 1 else []
            session.emit(ollama_status(True, models))
        else:
            session.emit(ollama_status(True, []))
    except (OSError, ConnectionRefusedError):
        session.emit(ollama_status(False))


async def _handle_chat(
    session: Session,
    text: str,
    deps_factory: Callable[[], AgentDeps],
    loop: asyncio.AbstractEventLoop,
) -> None:
    """处理自由对话：调 LLM 生成团队回复。"""
    deps = deps_factory()
    try:
        reply = await asyncio.to_thread(
            deps.llm.chat,
            "designer",
            [{"role": "user", "content": _CHAT_PROMPT.format(text=text)}],
        )
    except Exception as e:  # noqa: BLE001
        reply = f"（团队暂时无法回复：{e}。你可以直接点击「启动开发」按钮触发流水线。）"
    session.reply(reply)


def _resume_pipeline_thread(
    session: Session,
    deps: AgentDeps,
    task_id: str,
    initial_state: dict[str, Any],
) -> None:
    """恢复中断的流水线。"""
    session.pipeline_running = True
    checkpoint_db = _CHECKPOINT_DIR / f"{task_id}.db"
    config: dict[str, Any] = {"configurable": {"thread_id": task_id}}
    saver = make_checkpointer(checkpoint_db)
    try:
        graph = build_graph_with_checkpointer(deps, saver)
        resume_input = {"status": "running"}
        if initial_state:
            resume_input.update(initial_state)
        final = graph.invoke(resume_input, config=config)
        status = final.get("status", "") if isinstance(final, dict) else ""
        if status == "paused_human":
            session.emit(checkpoint(task_id, final.get("human_feedback", "")))
        else:
            session.emit(complete(task_id, _summarize(final if isinstance(final, dict) else {})))
    except Exception as e:  # noqa: BLE001
        session.emit(error_event(f"恢复异常: {e}"))
    finally:
        try:
            saver.conn.close()
        except Exception:  # noqa: BLE001
            pass
        session.pipeline_running = False


app = create_app()
