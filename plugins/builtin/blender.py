"""Blender 插件 — 3D 模型生产工具链。"""

from __future__ import annotations

from plugins.base import PluginBase, ToolChain, ToolDef


class BlenderPlugin(PluginBase):
    plugin_id = "blender"
    name = "Blender 4.2"
    plugin_type = "3d_editor"
    port = 19876

    def tools(self) -> list[ToolDef]:
        return [
            ToolDef("create_primitive", "创建基础体", {"prim_type": "CUBE", "name": "", "dimensions": [1, 1, 1]}),
            ToolDef("auto_uv", "自动 UV 展开", {"asset_id": ""}),
            ToolDef("assign_material", "赋材质", {"asset_id": "", "base_color": [0.8, 0.8, 0.8, 1]}),
            ToolDef("export_fbx", "导出 FBX", {"asset_id": "", "path": ""}),
            ToolDef("validate_export", "校验导出", {"path": ""}),
        ]

    def call(self, tool: str, params: dict) -> dict:
        return {"status": "ok", "result": {}}

    def tool_chains(self) -> dict[str, ToolChain]:
        return {
            "produce_model": ToolChain("produce_model", [
                {"tool": "create_primitive", "params": {"prim_type": "CUBE", "dimensions": [1, 1, 1]}},
                {"tool": "auto_uv", "params": {}},
                {"tool": "assign_material", "params": {"base_color": [0.8, 0.8, 0.8, 1], "roughness": 0.5, "metallic": 0.0}},
                {"tool": "export_fbx", "params": {}},
                {"tool": "validate_export", "params": {}},
            ]),
        }
