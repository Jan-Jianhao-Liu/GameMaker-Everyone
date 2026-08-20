"""Godot MCP Server：FastMCP + 6 白名单工具 + stdio + 版本校验。

通过 socket 客户端把指令转发给 Godot 插件（godot-plugin/addons/gaf_godot_mcp/）。
启动时校验 Godot 引擎版本（读 infra/versions.env），不匹配直接拒绝启动。

启动：uv run python mcp-servers/godot-mcp/server.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_COMMON = Path(__file__).resolve().parents[1] / "common"
sys.path.insert(0, str(_COMMON))

from audit import AuditLogger  # noqa: E402
from param_validator import BaseToolParams, validate_params  # noqa: E402
from socket_bridge import BlenderBridgeClient, read_port_from_env  # noqa: E402

from fastmcp import FastMCP  # noqa: E402
from pydantic import Field  # noqa: E402

_PORTS_ENV = Path(__file__).resolve().parents[2] / "infra" / "ports.env"
_VERSIONS_ENV = Path(__file__).resolve().parents[2] / "infra" / "versions.env"
_GAME_DIR = Path(__file__).resolve().parents[2] / "game"
_PORT = read_port_from_env(_PORTS_ENV, "GODOT_MCP_PORT", 19877)

mcp = FastMCP("godot-mcp")
audit = AuditLogger("godot-mcp")
_client: BlenderBridgeClient | None = None


def read_version_from_env(env_path: Path, key: str) -> str:
    """从 versions.env 读版本号。"""
    if not env_path.exists():
        raise RuntimeError(f"versions.env 不存在: {env_path}")
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip() == key:
            return v.strip()
    raise RuntimeError(f"{key} 未在 {env_path} 中定义")


def check_godot_version(versions_env: Path = _VERSIONS_ENV) -> str:
    """校验本机 Godot 版本与 versions.env 一致。不匹配抛 RuntimeError。"""
    expected = read_version_from_env(versions_env, "GODOT_VERSION")
    try:
        result = subprocess.run(
            ["godot", "--version"], capture_output=True, text=True, timeout=10
        )
    except FileNotFoundError as e:
        raise RuntimeError(
            "Godot 未安装或不在 PATH。请安装 Godot 4.4 stable 后重试。"
        ) from e
    if result.returncode != 0:
        raise RuntimeError(f"godot --version 失败: {result.stderr.strip()}")
    actual = result.stdout.strip()
    expected_major_minor = ".".join(expected.split(".")[:2])
    actual_major_minor = ".".join(actual.split(".")[:2])
    if actual_major_minor != expected_major_minor:
        raise RuntimeError(
            f"Godot 版本不匹配: 期望 {expected}（{expected_major_minor}.x），"
            f"实际 {actual}。请安装正确版本，防 EditorScript 行为被破坏。"
        )
    return actual


def _bridge() -> BlenderBridgeClient:
    global _client
    if _client is None:
        _client = BlenderBridgeClient(port=_PORT)
        _client.connect()
    return _client


def _check_res_path(path: str) -> None:
    """检查路径以 res:// 开头（防绝对路径逃逸）。"""
    if not path.startswith("res://"):
        raise ValueError(f"路径须以 res:// 开头: {path}")


class ImportAssetParams(BaseToolParams):
    fbx_path: str = Field(min_length=1)
    asset_id: str = Field(min_length=1)


class CreateSceneParams(BaseToolParams):
    scene_name: str = Field(min_length=1)
    template: str = Field(default="empty")


class AttachScriptParams(BaseToolParams):
    node_path: str = Field(min_length=1)
    script_content: str = Field(min_length=1)


class SetLevelDataParams(BaseToolParams):
    level_id: str = Field(min_length=1)
    json_path: str = Field(min_length=1)


class BuildExportParams(BaseToolParams):
    preset_name: str = Field(min_length=1)


class RunHeadlessTestParams(BaseToolParams):
    scene_path: str = Field(min_length=1)


@mcp.tool
def import_asset(fbx_path: str, asset_id: str) -> dict:
    """导入 FBX 并自动配置导入参数（贴图压缩、mipmap）。"""
    p = validate_params(ImportAssetParams, locals())
    try:
        _check_res_path(p.fbx_path)
        result = _bridge().call("import_asset", fbx_path=p.fbx_path,
                                asset_id=p.asset_id)
        audit.info("import_asset", params=locals(), result=result)
        return {"status": "ok", "result": result}
    except Exception as e:  # noqa: BLE001
        audit.error("import_asset", str(e), params=locals())
        return {"status": "error", "error": str(e)}


@mcp.tool
def create_scene(scene_name: str, template: str = "empty") -> dict:
    """从模板创建场景（empty/2d/3d/character 四类）。character 含 InputAdapter。"""
    p = validate_params(CreateSceneParams, locals())
    if p.template not in ("empty", "2d", "3d", "character"):
        return {"status": "error", "error": f"未知模板: {p.template}"}
    try:
        tpl = {"2d": "scene_2d", "3d": "scene_3d"}.get(p.template, p.template)
        result = _bridge().call("create_scene", scene_name=p.scene_name, template=tpl)
        audit.info("create_scene", params=locals(), result=result)
        return {"status": "ok", "result": result}
    except Exception as e:  # noqa: BLE001
        audit.error("create_scene", str(e), params=locals())
        return {"status": "error", "error": str(e)}


@mcp.tool
def attach_script(node_path: str, script_content: str) -> dict:
    """为节点挂载 GDScript（插件侧先做语法检查，失败则拒绝）。"""
    p = validate_params(AttachScriptParams, locals())
    try:
        _check_res_path("res://" + p.node_path)
        result = _bridge().call("attach_script", node_path=p.node_path,
                                script_content=p.script_content)
        audit.info("attach_script", params={"node_path": node_path}, result=result)
        return {"status": "ok", "result": result}
    except Exception as e:  # noqa: BLE001
        audit.error("attach_script", str(e), params={"node_path": node_path})
        return {"status": "error", "error": str(e)}


@mcp.tool
def set_level_data(level_id: str, json_path: str) -> dict:
    """读取策划数据表并生成场景内实体。"""
    p = validate_params(SetLevelDataParams, locals())
    try:
        result = _bridge().call("set_level_data", level_id=p.level_id,
                                json_path=p.json_path)
        audit.info("set_level_data", params=locals(), result=result)
        return {"status": "ok", "result": result}
    except Exception as e:  # noqa: BLE001
        audit.error("set_level_data", str(e), params=locals())
        return {"status": "error", "error": str(e)}


@mcp.tool
def build_export(preset_name: str) -> dict:
    """调用 Godot 命令行构建 Windows 桌面测试包（唯一验收目标）。"""
    p = validate_params(BuildExportParams, locals())
    try:
        result = _bridge().call("build_export", preset_name=p.preset_name)
        audit.info("build_export", params=locals(), result=result)
        return {"status": "ok", "result": result}
    except Exception as e:  # noqa: BLE001
        audit.error("build_export", str(e), params=locals())
        return {"status": "error", "error": str(e)}


@mcp.tool
def run_headless_test(scene_path: str) -> dict:
    """无头运行场景并捕获错误日志与关键节点截图。"""
    p = validate_params(RunHeadlessTestParams, locals())
    try:
        result = _bridge().call("run_headless_test", scene_path=p.scene_path)
        audit.info("run_headless_test", params=locals(), result=result)
        return {"status": "ok", "result": result}
    except Exception as e:  # noqa: BLE001
        audit.error("run_headless_test", str(e), params=locals())
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    actual = check_godot_version()
    print(f"[godot-mcp] Godot 版本校验通过: {actual}")
    mcp.run(transport="stdio")