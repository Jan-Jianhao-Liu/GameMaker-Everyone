"""请求路由：按 tool name 映射到 MCP Server。"""

from __future__ import annotations

TOOL_TO_SERVER: dict[str, str] = {
    "create_primitive": "blender",
    "auto_uv": "blender",
    "assign_material": "blender",
    "export_fbx": "blender",
    "validate_export": "blender",
    "get_scene_info": "blender",
    "create_canvas": "krita",
    "draw_rect": "krita",
    "draw_circle": "krita",
    "draw_line": "krita",
    "fill_layer": "krita",
    "export_png": "krita",
    "export_sprite_sheet": "krita",
    "apply_palette": "krita",
    "import_asset": "godot",
    "create_scene": "godot",
    "attach_script": "godot",
    "set_level_data": "godot",
    "build_export": "godot",
    "run_headless_test": "godot",
    "commit_asset": "git",
    "snapshot": "git",
    "diff_status": "git",
    "rollback": "git",
}


class ToolRouteError(KeyError):
    """未知工具，无法路由。"""


def route(tool: str) -> str:
    """tool name → server name（blender/krita/godot/git）。"""
    server = TOOL_TO_SERVER.get(tool)
    if server is None:
        raise ToolRouteError(f"未知工具，无法路由: {tool}")
    return server
