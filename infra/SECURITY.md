# 安全说明文档

## 1. 网络绑定

所有服务绑定 `127.0.0.1` 内网 IP，不对外暴露：

| 服务 | 绑定地址 | 端口 |
|---|---|---|
| Gitea HTTP | 127.0.0.1:13000 | 13000 |
| Gitea SSH | 127.0.0.1:13022 | 13022 |
| 网关 | 127.0.0.1:18080 | 18080 |
| Ollama | 127.0.0.1:11434 | 11434 |
| Blender addon socket | 127.0.0.1:19876 | 19876 |
| Godot 插件 socket | 127.0.0.1:19877 | 19877 |
| Krita 插件 socket | 127.0.0.1:19878 | 19878 |
| Git MCP socket | 127.0.0.1:19879 | 19879 |

如需跨机访问，通过 SSH 隧道转发，不直接改绑定为 0.0.0.0。

## 2. API Key 管理

- 云端 LLM API key 通过环境变量 `LLM_CLOUD_API_KEY` 注入，不写入代码或配置文件
- 各智能体角色的 API key 在 `gaf/cli.py` 的 `_ROLE_KEYS` 中定义默认值（仅本地开发用）
- 生产环境通过 `--api-key` 参数或环境变量注入真实 key

## 3. 沙箱隔离

- 网关 `Sandbox` 限制所有文件操作在 `game/` 与 `sandbox/` 目录内
- `realpath` 检查路径穿越（Windows 下大小写不敏感）
- 危险操作（批量删除、任意 shell）一律拒绝

## 4. 审计日志

- 所有网关调用记录到 SQLite 审计表（`logs/audit.db`）
- 字段：时间、角色、工具、参数摘要、结果状态
- 提供 `AuditDB.query()` API 供回溯

## 5. 速率限制

- 每角色每分钟最大 60 次调用（防死循环刷爆 Blender）
- 超限拒绝并记审计

## 6. Git LFS

- `*.fbx` / `*.png` / `*.wav` 等大文件强制走 LFS
- LFS 未安装时 `check_lfs` 脚本报错退出，不静默降级为普通提交

## 7. 容器隔离

- Docker Desktop（WSL2 后端）仅跑 Gitea + 网关
- Ollama 跑宿主机原生（避免 WSL2 显存转发损耗）
- 容器通过 `host.docker.internal` 访问宿主机 Ollama