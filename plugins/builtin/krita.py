"""Krita 插件 — 2D 贴图生产工具链。"""

from __future__ import annotations

from plugins.base import PluginBase, ToolChain, ToolDef


class KritaPlugin(PluginBase):
    plugin_id = "krita"
    name = "Krita"
    plugin_type = "2d_editor"
    port = 19878

    def tools(self) -> list[ToolDef]:
        return [
            ToolDef("create_canvas", "创建画布", {"width": 256, "height": 256, "dpi": 72, "color_space": "RGBA8"}),
            ToolDef("fill_layer", "填充图层", {"layer_name": "background", "color": [200, 200, 200, 255]}),
            ToolDef("export_png", "导出 PNG", {"asset_id": "", "path": ""}),
            ToolDef("validate_export", "校验导出", {"path": ""}),
        ]

    def call(self, tool: str, params: dict) -> dict:
        return {"status": "ok", "result": {}}

    def tool_chains(self) -> dict[str, ToolChain]:
        return {
            "produce_texture": ToolChain("produce_texture", [
                {"tool": "create_canvas", "params": {"width": "{width}", "height": "{height}", "dpi": 72, "color_space": "RGBA8"}},
                {"tool": "fill_layer", "params": {"layer_name": "background", "color": [200, 200, 200, 255]}},
                {"tool": "export_png", "params": {"asset_id": "{asset_id}", "path": "{out_path}"}},
                {"tool": "validate_export", "params": {"path": "{out_path}"}},
            ]),
        }
