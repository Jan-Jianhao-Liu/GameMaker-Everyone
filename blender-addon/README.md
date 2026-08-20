# blender-addon

Blender 插件：socket 桥 + 白名单指令执行器。

**归属 MCP Server**：`mcp-servers/blender-mcp/`

## 关键约束

- **bpy 非线程安全**：addon 在 `register()` 启动 socket 监听线程 + 注册 `bpy.app.timers` 定时器；socket 线程只收指令入队，timer 在主线程出队执行 bpy 调用。
- **无头模式**：`--background` 下 `bpy.app.timers` 仍执行（官方支持）。
- **端口**：读 `infra/ports.env` 的 `BLENDER_MCP_PORT`（默认 19876）。
- **路径**：全部 `pathlib.Path`，禁止硬编码分隔符。

## 施工阶段

M2 第一周先做 50 行最小验证脚本（`tests/` 下）：无头启动 → timer socket 收一条 create_primitive → 落盘 FBX。跑通后再写完整 addon。

## 无头模式运行（Windows 与 Linux 通用）

```bash
# 1. 安装 addon：把 blender-addon/game_agent_factory/ 复制到 Blender 的 addons 目录
#    或用 --python-expr 动态加载（开发模式）

# 2. 无头启动 + 加载 addon（socket server 自动启动）
blender --background --python-expr "import sys; sys.path.insert(0, r'blender-addon'); import game_agent_factory; game_agent_factory.register()"

# 3. 最小验证脚本（无头跑通 socket 桥 → 落盘 FBX）
blender --background --python blender-addon/tests/minimal_verify.py -- --out ./test_verify.fbx --port 19876

# 4. MCP Server（stdio，由网关或 MCP 客户端拉起）
uv run python mcp-servers/blender-mcp/server.py
```

端口可通过环境变量 `BLENDER_MCP_PORT` 覆盖，或改 `infra/ports.env`。

## 白名单工具

| 工具 | 参数 | 说明 |
|---|---|---|
| create_primitive | prim_type, name, dimensions | CUBE/SPHERE/CYLINDER/PLANE/CONE/TORUS |
| auto_uv | asset_id | 智能投影展 UV |
| assign_material | asset_id, base_color, roughness, metallic | PBR 材质 |
| export_fbx | asset_id, path | 强制 Y-up、米、选中物体、apply modifiers |
| validate_export | path | 调 art-spec.schema.json 校验 |
| get_scene_info | — | 返回场景资产列表 |