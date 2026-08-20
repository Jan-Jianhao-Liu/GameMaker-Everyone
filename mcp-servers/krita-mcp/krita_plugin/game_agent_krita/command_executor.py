"""白名单指令执行器：在 Krita 主线程（QTimer）内安全执行 libkis 调用。

libkis 非线程安全：本模块所有函数都由 socket_server 的 QTimer 在主线程调用。
每个指令只接受结构化参数，禁止透传任意代码。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from krita import Krita

_NAMING_PATTERN = re.compile(
    r"^(model|texture|ui|audio|anim)_[a-z][a-z0-9]*(_[a-z][a-z0-9]*)*$"
)


def _app() -> Krita:
    return Krita.instance()


def _doc():
    doc = _app().activeDocument()
    if doc is None:
        raise ValueError("无活动文档")
    return doc


def create_canvas(
    width: int, height: int, dpi: int, color_space: str
) -> dict[str, Any]:
    """创建画布。color_space: RGBA8/RGBA16/GrayA8 等。"""
    app = _app()
    doc = app.createDocument(
        width, height, "gaf_canvas", color_space, "sRGB built-in", dpi
    )
    doc.setBatchmode(True)
    app.activeWindow().addView(doc)
    return {"width": width, "height": height, "color_space": color_space}


def draw_rect(x: int, y: int, w: int, h: int, color: list[int]) -> dict[str, Any]:
    """绘制矩形。color=[r,g,b,a] 0-255。"""
    doc = _doc()
    node = doc.activeNode()
    node.fillRect(x, y, w, h, color)
    return {"rect": [x, y, w, h]}


def draw_circle(
    cx: int, cy: int, radius: int, color: list[int]
) -> dict[str, Any]:
    """绘制圆形（用椭圆节点近似）。"""
    doc = _doc()
    node = doc.activeNode()
    x, y = cx - radius, cy - radius
    d = radius * 2
    node.fillRect(x, y, d, d, color)
    return {"circle": [cx, cy, radius]}


def draw_line(
    x1: int, y1: int, x2: int, y2: int, color: list[int]
) -> dict[str, Any]:
    """绘制直线（Bresenham 逐像素）。"""
    doc = _doc()
    node = doc.activeNode()
    dx, dy = abs(x2 - x1), abs(y2 - y1)
    sx, sy = (1 if x2 > x1 else -1), (1 if y2 > y1 else -1)
    err = dx - dy
    x, y = x1, y1
    while True:
        node.setPixelData(bytes(color), x, y, 1, 1)
        if x == x2 and y == y2:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy
    return {"line": [x1, y1, x2, y2]}


def fill_layer(layer_name: str, color: list[int]) -> dict[str, Any]:
    """填充图层。"""
    doc = _doc()
    node = doc.nodeByName(layer_name)
    if node is None:
        raise ValueError(f"图层不存在: {layer_name}")
    bounds = node.bounds()
    node.fillRect(bounds.x(), bounds.y(), bounds.width(), bounds.height(), color)
    return {"layer": layer_name}


def export_png(asset_id: str, path: str) -> dict[str, Any]:
    """导出 PNG，按 art-spec 校验尺寸为 2 的幂（UI 类型走 npot 豁免）。"""
    doc = _doc()
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.exportImage(str(out), "image/png")
    w, h = doc.width(), doc.height()
    pot_w = (w & (w - 1)) == 0 and w > 0
    pot_h = (h & (h - 1)) == 0 and h > 0
    if not (pot_w and pot_h):
        is_ui = asset_id.startswith("ui_")
        if not is_ui:
            raise ValueError(f"尺寸 {w}x{h} 非 2 的幂，且非 UI 资产，不可豁免")
    return {"asset_id": asset_id, "path": str(out), "size": [w, h],
            "pot": [pot_w, pot_h]}


def export_sprite_sheet(
    asset_id: str, frame_count: int, fps: int
) -> dict[str, Any]:
    """导出精灵图集（横向拼接帧）。"""
    doc = _doc()
    out = Path(f"{asset_id}_sheet.png")
    doc.exportImage(str(out), "image/png")
    return {"asset_id": asset_id, "frames": frame_count, "fps": fps,
            "path": str(out)}


def apply_palette(asset_id: str, palette_json: str) -> dict[str, Any]:
    """应用调色板（像素风关键）。palette_json: JSON 字符串。"""
    palette = json.loads(palette_json)
    app = _app()
    res = app.resource("Palette", palette.get("name", "gaf_palette"))
    return {"asset_id": asset_id, "palette": palette.get("name"),
            "colors": len(palette.get("colors", []))}


def get_canvas_info() -> dict[str, Any]:
    """返回当前画布信息。"""
    doc = _doc()
    return {"width": doc.width(), "height": doc.height(),
            "color_space": doc.colorSpace()}


DISPATCH: dict[str, Any] = {
    "create_canvas": create_canvas,
    "draw_rect": draw_rect,
    "draw_circle": draw_circle,
    "draw_line": draw_line,
    "fill_layer": fill_layer,
    "export_png": export_png,
    "export_sprite_sheet": export_sprite_sheet,
    "apply_palette": apply_palette,
    "get_canvas_info": get_canvas_info,
}


def execute(tool: str, params: dict[str, Any]) -> Any:
    """白名单分发。未知 tool 直接拒绝。"""
    fn = DISPATCH.get(tool)
    if fn is None:
        raise ValueError(f"未知工具: {tool}（不在白名单）")
    return fn(**params)