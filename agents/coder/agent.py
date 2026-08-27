"""coder（程序）子图。

拉取已交付资产 + GDD，经网关调用 godot-mcp 或 godot-ai：
- godot-ai 路径（优先）: import_asset → scene_manage → node_create（逐节点）→
  node_set_property → script_attach → scene_save → project_run
- 原始路径（回退）: import_asset → create_scene → attach_script →
  set_level_data → build_export

build_export / scene_save 产出默认 draft 状态（发布确认卡点由 qa 通过后触发）。
完成后 current_role = "qa"。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agents.common.deps import AgentDeps
from agents.common.state import AgentState
from agents.common.thought_bus import get_bus
from agents.team_config import RoleConfig
from plugins.executor import ChainExecutor

_BUILD_OUTPUT = "game/build/windows"


def make_coder_node(
    deps: AgentDeps, role_config: RoleConfig | None = None,
) -> Callable[[AgentState], dict]:
    """构造 coder 节点函数。"""

    def coder_node(state: AgentState) -> dict:
        bus = get_bus()
        task_id = state.get("task_id", "unknown")
        key = deps.key_for("coder")
        produced = state.get("produced_assets", [])
        gdd = state.get("gdd", {})

        existing_build = state.get("build_result", {})
        if existing_build.get("status") in ("pending_release", "release"):
            return {"current_role": "qa"}

        use_godot_ai = _has_godot_ai(deps)
        if bus:
            mode = "godot-ai 逐节点构建" if use_godot_ai else "原始模板构建"
            bus.think("coder", f"导入 {len(produced)} 个资产并构建游戏（{mode}）")

        for asset in produced:
            asset_id = asset["asset_id"]
            if bus:
                bus.act("coder", f"导入资产 {asset_id}")
            r = deps.gateway.call(
                "coder", key, "import_asset", {"asset_id": asset_id, "path": asset["path"]}
            )
            if r.get("status") != "ok":
                if bus:
                    bus.error("coder", f"导入 {asset_id} 失败")
                deps.repo.save_task_memory(
                    "coder", task_id, "import_asset", "error", str(r.get("error"))
                )
                return {
                    "errors": [f"导入资产 {asset_id} 失败: {r.get('error')}"],
                    "current_role": "coder",
                }

        if bus:
            bus.act("coder", "创建场景 + 编写脚本 + 构建导出")
        if use_godot_ai:
            ok = _run_build_chain_godot_ai(deps, gdd, key, task_id, bus)
        else:
            ok = _run_build_chain(deps, gdd, key, task_id, role_config)
        if not ok:
            if bus:
                bus.error("coder", "构建失败")
            return {"errors": ["构建失败"], "current_role": "coder"}

        if bus:
            bus.result("coder", f"构建完成（draft），输出到 {_BUILD_OUTPUT}")
        deps.repo.save_task_memory("coder", task_id, "build", "ok", "构建完成（draft）")
        return {
            "build_result": {"path": _BUILD_OUTPUT, "status": "draft"},
            "current_role": "qa",
            "errors": [],
        }

    return coder_node


def _has_godot_ai(deps: AgentDeps) -> bool:
    """检查 godot-ai 插件是否已加载。"""
    if deps.plugins is None:
        return False
    return deps.plugins.get("godot_ai") is not None


def _run_build_chain_godot_ai(
    deps: AgentDeps, gdd: dict, key: str, task_id: str, bus: Any,
) -> bool:
    """使用 godot-ai 工具逐节点构建场景。

    改进点（借鉴 Beckett + godot-ai）:
    - batch_execute: 批量提交节点创建，减少 RPC 往返
    - validate-before-write: 先 script_create 验证编译再 script_attach
    - script_patch: 局部修补脚本而非整个重写
    """
    levels = gdd.get("levels", [])
    gw = deps.gateway

    def _call(tool: str, params: dict) -> dict:
        r = gw.call("coder", key, tool, params)
        if r.get("status") != "ok":
            deps.repo.save_task_memory("coder", task_id, tool, "error", str(r.get("error")))
        return r

    if bus:
        bus.act("coder", "scene_manage: 新建 Main 场景")
    if _call("scene_manage", {"action": "new", "name": "Main"}).get("status") != "ok":
        return False

    batch_calls = [
        {"tool": "node_create", "params": {"type": "CharacterBody3D", "name": "Player", "parent": "root"}},
        {"tool": "node_create", "params": {"type": "Camera3D", "name": "Camera3D", "parent": "Player"}},
        {"tool": "node_set_property", "params": {"node": "Player/Camera3D", "property": "transform", "value": [0, 1.5, 4, 0, 0, 0]}},
        {"tool": "node_create", "params": {"type": "DirectionalLight3D", "name": "SunLight", "parent": "root"}},
        {"tool": "node_set_property", "params": {"node": "SunLight", "property": "transform", "value": [0, 10, 0, -0.7, 0.7, 0]}},
        {"tool": "node_create", "params": {"type": "WorldEnvironment", "name": "WorldEnv", "parent": "root"}},
    ]

    for i, level in enumerate(levels):
        level_name = level.get("name", f"Level{i+1}")
        batch_calls.append({
            "tool": "node_create",
            "params": {"type": "Node3D", "name": level_name, "parent": "root"},
        })
        for ent in level.get("entities", []):
            batch_calls.append({
                "tool": "node_create",
                "params": {
                    "type": ent.get("type", "Node3D"),
                    "name": ent.get("name", "Entity"),
                    "parent": level_name,
                },
            })

    if bus:
        bus.act("coder", f"batch_execute: 批量创建 {len(batch_calls)} 个节点/属性")
    r = _call("batch_execute", {"calls": batch_calls})
    if r.get("status") != "ok":
        if bus:
            bus.act("coder", "batch_execute 失败，回退逐个执行")
        for call in batch_calls:
            if _call(call["tool"], call["params"]).get("status") != "ok":
                return False

    scripts = [
        ("Player", "res://scripts/player.gd", _PLAYER_SCRIPT),
        ("SunLight", "res://scripts/environment.gd", _ENV_SCRIPT),
    ]
    for node, path, code in scripts:
        if bus:
            bus.act("coder", f"script_create: 验证 {path} 编译")
        r = _call("script_create", {"path": path, "content": code})
        if r.get("status") != "ok":
            if bus:
                bus.error("coder", f"脚本编译失败: {path}")
            return False
        if bus:
            bus.act("coder", f"script_attach: {path} → {node}")
        if _call("script_attach", {"node": node, "script_path": path}).get("status") != "ok":
            return False

    if bus:
        bus.act("coder", "scene_save: 保存 Main.tscn")
    if _call("scene_save", {}).get("status") != "ok":
        return False

    return True


_PLAYER_SCRIPT = """extends CharacterBody3D

var speed: float = 5.0
var jump_velocity: float = 4.5
var gravity: float = 9.8

func _physics_process(delta: float) -> void:
    if not is_on_floor():
        velocity.y -= gravity * delta
    if Input.is_action_just_pressed("ui_accept") and is_on_floor():
        velocity.y = jump_velocity
    var input_dir = Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
    velocity.x = input_dir.x * speed
    velocity.z = input_dir.y * speed
    move_and_slide()
"""

_ENV_SCRIPT = """extends DirectionalLight3D

func _ready() -> void:
    light_energy = 1.2
    shadow_enabled = true
"""


def _patch_script(
    deps: AgentDeps, key: str, task_id: str, bus: Any,
    script_path: str, patches: list[dict],
) -> bool:
    """使用 script_patch 局部修改脚本（而非整个重写）。

    patches: [{"action": "replace", "range": [start_line, end_line], "content": "..."}]
    """
    gw = deps.gateway
    for patch in patches:
        if bus:
            bus.act("coder", f"script_patch: {patch.get('action', 'replace')} @ {script_path}")
        r = gw.call("coder", key, "script_patch", {
            "path": script_path,
            "action": patch.get("action", "replace"),
            "range": patch.get("range", []),
            "content": patch.get("content", ""),
        })
        if r.get("status") != "ok":
            deps.repo.save_task_memory("coder", task_id, "script_patch", "error", str(r.get("error")))
            return False
    return True


def _run_build_chain(
    deps: AgentDeps, gdd: dict, key: str, task_id: str,
    role_config: RoleConfig | None,
) -> bool:
    """执行构建步骤。优先插件链，回退硬编码。"""
    build_output = (role_config.build_output if role_config and role_config.build_output
                    else _BUILD_OUTPUT)
    levels = gdd.get("levels", [])

    if deps.plugins is not None and role_config and role_config.plugin and role_config.chain:
        executor = ChainExecutor()
        r = executor.execute(
            deps.plugins, role_config.plugin, role_config.chain,
            "coder", key, deps.gateway,
            {"levels": levels, "build_output": build_output},
        )
        if r["status"] != "ok":
            deps.repo.save_task_memory(
                "coder", task_id, r.get("tool", "build"), "error", r["error"],
            )
            return False
        return True

    steps = [
        ("create_scene", {"scene_name": "Main", "template": "scene_3d"}),
        ("attach_script", {"node": "Player", "script_template": "character"}),
        ("set_level_data", {"levels": levels}),
        ("build_export", {"platform": "windows", "output_path": build_output}),
    ]
    for tool, params in steps:
        r = deps.gateway.call("coder", key, tool, params)
        if r.get("status") != "ok":
            deps.repo.save_task_memory("coder", task_id, tool, "error", str(r.get("error")))
            return False
    return True
