"""Git 插件 — 版本控制工具。"""

from __future__ import annotations

from plugins.base import PluginBase, ToolChain, ToolDef


class GitPlugin(PluginBase):
    plugin_id = "git"
    name = "Git LFS"
    plugin_type = "vcs"
    port = 19879

    def tools(self) -> list[ToolDef]:
        return [
            ToolDef("commit_asset", "提交资产入库", {"asset_id": "", "file_paths": [], "message": ""}),
        ]

    def call(self, tool: str, params: dict) -> dict:
        return {"status": "ok", "result": {}}

    def tool_chains(self) -> dict[str, ToolChain]:
        return {
            "commit": ToolChain("commit", [
                {"tool": "commit_asset", "params": {}},
            ]),
        }
