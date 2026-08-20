"""Krita MCP Server：FastMCP + 6 白名单工具 + stdio。

通过 socket 客户端把指令转发给 Krita 插件
（mcp-servers/krita-mcp/krita_plugin/game_agent_krita/）。
复用 blender-mcp 的 socket 桥接架构，只写 Krita 特有工具。

启动：uv run python mcp-servers/krita-mcp/server.py
"""

from __future__ import annotations

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
_PORT = read_port_from_env(_PORTS_ENV, "KRITA_MCP_PORT", 19878)

mcp = FastMCP("krita-mcp")
audit = AuditLogger("krita-mcp")
_client: BlenderBridgeClient | None = None


def _bridge() -> BlenderBridgeClient:
    global _client
    if _client is None:
        _client = BlenderBridgeClient(port=_PORT)
        _client.connect()
    return _client


class CreateCanvasParams(BaseToolParams):
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    dpi: int = Field(gt=0)
    color_space: str = Field(min_length=1)


class DrawRectParams(BaseToolParams):
    x: int
    y: int
    w: int = Field(gt=0)
    h: int = Field(gt=0)
    color: list[int] = Field(min_length=4, max_length=4)


class ExportPngParams(BaseToolParams):
    asset_id: str = Field(min_length=1)
    path: str = Field(min_length=1)


class SpriteSheetParams(BaseToolParams):
    asset_id: str = Field(min_length=1)
    frame_count: int = Field(gt=0)
    fps: int = Field(gt=0)


class PaletteParams(BaseToolParams):
    asset_id: str = Field(min_length=1)
    palette_json: str = Field(min_length=1)


@mcp.tool
def create_canvas(width: int, height: int, dpi: int, color_space: str) -> dict:
    """创建画布。color_space: RGBA8/RGBA16/GrayA8 等。"""
    p = validate_params(CreateCanvasParams, locals())
    try:
        result = _bridge().call("create_canvas", width=p.width, height=p.height,
                                dpi=p.dpi, color_space=p.color_space)
        audit.info("create_canvas", params=locals(), result=result)
        return {"status": "ok", "result": result}
    except Exception as e:  # noqa: BLE001
        audit.error("create_canvas", str(e), params=locals())
        return {"status": "error", "error": str(e)}


@mcp.tool
def draw_rect(x: int, y: int, w: int, h: int, color: list[int]) -> dict:
    """绘制矩形。color=[r,g,b,a] 0-255。"""
    p = validate_params(DrawRectParams, locals())
    try:
        result = _bridge().call("draw_rect", x=p.x, y=p.y, w=p.w, h=p.h,
                                color=p.color)
        audit.info("draw_rect", params=locals(), result=result)
        return {"status": "ok", "result": result}
    except Exception as e:  # noqa: BLE001
        audit.error("draw_rect", str(e), params=locals())
        return {"status": "error", "error": str(e)}


@mcp.tool
def fill_layer(layer_name: str, color: list[int]) -> dict:
    """填充图层。"""
    try:
        result = _bridge().call("fill_layer", layer_name=layer_name, color=color)
        audit.info("fill_layer", params=locals(), result=result)
        return {"status": "ok", "result": result}
    except Exception as e:  # noqa: BLE001
        audit.error("fill_layer", str(e), params=locals())
        return {"status": "error", "error": str(e)}


@mcp.tool
def export_png(asset_id: str, path: str) -> dict:
    """导出 PNG，按 art-spec 校验尺寸为 2 的幂（UI 类型走 npot 豁免）。"""
    p = validate_params(ExportPngParams, locals())
    try:
        result = _bridge().call("export_png", asset_id=p.asset_id, path=p.path)
        audit.info("export_png", params=locals(), result=result)
        return {"status": "ok", "result": result}
    except Exception as e:  # noqa: BLE001
        audit.error("export_png", str(e), params=locals())
        return {"status": "error", "error": str(e)}


@mcp.tool
def export_sprite_sheet(asset_id: str, frame_count: int, fps: int) -> dict:
    """导出精灵图集（横向拼接帧）。"""
    p = validate_params(SpriteSheetParams, locals())
    try:
        result = _bridge().call("export_sprite_sheet", asset_id=p.asset_id,
                                frame_count=p.frame_count, fps=p.fps)
        audit.info("export_sprite_sheet", params=locals(), result=result)
        return {"status": "ok", "result": result}
    except Exception as e:  # noqa: BLE001
        audit.error("export_sprite_sheet", str(e), params=locals())
        return {"status": "error", "error": str(e)}


@mcp.tool
def apply_palette(asset_id: str, palette_json: str) -> dict:
    """应用调色板（像素风关键）。palette_json: JSON 字符串。"""
    p = validate_params(PaletteParams, locals())
    try:
        result = _bridge().call("apply_palette", asset_id=p.asset_id,
                                palette_json=p.palette_json)
        audit.info("apply_palette", params=locals(), result=result)
        return {"status": "ok", "result": result}
    except Exception as e:  # noqa: BLE001
        audit.error("apply_palette", str(e), params=locals())
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    mcp.run(transport="stdio")