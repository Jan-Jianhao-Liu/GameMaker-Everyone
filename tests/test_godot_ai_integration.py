"""godot-ai 集成测试：插件 45 工具 + 路由 + 鉴权 + 沙箱 + HTTP 转发器 + agent 路径。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from gateway.auth import is_authorized
from gateway.http_forwarder import HttpMcpForwarder, MultiForwarder
from gateway.router import route
from gateway.sandbox import Sandbox, SandboxError
from plugins.builtin.godot_ai import GodotAIPlugin

# ---------- 插件工具数 ----------


def test_godot_ai_plugin_has_45_tools():
    plugin = GodotAIPlugin()
    tools = plugin.tools()
    assert len(tools) == 45


def test_godot_ai_plugin_id_and_port():
    plugin = GodotAIPlugin()
    assert plugin.plugin_id == "godot_ai"
    assert plugin.port == 8001
    assert plugin.plugin_type == "game_engine"


def test_godot_ai_plugin_has_key_tools():
    plugin = GodotAIPlugin()
    names = {t.name for t in plugin.tools()}
    for expected in [
        "node_create", "node_set_property", "script_attach", "script_patch",
        "scene_save", "scene_manage", "editor_screenshot", "logs_read",
        "scene_get_hierarchy", "project_run", "batch_execute",
    ]:
        assert expected in names, f"缺少工具: {expected}"


def test_godot_ai_plugin_tool_chains():
    plugin = GodotAIPlugin()
    chains = plugin.tool_chains()
    assert "build_scene_node_by_node" in chains
    assert "visual_verify" in chains
    assert "build_and_run" in chains


# ---------- 路由 ----------


_GODOT_AI_TOOL_NAMES = [
    "editor_state", "node_get_properties", "scene_get_hierarchy", "session_activate",
    "session_manage", "scene_manage", "scene_open", "scene_save",
    "node_create", "node_find", "node_manage", "node_set_property",
    "script_attach", "script_create", "script_manage", "script_patch",
    "resource_manage", "animation_create", "animation_manage",
    "material_manage", "particle_manage", "camera_manage", "audio_manage",
    "ui_manage", "theme_manage", "tilemap_manage", "tileset_manage",
    "gridmap_manage", "csg_manage", "editor_manage", "editor_reload_plugin",
    "editor_screenshot", "logs_read", "project_manage", "project_run",
    "game_manage", "test_manage", "test_run", "filesystem_manage",
    "input_map_manage", "autoload_manage", "signal_manage", "api_manage",
    "client_manage", "batch_execute",
]


def test_route_all_godot_ai_tools():
    for tool in _GODOT_AI_TOOL_NAMES:
        assert route(tool) == "godot_ai", f"路由错误: {tool}"


def test_route_count():
    from gateway.router import TOOL_TO_SERVER
    godot_ai_count = sum(1 for v in TOOL_TO_SERVER.values() if v == "godot_ai")
    assert godot_ai_count == 45


def test_route_original_godot_still_works():
    assert route("build_export") == "godot"
    assert route("create_scene") == "godot"


# ---------- 鉴权 ----------


def test_coder_can_use_godot_ai_builder_tools():
    for tool in ["node_create", "node_set_property", "script_attach", "scene_save", "scene_manage"]:
        assert is_authorized("coder", tool), f"coder 应有权调用 {tool}"


def test_qa_can_use_visual_verification_tools():
    for tool in ["editor_screenshot", "logs_read", "scene_get_hierarchy", "test_run"]:
        assert is_authorized("qa", tool), f"qa 应有权调用 {tool}"


def test_qa_cannot_use_node_create():
    assert not is_authorized("qa", "node_create")


def test_coder_can_use_batch_execute():
    assert is_authorized("coder", "batch_execute")


def test_artist_cannot_use_godot_ai_tools():
    assert not is_authorized("artist3d", "node_create")
    assert not is_authorized("artist2d", "editor_screenshot")


# ---------- 沙箱 ----------


def test_sandbox_allows_batch_execute(tmp_path):
    sb = Sandbox([tmp_path])
    sb.check_tool("batch_execute", {"calls": []})


def test_sandbox_allows_script_create(tmp_path):
    sb = Sandbox([tmp_path])
    sb.check_tool("script_create", {"path": "res://scripts/player.gd"})


def test_sandbox_allows_script_patch(tmp_path):
    sb = Sandbox([tmp_path])
    sb.check_tool("script_patch", {"node": "Player"})


def test_sandbox_still_blocks_dangerous(tmp_path):
    sb = Sandbox([tmp_path])
    with pytest.raises(SandboxError):
        sb.check_tool("delete_all", {})


def test_sandbox_still_blocks_shell_exec(tmp_path):
    sb = Sandbox([tmp_path])
    with pytest.raises(SandboxError):
        sb.check_tool("shell_exec", {})


# ---------- HTTP 转发器 ----------


def test_http_forwarder_init():
    fwd = HttpMcpForwarder("http://127.0.0.1:8001/mcp", timeout=10.0)
    assert fwd._endpoint == "http://127.0.0.1:8001/mcp"
    assert fwd._timeout == 10.0
    assert fwd._initialized is False


def test_multi_forwarder_dispatch_to_registered():
    multi = MultiForwarder()
    mock_fwd = MagicMock()
    mock_fwd.call.return_value = {"status": "ok", "result": {}}
    multi.register("godot_ai", mock_fwd)
    result = multi.dispatch("godot_ai", "node_create", {"type": "Node3D"})
    assert result["status"] == "ok"
    mock_fwd.call.assert_called_once_with("godot_ai", "node_create", {"type": "Node3D"})


def test_multi_forwarder_dispatch_to_fallback():
    multi = MultiForwarder()

    def fallback(server, tool, params):
        return {"status": "ok", "result": server}

    multi.set_fallback(fallback)
    result = multi.dispatch("blender", "create_primitive", {"name": "cube"})
    assert result["status"] == "ok"
    assert result["result"] == "blender"


def test_multi_forwarder_no_forwarder_error():
    multi = MultiForwarder()
    result = multi.dispatch("unknown", "tool", {})
    assert result["status"] == "error"


def test_multi_forwarder_callable_as_forwarder():
    multi = MultiForwarder()
    mock_fwd = MagicMock()
    mock_fwd.call.return_value = {"status": "ok"}
    multi.register("godot_ai", mock_fwd)

    def fallback(server, tool, params):
        return {"status": "error"}

    multi.set_fallback(fallback)
    result = multi.dispatch("godot_ai", "scene_save", {})
    assert result["status"] == "ok"


# ---------- 插件注册表 ----------


def test_plugin_registry_loads_godot_ai():
    from plugins.registry import PluginRegistry
    registry = PluginRegistry()
    registry.load()
    plugin = registry.get("godot_ai")
    assert plugin is not None
    assert plugin.plugin_id == "godot_ai"
    assert len(plugin.tools()) == 45


# ---------- Coder agent godot-ai 路径 ----------


def _make_deps_with_godot_ai(gateway_mock=None):
    from agents.common.deps import AgentDeps
    from plugins.registry import PluginRegistry
    registry = PluginRegistry()
    registry.load()
    return AgentDeps(
        llm=MagicMock(),
        gateway=gateway_mock or MagicMock(),
        repo=MagicMock(),
        api_keys={"coder": "key-coder", "qa": "key-qa"},
        plugins=registry,
    )


def _make_deps_without_godot_ai(gateway_mock=None):
    from agents.common.deps import AgentDeps
    return AgentDeps(
        llm=MagicMock(),
        gateway=gateway_mock or MagicMock(),
        repo=MagicMock(),
        api_keys={"coder": "key-coder", "qa": "key-qa"},
        plugins=None,
    )


def test_coder_uses_godot_ai_when_available():
    from agents.coder.agent import _has_godot_ai
    deps = _make_deps_with_godot_ai()
    assert _has_godot_ai(deps) is True


def test_coder_falls_back_without_godot_ai():
    from agents.coder.agent import _has_godot_ai
    deps = _make_deps_without_godot_ai()
    assert _has_godot_ai(deps) is False


def test_coder_node_calls_godot_ai_tools():
    from agents.coder.agent import make_coder_node
    gw = MagicMock()
    gw.call.return_value = {"status": "ok", "result": {}}
    deps = _make_deps_with_godot_ai(gw)
    node = make_coder_node(deps)
    state = {
        "task_id": "test-1",
        "produced_assets": [],
        "gdd": {"levels": [{"name": "Level1", "entities": []}]},
    }
    result = node(state)
    called_tools = [c.args[2] for c in gw.call.call_args_list]
    assert "scene_manage" in called_tools
    assert "batch_execute" in called_tools or "node_create" in called_tools
    assert "scene_save" in called_tools
    assert result["current_role"] == "qa"


def test_coder_node_falls_back_without_plugin():
    from agents.coder.agent import make_coder_node
    gw = MagicMock()
    gw.call.return_value = {"status": "ok", "result": {}}
    deps = _make_deps_without_godot_ai(gw)
    node = make_coder_node(deps)
    state = {
        "task_id": "test-1",
        "produced_assets": [],
        "gdd": {"levels": []},
    }
    node(state)
    called_tools = [c.args[2] for c in gw.call.call_args_list]
    assert "create_scene" in called_tools
    assert "scene_manage" not in called_tools


# ---------- QA agent godot-ai 路径 ----------


def test_qa_uses_visual_verify_when_available():
    from agents.qa.agent import _has_godot_ai
    deps = _make_deps_with_godot_ai()
    assert _has_godot_ai(deps) is True


def test_qa_node_calls_visual_verification():
    from agents.qa.agent import make_qa_node
    gw = MagicMock()
    gw.call.return_value = {"status": "ok", "result": {"nodes": [{"name": "Player"}]}}
    deps = _make_deps_with_godot_ai(gw)
    node = make_qa_node(deps)
    state = {
        "task_id": "test-1",
        "build_result": {"path": "game/build", "status": "draft"},
    }
    result = node(state)
    called_tools = [c.args[2] for c in gw.call.call_args_list]
    assert "editor_screenshot" in called_tools
    assert "logs_read" in called_tools
    assert "scene_get_hierarchy" in called_tools
    assert result["status"] == "paused_human"


def test_qa_node_detects_missing_player():
    from agents.qa.agent import make_qa_node
    gw = MagicMock()

    def side_effect(role, key, tool, params):
        if tool == "scene_get_hierarchy":
            return {"status": "ok", "result": {"nodes": [{"name": "Camera3D"}]}}
        return {"status": "ok", "result": {}}

    gw.call.side_effect = side_effect
    deps = _make_deps_with_godot_ai(gw)
    node = make_qa_node(deps)
    state = {
        "task_id": "test-1",
        "build_result": {"path": "game/build", "status": "draft"},
    }
    result = node(state)
    assert result["current_role"] == "coder"
    assert any(d["type"] == "missing_player" for d in result["defects"])


def test_qa_node_detects_error_logs():
    from agents.qa.agent import make_qa_node
    gw = MagicMock()

    def side_effect(role, key, tool, params):
        if tool == "logs_read":
            return {"status": "ok", "result": {"logs": ["NullReference: player.gd:42"]}}
        if tool == "scene_get_hierarchy":
            return {"status": "ok", "result": {"nodes": [{"name": "Player"}]}}
        return {"status": "ok", "result": {}}

    gw.call.side_effect = side_effect
    deps = _make_deps_with_godot_ai(gw)
    node = make_qa_node(deps)
    state = {
        "task_id": "test-1",
        "build_result": {"path": "game/build", "status": "draft"},
    }
    result = node(state)
    assert result["current_role"] == "coder"
    assert any(d["type"] == "error_log" for d in result["defects"])


def test_qa_node_falls_back_without_plugin():
    from agents.qa.agent import make_qa_node
    gw = MagicMock()
    gw.call.return_value = {"status": "ok", "result": {"defects": []}}
    deps = _make_deps_without_godot_ai(gw)
    node = make_qa_node(deps)
    state = {
        "task_id": "test-1",
        "build_result": {"path": "game/build", "status": "draft"},
    }
    node(state)
    called_tools = [c.args[2] for c in gw.call.call_args_list]
    assert "run_headless_test" in called_tools
    assert "editor_screenshot" not in called_tools


# ---------- AI-effort 滑块 ----------


def test_effort_filter_low_coder():
    from gateway.auth import filter_tools_by_effort
    tools = filter_tools_by_effort("coder", "low")
    assert "scene_manage" in tools
    assert "node_create" in tools
    assert "script_attach" in tools
    assert "batch_execute" in tools
    assert "ui_manage" not in tools
    assert "audio_manage" not in tools
    assert "tilemap_manage" not in tools


def test_effort_filter_medium_coder():
    from gateway.auth import filter_tools_by_effort
    tools = filter_tools_by_effort("coder", "medium")
    assert "scene_manage" in tools
    assert "resource_manage" in tools
    assert "animation_create" in tools
    assert "camera_manage" in tools
    assert "ui_manage" not in tools
    assert "audio_manage" not in tools


def test_effort_filter_high_coder():
    from gateway.auth import filter_tools_by_effort
    tools = filter_tools_by_effort("coder", "high")
    assert "ui_manage" in tools
    assert "audio_manage" in tools
    assert "tilemap_manage" in tools
    assert "signal_manage" in tools


def test_effort_filter_non_godot_ai_tools_always_included():
    from gateway.auth import filter_tools_by_effort
    tools_low = filter_tools_by_effort("coder", "low")
    assert "create_scene" in tools_low
    assert "attach_script" in tools_low
    assert "build_export" in tools_low


def test_effort_filter_designer_empty():
    from gateway.auth import filter_tools_by_effort
    for effort in ("low", "medium", "high"):
        assert filter_tools_by_effort("designer", effort) == set()


def test_role_auth_with_effort():
    from gateway.auth import RoleAuth
    auth = RoleAuth(effort="low")
    auth.check_tool("coder", "scene_manage")
    auth.check_tool("coder", "node_create")
    with pytest.raises(PermissionError):
        auth.check_tool("coder", "ui_manage")


def test_role_auth_effort_change():
    from gateway.auth import RoleAuth
    auth = RoleAuth(effort="low")
    with pytest.raises(PermissionError):
        auth.check_tool("coder", "ui_manage")
    auth.effort = "high"
    auth.check_tool("coder", "ui_manage")


def test_role_auth_allowed_tools_cached():
    from gateway.auth import RoleAuth
    auth = RoleAuth(effort="medium")
    t1 = auth.allowed_tools("coder")
    t2 = auth.allowed_tools("coder")
    assert t1 is t2


def test_is_authorized_with_effort():
    from gateway.auth import is_authorized
    assert is_authorized("coder", "scene_manage", "low")
    assert not is_authorized("coder", "ui_manage", "low")
    assert is_authorized("coder", "ui_manage", "high")


def test_gateway_effort_property():
    from gateway.auth import RoleAuth
    from gateway.server import Gateway
    from unittest.mock import MagicMock
    auth = RoleAuth(effort="low")
    gw = Gateway(auth, MagicMock(), MagicMock(), MagicMock(), MagicMock())
    assert gw.effort == "low"
    assert "ui_manage" not in gw.allowed_tools("coder")
    gw.effort = "high"
    assert gw.effort == "high"
    assert "ui_manage" in gw.allowed_tools("coder")
