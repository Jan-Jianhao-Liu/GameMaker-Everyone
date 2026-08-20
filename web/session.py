"""会话管理：对话历史 + 流水线状态 + 事件回调。

每个 WebSocket 连接对应一个 Session。Session 持有：
- 对话历史 messages（用户/团队消息）
- 当前流水线状态（task_id / running / paused）
- 事件回调 emit（推 ServerEvent 给前端）
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from typing import Any

from web.events import ServerEvent, team_reply

_ROLES = ("designer", "supervisor", "artist3d", "artist2d", "coder", "qa")


class Session:
    """单个 WebSocket 会话。"""

    def __init__(self, session_id: str, emit: Callable[[ServerEvent], None]) -> None:
        self.id = session_id
        self._emit = emit
        self.messages: list[dict[str, Any]] = []
        self.role_states: dict[str, dict[str, str]] = {
            r: {"status": "idle", "detail": ""} for r in _ROLES
        }
        self.current_task_id: str | None = None
        self.pipeline_running = False
        self._lock = threading.Lock()

    def add_message(self, role: str, text: str) -> None:
        """role: 'user' | 'team'。"""
        with self._lock:
            self.messages.append({"role": role, "text": text})

    def update_role(self, role: str, status: str, detail: str = "") -> None:
        with self._lock:
            if role in self.role_states:
                self.role_states[role] = {"status": status, "detail": detail}

    def reset_roles(self) -> None:
        with self._lock:
            for r in _ROLES:
                self.role_states[r] = {"status": "idle", "detail": ""}

    def emit(self, event: ServerEvent) -> None:
        self._emit(event)

    def reply(self, text: str) -> None:
        self.add_message("team", text)
        self.emit(team_reply(text))

    def history_dict(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self.messages)


class SessionManager:
    """多会话管理。"""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def create(self, emit: Callable[[ServerEvent], None]) -> Session:
        sid = f"sess-{uuid.uuid4().hex[:8]}"
        sess = Session(sid, emit)
        with self._lock:
            self._sessions[sid] = sess
        return sess

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            return self._sessions.get(session_id)

    def all_ids(self) -> list[str]:
        with self._lock:
            return list(self._sessions.keys())
