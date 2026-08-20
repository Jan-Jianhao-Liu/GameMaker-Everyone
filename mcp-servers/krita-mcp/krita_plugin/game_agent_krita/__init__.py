"""Game Agent Krita Plugin.

socket 桥 + 白名单指令执行器，让 AI 智能体安全自动化 Krita 2D 资产生产。
libkis 非线程安全：register() 启动 socket 监听线程 + QTimer 定时器；
监听线程只收指令入队，QTimer 在主线程出队执行 libkis 调用。
"""

from __future__ import annotations

import os

from krita import Extension

_server = None


class GameAgentKritaExtension(Extension):
    def setup(self) -> None:
        pass

    def createActions(self, window) -> None:
        action = window.createAction("gaf_start", "启动 GAF 桥", "tools/scripts")
        action.triggered.connect(self._start)

    def _start(self) -> None:
        global _server
        from game_agent_krita.socket_server import KritaSocketServer

        port = int(os.environ.get("KRITA_MCP_PORT", "19878"))
        host = os.environ.get("KRITA_MCP_HOST", "127.0.0.1")
        _server = KritaSocketServer(host=host, port=port)
        _server.start()
        print(f"[GAF-Krita] socket server listening on {host}:{port}")


def register() -> None:
    from krita import Krita

    Krita.instance().addExtension(GameAgentKritaExtension(Krita.instance()))


def unregister() -> None:
    global _server
    if _server is not None:
        _server.stop()
        _server = None
        print("[GAF-Krita] socket server stopped")