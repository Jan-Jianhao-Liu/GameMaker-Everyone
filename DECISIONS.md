# 施工前决策记录（DECISIONS.md）

> 本文档固化"智能体游戏施工团队"方案开工前的全部决策，作为后续所有 Prompt 施工的约束基线。
> 任何与本文档冲突的实现均视为越权，需先修订本文档再施工。

---

## 0. 元信息

| 项 | 值 |
|---|---|
| 方案文档 | 智能体游戏施工团队：完整设计施工方案 + 可执行 Prompt 集.md |
| 决策日期 | 2026-08-20 |
| 施工方 | 单人 + AI 结对开发 |
| 方案版本 | v1 → v2（见 §9 修订点） |
| 总工期 | 12 周（含每周 20% 隐性 buffer） |

---

## 1. 环境基线

| 维度 | 决策 |
|---|---|
| **OS** | Windows 单机优先；代码保持 Linux 可移植（docker-compose 天然可移植，不做双平台原生支持） |
| **GPU** | RTX 2070 8GB |
| **本地模型** | Ollama 已部署 qwen3.5-4b、qwen3.5-2b |
| **LLM 策略** | **混合模式**：本地 4b 做编排/工具调用/日志解析；公有 API 做策划文档与代码生成 |
| **公有 API** | 支持 GLM-4 Air / DeepSeek / Qwen Plus 任选，通过环境变量 `LLM_CLOUD_PROVIDER` + `LLM_CLOUD_API_KEY` 配置（**待用户提供 key**） |
| **网络** | 可访问外网（Docker Hub / Ollama Library / GitHub / PyPI） |
| **离线备份** | uv.lock + `ollama pull` 本地留存 + `docker save` 镜像导出，三样齐备即可断网重建 |

### 1.1 模型分流配置（写进 Prompt 5 / infra/llm.env）

| 角色 | 模型 | 走向 | 理由 |
|---|---|---|---|
| designer（策划） | GLM-4 Air / DeepSeek | 公有 API | 文档生成质量敏感 |
| supervisor（监理） | GLM-4 Air / DeepSeek | 公有 API | 审核质量敏感 |
| artist3d / artist2d | qwen3.5-4b | 本地 | 主要做工具调用，推理深度要求低 |
| coder（程序） | GLM-4 Air / DeepSeek | 公有 API | GDScript 生成质量敏感 |
| qa（测试） | qwen3.5-2b | 本地 | 只做日志解析 |

Ollama 运行参数：`OLLAMA_NUM_PARALLEL=2`、`OLLAMA_MAX_LOADED_MODELS=2`。

### 1.2 Ollama 部署方式

**跑 Windows 原生版，不进容器**（避免 WSL2 显存转发损耗）。Docker Desktop（WSL2 后端）仅跑 Gitea / ArcadeDB。

---

## 2. 软件版本锁定（写进 infra/versions.env）

| 软件 | 版本 | 理由 |
|---|---|---|
| Blender | 4.2 LTS（锁定 4.2.x） | LTS 内 bpy API 稳定；规避 4.3+ Extension 平台对 addon 分发的影响 |
| Godot | 4.4 stable（锁定具体小版本如 4.4.1） | 4.4 的 --headless 与导出管线比 4.3 更稳 |
| MCP SDK | 官方 `mcp` Python SDK，FastMCP + stdio | 版本固定在发布 tag，写入 uv.lock |
| Python 包管理 | uv + uv.lock，禁止裸 pip | Windows 单二进制，可复现，方便离线 wheelhouse |

### 2.1 端口分配（infra/ports.env，全部可配置）

| 服务 | 默认端口 | 说明 |
|---|---|---|
| Blender addon socket | 19876 | 避开知名 blender-mcp 默认 9876 |
| Godot 插件 socket | 19877 | 避开 9877 |
| Ollama | 11434 | 原生 |
| Gitea HTTP | 13000 | |
| ArcadeDB | 2424 | |

网关启动时先做端口探测，被占用则报错并提示改配置，**不自动换端口**。

---

## 3. 架构职责划分

| 议题 | 决策 |
|---|---|
| **LangGraph vs Prefect** | **删 Prefect**，LangGraph 作唯一调度层。`--resume` 由 LangGraph checkpointer（SQLite 后端）承担 |
| **ArcadeDB vs SQLite** | **分阶段**：Phase 1–2 全 SQLite；Phase 3 出现跨任务记忆图检索时迁移 ArcadeDB。所有持久化经 `storage/` Repository 抽象层（SQLiteRepo / ArcadeRepo） |
| **Redis vs SQLite 锁** | **SQLite 锁表 + BEGIN IMMEDIATE**，删 Redis。速率限制同用 SQLite 计数表 |
| **A2A 消息总线** | **不需要**，LangGraph 共享 StateGraph 状态即智能体间通信。supervisor 退回重做 = 图上条件边回跳 |

---

## 4. MCP Server 清单与排期

| MCP Server | 对应 Prompt | 排期 | 共享基础设施 |
|---|---|---|---|
| blender-mcp | Prompt 2 | M2 | `mcp-servers/common/`（socket 桥、审计日志、参数校验、路径白名单） |
| krita-mcp | **Prompt 2b（新增）** | M2 末尾并行 | 复用 common/，只写 Krita 特有工具 |
| godot-mcp | Prompt 3 | M3 | 复用 common/ |
| git-mcp | **Prompt 8（新增）** | M2 末尾并行 | 复用 common/，GitPython + LFS 强制 |

四个 MCP Server 的工具函数签名、参数 Schema 独立成 `mcp-servers/common/tools.py` 共享模块。

---

## 5. 契约 Schema 细节（影响 Prompt 1）

### 5.1 GDD 的 numeric_tables（放弃自由 kv，改三强类型子表）

```json
"numeric_tables": {
  "schema_version": "int",
  "damage":  { "entries": [{"unit_id": "str", "base": "number", "growth_per_level": "number", "cooldown": "number"}] },
  "economy": { "entries": [{"resource": "str", "initial": "number", "per_wave": "number", "cost_cap": "number"}] },
  "growth":  { "entries": [{"unit_id": "str", "hp_curve": "number[]", "unlock_level": "int"}] }
}
```

### 5.2 资产 dependencies（强制 DAG，禁止环）

validator 加 Kahn 拓扑排序（约 15 行），检测到环直接报错并列出环上 asset_id 链；生产顺序即拓扑序。**写进 Prompt 1 验收标准**。

### 5.3 naming_pattern 正则（固定四段式，类型枚举开头）

```
^(model|texture|ui|audio|anim)_[a-z][a-z0-9]*(_[a-z][a-z0-9]*)*$
```

- 分段数 2–4 段（`model_hero` 合法、`texture_ui_btn_confirm` 合法）
- 首段必须是类型枚举，全小写，禁止连续下划线和结尾下划线
- validator 附"自动纠正建议"功能（提示词能力留给监理智能体，Schema 层只做判定）

### 5.4 texture_size 校验（宽高分别 POT，不必相等；NPOT 结构化豁免）

```json
"texture_spec": {
  "require_power_of_two": true,
  "require_square": false,
  "npot_exception": { "allowed_types": ["ui"], "requires_flag": true }
}
```

UI 资产允许显式 `npot: true` 标记 + 监理白名单豁免（如九宫格 96×32）。

---

## 6. Demo 验收边界

### 6.1 M5 端到端 Demo = "可玩 MVP"

| 必须做 | 不做 |
|---|---|
| 重力、碰撞（方块 vs 地面/障碍） | 得分 UI |
| 键盘控制移动跳跃 | 音效 |
| 关卡终点触发过关 | 存档 |
| 三关难度递增（由 spawn_table 驱动） | 动画状态机 |
| 失败重开 | |

**判定标准**：一个 8 岁小孩不看说明能玩通三关。空场景+可移动方块不构成"游戏"，无法验证 `set_level_data` 数据驱动链路。

### 6.2 构建目标平台

**Windows 桌面导出为唯一验收目标**。Web 导出留作 Phase 4（SharedArrayBuffer 跨域隔离、wasm 行为差异会污染 QA 信号）。

### 6.3 QA 测试深度（分两级，M5 只做一级）

| 级别 | 内容 | 排期 |
|---|---|---|
| 一级 | 无头启动 + 错误日志捕获 + 关键节点自动截图。验收：人为注入 GDScript 报错，QA 能捕获并回流 | M5 必须 |
| 二级 | 模拟输入自动化玩法测试（`Input.action_press()` 驱动角色 + 超时判定是否到达终点） | Phase 3 |

二级要求游戏逻辑与输入解耦（可注入），需在 Prompt 3 的 `attach_script` 模板里**预置输入抽象层**。

---

## 7. 人工介入卡点（共 4 个）

| 卡点 | 触发 | 处理 |
|---|---|---|
| GDD 确认 | make-game 启动时 | 用户 y/n/修改意见 |
| supervisor 三轮超限 | 监理审核连续 3 轮不通过 | 转人工 |
| **金样本** | 每种资产类型（模型/贴图/UI）的第一个成品 | 人工确认后成为金样本，后续同类由监理对照自动校验（防风格累积漂移） |
| **发布确认** | build_export 产出构建包 | 默认 draft 状态，人工确认后转 release（防测试包误当正式版） |

---

## 8. 现有资产与 Godot 模板

**本地无 Godot 模板工程**，需在 GitHub 寻找或自建。

### 8.1 候选清单（待 M3 前选定验证）

| 候选 | 用途 | 备注 |
|---|---|---|
| `godotengine/godot-demo-projects` | 官方示例集合，含 2d/platformer、3d/platformer | 最稳，可拆出 CharacterBody3D + 输入控制 |
| `GDQuest/godot-design-patterns` | 状态机、事件总线等架构模式 | 适合角色动画状态机 |
| `bitbrain/godot-fsm` | 有限状态机插件 | |
| 社区 godot4-template 主题 | 项目骨架 | 需 webfetch 验证（本次抓取失败） |

### 8.2 倾向策略

基于 `godot-demo-projects` 的 `3d/platformer` 拆出基础模板 + **自建场景模板系统**（empty/2d/3d/character 四类 .tscn 模板）+ 自建 `LevelGenerator`（从 spawn_table 生成实体）+ 自建输入抽象层。

若 M3 前找到更合适的完整模板工程，可跳过"场景模板系统"约 3 天工作量。

---

## 9. 对原方案的修订点（v1 → v2 diff）

### 9.1 Prompt 1 修订
- 新增 `blender-addon/`、`godot-plugin/` 空目录及 README
- `numeric_tables` 改三强类型子表 + `schema_version`
- `naming_pattern` 定四段式正则
- `texture_size` 宽高分别 POT + UI 结构化豁免
- validator 增 Kahn 拓扑排序检环
- 包管理改 uv（禁止裸 pip）

### 9.2 Prompt 2 修订
- 端口 9876 → 19876
- 路径强制 pathlib.Path，禁止硬编码分隔符
- **显式写明 bpy 非线程安全**：addon 在 register() 启动 socket 监听线程 + 注册 `bpy.app.timers` 轮询队列；socket 线程只收指令入队，timer 在主线程出队执行 bpy 调用
- M2 第一周先做 50 行最小验证脚本（无头启动 → timer socket 收一条 create_primitive → 落盘 FBX），跑通后再写完整 addon

### 9.3 Prompt 3 修订
- 端口 9877 → 19877
- 启动时校验 Godot 版本，不匹配直接拒绝启动
- `attach_script` 模板**预置输入抽象层**（为 Phase 3 二级测试铺路）

### 9.4 Prompt 5 修订
- 模型分流配置（见 §1.1）
- 任务锁 SQLite BEGIN IMMEDIATE（删 Redis）
- 记忆走 Repository 抽象层（SQLiteRepo）
- LLM 接入：本地走 Ollama OpenAI 兼容接口；云端走公有 API（环境变量配置）

### 9.5 Prompt 7 修订
- **删 Prefect** server/agent
- **删 Redis**
- **删 GIMP/Linux 自动化路线**，2D 统一走 Krita
- Makefile → **justfile** 或纯 Python 入口 `python -m gaf <command>`
- Ollama 跑 Windows 原生不进容器
- Docker 仅跑 Gitea / ArcadeDB

### 9.6 新增 Prompt 2b（krita-mcp）
M2 末尾并行，复用 common/ socket 桥接架构，只写 Krita 特有工具。

### 9.7 新增 Prompt 8（git-mcp）
GitPython + LFS 强制，白名单工具：commit_asset / snapshot / diff_status / rollback。详见 v2 方案文档。

### 9.8 仓库结构 2.2 修订
根目录新增：
```
game-agent-factory/
├── blender-addon/      # Blender 插件（socket 桥 + 白名单指令执行器）
├── godot-plugin/       # Godot 编辑器插件（原在 mcp-servers/godot-mcp/ 内，统一外置）
├── storage/            # Repository 抽象层（SQLiteRepo / ArcadeRepo）
└── mcp-servers/common/ # 四个 MCP Server 共享基础设施
```

### 9.9 里程碑修订

| 阶段 | 内容 | Prompt | 周期 |
|---|---|---|---|
| M1 地基 | 骨架 + 契约 Schema | 1 | 1 周 |
| M2 单软件闭环 | Blender-MCP + krita-mcp + git-mcp | 2, 2b, 8 | 2 周 |
| M3 引擎闭环 | Godot-MCP + 端到端 demo | 3 | 2 周 |
| M4 安全与治理 | 网关 + 沙箱 + 审计 | 4 | 1 周 |
| M5 智能体团队 | 五角色编排 | 5 | **4 周**（原 3 周，扩 1 周应对联调不确定性） |
| M6 体验封装 | Prompt-to-Pipeline CLI | 6 | 1 周 |
| M7 私有化底座 | 全套 infra 一键部署 | 7 | 1 周 |

**总计 12 周**。

---

## 10. 待确认 / TODO

| 项 | 状态 | 阻塞 |
|---|---|---|
| 公有 API key（GLM-4 Air / DeepSeek / Qwen Plus 任选） | **待用户提供** | M5 起阻塞，M1–M4 不阻塞（本地 4b 够用） |
| Godot 模板工程最终选定 | M3 前验证 | M3 阻塞 |
| Blender 4.2 / Godot 4.4 本机安装版本核对 | M2/M3 启动前核对 | 局部阻塞 |
| 离线 wheelhouse 导出（若需断网兜底） | M7 后做 | 不阻塞 |

---

## 11. 决策溯源（27 问对应）

本文件 §1–§9 即对原 27 问的逐条固化，对应关系：

| 原问题 | 本文件章节 |
|---|---|
| Q1 OS | §1 |
| Q2 显存 | §1（2070 8GB） |
| Q3 并发推理 | §1.1 |
| Q4 网络 | §1 |
| Q5 Blender 版本 | §2 |
| Q6 Godot 版本 | §2 |
| Q7 MCP SDK | §2 |
| Q8 端口 | §2.1 |
| Q9 无头+socket 共存 | §9.2 |
| Q10 LangGraph vs Prefect | §3 |
| Q11 ArcadeDB vs SQLite | §3 |
| Q12 Redis vs SQLite 锁 | §3 |
| Q13 A2A | §3 |
| Q14 krita-mcp | §4、§9.6 |
| Q15 git-mcp | §4、§9.7 |
| Q16 blender-addon 目录 | §9.8 |
| Q17 numeric_tables | §5.1 |
| Q18 dependencies 环 | §5.2 |
| Q19 naming_pattern | §5.3 |
| Q20 texture_size | §5.4 |
| Q21 Demo 复杂度 | §6.1 |
| Q22 构建平台 | §6.2 |
| Q23 QA 深度 | §6.3 |
| Q24 人工卡点 | §7 |
| Q25 人力 buffer | §0、§9.9 |
| Q26 包管理 | §2 |
| Q27 现有资产 | §8 |