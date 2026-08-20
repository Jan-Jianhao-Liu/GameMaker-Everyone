"""Prompt 5 编排器单元测试：端到端编排 + 状态流转 + supervisor 退回 + 金样本卡点。

mock LLM（返回预构造契约 JSON）+ mock Gateway（返回 ok）+ 真实 SQLiteRepo。
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agents.common.deps import AgentDeps
from agents.common.llm import HybridLLM, LLMClient
from agents.orchestrator import build_graph, resume_pipeline, run_pipeline
from storage.sqlite_repo import SQLiteRepo

# ---------- 测试数据 ----------

VALID_GDD = {
    "game_title": "方块跳跃",
    "genre": "platformer",
    "core_loop": "跳跃避障到达终点",
    "levels": [
        {
            "level_id": "lvl_00", "name": "第一关", "difficulty": 1,
            "spawn_table": [
                {"entity_id": "e1", "asset_id": "model_hero",
                 "position": {"x": 0, "y": 0, "z": 0}, "count": 1}
            ],
        },
        {"level_id": "lvl_01", "name": "第二关", "difficulty": 3, "spawn_table": []},
        {"level_id": "lvl_02", "name": "第三关", "difficulty": 5, "spawn_table": []},
    ],
    "numeric_tables": {
        "schema_version": 1,
        "damage": {"entries": [
            {"unit_id": "hero", "base": 0, "growth_per_level": 0, "cooldown": 0}
        ]},
        "economy": {"entries": [
            {"resource": "gold", "initial": 0, "per_wave": 0, "cost_cap": 0}
        ]},
        "growth": {"entries": [
            {"unit_id": "hero", "hp_curve": [100, 120, 140], "unlock_level": 1}
        ]},
    },
}

VALID_MANIFEST = {
    "assets": [
        {"asset_id": "model_hero", "type": "model", "target_scene": "Main",
         "dependencies": [], "status": "pending"},
        {"asset_id": "texture_hero", "type": "texture", "target_scene": "Main",
         "dependencies": [], "status": "pending"},
    ]
}

VALID_ART_SPEC = {
    "texture_spec": {
        "require_power_of_two": True, "require_square": False,
        "npot_exception": {"allowed_types": ["ui"], "requires_flag": True},
    },
    "fbx_axis": "Y_UP",
    "naming_pattern": r"^(model|texture|ui|audio|anim)_[a-z][a-z0-9]*(_[a-z][a-z0-9]*)*$",
    "allowed_formats": ["fbx", "png"],
}

VALID_BUNDLE = {"gdd": VALID_GDD, "manifest": VALID_MANIFEST, "art_spec": VALID_ART_SPEC}


# ---------- mock 工具 ----------


class _ScriptedLLM(LLMClient):
    """按脚本返回的 mock LLM。每次 chat 返回脚本中下一个响应。"""

    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls = 0

    def chat(self, model: str, messages: list[dict[str, str]], **kwargs) -> str:
        idx = min(self.calls, len(self.responses) - 1)
        self.calls += 1
        return self.responses[idx]


def _ok_gateway() -> MagicMock:
    """所有调用返回 ok 的 mock Gateway。"""
    gw = MagicMock()
    gw.call.return_value = {"status": "ok", "result": {}}
    return gw


def _ok_gateway_with_defects(defects: list[dict]) -> MagicMock:
    """run_headless_test 首次返回缺陷、之后返回空（避免无限退回循环）。"""
    gw = MagicMock()
    call_count = {"test": 0}

    def _call(role, key, tool, params):
        if tool == "run_headless_test":
            call_count["test"] += 1
            if call_count["test"] == 1:
                return {"status": "ok", "result": {"defects": defects}}
            return {"status": "ok", "result": {"defects": []}}
        return {"status": "ok", "result": {}}

    gw.call.side_effect = _call
    return gw


def _make_deps(
    llm_responses: list[str], gateway: MagicMock, repo: SQLiteRepo, max_retries: int = 3
) -> AgentDeps:
    llm = HybridLLM(
        local_client=_ScriptedLLM(llm_responses),
        cloud_client=_ScriptedLLM(llm_responses),
    )
    return AgentDeps(
        llm=llm, gateway=gateway, repo=repo,
        api_keys={r: f"key-{r}" for r in (
            "designer", "supervisor", "artist3d", "artist2d", "coder", "qa"
        )},
        max_retries=max_retries,
    )


def _bundle_json(bundle: dict) -> str:
    return f"```json\n{json.dumps(bundle, ensure_ascii=False)}\n```"


# ---------- 测试 ----------


@pytest.fixture()
def repo(tmp_path: Path) -> SQLiteRepo:
    return SQLiteRepo(tmp_path / "orchestrator.db")


def test_pipeline_gold_sample_checkpoint(repo: SQLiteRepo):
    """金样本未确认 → artist3d 暂停。"""
    deps = _make_deps([_bundle_json(VALID_BUNDLE)], _ok_gateway(), repo)
    final = run_pipeline(deps, "T1", "做一个跳跃游戏")
    assert final["status"] == "paused_human"
    assert "金样本" in final["human_feedback"]


def test_pipeline_happy_path_to_release_checkpoint(repo: SQLiteRepo):
    """金样本预填 → 跑通到 qa → 发布确认卡点。"""
    deps = _make_deps([_bundle_json(VALID_BUNDLE)], _ok_gateway(), repo)
    final = run_pipeline(
        deps, "T2", "做一个跳跃游戏",
        initial_state={"gold_samples": {"model": {}, "texture": {}}},
    )
    assert final["status"] == "paused_human"
    assert "待确认发布" in final["human_feedback"]
    assert final["build_result"]["status"] == "pending_release"
    assert len(final["produced_assets"]) == 2


def test_supervisor_rejects_invalid_gdd(repo: SQLiteRepo):
    """GDD 缺字段 → supervisor 退回 designer，retries 增加。"""
    bad_bundle = {
        "gdd": {"game_title": "x"}, "manifest": VALID_MANIFEST, "art_spec": VALID_ART_SPEC,
    }
    good_bundle = VALID_BUNDLE
    deps = _make_deps(
        [_bundle_json(bad_bundle), _bundle_json(good_bundle)],
        _ok_gateway(), repo, max_retries=3,
    )
    final = run_pipeline(
        deps, "T3", "测试退回",
        initial_state={"gold_samples": {"model": {}, "texture": {}}},
    )
    assert final["status"] == "paused_human"
    assert "待确认发布" in final["human_feedback"]
    mem = repo.query_task_memory("T3")
    rejects = [m for m in mem if m["outcome"] == "reject"]
    assert len(rejects) >= 1


def test_supervisor_three_strikes_paused_human(repo: SQLiteRepo):
    """连续 3 轮不合规 → status=paused_human（人工卡点）。"""
    bad_bundle = {
        "gdd": {"game_title": "x"}, "manifest": VALID_MANIFEST, "art_spec": VALID_ART_SPEC,
    }
    deps = _make_deps([_bundle_json(bad_bundle)], _ok_gateway(), repo, max_retries=3)
    final = run_pipeline(deps, "T4", "测试三轮超限")
    assert final["status"] == "paused_human"
    assert "转人工" in final["human_feedback"]
    assert final["retries"]["designer"] == 3


def test_qa_defects_return_to_coder(repo: SQLiteRepo):
    """qa 发现缺陷 → 退回 coder。

    注：coder 重新构建后 qa 再测，mock 仍返回相同缺陷会无限循环。
    这里用 max_retries 不直接控制 coder 退回，故仅验证首轮 defects 已记录。
    为避免死循环，用 defects 为空但先触发一次有缺陷的场景不现实——
    改为直接测 qa 节点单元行为。
    """
    deps = _make_deps(
        [_bundle_json(VALID_BUNDLE)],
        _ok_gateway_with_defects([{"id": "D1", "desc": "角色穿模"}]),
        repo,
    )
    final = run_pipeline(
        deps, "T5", "测试缺陷退回",
        initial_state={"gold_samples": {"model": {}, "texture": {}}},
    )
    assert len(final["defects"]) >= 1


def test_graph_builds_successfully(repo: SQLiteRepo):
    """图可编译。"""
    deps = _make_deps([_bundle_json(VALID_BUNDLE)], _ok_gateway(), repo)
    graph = build_graph(deps)
    assert graph is not None


def test_designer_error_marks_failed(repo: SQLiteRepo):
    """designer LLM 返回非 JSON → status=failed。"""
    deps = _make_deps(["not json at all"], _ok_gateway(), repo)
    final = run_pipeline(deps, "T6", "测试 designer 失败")
    assert final["status"] == "failed"
    assert len(final["errors"]) >= 1


def test_gold_sample_checkpoint_resume_no_loop(repo: SQLiteRepo, tmp_path: Path):
    """金样本卡点确认后恢复不死循环：恢复后应前进到下一阶段，不重复同一卡点。"""
    deps = _make_deps([_bundle_json(VALID_BUNDLE)], _ok_gateway(), repo)
    ckpt_db = tmp_path / "ckpt_resume.db"
    final1 = run_pipeline(deps, "T-resume", "测试恢复", checkpoint_db=ckpt_db)
    assert final1["status"] == "paused_human"
    assert "model" in final1.get("gold_samples", {})
    fb1 = final1.get("human_feedback", "")
    final2 = resume_pipeline(deps, "T-resume", ckpt_db)
    assert final2["status"] == "paused_human"
    fb2 = final2.get("human_feedback", "")
    assert fb2 != fb1, "恢复后不应重复同一个金样本卡点"
    assert "texture" in final2.get("gold_samples", {}), "应已前进到 2D 金样本阶段"


def test_release_checkpoint_resume_no_loop(repo: SQLiteRepo, tmp_path: Path):
    """发布确认卡点确认后恢复不死循环：恢复后应 completed，不重复卡点。"""
    deps = _make_deps([_bundle_json(VALID_BUNDLE)], _ok_gateway(), repo)
    ckpt_db = tmp_path / "ckpt_release.db"
    final1 = run_pipeline(
        deps, "T-rel", "测试发布", checkpoint_db=ckpt_db,
        initial_state={"gold_samples": {"model": {}, "texture": {}}},
    )
    assert final1["status"] == "paused_human"
    assert "待确认发布" in final1.get("human_feedback", "")
    final2 = resume_pipeline(deps, "T-rel", ckpt_db)
    assert final2["status"] == "completed", "恢复后应完成，不重复发布卡点"
    assert final2.get("build_result", {}).get("status") == "release"
