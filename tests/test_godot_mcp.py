"""Prompt 3 godot-mcp 单元测试：版本校验 + 路径白名单 + 模板 + InputAdapter。"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_COMMON = str(_ROOT / "mcp-servers" / "common")
_GODOT_MCP = str(_ROOT / "mcp-servers" / "godot-mcp")
for _p in (_COMMON, _GODOT_MCP):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "godot_mcp_server", _ROOT / "mcp-servers" / "godot-mcp" / "server.py"
)
godot_server = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(godot_server)

_TEMPLATES = _ROOT / "godot-plugin" / "addons" / "gaf_godot_mcp" / "templates"


# ---------- 版本校验 ----------


def test_read_version_from_env():
    v = godot_server.read_version_from_env(godot_server._VERSIONS_ENV, "GODOT_VERSION")
    assert v.startswith("4.4")


def test_check_godot_version_ok():
    fake = MagicMock(returncode=0, stdout="4.4.1\n", stderr="")
    with patch("subprocess.run", return_value=fake):
        assert godot_server.check_godot_version() == "4.4.1"


def test_check_godot_version_mismatch():
    fake = MagicMock(returncode=0, stdout="4.3.0\n", stderr="")
    with patch("subprocess.run", return_value=fake):
        with pytest.raises(RuntimeError, match="版本不匹配"):
            godot_server.check_godot_version()


def test_check_godot_version_not_installed():
    with patch("subprocess.run", side_effect=FileNotFoundError):
        with pytest.raises(RuntimeError, match="Godot 未安装"):
            godot_server.check_godot_version()


# ---------- 路径白名单 ----------


def test_check_res_path_ok():
    godot_server._check_res_path("res://models/hero.fbx")


def test_check_res_path_rejected():
    with pytest.raises(ValueError, match="res://"):
        godot_server._check_res_path("C:/evil/abs.fbx")


def test_import_asset_rejects_non_res():
    result = godot_server.import_asset(fbx_path="/abs/evil.fbx", asset_id="x")
    assert result["status"] == "error"
    assert "res://" in result["error"]


# ---------- create_scene 模板映射 ----------


def test_create_scene_template_mapping_2d():
    mock_client = MagicMock()
    mock_client.call.return_value = {"scene": "res://s.tscn"}
    with patch.object(godot_server, "_bridge", return_value=mock_client):
        godot_server.create_scene(scene_name="s", template="2d")
    _, kwargs = mock_client.call.call_args
    assert kwargs["template"] == "scene_2d"


def test_create_scene_template_mapping_3d():
    mock_client = MagicMock()
    mock_client.call.return_value = {"scene": "res://s.tscn"}
    with patch.object(godot_server, "_bridge", return_value=mock_client):
        godot_server.create_scene(scene_name="s", template="3d")
    _, kwargs = mock_client.call.call_args
    assert kwargs["template"] == "scene_3d"


def test_create_scene_unknown_template():
    result = godot_server.create_scene(scene_name="s", template="evil")
    assert result["status"] == "error"


# ---------- 场景模板文件 ----------


def test_templates_exist():
    for name in ("empty", "scene_2d", "scene_3d", "character"):
        assert (_TEMPLATES / f"{name}.tscn").exists(), f"模板缺失: {name}"


def test_character_template_has_input_adapter():
    content = (_TEMPLATES / "character.tscn").read_text(encoding="utf-8")
    assert "InputAdapter" in content
    assert "input_adapter.gd" in content
    assert "CharacterBody3D" in content


def test_character_template_has_collision_and_mesh():
    content = (_TEMPLATES / "character.tscn").read_text(encoding="utf-8")
    assert "CollisionShape3D" in content
    assert "MeshInstance3D" in content


# ---------- InputAdapter 脚本 ----------


def test_input_adapter_script_exists():
    adapter = _ROOT / "godot-plugin" / "addons" / "gaf_godot_mcp" / "input_adapter.gd"
    content = adapter.read_text(encoding="utf-8")
    assert "is_pressed" in content
    assert "just_pressed" in content
    assert "start_mocking" in content
    assert "set_mock_action" in content
