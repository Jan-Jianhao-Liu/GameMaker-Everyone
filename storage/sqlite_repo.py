"""SQLiteRepo：Phase 1-2 默认实现。

表结构：
- task_memory(id, ts, agent, task_id, action, outcome, lesson)  智能体执行历史
- audit_log(id, ts, agent, tool, params_json, status)            审计日志
- asset_lock(asset_id PK, holder, acquired_at)                   资产互斥锁

并发模式：持久连接 + WAL + threading.Lock 串行化（同 gateway.RateLimiter/AuditDB）。
acquire_lock 用 INSERT OR IGNORE 原子抢锁，rowcount=0 即已被占。
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from storage.base import Repository

_SCHEMA = """
CREATE TABLE IF NOT EXISTS task_memory (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      TEXT    NOT NULL,
    agent   TEXT    NOT NULL,
    task_id TEXT    NOT NULL,
    action  TEXT    NOT NULL,
    outcome TEXT    NOT NULL,
    lesson  TEXT
);
CREATE INDEX IF NOT EXISTS idx_memory_task ON task_memory(task_id, id);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT    NOT NULL,
    agent       TEXT    NOT NULL,
    tool        TEXT    NOT NULL,
    params_json TEXT,
    status      TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_agent_ts ON audit_log(agent, id);

CREATE TABLE IF NOT EXISTS asset_lock (
    asset_id    TEXT    PRIMARY KEY,
    holder      TEXT    NOT NULL,
    acquired_at TEXT    NOT NULL
);
"""


class SQLiteRepo(Repository):
    """SQLite 持久化仓库。线程安全（单连接 + Lock 串行）。"""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._lock = threading.Lock()

    def save_task_memory(
        self, agent: str, task_id: str, action: str, outcome: str, lesson: str
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO task_memory (ts, agent, task_id, action, outcome, lesson) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (datetime.now().isoformat(), agent, task_id, action, outcome, lesson),
            )
            self._conn.commit()

    def query_task_memory(self, task_id: str) -> list[dict[str, Any]]:
        with self._lock:
            self._conn.row_factory = sqlite3.Row
            rows = self._conn.execute(
                "SELECT ts, agent, task_id, action, outcome, lesson "
                "FROM task_memory WHERE task_id=? ORDER BY id",
                (task_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def acquire_lock(self, asset_id: str, holder: str) -> bool:
        """原子抢锁。成功返回 True；已被占返回 False。"""
        with self._lock:
            cur = self._conn.execute(
                "INSERT OR IGNORE INTO asset_lock (asset_id, holder, acquired_at) "
                "VALUES (?, ?, ?)",
                (asset_id, holder, datetime.now().isoformat()),
            )
            self._conn.commit()
            return cur.rowcount == 1

    def release_lock(self, asset_id: str, holder: str) -> bool:
        """释放锁。仅持锁者能释放（防误释他人锁）。"""
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM asset_lock WHERE asset_id=? AND holder=?",
                (asset_id, holder),
            )
            self._conn.commit()
            return cur.rowcount == 1

    def log_audit(self, agent: str, tool: str, params: dict, status: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO audit_log (ts, agent, tool, params_json, status) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    datetime.now().isoformat(),
                    agent,
                    tool,
                    json.dumps(params, ensure_ascii=False, default=str)[:500],
                    status,
                ),
            )
            self._conn.commit()

    def query_audit(
        self, agent: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """审计查询（扩展方法，便于 supervisor 回溯）。"""
        with self._lock:
            self._conn.row_factory = sqlite3.Row
            if agent is None:
                rows = self._conn.execute(
                    "SELECT ts, agent, tool, params_json, status FROM audit_log "
                    "ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT ts, agent, tool, params_json, status FROM audit_log "
                    "WHERE agent=? ORDER BY id DESC LIMIT ?",
                    (agent, limit),
                ).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
