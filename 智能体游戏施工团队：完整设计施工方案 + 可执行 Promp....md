# 智能体游戏施工团队：完整设计施工方案 + 可执行 Prompt 集

## 一、方案定位与业界对标

在给出施工方案前，先明确两个来自信源的关键判断，作为方案的依据：

1. **多智能体团队化已是成熟工程路线**：目前已有在 Discord 上跑通 OpenClaw 六智能体集群（含 A2A 协作）的深度实战案例，也有完整部署指南、五角色协作操作系统的技术拆解，甚至有个人以约 2700 元成本搭建 24 小时运转 AI 团队的实践，以及“自动发现 3 倍 Bug、快 20 倍”的自主智能体团队框架。你规划的“策划/程序/美术/监理/测试”五角色分工与这些实践中的角色化协作模式高度一致。
2. **AI 智能体直接生成游戏已有先例可对标**：Gameable 已实现 AI Agents 构建浏览器游戏，Portal 展示了 Prompt-to-Game 的一句话生成游戏路径，国内也有基于 AI Agent 的小游戏开发实践 和智能体+领域大模型驱动的端到端游戏生成框架解析。你的方案相当于把这些“云端黑盒产品”拆开，用全开源栈自建同能力，且保留人工介入节点——定位更可控。
3. **美术自动化工具链有补充选项**：Blender 自动化脚本已有成体系的文档参考；GIMP 也支持 Python 自动化处理图像（如自动海报构图项目、Linux 下 GIMP 图像自动化处理），可作为 Krita 之外的第二条 2D 自动化路线。

***

## 二、最终架构设计（施工蓝图）

### 2.1 系统分层

```
┌────────────────────────────────────────────────────────┐
│ L0 模型层    Ollama + Qwen3 / GLM4（OpenAI 兼容接口）      │
├────────────────────────────────────────────────────────┤
│ L1 编排层    LangGraph                                  │
│   策划Agent · 程序Agent · 美术Agent(3D/2D) · 监理Agent · 测试Agent │
├────────────────────────────────────────────────────────┤
│ L2 网关层    MCP Gateway：鉴权 · 沙箱 · 白名单 · 路由 · 审计  │
├────────────────────────────────────────────────────────┤
│ L3 适配层    blender-mcp · krita-mcp · godot-mcp · git-mcp │
├────────────────────────────────────────────────────────┤
│ L4 基础设施   Gitea+LFS · ArcadeDB(记忆/工单) · Prefect(编排) │
└────────────────────────────────────────────────────────┘
```

### 2.2 推荐仓库结构（Monorepo）

```
game-agent-factory/
├── contracts/              # 交付契约（第一阶段就要建）
│   ├── gdd.schema.json         # 游戏设计文档 Schema
│   ├── asset-manifest.schema.json  # 资产清单 Schema
│   └── art-spec.schema.json    # 美术规范 Schema（尺寸/格式/轴向）
├── agents/                 # LangGraph 智能体定义
│   ├── designer/  coder/  artist3d/  artist2d/  qa/  supervisor/
├── mcp-servers/
│   ├── blender-mcp/
│   ├── krita-mcp/
│   ├── godot-mcp/
│   └── git-mcp/
├── gateway/                # MCP 网关（鉴权/沙箱/审计日志）
├── pipelines/              # Prefect 工作流
├── sandbox/                # 白名单脚本池 + Docker 沙箱
├── game/                   # Godot 项目（Git LFS 管理）
└── infra/                  # Gitea / ArcadeDB / Ollama 的 docker-compose
```

### 2.3 核心契约（所有智能体的“接口”）

三个 JSON Schema 是整套系统的地基：

* **GDD Schema**：玩法描述、关卡配置、数值表——程序智能体的唯一输入
* **资产清单 Schema**：资产 ID、类型（模型/贴图/UI/音效）、归属场景、依赖关系
* **美术规范 Schema**：贴图 2 幂尺寸、FBX 轴向（Y-up）、命名规则（`char_hero_body`）、导出格式——监理智能体据此自动拦截不合规产出

***

## 三、施工 Prompt 集

> 使用方式：按阶段顺序，一次投喂一个 Prompt 给你的编码智能体（如 Claude Code / OpenClaw Worker）。每个 Prompt 都自带验收标准，方便你检查产出。

### 📌 Prompt 1：项目骨架 + 契约 Schema

```
你是一位资深 Python 后端架构师。请为我搭建一个名为 game-agent-factory 的 Monorepo 项目骨架，用于构建"AI 智能体自动化游戏开发流水线"。

要求：
1. 按以下结构创建目录：contracts/、agents/、mcp-servers/{blender,krita,godot,git}-mcp/、gateway/、pipelines/、sandbox/、game/、infra/
2. 在 contracts/ 下编写三个 JSON Schema（含中文注释字段 description）：
   a) gdd.schema.json：游戏设计文档。字段包括 game_title、genre、core_loop、levels[]（level_id/name/difficulty/spawn_table）、numeric_tables{}
   b) asset-manifest.schema.json：资产清单。字段包括 assets[]，每项含 asset_id、type(enum: model/texture/ui/audio/anim)、target_scene、dependencies[]、status(enum: pending/in_review/delivered/rejected)
   c) art-spec.schema.json：美术规范。含 texture_size(必须是2的幂)、fbx_axis(枚举固定 Y_UP)、naming_pattern(正则)、allowed_formats[]
   并为每个 Schema 编写对应的 Python 校验函数（用 jsonschema 库），放在 contracts/validators.py
3. 创建 pyproject.toml（统一 uv/pip 管理，依赖：langgraph、mcp、jsonschema、pydantic）
4. 创建 README.md，写清各目录职责和整体架构分层图（ASCII）

验收标准：python -c "from contracts.validators import validate_gdd" 可运行；三个 Schema 能通过 jsonschema 校验器自检。
```

### 📌 Prompt 2：Blender MCP Server

```
你是一位 Blender Python API(bpy) 专家 + MCP 协议开发者。请在 mcp-servers/blender-mcp/ 下实现一个 MCP Server，让 AI 智能体能够安全地自动化 Blender 3D 资产生产。

技术要求：
1. 用 Python 官方 mcp SDK（FastMCP）实现，通过 stdio 通信
2. Blender 端：写一个 addon（game-agent-factory/blender-addon/），内置一个 socket server（端口 9876）接收 JSON 指令，在 Blender 主线程安全执行 bpy 脚本
3. MCP Server 端暴露以下白名单工具（每个工具只接受结构化参数，禁止透传任意代码）：
   - create_primitive(type, name, dimensions)：创建基础几何体
   - auto_uv(asset_id)：智能投影自动展 UV
   - assign_material(asset_id, base_color, roughness, metallic)：创建并赋予基础 PBR 材质
   - export_fbx(asset_id, path)：按规范导出（强制 Y-up、单位米、只导出选中物体、apply modifiers）
   - validate_export(path)：调用 contracts/art-spec.schema.json 校验导出物
   - get_scene_info()：返回当前场景资产列表
4. 所有指令执行写入审计日志（logs/blender-mcp.log），失败时返回结构化错误码
5. 编写 docker-compose 或说明文档，描述无头模式（blender --background --python）运行方式

验收标准：Blender 打开任意场景后，用 MCP 客户端调用 create_primitive → auto_uv → export_fbx 三步，能在指定目录得到符合 art-spec 的 FBX 文件。
```

### 📌 Prompt 3：Godot MCP Server

```
你是一位 Godot 4 引擎专家。请在 mcp-servers/godot-mcp/ 下实现 MCP Server，让 AI 智能体自动化 Godot 项目施工。

技术要求：
1. 采用"Godot Editor 插件 + 外部 MCP Server"双件套架构：
   a) Godot 插件（godot-plugin/）：GDScript 实现 EditorScript 桥，通过本地 socket 或 HTTP（端口 9877）接收 JSON 指令，在编辑器内安全执行
   b) MCP Server（Python FastMCP）：暴露工具并转发指令给插件
2. 白名单工具：
   - import_asset(fbx_path, asset_id)：导入 FBX 并自动配置导入参数（贴图压缩、mipmap）
   - create_scene(scene_name, template)：从模板创建场景（空场景/2D场景/3D场景/角色场景）
   - attach_script(node_path, script_content)：为节点挂载 GDScript（先做语法检查，失败则拒绝）
   - set_level_data(level_id, json_path)：读取策划数据表并生成场景内实体
   - build_export(preset_name)：调用 Godot 命令行（--export-release）构建测试包
   - run_headless_test(scene_path)：无头运行场景并捕获错误日志与截图
3. 所有涉及文件写入的操作必须在 game/ 仓库目录内，路径逃逸直接拒绝
4. 输出详细中文注释和调试指南

验收标准：通过 MCP 调用，完成"导入一个 FBX → 创建 3D 场景 → 挂载脚本 → 构建出可运行测试包"全流程。
```

### 📌 Prompt 4：MCP 网关 + 沙箱

```
你是一位安全架构师。请在 gateway/ 下实现 MCP 网关，统一管理所有软件适配器的访问。

要求：
1. 基于 Python 实现，功能：
   - 请求路由：按 tool name 前缀路由到 blender-mcp / godot-mcp / krita-mcp / git-mcp
   - 鉴权：API Key + 工具级白名单（每个智能体角色只能调用其允许的工具集合，例如美术 Agent 禁止调用 build_export）
   - 沙箱：所有文件操作限制在 game/ 与 sandbox/ 目录内，用 realpath 检查路径穿越；危险操作（批量删除、任意 shell）一律拒绝
   - 审计：所有调用记录到 ArcadeDB 或 SQLite（时间、角色、工具、参数摘要、结果状态），并提供查询 API
   - 速率限制：每智能体每分钟最大调用数，防止死循环刷爆 Blender
2. 提供 docker-compose.yml，将网关与各 MCP Server 容器化
3. 编写压力测试脚本模拟 5 个智能体并发调用

验收标准：越权调用被拒绝并记入审计日志；正常调用链路延迟 < 200ms。
```

### 📌 Prompt 5：五角色智能体编排

```
你是一位 LangGraph 多智能体系统专家。请在 agents/ 下实现五角色游戏开发智能体团队，参考业界已验证的"角色分工 + 自审查循环"模式。

角色定义（每个角色一个子图 subgraph）：
1. designer（策划）：输入用户需求文本，调用 LLM 生成符合 contracts/gdd.schema.json 的设计文档 + 资产清单；产出后自动进入 supervisor 审核
2. supervisor（监理）：调用 contracts/validators.py 校验三份契约的合规性；不合规则携带错误信息退回对应角色重做（最多 3 轮，超限转人工）
3. artist3d / artist2d（美术）：从资产清单领取状态为 pending 的资产，经网关调用 blender-mcp / krita-mcp 生产资产，产出后自动 validate，通过则提交 git-mcp 入库（Git LFS）
4. coder（程序）：拉取已交付资产 + GDD，经网关调用 godot-mcp 创建场景、挂载脚本、构建测试包
5. qa（测试）：调用 godot-mcp 的 run_headless_test，收集报错与截图，产出缺陷报告回流给 coder / artist

编排要求：
- 用 LangGraph StateGraph 串联，状态对象包含：task_id、gdd、manifest、build_result、defects[]
- 引入任务锁：同一 asset_id 同时只允许一个智能体操作（用 Redis 或 SQLite 锁表实现）
- 每个智能体执行历史写入 ArcadeDB（或先用 SQLite 表 memory 表替代），字段：agent、task_id、action、outcome、lesson（用于沉淀失败经验）
- LLM 接入：统一走 Ollama 的 OpenAI 兼容接口（http://localhost:11434/v1），模型名可配置

验收标准：跑通端到端 demo——输入"做一个有 3 个关卡的方块跳跃游戏"，系统自动产出：GDD 文档、1 个 FBX 方块模型、Godot 工程、1 个可运行的测试构建包。
```

### 📌 Prompt 6：Prompt-to-Pipeline 入口

```
你是产品工程师。请为 game-agent-factory 增加一个"一句话启动流水线"的 CLI 入口（make-game），对标业界 Prompt-to-Game 产品的体验。

要求：
1. 命令：make-game "做一个像素风塔防游戏，10 波敌人，3 种防御塔"
2. 流程：意图解析（LLM 抽取 genre/core_loop/资产需求）→ 生成 GDD 草案 → 展示给用户确认（y/n/修改意见）→ 确认后启动 Prompt 5 的五角色流水线
3. 实时进度展示：终端彩色输出每个智能体的当前任务与产出物路径
4. 完成后自动汇总：构建包路径、资产清单表格、缺陷报告摘要
5. 支持 --resume 参数从中断处恢复（读取 ArcadeDB/SQLite 中的任务状态）

验收标准：一条命令跑完全程，Ctrl+C 中断后 --resume 能继续。
```

### 📌 Prompt 7：基础设施（私有化底座）

```
你是 DevOps 工程师。请在 infra/ 下编写全套 docker-compose 基础设施：

1. gitea + Git LFS：私有代码仓库，初始化 game/ 仓库并配置 .gitattributes（*.fbx、*.png、*.wav 走 LFS）
2. ollama：预拉取 qwen3:32b（或可配置），暴露 11434 端口
3. arcadedb：单节点模式，预创建图数据库 schema——节点类型：Agent、Task、Asset；边类型：PRODUCED、REVIEWED、DEPENDS_ON
4. redis：任务锁与速率限制
5. prefect server + agent：注册 pipelines/ 下的流水线（设计→美术→程序→测试四阶段 DAG）
6. 编写 Makefile：make up / make down / make seed（灌入演示数据）/ make demo（一键跑通示例游戏）
7. 全部服务绑定内网 IP，附安全说明文档

验收标准：make up 后所有服务健康检查通过；make demo 产出测试构建包。
```

***

## 四、施工顺序与里程碑

| **阶段**   | **内容**                                       | **消化 Prompt** | **建议周期** |
| -------- | -------------------------------------------- | ------------- | -------- |
| M1 地基    | 骨架 + 契约 Schema                               | 1             | 1 周      |
| M2 单软件闭环 | Blender-MCP（参考已有 Blender 自动化脚本模式）            | 2             | 2 周      |
| M3 引擎闭环  | Godot-MCP + 端到端 demo                         | 3             | 2 周      |
| M4 安全与治理 | 网关 + 沙箱 + 审计                                 | 4             | 1 周      |
| M5 智能体团队 | 五角色编排（对标 OpenClaw 六智能体集群的 A2A 协作实践 与五角色协作系统） | 5             | 3 周      |
| M6 体验封装  | Prompt-to-Pipeline CLI                       | 6             | 1 周      |
| M7 私有化底座 | 全套 infra 一键部署                                | 7             | 1 周      |

