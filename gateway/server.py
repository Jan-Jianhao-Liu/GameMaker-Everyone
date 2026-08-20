"""MCP 网关入口：Gateway 核心类 + SQLite 审计 + 端口探测。

Gateway.call(role, api_key, tool, params) 流程：
鉴权 → 路由 → 沙箱 → 速率限制 → 转发 → 审计
越权/越界/超限均拒绝并记审计日志。
"""

from __future__ import annotations

import json
import socket
import sqlite3
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from gateway.auth import AuthError, RoleAuth
from gateway.rate_limit import RateLimiter
from gateway.router import ToolRouteError, route
from gateway.sandbox import Sandbox, SandboxError

_ROOT = Path(__file__).resolve().parents[1]


class AuditDB:
    """SQLite 审计表 + 查询 API。持久连接 + WAL + Lock。"""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS audit ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, "
            "role TEXT NOT NULL, tool TEXT NOT NULL, "
            "params TEXT, status TEXT NOT NULL, error TEXT)"
        )
        self._lock = threading.Lock()

    def log(
        self, role: str, tool: str, params: dict, status: str, error: str | None = None
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO audit (ts, role, tool, params, status, error) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    datetime.now().isoformat(),
                    role,
                    tool,
                    json.dumps(params, ensure_ascii=False, default=str)[:500],
                    status,
                    error,
                ),
            )
            self._conn.commit()

    def query(self, role: str | None = None, limit: int = 100) -> list[dict]:
        with self._lock:
            self._conn.row_factory = sqlite3.Row
            if role is None:
                rows = self._conn.execute(
                    "SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM audit WHERE role=? ORDER BY id DESC LIMIT ?",
                    (role, limit),
                ).fetchall()
        return [dict(r) for r in rows]


Forwarder = Callable[[str, str, dict[str, Any]], Any]


class Gateway:
    """MCP 网关核心：鉴权 · 路由 · 沙箱 · 速率限制 · 审计 · 转发。"""

    def __init__(
        self,
        auth: RoleAuth,
        sandbox: Sandbox,
        rate_limiter: RateLimiter,
        audit: AuditDB,
        forwarder: Forwarder,
    ) -> None:
        self._auth = auth
        self._sandbox = sandbox
        self._rate = rate_limiter
        self._audit = audit
        self._forward = forwarder

    def call(self, role: str, api_key: str, tool: str, params: dict[str, Any]) -> dict[str, Any]:
        """智能体调用入口。返回 {"status": "ok"/"error", ...}。"""
        try:
            self._auth.resolve_role(api_key)
        except AuthError as e:
            self._audit.log(role, tool, params, "rejected", str(e))
            return {"status": "error", "error": str(e)}
        try:
            self._auth.check_tool(role, tool)
            server = route(tool)
            self._sandbox.check_tool(tool, params)
            if not self._rate.acquire(role):
                raise SandboxError(f"速率超限: {role}")
        except (AuthError, ToolRouteError, SandboxError) as e:
            self._audit.log(role, tool, params, "rejected", str(e))
            return {"status": "error", "error": str(e)}
        try:
            result = self._forward(server, tool, params)
            self._audit.log(role, tool, params, "ok")
            return {"status": "ok", "result": result}
        except Exception as e:  # noqa: BLE001
            self._audit.log(role, tool, params, "error", str(e))
            return {"status": "error", "error": str(e)}


def check_port_available(port: int, host: str = "127.0.0.1") -> bool:
    """端口探测：被占用返回 False。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def read_ports(env_path: Path) -> dict[str, int]:
    """读 ports.env 全部端口。"""
    ports: dict[str, int] = {}
    if not env_path.exists():
        return ports
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        ports[k.strip()] = int(v.strip())
    return ports


def check_all_ports(env_path: Path = _ROOT / "infra" / "ports.env") -> list[str]:
    """启动时端口探测。返回被占用端口名列表（空则全部可用）。"""
    ports = read_ports(env_path)
    occupied: list[str] = []
    for name, port in ports.items():
        if not check_port_available(port):
            occupied.append(f"{name}={port}")
    return occupied
