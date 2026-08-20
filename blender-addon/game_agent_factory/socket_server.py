"""Blender addon 的 socket 服务端 + timer 队列。

bpy 非线程安全的核心处理：
- socket 监听线程：只做 socket IO + 队列操作，绝不调用 bpy
- bpy.app.timers 定时器：在主线程出队，调用 command_executor.execute（bpy 调用）
- 两个线程通过 queue.Queue 通信（线程安全）
"""

from __future__ import annotations

import json
import queue
import socket
import threading
from typing import Any

import bpy

from game_agent_factory.command_executor import execute


class BlenderSocketServer:
    """addon 内的 socket 服务端。

    register() 启动监听线程 + timer；unregister() 停止。
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 19876) -> None:
        self.host = host
        self.port = port
        self._cmd_queue: queue.Queue[tuple[str, str, dict, queue.Queue]] = queue.Queue()
        self._running = threading.Event()
        self._running.set()
        self._listen_thread: threading.Thread | None = None
        self._sock: socket.socket | None = None

    def start(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))
        self._sock.listen(1)
        self._sock.settimeout(0.5)
        self._listen_thread = threading.Thread(
            target=self._listen_loop, daemon=True, name="blender-mcp-listen"
        )
        self._listen_thread.start()
        bpy.app.timers.register(self._timer_loop, first_interval=0.01)

    def stop(self) -> None:
        self._running.clear()
        if self._sock:
            self._sock.close()
        if bpy.app.timers.is_registered(self._timer_loop):
            bpy.app.timers.unregister(self._timer_loop)
        if self._listen_thread:
            self._listen_thread.join(timeout=2.0)

    def _listen_loop(self) -> None:
        """监听线程：accept 连接，收指令入队，等响应发回。绝不调用 bpy。"""
        while self._running.is_set():
            try:
                conn, _ = self._sock.accept()  # type: ignore[union-attr]
            except socket.timeout:
                continue
            except OSError:
                break
            self._handle_connection(conn)

    def _handle_connection(self, conn: socket.socket) -> None:
        """单连接处理：收指令 → 入队 → 等响应 → 发回。"""
        try:
            buf = b""
            while self._running.is_set():
                try:
                    chunk = conn.recv(4096)
                except (ConnectionResetError, OSError):
                    break
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if not line.strip():
                        continue
                    self._process_line(conn, line)
        finally:
            conn.close()

    def _process_line(self, conn: socket.socket, line: bytes) -> None:
        """解析一条指令，入队，阻塞等响应，发回客户端。"""
        try:
            msg = json.loads(line.decode("utf-8"))
            req_id = msg["req_id"]
            tool = msg["tool"]
            params = msg.get("params", {})
        except (json.JSONDecodeError, KeyError) as e:
            resp = {
                "req_id": "?", "status": "error",
                "error": f"指令解析失败: {e}",
            }
            conn.sendall((json.dumps(resp, ensure_ascii=False) + "\n").encode())
            return
        resp_q: queue.Queue = queue.Queue()
        self._cmd_queue.put((req_id, tool, params, resp_q))
        result = resp_q.get()
        conn.sendall(
            (json.dumps(result, ensure_ascii=False, default=str) + "\n").encode()
        )

    def _timer_loop(self) -> float | None:
        """主线程 timer：非阻塞出队执行 bpy 调用。返回 None 停止，0.01 持续。"""
        if not self._running.is_set():
            return None
        try:
            req_id, tool, params, resp_q = self._cmd_queue.get_nowait()
        except queue.Empty:
            return 0.01
        try:
            result = execute(tool, params)
            resp_q.put(
                {"req_id": req_id, "status": "ok", "result": result}
            )
        except Exception as e:  # noqa: BLE001
            resp_q.put(
                {"req_id": req_id, "status": "error", "error": str(e)}
            )
        return 0.01