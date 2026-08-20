"""Prompt 4 网关单元测试：鉴权 + 路由 + 沙箱 + 速率限制 + 审计 + 越权拒绝 + 延迟。"""

from __future__ import annotations

import socket
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from gateway.auth import AuthError, RoleAuth, is_authorized
from gateway.rate_limit import RateLimiter
from gateway.router import ToolRouteError, route
from gateway.sandbox import Sandbox, SandboxError
from gateway.server import AuditDB, Gateway, check_all_ports, check_port_available

_ROOT = Path(__file__).resolve().parent.parent


# ---------- 鉴权 ----------


def test_build_export_only_coder():
    assert is_authorized("coder", "build_export")
    assert not is_authorized("artist3d", "build_export")
    assert not is_authorized("artist2d", "build_export")


def test_rollback_only_supervisor():
    assert is_authorized("supervisor", "rollback")
    assert not is_authorized("coder", "rollback")
    assert not is_authorized("artist3d", "rollback")


def test_artist_can_commit():
    assert is_authorized("artist3d", "commit_asset")
    assert is_authorized("artist2d", "commit_asset")


def test_designer_no_tools():
    assert not is_authorized("designer", "create_primitive")


def test_auth_rejects_bad_key():
    auth = RoleAuth({"good": "coder"})
    with pytest.raises(AuthError):
        auth.resolve_role("bad")


def test_auth_rejects_unknown_role():
    auth = RoleAuth()
    with pytest.raises(AuthError):
        auth.check_tool("evil", "create_primitive")


# ---------- 路由 ----------


def test_route_blender():
    assert route("create_primitive") == "blender"
    assert route("export_fbx") == "blender"


def test_route_godot():
    assert route("build_export") == "godot"


def test_route_git():
    assert route("commit_asset") == "git"
    assert route("rollback") == "git"


def test_route_unknown():
    with pytest.raises(ToolRouteError):
        route("evil_tool")


# ---------- 沙箱 ----------


def test_sandbox_rejects_dangerous_tool(tmp_path):
    sb = Sandbox([tmp_path])
    with pytest.raises(SandboxError):
        sb.check_tool("delete_all", {})


def test_sandbox_rejects_dangerous_param(tmp_path):
    sb = Sandbox([tmp_path])
    with pytest.raises(SandboxError):
        sb.check_tool("create_primitive", {"cmd": "rm -rf /"})


def test_sandbox_rejects_path_escape(tmp_path):
    game = tmp_path / "game"
    game.mkdir()
    outside = tmp_path / "secret.txt"
    sb = Sandbox([game])
    with pytest.raises(SandboxError):
        sb.check_tool("export_fbx", {"path": str(outside)})


def test_sandbox_allows_safe(tmp_path):
    game = tmp_path / "game"
    game.mkdir()
    sb = Sandbox([game])
    sb.check_tool("create_primitive", {"name": "cube"})


# ---------- 速率限制 ----------


def test_rate_limit_allows_under_limit(tmp_path):
    rl = RateLimiter(tmp_path / "rate.db", limit_per_minute=5)
    for _ in range(5):
        assert rl.acquire("coder")


def test_rate_limit_blocks_over_limit(tmp_path):
    rl = RateLimiter(tmp_path / "rate.db", limit_per_minute=3)
    for _ in range(3):
        assert rl.acquire("coder")
    assert not rl.acquire("coder")


# ---------- Gateway 集成 ----------


@pytest.fixture
def gateway(tmp_path):
    auth = RoleAuth({"key-coder": "coder", "key-art": "artist3d", "key-sup": "supervisor"})
    sandbox = Sandbox([tmp_path / "game"])
    (tmp_path / "game").mkdir()
    rate = RateLimiter(tmp_path / "rate.db", limit_per_minute=100)
    audit = AuditDB(tmp_path / "audit.db")
    forwarder = MagicMock(return_value={"ok": True})
    return Gateway(auth, sandbox, rate, audit, forwarder), audit, forwarder


def test_gateway_normal_call(gateway):
    gw, audit, fwd = gateway
    result = gw.call("coder", "key-coder", "create_scene", {"scene_name": "lvl1", "template": "3d"})
    assert result["status"] == "ok"
    fwd.assert_called_once_with("godot", "create_scene", {"scene_name": "lvl1", "template": "3d"})
    logs = audit.query("coder")
    assert len(logs) == 1 and logs[0]["status"] == "ok"


def test_gateway_rejects_unauthorized(gateway):
    gw, audit, fwd = gateway
    result = gw.call("artist3d", "key-art", "build_export", {"preset_name": "x"})
    assert result["status"] == "error"
    assert "无权" in result["error"]
    fwd.assert_not_called()
    logs = audit.query("artist3d")
    assert logs[0]["status"] == "rejected"


def test_gateway_rejects_bad_key(gateway):
    gw, audit, fwd = gateway
    result = gw.call("coder", "evil-key", "create_scene", {})
    assert result["status"] == "error"
    fwd.assert_not_called()


def test_gateway_rejects_dangerous(gateway):
    gw, audit, fwd = gateway
    result = gw.call("coder", "key-coder", "create_scene", {"cmd": "rm -rf /"})
    assert result["status"] == "error"
    fwd.assert_not_called()


def test_gateway_latency_under_200ms(gateway):
    gw, audit, fwd = gateway
    times = []
    for _ in range(50):
        t0 = time.perf_counter()
        gw.call("coder", "key-coder", "create_scene", {"scene_name": "s", "template": "3d"})
        times.append((time.perf_counter() - t0) * 1000)
    p99 = sorted(times)[int(len(times) * 0.99)]
    assert p99 < 200, f"P99 延迟 {p99:.1f}ms 超过 200ms"


# ---------- 端口探测 ----------


def test_check_port_available_free():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    assert check_port_available(port)


def test_check_all_ports_returns_list():
    occupied = check_all_ports(_ROOT / "infra" / "ports.env")
    assert isinstance(occupied, list)
