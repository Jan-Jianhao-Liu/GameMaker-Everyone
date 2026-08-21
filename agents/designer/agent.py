"""designer（策划）子图。

输入用户需求文本，调用云端 LLM 生成符合 contracts/ Schema 的：
- GDD（游戏设计文档）
- 资产清单 manifest
- 美术规范 art_spec

节点内部自带校验+重试循环：生成 → 自校验 → 若失败把错误反馈 LLM 重生成，
最多重试 max_retries 轮。通过后 current_role 改为 supervisor 进入审核。
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from jsonschema import ValidationError

from agents.common.deps import AgentDeps
from agents.common.json_utils import extract_json
from agents.common.questioning import check_question
from agents.common.state import AgentState
from agents.common.thought_bus import get_bus
from agents.team_config import RoleConfig
from contracts.validators import (
    CircularDependencyError,
    validate_art_spec,
    validate_asset_manifest,
    validate_gdd,
    validate_no_circular_deps,
)

_CONTRACTS_DIR = Path(__file__).resolve().parents[2] / "contracts"


def _load_schema(name: str) -> str:
    """读取契约 schema 并压缩为紧凑 JSON 字符串（去掉 $schema/$id 等元数据）。"""
    raw = json.loads((_CONTRACTS_DIR / name).read_text(encoding="utf-8"))
    for k in ("$schema", "$id", "title", "description"):
        raw.pop(k, None)
    return json.dumps(raw, ensure_ascii=False, separators=(",", ":"))


_GDD_SCHEMA = _load_schema("gdd.schema.json")
_MANIFEST_SCHEMA = _load_schema("asset-manifest.schema.json")
_ART_SPEC_SCHEMA = _load_schema("art-spec.schema.json")

_PROMPT = """你是游戏策划。根据用户需求生成三份契约文档，严格遵循下方 JSON Schema，不得多/少任何字段。

用户需求：{request}

【GDD Schema】（顶层必填: game_title, genre, core_loop, levels, numeric_tables；禁止额外字段）
{gdd_schema}

【Asset Manifest Schema】（顶层必填: assets；禁止额外字段。注意 schema_version 不在 manifest 顶层，它在 GDD.numeric_tables 内）
{manifest_schema}

【Art Spec Schema】（顶层必填: texture_spec, fbx_axis, naming_pattern, allowed_formats；禁止额外字段。fbx_axis 固定 "Y_UP"，naming_pattern 固定 "^(model|texture|ui|audio|anim)_[a-z][a-z0-9]*(_[a-z][a-z0-9]*)*$"）
{art_spec_schema}

生成要求：
1. gdd：含 game_title、genre、core_loop、levels（至少 3 关，level_id 格式 lvl_00/lvl_01）、numeric_tables（含 schema_version=1、damage/economy/growth 三表）
2. manifest：assets 列表，每项含 asset_id（命名匹配上述正则）、type、target_scene、dependencies、status；dependencies 须构成 DAG 无环
3. art_spec：含 texture_spec（require_power_of_two=true, require_square=false, npot_exception.allowed_types=["ui"], npot_exception.requires_flag=true）、fbx_axis="Y_UP"、naming_pattern、allowed_formats（如 ["fbx","png","wav"]）

只返回 JSON 对象，键为 gdd / manifest / art_spec，不要任何解释文字。格式：
```json
{{"gdd": {{...}}, "manifest": {{...}}, "art_spec": {{...}}}}
```"""

_FIX_PROMPT = """上次生成的契约存在以下错误，请修复后重新返回完整 JSON：

{errors}

请严格按 Schema 修正上述问题，只返回修复后的完整 JSON（同样 gdd/manifest/art_spec 三键结构），不要解释。"""


def _validate_all(gdd: dict, manifest: dict, art_spec: dict) -> list[str]:
    """校验三份契约，返回错误信息列表（空表示全部通过）。"""
    errors: list[str] = []
    try:
        validate_gdd(gdd)
    except ValidationError as e:
        errors.append(f"GDD 不合规: {e.message}")
    try:
        validate_asset_manifest(manifest)
        validate_no_circular_deps(manifest)
    except ValidationError as e:
        errors.append(f"资产清单不合规: {e.message}")
    except CircularDependencyError as e:
        errors.append(str(e))
    try:
        validate_art_spec(art_spec)
    except ValidationError as e:
        errors.append(f"美术规范不合规: {e.message}")
    return errors


def make_designer_node(
    deps: AgentDeps, role_config: RoleConfig | None = None,
) -> Callable[[AgentState], dict]:
    """构造 designer 节点函数。内部自带校验+重试循环。"""

    def designer_node(state: AgentState) -> dict:
        bus = get_bus()
        task_id = state.get("task_id", "unknown")
        request = state.get("user_request", "")

        existing_gdd = state.get("gdd", {})
        existing_manifest = state.get("manifest", {})
        existing_art_spec = state.get("art_spec", {})
        if existing_gdd and existing_manifest and existing_art_spec:
            if not _validate_all(existing_gdd, existing_manifest, existing_art_spec):
                return {"current_role": "supervisor", "errors": []}

        answered = state.get("answered_questions", [])
        asked_roles = {q.get("role") for q in answered}
        if bus and "designer" not in asked_roles:
            q = check_question("designer", state)
            if q is not None:
                if bus:
                    bus.think("designer", "需求不够明确，向用户追问...")
                return {
                    "status": "paused_question",
                    "pause_type": "question",
                    "current_role": "designer",
                    "pending_question": q.to_dict(),
                    "human_feedback": q.question,
                }

        if bus:
            bus.think("designer", "分析用户需求", request=request[:100])
            bus.act("designer", "准备生成契约文档（GDD + Manifest + ArtSpec）")

        base_prompt = _PROMPT.format(
            request=request,
            gdd_schema=_GDD_SCHEMA,
            manifest_schema=_MANIFEST_SCHEMA,
            art_spec_schema=_ART_SPEC_SCHEMA,
        )

        gdd: dict = {}
        manifest: dict = {}
        art_spec: dict = {}
        errors: list[str] = []

        for attempt in range(deps.max_retries):
            try:
                prompt = base_prompt
                if errors:
                    prompt += "\n\n" + _FIX_PROMPT.format(
                        errors="\n".join(f"  • {e}" for e in errors)
                    )
                if bus:
                    bus.act("designer", f"调用 LLM 生成契约（第 {attempt + 1} 轮）")
                text = deps.llm.chat(
                    "designer",
                    [{"role": "user", "content": prompt}],
                    temperature=0.7,
                )
                if bus:
                    bus.think("designer", "LLM 返回结果，解析 JSON", length=len(text))
                bundle = extract_json(text)
                gdd = bundle.get("gdd", {})
                manifest = bundle.get("manifest", {})
                art_spec = bundle.get("art_spec", {})
            except Exception as e:  # noqa: BLE001
                if bus:
                    bus.error("designer", f"生成失败: {e}")
                deps.repo.save_task_memory(
                    "designer", task_id, "generate_contracts", "error", str(e)
                )
                return {
                    "errors": [f"designer 生成失败: {e}"],
                    "current_role": "supervisor",
                    "status": "failed",
                }

            errors = _validate_all(gdd, manifest, art_spec)
            if not errors:
                if bus:
                    bus.result("designer", "三份契约校验通过",
                               gdd_title=gdd.get("game_title", ""),
                               assets=len(manifest.get("assets", [])))
                deps.repo.save_task_memory(
                    "designer",
                    task_id,
                    "generate_contracts",
                    "ok",
                    f"三份契约已生成（内部第 {attempt + 1} 轮通过）",
                )
                return {
                    "gdd": gdd,
                    "manifest": manifest,
                    "art_spec": art_spec,
                    "current_role": "supervisor",
                    "errors": [],
                }
            if bus:
                bus.think("designer", f"第 {attempt + 1} 轮校验失败，准备修复",
                          errors=errors[:3])
            deps.repo.save_task_memory(
                "designer",
                task_id,
                "generate_contracts",
                "reject",
                f"内部第 {attempt + 1} 轮校验失败: {errors}",
            )

        if bus:
            bus.error("designer", f"{deps.max_retries} 轮均未通过，交 supervisor")
        deps.repo.save_task_memory(
            "designer",
            task_id,
            "generate_contracts",
            "error",
            f"内部 {deps.max_retries} 轮均未通过，交 supervisor 审核",
        )
        return {
            "gdd": gdd,
            "manifest": manifest,
            "art_spec": art_spec,
            "current_role": "supervisor",
            "errors": errors,
        }

    return designer_node
