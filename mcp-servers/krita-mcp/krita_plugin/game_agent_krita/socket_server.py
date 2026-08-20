"""Krita 插件的 socket 服务端 + QTimer 队列。

libkis 非线程安全：socket 监听线程只收指令入队，
QTimer 在主线程出队执行 command_executor.execute（libkis 调用）。
"""

from __future__ import annotations

import json
import queue
import socket
import threading
from typing import Any

from PyQt5.QtCore import QTimer

from game_agent_krita.command_executor import execute


class KritaSocketServer:
    """Krita 插件内的 socket 服务端。"""

    def __init__(self, host: str = "127.0.0.1", port: int = 19878) -> None:
        self.host = host
        self.port = port
        self._cmd_queue: queue.Queue[tuple[str, str, dict, queue.Queue]] = queue.Queue()
        self._running = threading.Event()
        self._running.set()
        self._listen_thread: threading.Thread | None = None
        self._sock: socket.socket | None = None
        self._timer: QTimer | None = None

    def start(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))
        self._sock.listen(1)
        self._sock.settimeout(0.5)
        self._listen_thread = threading.Thread(
            target=self._listen_loop, daemon=True, name="krita-mcp-listen"
        )
        self._listen_thread.start()
        self._timer = QTimer()
        self._timer.timeout.connect(self._timer_tick)
        self._timer.start(10)

    def stop(self) -> None:
        self._running.clear()
        if self._timer:
            self._timer.stop()
        if self._sock:
            self._sock.close()
        if self._listen_thread:
            self._listen_thread.join(timeout=2.0)

    def _listen_loop(self) -> None:
        while self._running.is_set():
            try:
                conn, _ = self._sock.accept()  # type: ignore[union-attr]
            except TimeoutError:
                continue
            except OSError:
                break
            self._handle_connection(conn)

    def _handle_connection(self, conn: socket.socket) -> None:
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
        try:
            msg = json.loads(line.decode("utf-8"))
            req_id = msg["req_id"]
            tool = msg["tool"]
            params = msg.get("params", {})
        except (json.JSONDecodeError, KeyError) as e:
            resp = {"req_id": "?", "status": "error", "error": f"指令解析失败: {e}"}
            conn.sendall((json.dumps(resp, ensure_ascii=False) + "\n").encode())
            return
        resp_q: queue.Queue = queue.Queue()
        self._cmd_queue.put((req_id, tool, params, resp_q))
        result = resp_q.get()
        conn.sendall(
            (json.dumps(result, ensure_ascii=False, default=str) + "\n").encode()
        )

    def _timer_tick(self) -> None:
        """主线程 QTimer tick：非阻塞出队执行 libkis 调用。"""
        while True:
            try:
                req_id, tool, params, resp_q = self._cmd_queue.get_nowait()
            except queue.Empty:
                return
            try:
                result = execute(tool, params)
                resp_q.put({"req_id": req_id, "status": "ok", "result": result})
            except Exception as e:  # noqa: BLE001
                resp_q.put({"req_id": req_id, "status": "error", "error": str(e)})