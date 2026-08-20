"""速率限制：SQLite 计数表，每角色每分钟最大调用数。

用持久连接 + WAL + threading.Lock 串行化，避免 BEGIN IMMEDIATE 重试开销。
防死循环刷爆 Blender（如智能体重试风暴）。
"""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path


class RateLimiter:
    """每角色每分钟速率限制。"""

    def __init__(self, db_path: Path, limit_per_minute: int = 60) -> None:
        self.db_path = db_path
        self.limit = limit_per_minute
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS rate_log (role TEXT NOT NULL, ts REAL NOT NULL)"
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_rate_role_ts ON rate_log(role, ts)")
        self._lock = threading.Lock()

    def acquire(self, role: str) -> bool:
        """检查并记录一次调用。超限返回 False。"""
        now = time.time()
        cutoff = now - 60.0
        with self._lock:
            count = self._conn.execute(
                "SELECT COUNT(*) FROM rate_log WHERE role=? AND ts>=?",
                (role, cutoff),
            ).fetchone()[0]
            if count >= self.limit:
                return False
            self._conn.execute("INSERT INTO rate_log (role, ts) VALUES (?, ?)", (role, now))
            self._conn.commit()
            return True

    def reset(self, role: str | None = None) -> None:
        """重置计数（测试用）。"""
        with self._lock:
            if role is None:
                self._conn.execute("DELETE FROM rate_log")
            else:
                self._conn.execute("DELETE FROM rate_log WHERE role=?", (role,))
            self._conn.commit()
