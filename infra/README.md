# infra

基础设施配置与部署脚本。

## 文件

| 文件 | 职责 |
|---|---|
| `versions.env` | 软件版本锁定（Blender 4.2 LTS / Godot 4.4.1 / MCP SDK） |
| `ports.env` | 端口分配（全部可配置，网关启动时探测占用） |
| `llm.env` | LLM 接入配置（混合模式：本地 Ollama + 云端公有 API） |
| `docker-compose.yml` | Gitea + 网关容器化（Ollama 宿主机原生） |
| `SECURITY.md` | 安全说明（内网绑定 / API Key / 沙箱 / 审计） |
| `scripts/check_lfs.py` | Git LFS 检测（未安装报错 + Windows 安装指引） |
| `scripts/pull_ollama.py` | Ollama 模型预拉 + 健康检查 |
| `scripts/seed_gitea.py` | Gitea 初始化 + game/ 仓库 + .gitattributes（LFS） |
| `scripts/export_offline.py` | 离线包导出（uv wheelhouse + ollama blob + docker save） |

## 部署

- **Ollama**：跑 Windows 原生版，不进容器（避免 WSL2 显存转发损耗）
- **Docker Desktop**（WSL2 后端）：仅跑 Gitea / 网关
- **任务入口**：`justfile`（跨平台，替代 Makefile）

## 常用命令

```bash
just init           # 安装依赖 + 检查 LFS + 预拉模型
just up             # 启动 Gitea + 网关
just seed           # 初始化 game/ 仓库（LFS 强制）
just demo           # 一键跑通示例游戏
just export-offline # 导出离线包
just all            # 全套自检
```

## 不部署的服务

| 服务 | 理由 |
|---|---|
| Redis | 任务锁与速率限制用 SQLite |
| Prefect | LangGraph 作唯一调度层 |
| ArcadeDB | Phase 1-2 用 SQLite，Phase 3 跨任务记忆图检索时启用 |
| GIMP/Linux | 2D 统一走 Krita |
