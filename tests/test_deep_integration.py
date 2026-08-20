"""深度集成测试：插件工具链执行 + 自定义角色 + 配置驱动节点。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agents.common.deps import AgentDeps
from agents.common.generic_node import make_generic_node
from agents.common.llm import HybridLLM, LLMClient
from agents.common.state import AgentState
from agents.orchestrator import build_graph, run_pipeline
from agents.team_config import RoleConfig, TeamConfig
from plugins.executor import ChainExecutor, resolve_params
from plugins.registry import PluginRegistry
from storage.sqlite_repo import SQLiteRepo


class _OkLLM(LLMClient):
    def chat(self, model: str, messages: list[dict[str, str]], **kwargs) -> str:
        return "ok"


def _ok_gw() -> MagicMock:
    gw = MagicMock()
    gw.call.return_value = {"status": "ok", "result": {}}
    return gw


def _make_deps(repo: SQLiteRepo, gw: MagicMock | None = None) -> AgentDeps:
    registry = PluginRegistry()
    registry.load()
    llm = HybridLLM(local_client=_OkLLM(), cloud_client=_OkLLM())
    return AgentDeps(
        llm=llm, gateway=gw or _ok_gw(), repo=repo,
        api_keys={r: f"k-{r}" for r in ("designer", "supervisor", "artist3d", "artist2d", "coder", "qa", "custom_prod")},
        plugins=registry,
    )


@pytest.fixture()
def repo(tmp_path: Path) -> SQLiteRepo:
    return SQLiteRepo(tmp_path / "deep.db")


# ---------- ChainExecutor 占位符替换 ----------


class TestResolveParams:
    def test_full_placeholder_keeps_type(self):
        r = resolve_params({"x": "{val}"}, {"val": [1, 2, 3]})
        assert r["x"] == [1, 2, 3]

    def test_partial_placeholder_string(self):
        r = resolve_params({"msg": "asset {id} done"}, {"id": "hero"})
        assert r["msg"] == "asset hero done"

    def test_no_placeholder(self):
        r = resolve_params({"x": 42, "y": [1, 2]}, {})
        assert r == {"x": 42, "y": [1, 2]}

    def test_nested_dict(self):
        r = resolve_params({"d": {"a": "{v}"}}, {"v": "hello"})
        assert r["d"]["a"] == "hello"

    def test_nested_list(self):
        r = resolve_params({"l": ["{v}", 2]}, {"v": "x"})
        assert r["l"] == ["x", 2]

    def test_unresolved_placeholder_kept(self):
        r = resolve_params({"x": "{unknown}"}, {})
        assert r["x"] == "{unknown}"


# ---------- ChainExecutor 执行 ----------


class TestChainExecutor:
    def test_execute_ok(self):
        registry = PluginRegistry()
        registry.load()
        gw = _ok_gw()
        executor = ChainExecutor()
        r = executor.execute(
            registry, "blender", "produce_model",
            "artist3d", "k", gw,
            {"asset_id": "hero", "out_path": "out.fbx"},
        )
        assert r["status"] == "ok"
        assert gw.call.call_count == 5

    def test_execute_plugin_not_found(self):
        registry = PluginRegistry()
        executor = ChainExecutor()
        r = executor.execute(
            registry, "nonexistent", "chain", "role", "k", _ok_gw(), {},
        )
        assert r["status"] == "error"
        assert "未加载" in r["error"]

    def test_execute_chain_not_found(self):
        registry = PluginRegistry()
        registry.load()
        executor = ChainExecutor()
        r = executor.execute(
            registry, "blender", "nonexistent", "role", "k", _ok_gw(), {},
        )
        assert r["status"] == "error"
        assert "不存在" in r["error"]

    def test_execute_error_propagates(self):
        registry = PluginRegistry()
        registry.load()
        gw = MagicMock()
        gw.call.return_value = {"status": "error", "error": "boom"}
        executor = ChainExecutor()
        r = executor.execute(
            registry, "blender", "produce_model",
            "artist3d", "k", gw, {"asset_id": "x", "out_path": "x.fbx"},
        )
        assert r["status"] == "error"
        assert "boom" in r["error"]


# ---------- artist3d 用插件链 ----------


class TestArtist3dPluginChain:
    def test_uses_plugin_chain_when_configured(self, repo: SQLiteRepo):
        """artist3d 有 plugin+chain 时通过 ChainExecutor 执行。"""
        gw = _ok_gw()
        deps = _make_deps(repo, gw)
        rc = RoleConfig(id="artist3d", plugin="blender", chain="produce_model")
        from agents.artist3d.agent import make_artist3d_node
        node = make_artist3d_node(deps, rc)
        state: AgentState = {
            "task_id": "t1",
            "manifest": {"assets": [
                {"asset_id": "m1", "type": "model", "status": "pending"},
            ]},
            "produced_assets": [],
            "gold_samples": {"model": "m1"},
        }
        result = node(state)
        assert len(result.get("produced_assets", [])) == 1
        assert result["produced_assets"][0]["asset_id"] == "m1"
        assert gw.call.call_count == 6

    def test_falls_back_without_plugins(self, repo: SQLiteRepo):
        """deps.plugins=None 时回退硬编码。"""
        gw = _ok_gw()
        llm = HybridLLM(local_client=_OkLLM(), cloud_client=_OkLLM())
        deps = AgentDeps(llm=llm, gateway=gw, repo=repo, api_keys={"artist3d": "k"})
        from agents.artist3d.agent import make_artist3d_node
        node = make_artist3d_node(deps)
        state: AgentState = {
            "task_id": "t1",
            "manifest": {"assets": [
                {"asset_id": "m1", "type": "model", "status": "pending"},
            ]},
            "produced_assets": [],
            "gold_samples": {"model": "m1"},
        }
        result = node(state)
        assert len(result.get("produced_assets", [])) == 1
        assert gw.call.call_count == 6


# ---------- 自定义角色 generic_node ----------


class TestGenericNode:
    def test_passthrough(self, repo: SQLiteRepo):
        rc = RoleConfig(id="custom_step", kind="custom", next="coder")
        node = make_generic_node(_make_deps(repo), rc)
        result = node({"task_id": "t1"})
        assert result["current_role"] == "coder"

    def test_producer(self, repo: SQLiteRepo):
        gw = _ok_gw()
        deps = _make_deps(repo, gw)
        rc = RoleConfig(
            id="custom_prod", kind="producer",
            plugin="blender", chain="produce_model",
            asset_type="model", output_dir="game/assets/models",
            next="next_role",
        )
        node = make_generic_node(deps, rc)
        state: AgentState = {
            "task_id": "t1",
            "manifest": {"assets": [
                {"asset_id": "m1", "type": "model", "status": "pending"},
            ]},
            "produced_assets": [],
        }
        result = node(state)
        assert len(result["produced_assets"]) == 1
        assert result["current_role"] == "next_role"

    def test_builder(self, repo: SQLiteRepo):
        gw = _ok_gw()
        deps = _make_deps(repo, gw)
        rc = RoleConfig(
            id="custom_build", kind="builder",
            plugin="godot", chain="build_game",
            build_output="game/build/x",
            next="qa",
        )
        node = make_generic_node(deps, rc)
        result = node({"task_id": "t1", "gdd": {"levels": []}})
        assert result["build_result"]["status"] == "draft"
        assert result["current_role"] == "qa"

    def test_validator_missing_input(self, repo: SQLiteRepo):
        deps = _make_deps(repo)
        rc = RoleConfig(
            id="custom_val", kind="validator",
            inputs=["gdd"], next_on_pass="next", next_on_fail="back",
        )
        node = make_generic_node(deps, rc)
        result = node({"task_id": "t1"})
        assert result["current_role"] == "back"

    def test_validator_pass(self, repo: SQLiteRepo):
        deps = _make_deps(repo)
        rc = RoleConfig(
            id="custom_val", kind="validator",
            inputs=["gdd"], next_on_pass="next", next_on_fail="back",
        )
        node = make_generic_node(deps, rc)
        result = node({"task_id": "t1", "gdd": {"x": 1}})
        assert result["current_role"] == "next"


# ---------- 自定义角色端到端 ----------


class TestCustomRoleInPipeline:
    def test_custom_role_in_team_config(self, repo: SQLiteRepo, tmp_path: Path):
        """team.json 含自定义角色时图能构建并执行。"""
        import json
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        team_data = {
            "roles": [
                {"id": "designer", "label": "策划", "kind": "generator",
                 "outputs": ["gdd"], "next": "custom_step"},
                {"id": "custom_step", "label": "自定义", "kind": "custom",
                 "next": "END"},
            ]
        }
        (config_dir / "team.json").write_text(
            json.dumps(team_data, ensure_ascii=False), encoding="utf-8")
        team = TeamConfig(config_dir=config_dir)
        team.load()
        deps = _make_deps(repo)
        graph = build_graph(deps, team)
        assert graph is not None