"""Prompt 5 agents.common 单元测试：state + llm 混合模式 + task_lock。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from agents.common.llm import CloudClient, HybridLLM, LLMClient, OllamaClient
from agents.common.state import AgentState
from agents.common.task_lock import AssetLock, LockError
from storage.sqlite_repo import SQLiteRepo

# ---------- state ----------


def test_state_typed_dict_optional():
    state: AgentState = {"task_id": "T1", "user_request": "做一个跳跃游戏"}
    assert state["task_id"] == "T1"


def test_state_supports_all_fields():
    state: AgentState = {
        "task_id": "T1",
        "user_request": "demo",
        "gdd": {},
        "manifest": {},
        "art_spec": {},
        "gold_samples": {},
        "produced_assets": [],
        "build_result": {},
        "defects": [],
        "errors": [],
        "retries": {},
        "current_role": "designer",
        "status": "running",
        "human_feedback": "",
    }
    assert state["current_role"] == "designer"


# ---------- llm ----------


class _FakeClient(LLMClient):
    """测试用假客户端，记录调用并返回固定文本。"""

    def __init__(self, returns: str = "fake-response") -> None:
        self.returns = returns
        self.calls: list[tuple[str, list[dict]]] = []

    def chat(self, model: str, messages: list[dict[str, str]], **kwargs) -> str:
        self.calls.append((model, messages))
        return self.returns


def test_hybrid_routes_local_for_artist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MODEL_ARTIST3D", "qwen3.5:4b")
    local = _FakeClient("local-ok")
    cloud = _FakeClient("cloud-ok")
    llm = HybridLLM(local_client=local, cloud_client=cloud)
    out = llm.chat("artist3d", [{"role": "user", "content": "hi"}])
    assert out == "local-ok"
    assert local.calls[0][0] == "qwen3.5:4b"
    assert cloud.calls == []


def test_hybrid_routes_cloud_for_designer(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MODEL_DESIGNER", "cloud")
    monkeypatch.setenv("LLM_CLOUD_PROVIDER", "glm")
    local = _FakeClient("local-ok")
    cloud = _FakeClient("cloud-ok")
    llm = HybridLLM(local_client=local, cloud_client=cloud)
    out = llm.chat("designer", [{"role": "user", "content": "hi"}])
    assert out == "cloud-ok"
    assert cloud.calls[0][0] == "glm-4-air"
    assert local.calls == []


def test_hybrid_routes_qa_to_local_2b(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MODEL_QA", "qwen3.5:2b")
    local = _FakeClient("local-ok")
    llm = HybridLLM(local_client=local, cloud_client=_FakeClient())
    out = llm.chat("qa", [{"role": "user", "content": "hi"}])
    assert out == "local-ok"
    assert local.calls[0][0] == "qwen3.5:2b"


def test_hybrid_unknown_role_raises():
    llm = HybridLLM(local_client=_FakeClient(), cloud_client=_FakeClient())
    with pytest.raises(ValueError, match="未知角色"):
        llm.chat("unknown_role", [])


def test_hybrid_cloud_lazy_init_when_needed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MODEL_DESIGNER", "cloud")
    monkeypatch.setenv("LLM_CLOUD_API_KEY", "sk-test")
    local = _FakeClient()
    llm = HybridLLM(local_client=local, cloud_client=None)
    assert llm._cloud is None
    with patch.object(CloudClient, "chat", return_value="lazy-cloud") as mock_chat:
        out = llm.chat("designer", [{"role": "user", "content": "hi"}])
    assert out == "lazy-cloud"
    assert mock_chat.call_count == 1


def test_cloud_client_requires_api_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("LLM_CLOUD_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="LLM_CLOUD_API_KEY"):
        CloudClient()


def test_ollama_client_default_url(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    client = OllamaClient()
    assert client.base_url == "http://localhost:11434/v1"


# ---------- task_lock ----------


@pytest.fixture()
def repo(tmp_path: Path) -> SQLiteRepo:
    return SQLiteRepo(tmp_path / "lock.db")


def test_asset_lock_acquire_and_release(repo: SQLiteRepo):
    with AssetLock(repo, "asset_001", "artist3d"):
        assert not repo.acquire_lock("asset_001", "artist2d")
    assert repo.acquire_lock("asset_001", "artist2d")


def test_asset_lock_blocks_concurrent(repo: SQLiteRepo):
    repo.acquire_lock("asset_001", "artist3d")
    with pytest.raises(LockError, match="已被其他智能体锁定"):
        with AssetLock(repo, "asset_001", "artist2d"):
            pass


def test_asset_lock_released_on_exception(repo: SQLiteRepo):
    with pytest.raises(ValueError):
        with AssetLock(repo, "asset_001", "artist3d"):
            raise ValueError("boom")
    assert repo.acquire_lock("asset_001", "artist2d")
