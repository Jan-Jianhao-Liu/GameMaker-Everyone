"""Blender MCP Server：FastMCP + 6 白名单工具 + stdio。

通过 socket 客户端把指令转发给 Blender addon（blender-addon/game_agent_factory/）。
所有工具只接受结构化参数，禁止透传任意代码。

启动：uv run python mcp-servers/blender-mcp/server.py
（stdio 通信，由 MCP 客户端或网关拉起）
"""

from __future__ import annotations

import sys
from pathlib import Path

# 注入 common 共享模块（mcp-servers 带连字符不能作 Python 包）
_COMMON = Path(__file__).resolve().parents[1] / "common"
sys.path.insert(0, str(_COMMON))

from audit import AuditLogger  # noqa: E402
from param_validator import BaseToolParams, validate_params  # noqa: E402
from socket_bridge import BlenderBridgeClient, read_port_from_env  # noqa: E402

from fastmcp import FastMCP  # noqa: E402
from pydantic import Field, field_validator  # noqa: E402

_PORTS_ENV = Path(__file__).resolve().parents[2] / "infra" / "ports.env"
_PORT = read_port_from_env(_PORTS_ENV, "BLENDER_MCP_PORT", 19876)

mcp = FastMCP("blender-mcp")
audit = AuditLogger("blender-mcp")
_client: BlenderBridgeClient | None = None


def _bridge() -> BlenderBridgeClient:
    global _client
    if _client is None:
        _client = BlenderBridgeClient(port=_PORT)
        _client.connect()
    return _client


class CreatePrimitiveParams(BaseToolParams):
    prim_type: str = Field(description="CUBE/SPHERE/CYLINDER/PLANE/CONE/TORUS")
    name: str = Field(min_length=1)
    dimensions: list[float] = Field(min_length=3, max_length=3)


class AutoUvParams(BaseToolParams):
    asset_id: str = Field(min_length=1)


class AssignMaterialParams(BaseToolParams):
    asset_id: str = Field(min_length=1)
    base_color: list[float] = Field(min_length=4, max_length=4)
    roughness: float = Field(ge=0.0, le=1.0)
    metallic: float = Field(ge=0.0, le=1.0)


class ExportFbxParams(BaseToolParams):
    asset_id: str = Field(min_length=1)
    path: str = Field(min_length=1)


class ValidateExportParams(BaseToolParams):
    path: str = Field(min_length=1)


@mcp.tool
def create_primitive(prim_type: str, name: str, dimensions: list[float]) -> dict:
    """创建基础几何体。prim_type: CUBE/SPHERE/CYLINDER/PLANE/CONE/TORUS。"""
    p = validate_params(CreatePrimitiveParams, locals())
    try:
        result = _bridge().call("create_primitive", prim_type=p.prim_type,
                                name=p.name, dimensions=p.dimensions)
        audit.info("create_primitive", params=locals(), result=result)
        return {"status": "ok", "result": result}
    except Exception as e:  # noqa: BLE001
        audit.error("create_primitive", str(e), params=locals())
        return {"status": "error", "error": str(e)}


@mcp.tool
def auto_uv(asset_id: str) -> dict:
    """智能投影自动展 UV（对选中物体）。"""
    p = validate_params(AutoUvParams, {"asset_id": asset_id})
    try:
        result = _bridge().call("auto_uv", asset_id=p.asset_id)
        audit.info("auto_uv", params={"asset_id": asset_id}, result=result)
        return {"status": "ok", "result": result}
    except Exception as e:  # noqa: BLE001
        audit.error("auto_uv", str(e), params={"asset_id": asset_id})
        return {"status": "error", "error": str(e)}


@mcp.tool
def assign_material(
    asset_id: str, base_color: list[float], roughness: float, metallic: float
) -> dict:
    """创建并赋予基础 PBR 材质。base_color=[r,g,b,a]。"""
    p = validate_params(AssignMaterialParams, locals())
    try:
        result = _bridge().call(
            "assign_material", asset_id=p.asset_id, base_color=p.base_color,
            roughness=p.roughness, metallic=p.metallic,
        )
        audit.info("assign_material", params=locals(), result=result)
        return {"status": "ok", "result": result}
    except Exception as e:  # noqa: BLE001
        audit.error("assign_material", str(e), params=locals())
        return {"status": "error", "error": str(e)}


@mcp.tool
def export_fbx(asset_id: str, path: str) -> dict:
    """按规范导出 FBX：强制 Y-up、单位米、只导出选中物体、apply modifiers。"""
    p = validate_params(ExportFbxParams, locals())
    try:
        result = _bridge().call("export_fbx", asset_id=p.asset_id, path=p.path)
        audit.info("export_fbx", params=locals(), result=result)
        return {"status": "ok", "result": result}
    except Exception as e:  # noqa: BLE001
        audit.error("export_fbx", str(e), params=locals())
        return {"status": "error", "error": str(e)}


@mcp.tool
def validate_export(path: str) -> dict:
    """调用 contracts/art-spec.schema.json 校验导出物。"""
    p = validate_params(ValidateExportParams, {"path": path})
    try:
        result = _bridge().call("validate_export", path=p.path)
        audit.info("validate_export", params={"path": path}, result=result)
        return {"status": "ok", "result": result}
    except Exception as e:  # noqa: BLE001
        audit.error("validate_export", str(e), params={"path": path})
        return {"status": "error", "error": str(e)}


@mcp.tool
def get_scene_info() -> dict:
    """返回当前场景资产列表。"""
    try:
        result = _bridge().call("get_scene_info")
        audit.info("get_scene_info", params={}, result=result)
        return {"status": "ok", "result": result}
    except Exception as e:  # noqa: BLE001
        audit.error("get_scene_info", str(e), params={})
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    mcp.run(transport="stdio")