"""Godot 插件 — 游戏引擎构建工具链。"""

from __future__ import annotations

from plugins.base import PluginBase, ToolChain, ToolDef


class GodotPlugin(PluginBase):
    plugin_id = "godot"
    name = "Godot 4.4"
    plugin_type = "game_engine"
    port = 19877

    def tools(self) -> list[ToolDef]:
        return [
            ToolDef("import_asset", "导入资产", {"asset_id": "", "path": ""}),
            ToolDef("create_scene", "创建场景", {"scene_name": "Main", "template": "scene_3d"}),
            ToolDef("attach_script", "挂载脚本", {"node": "Player", "script_template": "character"}),
            ToolDef("set_level_data", "设置关卡数据", {"levels": []}),
            ToolDef("build_export", "构建导出", {"platform": "windows", "output_path": ""}),
            ToolDef("run_headless_test", "无头测试", {"build_path": ""}),
        ]

    def call(self, tool: str, params: dict) -> dict:
        return {"status": "ok", "result": {}}

    def tool_chains(self) -> dict[str, ToolChain]:
        return {
            "build_game": ToolChain("build_game", [
                {"tool": "create_scene", "params": {"scene_name": "Main", "template": "scene_3d"}},
                {"tool": "attach_script", "params": {"node": "Player", "script_template": "character"}},
                {"tool": "set_level_data", "params": {"levels": "{levels}"}},
                {"tool": "build_export", "params": {"platform": "windows", "output_path": "{build_output}"}},
            ]),
            "test_game": ToolChain("test_game", [
                {"tool": "run_headless_test", "params": {"build_path": "{build_path}"}},
            ]),
        }
