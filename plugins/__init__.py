"""插件抽象层 — 可插拔的引擎/编辑器/工具接口。

任何游戏引擎（Blender/Unity/Unreal）、美术编辑器（Krita/Photoshop/GIMP）、
版本控制（Git/Plastic）都实现为 PluginBase 子类，通过 config/plugins.json 注册。

核心概念：
  - PluginBase: 插件抽象基类，声明工具集 + 工具链 + 调用入口
  - ToolDef: 工具描述（名称/参数/说明）
  - PluginRegistry: 插件注册表，从 JSON 配置加载，按类型/ID 查询
"""
