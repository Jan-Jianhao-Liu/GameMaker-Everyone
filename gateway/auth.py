"""鉴权：API Key + 角色工具白名单 + AI-effort 动态裁剪。

每智能体角色只能调用其允许的工具集合：
- designer：只生成 GDD，不调工具
- supervisor：校验 + 回滚
- artist3d/artist2d：各自美术工具 + commit_asset
- coder：Godot 工具 + godot-ai 全构建工具 + snapshot
- qa：测试 + 校验 + godot-ai 视觉验证工具

AI-effort 滑块（借鉴 beckett-godot-mcp）：
- low:    仅核心工具（场景/节点/脚本/批量）→ ~15 个
- medium: 标准工具集（+资源/动画/材质/相机/编辑器/项目）→ ~25 个
- high:   全部工具（+UI/主题/TileMap/CSG/文件系统/信号/...）→ 37 个
"""

from __future__ import annotations

# ---------- AI-effort 滑块 ----------

EffortLevel = str  # "low" | "medium" | "high"

_EFFORT_CATEGORIES: dict[str, set[str]] = {
    "low": {
        "editor", "scene", "node", "script", "session", "batch",
    },
    "medium": {
        "editor", "scene", "node", "script", "session", "batch",
        "resource", "animation", "material", "camera", "project",
    },
    "high": {
        "editor", "scene", "node", "script", "session", "batch",
        "resource", "animation", "material", "camera", "project",
        "particle", "audio", "ui", "theme", "tilemap", "tileset",
        "gridmap", "csg", "filesystem", "input_map", "autoload",
        "signal", "api", "client", "game", "testing",
    },
}

_TOOL_TO_CATEGORY: dict[str, str] = {
    "editor_state": "editor", "node_get_properties": "node",
    "scene_get_hierarchy": "scene", "session_activate": "session",
    "session_manage": "session", "scene_manage": "scene",
    "scene_open": "scene", "scene_save": "scene",
    "node_create": "node", "node_find": "node",
    "node_manage": "node", "node_set_property": "node",
    "script_attach": "script", "script_create": "script",
    "script_manage": "script", "script_patch": "script",
    "resource_manage": "resource", "animation_create": "animation",
    "animation_manage": "animation", "material_manage": "material",
    "particle_manage": "particle", "camera_manage": "camera",
    "audio_manage": "audio", "ui_manage": "ui",
    "theme_manage": "theme", "tilemap_manage": "tilemap",
    "tileset_manage": "tileset", "gridmap_manage": "gridmap",
    "csg_manage": "csg", "editor_manage": "editor",
    "editor_reload_plugin": "editor", "editor_screenshot": "editor",
    "logs_read": "editor", "project_manage": "project",
    "project_run": "project", "game_manage": "game",
    "test_manage": "testing", "test_run": "testing",
    "filesystem_manage": "filesystem", "input_map_manage": "input_map",
    "autoload_manage": "autoload", "signal_manage": "signal",
    "api_manage": "api", "client_manage": "client",
    "batch_execute": "batch",
}


def filter_tools_by_effort(role: str, effort: EffortLevel = "high") -> set[str]:
    """按 AI-effort 级别裁剪角色可用工具。

    非 godot-ai 工具（Blender/Krita/Git 等）不受 effort 影响，始终保留。
    godot-ai 工具按其 category 是否在 _EFFORT_CATEGORIES[effort] 中过滤。
    """
    base = ROLE_TOOLS.get(role, set())
    if effort == "high":
        return set(base)
    allowed_cats = _EFFORT_CATEGORIES.get(effort, _EFFORT_CATEGORIES["high"])
    result: set[str] = set()
    for t in base:
        cat = _TOOL_TO_CATEGORY.get(t)
        if cat is None or cat in allowed_cats:
            result.add(t)
    return result


_GODOT_AI_CODER_TOOLS = {
    "editor_state",
    "node_get_properties",
    "scene_get_hierarchy",
    "session_activate",
    "session_manage",
    "scene_manage",
    "scene_open",
    "scene_save",
    "node_create",
    "node_find",
    "node_manage",
    "node_set_property",
    "script_attach",
    "script_create",
    "script_manage",
    "script_patch",
    "resource_manage",
    "animation_create",
    "animation_manage",
    "material_manage",
    "particle_manage",
    "camera_manage",
    "audio_manage",
    "ui_manage",
    "theme_manage",
    "tilemap_manage",
    "tileset_manage",
    "gridmap_manage",
    "csg_manage",
    "editor_manage",
    "project_manage",
    "project_run",
    "filesystem_manage",
    "input_map_manage",
    "autoload_manage",
    "signal_manage",
    "batch_execute",
}

_GODOT_AI_QA_TOOLS = {
    "editor_state",
    "node_get_properties",
    "scene_get_hierarchy",
    "session_activate",
    "session_manage",
    "scene_open",
    "editor_screenshot",
    "logs_read",
    "test_manage",
    "test_run",
    "game_manage",
    "editor_reload_plugin",
}

ROLE_TOOLS: dict[str, set[str]] = {
    "designer": set(),
    "supervisor": {"validate_export", "diff_status", "rollback"},
    "artist3d": {
        "create_primitive",
        "auto_uv",
        "assign_material",
        "export_fbx",
        "validate_export",
        "get_scene_info",
        "commit_asset",
    },
    "artist2d": {
        "create_canvas",
        "draw_rect",
        "draw_circle",
        "draw_line",
        "fill_layer",
        "export_png",
        "export_sprite_sheet",
        "apply_palette",
        "commit_asset",
    },
    "coder": {
        "import_asset",
        "create_scene",
        "attach_script",
        "set_level_data",
        "build_export",
        "run_headless_test",
        "snapshot",
    } | _GODOT_AI_CODER_TOOLS,
    "qa": {"run_headless_test", "validate_export", "diff_status"} | _GODOT_AI_QA_TOOLS,
}

VALID_ROLES = set(ROLE_TOOLS)


class AuthError(PermissionError):
    """鉴权失败。"""


class RoleAuth:
    """API Key + 角色工具白名单校验（支持 AI-effort 动态裁剪）。"""

    def __init__(
        self,
        api_keys: dict[str, str] | None = None,
        effort: EffortLevel = "high",
    ) -> None:
        self._api_keys = api_keys or {}
        self._effort = effort
        self._effort_cache: dict[str, set[str]] = {}

    @property
    def effort(self) -> EffortLevel:
        return self._effort

    @effort.setter
    def effort(self, value: EffortLevel) -> None:
        self._effort = value
        self._effort_cache.clear()

    def allowed_tools(self, role: str) -> set[str]:
        """获取角色在当前 effort 级别下的可用工具集。"""
        if role not in self._effort_cache:
            self._effort_cache[role] = filter_tools_by_effort(role, self._effort)
        return self._effort_cache[role]

    def resolve_role(self, api_key: str) -> str:
        """API Key → 角色名。未知 key 抛 AuthError。"""
        role = self._api_keys.get(api_key)
        if role is None:
            raise AuthError("无效 API Key")
        return role

    def check_tool(self, role: str, tool: str) -> None:
        """检查角色是否有权调用工具（考虑 effort 裁剪）。越权抛 AuthError。"""
        allowed = self.allowed_tools(role)
        if not allowed and role not in ROLE_TOOLS:
            raise AuthError(f"未知角色: {role}")
        if tool not in allowed:
            raise AuthError(f"角色 {role} 无权调用工具 {tool}（允许: {sorted(allowed)}）")


def is_authorized(role: str, tool: str, effort: EffortLevel = "high") -> bool:
    """便捷函数：角色在指定 effort 下是否有权调用工具。"""
    return tool in filter_tools_by_effort(role, effort)
