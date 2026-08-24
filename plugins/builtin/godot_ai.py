"""Godot-AI 插件 — godot-ai v3.1.5 的 45 个 MCP 工具。

通过 HTTP streamable-http 传输与 godot-ai Python 服务器通信：
  uvx --from "godot-ai==3.1.5" godot-ai --transport streamable-http --port 8001 --ws-port 9501

工具分类（45 个）:
  core(4):    editor_state, node_get_properties, scene_get_hierarchy, session_activate
  session(1): session_manage
  scene(3):   scene_manage, scene_open, scene_save
  node(4):    node_create, node_find, node_manage, node_set_property
  script(4):  script_attach, script_create, script_manage, script_patch
  resource(1): resource_manage
  animation(2): animation_create, animation_manage
  material(1): material_manage
  particle(1): particle_manage
  camera(1):  camera_manage
  audio(1):   audio_manage
  ui(1):      ui_manage
  theme(1):   theme_manage
  tilemap(1): tilemap_manage
  tileset(1): tileset_manage
  gridmap(1): gridmap_manage
  csg(1):     csg_manage
  editor(4):  editor_manage, editor_reload_plugin, editor_screenshot, logs_read
  project(2): project_manage, project_run
  game(1):    game_manage
  testing(2): test_manage, test_run
  filesystem(1): filesystem_manage
  input_map(1): input_map_manage
  autoload(1): autoload_manage
  signal(1):  signal_manage
  api(1):     api_manage
  client(1):  client_manage
  batch(1):   batch_execute
"""

from __future__ import annotations

from plugins.base import PluginBase, ToolChain, ToolDef

_GODOT_AI_TOOLS: list[ToolDef] = [
    ToolDef("editor_state", "获取编辑器状态", readonly=True, category="editor"),
    ToolDef("node_get_properties", "获取节点属性", readonly=True, category="node"),
    ToolDef("scene_get_hierarchy", "获取场景树", readonly=True, category="scene"),
    ToolDef("session_activate", "激活会话", category="session"),
    ToolDef("session_manage", "会话管理", category="session"),
    ToolDef("scene_manage", "场景管理（创建/删除/列表）", destructive=True, category="scene"),
    ToolDef("scene_open", "打开场景", category="scene"),
    ToolDef("scene_save", "保存场景", category="scene"),
    ToolDef("node_create", "创建节点", category="node"),
    ToolDef("node_find", "查找节点", readonly=True, category="node"),
    ToolDef("node_manage", "节点管理（移动/删除/复制）", destructive=True, category="node"),
    ToolDef("node_set_property", "设置节点属性", category="node"),
    ToolDef("script_attach", "挂载脚本到节点", category="script"),
    ToolDef("script_create", "创建脚本文件", category="script"),
    ToolDef("script_manage", "脚本管理", category="script"),
    ToolDef("script_patch", "局部修补脚本", category="script"),
    ToolDef("resource_manage", "资源管理（加载/保存/导入）", category="resource"),
    ToolDef("animation_create", "创建动画", category="animation"),
    ToolDef("animation_manage", "动画管理", category="animation"),
    ToolDef("material_manage", "材质管理", category="material"),
    ToolDef("particle_manage", "粒子系统管理", category="particle"),
    ToolDef("camera_manage", "相机管理", category="camera"),
    ToolDef("audio_manage", "音频管理", category="audio"),
    ToolDef("ui_manage", "UI 控件管理", category="ui"),
    ToolDef("theme_manage", "主题管理", category="theme"),
    ToolDef("tilemap_manage", "TileMap 管理", category="tilemap"),
    ToolDef("tileset_manage", "TileSet 管理", category="tileset"),
    ToolDef("gridmap_manage", "GridMap 管理", category="gridmap"),
    ToolDef("csg_manage", "CSG 几何管理", category="csg"),
    ToolDef("editor_manage", "编辑器管理（设置/快捷键）", category="editor"),
    ToolDef("editor_reload_plugin", "重载插件", category="editor"),
    ToolDef("editor_screenshot", "编辑器截图（视觉验证）", readonly=True, category="editor"),
    ToolDef("logs_read", "读取编辑器日志", readonly=True, category="editor"),
    ToolDef("project_manage", "项目设置管理", category="project"),
    ToolDef("project_run", "运行项目", category="project"),
    ToolDef("game_manage", "游戏运行管理", category="game"),
    ToolDef("test_manage", "测试管理", category="testing"),
    ToolDef("test_run", "运行测试", category="testing"),
    ToolDef("filesystem_manage", "文件系统管理", destructive=True, category="filesystem"),
    ToolDef("input_map_manage", "输入映射管理", category="input_map"),
    ToolDef("autoload_manage", "Autoload 管理", category="autoload"),
    ToolDef("signal_manage", "信号管理", category="signal"),
    ToolDef("api_manage", "API 管理", category="api"),
    ToolDef("client_manage", "客户端管理", category="client"),
    ToolDef("batch_execute", "批量执行多个工具调用", category="batch"),
]

assert len(_GODOT_AI_TOOLS) == 45, f"工具数应为 45，实际 {len(_GODOT_AI_TOOLS)}"


class GodotAIPlugin(PluginBase):
    plugin_id = "godot_ai"
    name = "Godot-AI 3.1.5"
    plugin_type = "game_engine"
    port = 8001

    def tools(self) -> list[ToolDef]:
        return list(_GODOT_AI_TOOLS)

    def call(self, tool: str, params: dict) -> dict:
        return {"status": "ok", "result": {}}

    def tool_chains(self) -> dict[str, ToolChain]:
        return {
            "build_scene_node_by_node": ToolChain(
                "build_scene_node_by_node",
                [
                    {"tool": "scene_manage", "params": {"action": "new", "name": "{scene_name}"}},
                    {"tool": "node_create", "params": {"type": "CharacterBody3D", "name": "Player", "parent": "root"}},
                    {"tool": "node_set_property", "params": {"node": "Player", "property": "transform", "value": "{player_transform}"}},
                    {"tool": "script_attach", "params": {"node": "Player", "script_path": "{player_script}"}},
                    {"tool": "scene_save", "params": {}},
                ],
            ),
            "visual_verify": ToolChain(
                "visual_verify",
                [
                    {"tool": "editor_screenshot", "params": {"viewport": "3d"}},
                    {"tool": "logs_read", "params": {"level": "error"}},
                ],
            ),
            "build_and_run": ToolChain(
                "build_and_run",
                [
                    {"tool": "scene_save", "params": {}},
                    {"tool": "project_run", "params": {}},
                ],
            ),
        }
