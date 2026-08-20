"""鉴权：API Key + 角色工具白名单。

每智能体角色只能调用其允许的工具集合：
- designer：只生成 GDD，不调工具
- supervisor：校验 + 回滚
- artist3d/artist2d：各自美术工具 + commit_asset
- coder：Godot 工具 + snapshot（build_export 仅 coder，美术禁止）
- qa：测试 + 校验
"""

from __future__ import annotations

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
    },
    "qa": {"run_headless_test", "validate_export", "diff_status"},
}

VALID_ROLES = set(ROLE_TOOLS)


class AuthError(PermissionError):
    """鉴权失败。"""


class RoleAuth:
    """API Key + 角色工具白名单校验。"""

    def __init__(self, api_keys: dict[str, str] | None = None) -> None:
        self._api_keys = api_keys or {}

    def resolve_role(self, api_key: str) -> str:
        """API Key → 角色名。未知 key 抛 AuthError。"""
        role = self._api_keys.get(api_key)
        if role is None:
            raise AuthError("无效 API Key")
        return role

    def check_tool(self, role: str, tool: str) -> None:
        """检查角色是否有权调用工具。越权抛 AuthError。"""
        allowed = ROLE_TOOLS.get(role)
        if allowed is None:
            raise AuthError(f"未知角色: {role}")
        if tool not in allowed:
            raise AuthError(f"角色 {role} 无权调用工具 {tool}（允许: {sorted(allowed)}）")


def is_authorized(role: str, tool: str) -> bool:
    """便捷函数：角色是否有权调用工具。"""
    return tool in ROLE_TOOLS.get(role, set())
