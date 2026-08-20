# mcp-servers/common

四个 MCP Server（blender/krita/godot/git）共享的基础设施。

## 模块

| 模块 | 职责 |
|---|---|
| `socket_bridge.py` | socket 桥基类：监听线程 + 指令队列 + 主线程出队执行（bpy/Krita 非线程安全） |
| `audit.py` | 审计日志：写入 `logs/<server>.log`，结构化错误码 |
| `param_validator.py` | 参数校验：工具函数签名的 pydantic 模型 |
| `path_whitelist.py` | 路径白名单：realpath 检查路径穿越，Windows 大小写不敏感 |

## 设计原则

- 所有 MCP Server 的工具函数签名、参数 Schema 独立成本包共享模块，避免四个 Server 各写一套参数校验。
- Phase 1–3 全部 stdio 通信（本地单机，最简、无端口暴露）；SSE/streamable-http 仅在 Phase 4 远程多机时启用。