"""Prompt 6 CLI 单元测试：make-game 入口 + 意图解析 + 汇总 + resume。"""

from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agents.common.deps import AgentDeps
from agents.common.llm import HybridLLM, LLMClient
from gaf import progress, summary
from gaf.cli import _build_default_deps, main, make_game
from gaf.intent import format_intent_for_review, parse_intent
from storage.sqlite_repo import SQLiteRepo

# ---------- 测试数据（复用 test_orchestrator 的合法 bundle） ----------

VALID_GDD = {
    "game_title": "方块跳跃",
    "genre": "platformer",
    "core_loop": "跳跃避障到达终点",
    "levels": [
        {"level_id": "lvl_00", "name": "第一关", "difficulty": 1, "spawn_table": []},
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
            {"unit_id": "hero", "hp_curve": [100], "unlock_level": 1}
        ]},
    },
}
VALID_MANIFEST = {
    "assets": [
        {"asset_id": "model_hero", "type": "model", "target_scene": "Main",
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
INTENT_RESP = {
    "game_title": "方块跳跃", "genre": "platformer",
    "core_loop": "跳跃", "asset_summary": ["model_hero"],
}


class _ScriptedLLM(LLMClient):
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls = 0

    def chat(self, model: str, messages: list[dict[str, str]], **kwargs) -> str:
        idx = min(self.calls, len(self.responses) - 1)
        self.calls += 1
        return self.responses[idx]


def _json_resp(d: dict) -> str:
    return f"```json\n{json.dumps(d, ensure_ascii=False)}\n```"


def _ok_gateway() -> MagicMock:
    gw = MagicMock()
    gw.call.return_value = {"status": "ok", "result": {}}
    return gw


def _make_deps(responses: list[str], repo: SQLiteRepo) -> AgentDeps:
    llm = HybridLLM(
        local_client=_ScriptedLLM(responses),
        cloud_client=_ScriptedLLM(responses),
    )
    return AgentDeps(
        llm=llm, gateway=_ok_gateway(), repo=repo,
        api_keys={r: f"key-{r}" for r in (
            "designer", "supervisor", "artist3d", "artist2d", "coder", "qa"
        )},
    )


# ---------- intent ----------


def test_parse_intent():
    repo = SQLiteRepo(Path(":memory:"))
    deps = _make_deps([_json_resp(INTENT_RESP)], repo)
    intent = parse_intent(deps.llm, "做一个跳跃游戏")
    assert intent["genre"] == "platformer"
    assert intent["game_title"] == "方块跳跃"


def test_format_intent_for_review():
    text = format_intent_for_review(INTENT_RESP)
    assert "platformer" in text
    assert "方块跳跃" in text


# ---------- progress ----------


def test_progress_role_event():
    buf = io.StringIO()
    progress.role_event("designer", "生成契约", "3 份文档", buf)
    out = buf.getvalue()
    assert "designer" in out
    assert "生成契约" in out


def test_progress_checkpoint():
    buf = io.StringIO()
    progress.checkpoint("金样本待确认", buf)
    assert "人工卡点" in buf.getvalue()


# ---------- summary ----------


def test_summary_with_build_and_assets():
    buf = io.StringIO()
    state = {
        "build_result": {"path": "game/build/windows", "status": "draft"},
        "produced_assets": [
            {"asset_id": "model_hero", "type": "model", "producer": "artist3d", "path": "a.fbx"},
        ],
        "defects": [],
        "status": "paused_human",
        "human_feedback": "待确认发布",
    }
    text = summary.summarize(state, buf)
    assert "构建包路径" in text
    assert "model_hero" in text
    assert "待确认发布" in text


def test_summary_with_defects():
    buf = io.StringIO()
    state = {
        "produced_assets": [],
        "defects": [{"id": "D1", "desc": "穿模"}],
        "status": "running",
    }
    text = summary.summarize(state, buf)
    assert "缺陷报告" in text
    assert "穿模" in text


# ---------- make_game ----------


def test_make_game_auto_confirm_gold_sample_checkpoint(tmp_path: Path):
    """auto_confirm + 金样本未预填 → 暂停在金样本卡点。"""
    repo = SQLiteRepo(tmp_path / "cli.db")
    responses = [_json_resp(INTENT_RESP), _json_resp(VALID_BUNDLE)]
    deps = _make_deps(responses, repo)
    buf = io.StringIO()
    final = make_game(
        "做一个跳跃游戏", deps=deps, auto_confirm=True, stream=buf,
    )
    assert final["status"] == "paused_human"
    assert "金样本" in final.get("human_feedback", "")


def test_make_game_user_cancel(tmp_path: Path):
    """用户取消确认 → status=cancelled。"""
    repo = SQLiteRepo(tmp_path / "cli.db")
    deps = _make_deps([_json_resp(INTENT_RESP)], repo)
    buf = io.StringIO()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("builtins.input", lambda: "n")
        final = make_game("做一个跳跃游戏", deps=deps, stream=buf)
    assert final["status"] == "cancelled"


def test_make_game_resume(tmp_path: Path):
    """先跑任务到金样本暂停，再 resume 恢复。"""
    repo = SQLiteRepo(tmp_path / "cli.db")
    responses = [_json_resp(INTENT_RESP), _json_resp(VALID_BUNDLE)]
    deps = _make_deps(responses, repo)
    buf = io.StringIO()
    final1 = make_game(
        "做一个跳跃游戏", deps=deps, auto_confirm=True, stream=buf,
    )
    assert final1["status"] == "paused_human"
    task_id = final1["task_id"]

    final2 = make_game(
        "", deps=deps, resume_task_id=task_id, stream=buf,
    )
    assert final2 is not None


# ---------- main / argparse ----------


def test_main_requires_subcommand():
    with pytest.raises(SystemExit):
        main([])


def test_main_make_game_needs_request_or_resume():
    with pytest.raises(SystemExit):
        main(["make-game"])


def test_main_make_game_with_request(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """main() 能解析 make-game 参数并调用（mock make_game 避免真实 LLM）。"""
    called: dict = {}

    def _fake_make_game(**kwargs):
        called.update(kwargs)
        return {"status": "ok"}

    monkeypatch.setattr("gaf.cli.make_game", _fake_make_game)
    rc = main(["make-game", "做一个游戏", "--api-key", "sk-test", "--cloud-provider", "glm"])
    assert rc == 0
    assert called["request"] == "做一个游戏"
    assert called["api_key"] == "sk-test"
    assert called["cloud_provider"] == "glm"


def test_main_make_game_resume(monkeypatch: pytest.MonkeyPatch):
    called: dict = {}

    def _fake_make_game(**kwargs):
        called.update(kwargs)
        return {"status": "ok"}

    monkeypatch.setattr("gaf.cli.make_game", _fake_make_game)
    rc = main(["make-game", "--resume", "task-abc"])
    assert rc == 0
    assert called["resume_task_id"] == "task-abc"


# ---------- default deps ----------


def test_build_default_deps():
    deps = _build_default_deps()
    assert deps.repo is not None
    assert deps.gateway is not None
    assert deps.llm is not None
