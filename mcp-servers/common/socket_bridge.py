"""socket 桥共享模块：协议定义 + 客户端。

addon 端（Blender 内）是 socket 服务端，MCP Server 端是客户端。
bpy 非线程安全：addon 的 socket 监听线程只收指令入队，
bpy.app.timers 定时器在主线程出队执行 bpy 调用，结果入响应队列。
"""

from __future__ import annotations

import json
import socket
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Command:
    """客户端 → addon 的指令。"""

    req_id: str
    tool: str
    params: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> bytes:
        return (json.dumps(
            {"req_id": self.req_id, "tool": self.tool, "params": self.params},
            ensure_ascii=False,
        ) + "\n").encode("utf-8")


@dataclass
class Response:
    """addon → 客户端的响应。"""

    req_id: str
    status: str  # "ok" | "error"
    result: Any = None
    error: str | None = None

    @classmethod
    def from_json(cls, data: bytes) -> "Response":
        obj = json.loads(data.decode("utf-8"))
        return cls(
            req_id=obj["req_id"],
            status=obj["status"],
            result=obj.get("result"),
            error=obj.get("error"),
        )

    def to_json(self) -> bytes:
        return (json.dumps(
            {"req_id": self.req_id, "status": self.status,
             "result": self.result, "error": self.error},
            ensure_ascii=False,
        ) + "\n").encode("utf-8")


class BlenderBridgeClient:
    """MCP Server 端的 socket 客户端：发指令给 addon，同步收响应。

    每个 tool 调用创建一个 Command（带唯一 req_id），发送后阻塞等对应响应。
    线程安全：每次调用加锁，避免多智能体并发时 socket 读写交错。
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 19876,
                 timeout: float = 60.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self._lock = threading.Lock()
        self._sock: socket.socket | None = None

    def connect(self) -> None:
        self._sock = socket.create_connection(
            (self.host, self.port), timeout=self.timeout
        )

    def close(self) -> None:
        if self._sock:
            self._sock.close()
            self._sock = None

    def call(self, tool: str, **params: Any) -> Any:
        """发指令并同步等响应。返回 result；失败抛 RuntimeError。"""
        if not self._sock:
            self.connect()
        assert self._sock is not None
        cmd = Command(req_id=str(uuid.uuid4()), tool=tool, params=params)
        with self._lock:
            self._sock.sendall(cmd.to_json())
            buf = b""
            while b"\n" not in buf:
                chunk = self._sock.recv(4096)
                if not chunk:
                    raise ConnectionError("addon 连接断开")
                buf += chunk
            resp = Response.from_json(buf.strip())
        if resp.status == "error":
            raise RuntimeError(f"Blender 工具 {tool} 失败: {resp.error}")
        return resp.result

    def __enter__(self) -> "BlenderBridgeClient":
        self.connect()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


def read_port_from_env(env_path: Path, key: str, default: int) -> int:
    """从 infra/ports.env 读端口，避免硬编码。"""
    if not env_path.exists():
        return default
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip() == key:
            return int(v.strip())
    return default