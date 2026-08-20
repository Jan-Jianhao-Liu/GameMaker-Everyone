"""Prompt 2 单元测试：common 共享模块 + command_executor（mock bpy）。

Blender 未安装时，bpy 用 MagicMock 注入；socket 用真实 loopback 测试。
"""

from __future__ import annotations

import json
import socket
import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_COMMON = _ROOT / "mcp-servers" / "common"
_ADDON = _ROOT / "blender-addon"

for _p in (str(_COMMON), str(_ADDON)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

sys.modules.setdefault("bpy", MagicMock())

from audit import AuditLogger  # noqa: E402
from param_validator import BaseToolParams, validate_params  # noqa: E402
from path_whitelist import is_path_safe  # noqa: E402
from socket_bridge import (  # noqa: E402
    BlenderBridgeClient,
    Command,
    Response,
    read_port_from_env,
)

# ---------- Command / Response 序列化 ----------


def test_command_to_json():
    cmd = Command(req_id="r1", tool="create_primitive", params={"prim_type": "CUBE"})
    data = cmd.to_json()
    assert data.endswith(b"\n")
    obj = json.loads(data)
    assert obj["req_id"] == "r1" and obj["tool"] == "create_primitive"


def test_response_from_json():
    raw = b'{"req_id":"r1","status":"ok","result":{"x":1},"error":null}\n'
    resp = Response.from_json(raw.strip())
    assert resp.req_id == "r1" and resp.status == "ok" and resp.result == {"x": 1}


# ---------- read_port_from_env ----------


def test_read_port_from_env(tmp_path):
    env = tmp_path / "ports.env"
    env.write_text("# comment\nBLENDER_MCP_PORT=19876\nGODOT_MCP_PORT=19877\n")
    assert read_port_from_env(env, "BLENDER_MCP_PORT", 9999) == 19876


def test_read_port_default(tmp_path):
    assert read_port_from_env(tmp_path / "no.env", "X", 19876) == 19876


# ---------- BlenderBridgeClient（真实 loopback socket） ----------


def _echo_server(port: int, ready: threading.Event, stop: threading.Event):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", port))
    srv.listen(1)
    srv.settimeout(0.5)
    ready.set()
    while not stop.is_set():
        try:
            conn, _ = srv.accept()
        except TimeoutError:
            continue
        buf = b""
        while b"\n" not in buf:
            buf += conn.recv(4096)
        cmd = json.loads(buf.strip())
        resp = {
            "req_id": cmd["req_id"],
            "status": "ok",
            "result": {"echo": cmd["tool"]},
            "error": None,
        }
        conn.sendall((json.dumps(resp) + "\n").encode())
        conn.close()
    srv.close()


def test_blender_bridge_client():
    port = 19890
    ready, stop = threading.Event(), threading.Event()
    t = threading.Thread(target=_echo_server, args=(port, ready, stop), daemon=True)
    t.start()
    ready.wait(timeout=2)
    try:
        with BlenderBridgeClient(port=port, timeout=5) as client:
            result = client.call("create_primitive", prim_type="CUBE")
            assert result == {"echo": "create_primitive"}
    finally:
        stop.set()
        t.join(timeout=2)


# ---------- AuditLogger ----------


def test_audit_logger(tmp_path):
    logger = AuditLogger("test-unit", log_dir=tmp_path)
    logger.info("create_primitive", params={"x": 1}, result={"ok": True})
    logger.error("export_fbx", "no selection", params={"asset_id": "a"})
    lines = (tmp_path / "test-unit.log").read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    e1 = json.loads(lines[0])
    assert e1["tool"] == "create_primitive" and e1["status"] == "ok"
    e2 = json.loads(lines[1])
    assert e2["status"] == "error" and e2["error"] == "no selection"


# ---------- param_validator ----------


class _SampleParams(BaseToolParams):
    name: str
    count: int


def test_validate_params_ok():
    p = validate_params(_SampleParams, {"name": "x", "count": 3})
    assert p.name == "x" and p.count == 3


def test_validate_params_reject_extra():
    with pytest.raises(ValueError):
        validate_params(_SampleParams, {"name": "x", "count": 3, "evil": "code"})


def test_validate_params_reject_missing():
    with pytest.raises(ValueError):
        validate_params(_SampleParams, {"name": "x"})


# ---------- path_whitelist ----------


def test_path_safe(tmp_path):
    root = tmp_path / "game"
    root.mkdir()
    target = root / "scene.tscn"
    target.touch()
    assert is_path_safe(target, [root])


def test_path_escape_rejected(tmp_path):
    root = tmp_path / "game"
    root.mkdir()
    outside = tmp_path / "secret.txt"
    outside.touch()
    assert not is_path_safe(outside, [root])


# ---------- command_executor（mock bpy） ----------


def test_execute_unknown_tool_rejected():
    from game_agent_factory.command_executor import execute

    with pytest.raises(ValueError, match="未知工具"):
        execute("evil_shell", {"cmd": "rm -rf /"})


def test_dispatch_has_six_tools():
    from game_agent_factory.command_executor import DISPATCH

    assert set(DISPATCH) == {
        "create_primitive",
        "auto_uv",
        "assign_material",
        "export_fbx",
        "validate_export",
        "get_scene_info",
    }


def test_get_scene_info_mock():
    import bpy

    bpy.context.scene.name = "Scene"
    bpy.data.objects = [MagicMock(name="Cube", type="MESH", location=(0, 0, 0))]
    from game_agent_factory.command_executor import get_scene_info

    info = get_scene_info()
    assert info["scene"] == "Scene"
    assert len(info["objects"]) == 1
