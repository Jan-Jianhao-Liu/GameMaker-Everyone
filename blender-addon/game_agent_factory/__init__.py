"""Game Agent Factory Blender Addon.

socket 桥 + 白名单指令执行器，让 AI 智能体安全自动化 Blender 3D 资产生产。

bpy 非线程安全：register() 启动 socket 监听线程 + bpy.app.timers 定时器；
监听线程只收指令入队，timer 在主线程出队执行 bpy 调用。
"""

from __future__ import annotations

import os

bl_info = {
    "name": "Game Agent Factory",
    "author": "game-agent-factory",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > GAF",
    "description": "AI 智能体自动化 Blender 3D 资产生产（socket 桥 + 白名单指令）",
    "category": "Object",
}

_server = None


def register() -> None:
    global _server
    from game_agent_factory.socket_server import BlenderSocketServer

    port = int(os.environ.get("BLENDER_MCP_PORT", "19876"))
    host = os.environ.get("BLENDER_MCP_HOST", "127.0.0.1")
    _server = BlenderSocketServer(host=host, port=port)
    _server.start()
    print(f"[GAF] socket server listening on {host}:{port}")


def unregister() -> None:
    global _server
    if _server is not None:
        _server.stop()
        _server = None
        print("[GAF] socket server stopped")