# game-agent-factory

AI 智能体自动化游戏开发流水线。多智能体团队（策划/程序/美术/监理/测试）经 LangGraph 编排，通过 MCP 网关驱动 Blender/Krita/Godot/Git 自动产出可运行游戏构建包。

> 施工约束基线见 [`DECISIONS.md`](./DECISIONS.md)，方案全文见 [`智能体游戏施工团队 v2.md`](./智能体游戏施工团队%20v2.md)。

## 架构分层

```
┌────────────────────────────────────────────────────────┐
│ L0 模型层    Ollama(qwen3.5-4b/2b 本地) + 公有 API(GLM-4 Air/DeepSeek) │
├────────────────────────────────────────────────────────┤
│ L1 编排层    LangGraph（唯一调度层，checkpointer 恢复）         │
│   策划Agent · 程序Agent · 美术Agent(3D/2D) · 监理Agent · 测试Agent │
├────────────────────────────────────────────────────────┤
│ L2 网关层    MCP Gateway：鉴权 · 沙箱 · 白名单 · 路由 · 审计  │
├────────────────────────────────────────────────────────┤
│ L3 适配层    blender-mcp · krita-mcp · godot-mcp · git-mcp │
│             共享 mcp-servers/common/（socket桥/审计/校验/路径白名单）│
├────────────────────────────────────────────────────────┤
│ L4 基础设施   Gitea+LFS · SQLite(记忆/工单/锁/审计) · Ollama(Win原生)│
│             storage/ Repository 抽象层（SQLiteRepo→ArcadeRepo 可迁移）│
└────────────────────────────────────────────────────────┘
```

## 目录职责

| 目录 | 职责 |
|---|---|
| `contracts/` | 交付契约：GDD/资产清单/美术规范 Schema + validators.py（含 Kahn 检环） |
| `agents/` | LangGraph 智能体定义（designer/coder/artist3d/artist2d/qa/supervisor） |
| `mcp-servers/common/` | 四个 MCP Server 共享基础设施（socket 桥、审计、参数校验、路径白名单） |
| `mcp-servers/blender-mcp/` | Blender 3D 资产生产 MCP Server |
| `mcp-servers/krita-mcp/` | Krita 2D 资产生产 MCP Server |
| `mcp-servers/godot-mcp/` | Godot 项目施工 MCP Server |
| `mcp-servers/git-mcp/` | Git 提交/快照/回滚 MCP Server（GitPython + LFS） |
| `blender-addon/` | Blender 插件（socket 桥 + 白名单指令执行器，归属 blender-mcp） |
| `godot-plugin/` | Godot 编辑器插件（EditorScript 桥，归属 godot-mcp） |
| `gateway/` | MCP 网关（鉴权/沙箱/审计/速率限制） |
| `pipelines/` | LangGraph 工作流定义 |
| `sandbox/` | 白名单脚本池 + Docker 沙箱 |
| `storage/` | Repository 抽象层（SQLiteRepo / ArcadeRepo 可迁移） |
| `game/` | Godot 项目（Git LFS 管理） |
| `infra/` | Gitea/ArcadeDB/Ollama 配置 + versions.env + ports.env + llm.env |
| `logs/` | 审计日志 |

## 快速开始

```powershell
# 安装 just（跨平台任务入口）
winget install Casey.Just

# 初始化依赖
just init

# 自检
just check
just all
```

## 环境基线

- **OS**：Windows 单机优先（代码保持 Linux 可移植）
- **GPU**：RTX 2070 8GB
- **LLM**：混合模式（本地 qwen3.5-4b/2b + 公有 API）
- **Blender**：4.2 LTS
- **Godot**：4.4 stable
- **Python**：≥ 3.11，uv 包管理

详见 `DECISIONS.md` §1。