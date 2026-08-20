# godot-plugin

Godot 编辑器插件：EditorScript 桥，通过本地 socket 接收 JSON 指令，在编辑器内安全执行。

**归属 MCP Server**：`mcp-servers/godot-mcp/`

## 关键约束

- **版本校验**：启动时校验 Godot 引擎版本（读 `infra/versions.env`），不匹配直接拒绝启动。
- **端口**：读 `infra/ports.env` 的 `GODOT_MCP_PORT`（默认 19877）。
- **路径逃逸**：所有文件写入操作必须在 `game/` 目录内，realpath 检查（Windows 下大小写不敏感）。
- **InputAdapter**：`attach_script` 的 character 模板须含 InputAdapter 节点，游戏逻辑通过 InputAdapter 读取输入而非直接 `Input.xxx`，为 Phase 3 二级自动化测试铺路。

## 安装与运行

```bash
# 1. 把 addons/gaf_godot_mcp/ 复制到 game/addons/（或符号链接）
# 2. Godot 编辑器 → 项目设置 → 插件 → 启用 "GAF Godot MCP"
# 3. 插件启用后 bridge 自动监听 GODOT_MCP_PORT（默认 19877）
# 4. MCP Server（stdio，由网关拉起）
uv run python mcp-servers/godot-mcp/server.py
```

## 白名单工具

| 工具 | 参数 | 说明 |
|---|---|---|
| import_asset | fbx_path, asset_id | 导入 FBX + 配置贴图压缩/mipmap |
| create_scene | scene_name, template | empty/2d/3d/character 四类模板 |
| attach_script | node_path, script_content | 挂载 GDScript（先语法检查） |
| set_level_data | level_id, json_path | 读策划数据表生成实体 |
| build_export | preset_name | --export-release 构建 Windows 桌面包 |
| run_headless_test | scene_path | 无头运行 + 错误日志 + 截图 |

## 场景模板

| 模板 | 根节点 | 特殊 |
|---|---|---|
| empty | Node | 空场景 |
| scene_2d | Node2D | 2D 场景 |
| scene_3d | Node3D | 3D 场景 |
| character | CharacterBody3D | 含 InputAdapter + CollisionShape3D + MeshInstance3D |