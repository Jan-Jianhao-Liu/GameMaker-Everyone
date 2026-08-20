# game-agent-factory 跨平台任务入口（替代 Makefile）
# 需安装 just: https://github.com/casey/just

# 初始化：安装依赖 + 检查 LFS + 预拉 Ollama 模型
init:
    uv sync
    uv run python -m infra.scripts.check_lfs
    uv run python -m infra.scripts.pull_ollama

# 校验：Schema 自检 + 导入检查
check:
    uv run python -c "from contracts.validators import validate_gdd, validate_no_circular_deps, suggest_naming; print('validators import OK')"

# lint
lint:
    uv run ruff check .
    uv run ruff format --check .

# 格式化
fmt:
    uv run ruff format .
    uv run ruff check --fix .

# 类型检查
typecheck:
    uv run mypy contracts/ storage/ agents/ gaf/

# 测试
test:
    uv run pytest -q

# 测试带覆盖率
test-cov:
    uv run pytest --cov=contracts --cov=storage --cov=agents -q

# ---------- Web 对话界面 ----------

# 启动 Web 对话界面（默认 http://127.0.0.1:8080）
web port="8080":
    uv run uvicorn web.server:app --host 127.0.0.1 --port {{port}}

# ---------- 基础设施 ----------

# 启动基础设施（Gitea + 网关）
up:
    docker compose -f infra/docker-compose.yml up -d
    @echo "等待服务就绪..."
    @timeout 10 docker compose -f infra/docker-compose.yml ps

# 停止基础设施
down:
    docker compose -f infra/docker-compose.yml down

# 查看服务状态
ps:
    docker compose -f infra/docker-compose.yml ps

# 查看日志
logs service="":
    docker compose -f infra/docker-compose.yml logs {{service}}

# ---------- 种子数据 ----------

# 初始化 Gitea + game/ 仓库（LFS 强制）
seed:
    uv run python -m infra.scripts.check_lfs
    uv run python -m infra.scripts.seed_gitea

# 预拉 Ollama 模型
pull-models:
    uv run python -m infra.scripts.pull_ollama

# ---------- 一键 Demo ----------

# 一键跑通示例游戏
demo request="做一个有 3 个关卡的方块跳跃游戏":
    just up
    just seed
    uv run python -m gaf make-game "{{request}}"

# ---------- 离线包 ----------

# 导出离线包（uv wheelhouse + ollama 模型清单 + docker 镜像 tar）
export-offline out="dist/offline":
    uv run python -m infra.scripts.export_offline {{out}}

# ---------- 一键自检 ----------

# 全套自检
all: check lint test
    @echo "✓ 全套自检通过"
