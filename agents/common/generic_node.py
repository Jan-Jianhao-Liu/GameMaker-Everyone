"""通用节点工厂 — 按 RoleConfig.kind 为自定义角色生成节点函数。

已知角色（designer/supervisor/artist3d/artist2d/coder/qa）有专门的 make_*_node，
自定义角色（不在 _NODE_FACTORIES 中的）由本模块按 kind 生成简化通用节点：

- generator → 用 LLM 生成 outputs 声明的产物（简化版，不嵌入 schema）
- validator → 用 LLM 校验 inputs，通过转 next_on_pass，不通过转 next_on_fail
- producer  → 用 plugin+chain 生产 asset_type 资产 + commit_asset
- builder   → 用 plugin+chain 构建，设 build_result
- tester    → 用 plugin+chain 测试，有缺陷退回 next_on_fail
- custom    → 透传到 next
"""

from __future__ import annotations

from collections.abc import Callable

from agents.common.deps import AgentDeps
from agents.common.state import AgentState
from agents.common.task_lock import AssetLock, LockError
from agents.team_config import RoleConfig
from plugins.executor import ChainExecutor


def make_generic_node(
    deps: AgentDeps, role_config: RoleConfig,
) -> Callable[[AgentState], dict]:
    """按 RoleConfig.kind 生成通用节点函数。"""
    kind = role_config.kind
    if kind == "producer":
        return _make_producer(deps, role_config)
    if kind == "builder":
        return _make_builder(deps, role_config)
    if kind == "tester":
        return _make_tester(deps, role_config)
    if kind == "generator":
        return _make_generator(deps, role_config)
    if kind == "validator":
        return _make_validator(deps, role_config)
    return _make_passthrough(role_config)


def _next_role(rc: RoleConfig) -> str:
    return rc.next or rc.next_on_pass or ""


def _make_passthrough(rc: RoleConfig) -> Callable[[AgentState], dict]:
    nxt = _next_role(rc)

    def node(state: AgentState) -> dict:
        return {"current_role": nxt}

    return node


def _make_producer(
    deps: AgentDeps, rc: RoleConfig,
) -> Callable[[AgentState], dict]:
    """通用资产生产节点：用 plugin+chain 生产 + commit_asset。"""
    nxt = _next_role(rc)
    asset_types = tuple(rc.asset_types) if rc.asset_types else (rc.asset_type or "",)
    output_dir = rc.output_dir or "game/assets"
    role_id = rc.id

    def node(state: AgentState) -> dict:
        task_id = state.get("task_id", "unknown")
        key = deps.key_for(role_id)
        manifest = state.get("manifest", {})
        produced_ids = {a["asset_id"] for a in state.get("produced_assets", [])}
        pending = [
            a for a in manifest.get("assets", [])
            if a.get("type") in asset_types and a["asset_id"] not in produced_ids
        ]
        if not pending:
            return {"current_role": nxt}

        produced: list[dict] = []
        for asset in pending:
            asset_id = asset["asset_id"]
            ext = "fbx" if asset.get("type") == "model" else "png"
            out_path = f"{output_dir}/{asset_id}.{ext}"
            try:
                with AssetLock(deps.repo, asset_id, role_id):
                    if not _run_chain(deps, rc, role_id, key, task_id,
                                      {"asset_id": asset_id, "out_path": out_path}):
                        continue
                    deps.gateway.call(role_id, key, "commit_asset", {
                        "asset_id": asset_id, "file_paths": [out_path],
                        "message": f"{role_id} 资产 {asset_id} 入库",
                    })
                    produced.append({
                        "asset_id": asset_id, "type": asset.get("type"),
                        "path": out_path, "producer": role_id,
                    })
            except LockError:
                continue
        return {"produced_assets": produced, "current_role": nxt}

    return node


def _make_builder(
    deps: AgentDeps, rc: RoleConfig,
) -> Callable[[AgentState], dict]:
    """通用构建节点：用 plugin+chain 构建。"""
    nxt = _next_role(rc)
    role_id = rc.id
    build_output = rc.build_output or "game/build/windows"

    def node(state: AgentState) -> dict:
        task_id = state.get("task_id", "unknown")
        key = deps.key_for(role_id)
        gdd = state.get("gdd", {})
        if not _run_chain(deps, rc, role_id, key, task_id,
                          {"levels": gdd.get("levels", []), "build_output": build_output}):
            return {"errors": ["构建失败"], "current_role": role_id}
        return {
            "build_result": {"path": build_output, "status": "draft"},
            "current_role": nxt,
        }

    return node


def _make_tester(
    deps: AgentDeps, rc: RoleConfig,
) -> Callable[[AgentState], dict]:
    """通用测试节点：用 plugin+chain 测试。"""
    role_id = rc.id
    fail_next = rc.next_on_fail or rc.next

    def node(state: AgentState) -> dict:

        key = deps.key_for(role_id)
        build = state.get("build_result", {})
        build_path = build.get("path", "")
        ok, result = _run_test_chain(deps, rc, role_id, key, build_path)
        if not ok:
            return {"errors": [f"测试失败: {result}"], "current_role": role_id}
        defects = result.get("defects", [])
        if defects:
            return {"defects": defects, "current_role": fail_next}
        return {"defects": [], "current_role": rc.next_on_pass or rc.next}

    return node


def _make_generator(
    deps: AgentDeps, rc: RoleConfig,
) -> Callable[[AgentState], dict]:
    """通用生成器节点：用 LLM 生成 outputs 声明的产物（简化版）。"""
    nxt = _next_role(rc)
    role_id = rc.id

    def node(state: AgentState) -> dict:
        request = state.get("user_request", "")
        prompt = f"你是{rc.label or role_id}。根据以下需求生成游戏设计文档:\n{request}"
        try:
            resp = deps.llm.chat(role_id, prompt)
        except Exception:
            return {"errors": [f"{role_id} LLM 调用失败"], "current_role": role_id}
        update: dict = {}
        for out in rc.outputs:
            update[out] = {"generated": True, "raw": resp[:500]}
        update["current_role"] = nxt
        return update

    return node


def _make_validator(
    deps: AgentDeps, rc: RoleConfig,
) -> Callable[[AgentState], dict]:
    """通用校验器节点：检查 inputs 是否存在，通过转 next_on_pass。"""
    role_id = rc.id

    def node(state: AgentState) -> dict:
        for inp in rc.inputs:
            if not state.get(inp):
                return {"errors": [f"{role_id}: 缺少输入 {inp}"], "current_role": rc.next_on_fail}
        return {"current_role": rc.next_on_pass or rc.next}

    return node


def _run_chain(
    deps: AgentDeps, rc: RoleConfig, role_id: str, key: str, task_id: str,
    context: dict,
) -> bool:
    """执行插件工具链。回退：无插件时直接返回 True。"""
    if deps.plugins is None or not rc.plugin or not rc.chain:
        return True
    executor = ChainExecutor()
    r = executor.execute(deps.plugins, rc.plugin, rc.chain, role_id, key, deps.gateway, context)
    if r["status"] != "ok":
        deps.repo.save_task_memory(role_id, task_id, r.get("tool", "chain"), "error", r["error"])
        return False
    return True


def _run_test_chain(
    deps: AgentDeps, rc: RoleConfig, role_id: str, key: str, build_path: str,
) -> tuple[bool, dict]:
    """执行测试链。回退：无插件时返回 ok + 空 defects。"""
    if deps.plugins is None or not rc.plugin or not rc.chain:
        return True, {"defects": []}
    executor = ChainExecutor()
    r = executor.execute(
        deps.plugins, rc.plugin, rc.chain, role_id, key, deps.gateway,
        {"build_path": build_path},
    )
    if r["status"] == "ok":
        return True, r.get("result", {})
    return False, {"error": r.get("error", "")}
