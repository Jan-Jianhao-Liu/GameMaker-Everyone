"""Prompt 9 Web 界面单元测试：事件协议 + 会话 + FastAPI 端点 + WebSocket。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from agents.common.deps import AgentDeps
from agents.common.llm import HybridLLM, LLMClient
from storage.sqlite_repo import SQLiteRepo
from web.events import (
    checkpoint,
    complete,
    error_event,
    history,
    parse_client,
    role_status,
    team_reply,
)
from web.server import create_app
from web.session import Session, SessionManager

# ---------- events ----------


def test_parse_client_chat():
    ev = parse_client({"type": "chat", "text": "你好"})
    assert ev.type == "chat"
    assert ev.text == "你好"


def test_parse_client_make_game():
    ev = parse_client({"type": "make_game", "request": "做一个塔防"})
    assert ev.type == "make_game"
    assert ev.request == "做一个塔防"


def test_parse_client_checkpoint_response():
    ev = parse_client({
        "type": "checkpoint_response", "task_id": "T1",
        "accept": False, "feedback": "改一下",
    })
    assert ev.task_id == "T1"
    assert ev.accept is False
    assert ev.feedback == "改一下"


def test_team_reply_to_dict():
    assert team_reply("hello").to_dict() == {"type": "team_reply", "text": "hello"}


def test_role_status_to_dict():
    ev = role_status("designer", "working", "生成中")
    expected = {"type": "role_status", "role": "designer", "status": "working", "detail": "生成中"}
    assert ev.to_dict() == expected


def test_checkpoint_to_dict():
    ev = checkpoint("T1", "确认金样本")
    assert ev.to_dict()["type"] == "checkpoint"
    assert ev.to_dict()["task_id"] == "T1"


def test_complete_to_dict():
    ev = complete("T1", {"status": "ok"})
    assert ev.to_dict()["summary"]["status"] == "ok"


def test_error_event_to_dict():
    assert error_event("boom").to_dict() == {"type": "error", "message": "boom"}


def test_history_to_dict():
    ev = history([{"role": "user", "text": "hi"}])
    assert ev.to_dict()["messages"][0]["text"] == "hi"


# ---------- session ----------


def test_session_manager_create():
    mgr = SessionManager()
    sess = mgr.create(lambda e: None)
    assert sess.id.startswith("sess-")
    assert mgr.get(sess.id) is sess


def test_session_add_message():
    sess = Session("s1", lambda e: None)
    sess.add_message("user", "hello")
    sess.add_message("team", "hi there")
    assert len(sess.history_dict()) == 2
    assert sess.history_dict()[0]["role"] == "user"


def test_session_update_role():
    sess = Session("s1", lambda e: None)
    sess.update_role("designer", "working", "生成契约")
    assert sess.role_states["designer"]["status"] == "working"
    assert sess.role_states["designer"]["detail"] == "生成契约"


def test_session_reset_roles():
    sess = Session("s1", lambda e: None)
    sess.update_role("coder", "working")
    sess.reset_roles()
    assert all(s["status"] == "idle" for s in sess.role_states.values())


def test_session_reply_emits():
    events: list = []
    sess = Session("s1", lambda e: events.append(e))
    sess.reply("团队回复")
    assert len(events) == 1
    assert events[0].to_dict()["text"] == "团队回复"
    assert sess.history_dict()[-1]["role"] == "team"


# ---------- FastAPI 端点 ----------


class _FakeLLM(LLMClient):
    def chat(self, model: str, messages: list[dict[str, str]], **kwargs) -> str:
        return "这是团队的模拟回复。"


def _mock_deps_factory() -> AgentDeps:
    repo = SQLiteRepo(Path(":memory:"))
    llm = HybridLLM(local_client=_FakeLLM(), cloud_client=_FakeLLM())
    gw = MagicMock()
    gw.call.return_value = {"status": "ok", "result": {}}
    return AgentDeps(
        llm=llm, gateway=gw, repo=repo,
        api_keys={r: f"k-{r}" for r in (
            "designer", "supervisor", "artist3d", "artist2d", "coder", "qa"
        )},
    )


@pytest.fixture()
def app():
    return create_app(deps_factory=_mock_deps_factory)


@pytest.fixture()
def client(app):
    return TestClient(app)


def test_health_endpoint(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_sessions_endpoint(client):
    r = client.get("/api/sessions")
    assert r.status_code == 200
    assert "sessions" in r.json()


def test_index_page(client):
    r = client.get("/")
    assert r.status_code == 200


# ---------- WebSocket ----------


def test_websocket_connect_and_history(client):
    with client.websocket_connect("/ws") as ws:
        data = ws.receive_json()
        assert data["type"] == "history"


def test_websocket_chat_receives_team_reply(client):
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()  # history
        ws.send_json({"type": "chat", "text": "你好"})
        received = False
        for _ in range(10):
            data = ws.receive_json()
            if data["type"] == "team_reply":
                assert "模拟回复" in data["text"]
                received = True
                break
        assert received, "未收到 team_reply"
