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
    "editor_state": "godot_ai",
    "node_get_properties": "godot_ai",
    "scene_get_hierarchy": "godot_ai",
    "session_activate": "godot_ai",
    "session_manage": "godot_ai",
    "scene_manage": "godot_ai",
    "scene_open": "godot_ai",
    "scene_save": "godot_ai",
    "node_create": "godot_ai",
    "node_find": "godot_ai",
    "node_manage": "godot_ai",
    "node_set_property": "godot_ai",
    "script_attach": "godot_ai",
    "script_create": "godot_ai",
    "script_manage": "godot_ai",
    "script_patch": "godot_ai",
    "resource_manage": "godot_ai",
    "animation_create": "godot_ai",
    "animation_manage": "godot_ai",
    "material_manage": "godot_ai",
    "particle_manage": "godot_ai",
    "camera_manage": "godot_ai",
    "audio_manage": "godot_ai",
    "ui_manage": "godot_ai",
    "theme_manage": "godot_ai",
    "tilemap_manage": "godot_ai",
    "tileset_manage": "godot_ai",
    "gridmap_manage": "godot_ai",
    "csg_manage": "godot_ai",
    "editor_manage": "godot_ai",
    "editor_reload_plugin": "godot_ai",
    "editor_screenshot": "godot_ai",
    "logs_read": "godot_ai",
    "project_manage": "godot_ai",
    "project_run": "godot_ai",
    "game_manage": "godot_ai",
    "test_manage": "godot_ai",
    "test_run": "godot_ai",
    "filesystem_manage": "godot_ai",
    "input_map_manage": "godot_ai",
    "autoload_manage": "godot_ai",
    "signal_manage": "godot_ai",
    "api_manage": "godot_ai",
    "client_manage": "godot_ai",
    "batch_execute": "godot_ai",
}


class ToolRouteError(KeyError):
    """未知工具，无法路由。"""


def route(tool: str) -> str:
    """tool name → server name（blender/krita/godot/git）。"""
    server = TOOL_TO_SERVER.get(tool)
    if server is None:
        raise ToolRouteError(f"未知工具，无法路由: {tool}")
    return server
