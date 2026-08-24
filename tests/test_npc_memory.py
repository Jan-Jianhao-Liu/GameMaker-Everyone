"""NPC 记忆管理器测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.npc.memory_manager import NPCConfig, NPCMemoryManager


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    (tmp_path / "npc_memory").mkdir()
    (tmp_path / "npc_config").mkdir()
    return tmp_path


def test_save_and_load_config(tmp_project: Path):
    mgr = NPCMemoryManager(tmp_project)
    cfg = NPCConfig(
        npc_id="guard_01",
        name="神殿守卫",
        persona="你是幽冥神殿的守卫，说话古风。",
    )
    mgr.save_config(cfg)
    loaded = mgr.load_config("guard_01")
    assert loaded is not None
    assert loaded.npc_id == "guard_01"
    assert loaded.name == "神殿守卫"
    assert loaded.persona == "你是幽冥神殿的守卫，说话古风。"


def test_load_nonexistent_config(tmp_project: Path):
    mgr = NPCMemoryManager(tmp_project)
    assert mgr.load_config("nonexistent") is None


def test_list_npcs(tmp_project: Path):
    mgr = NPCMemoryManager(tmp_project)
    mgr.save_config(NPCConfig(npc_id="npc_a", name="A"))
    mgr.save_config(NPCConfig(npc_id="npc_b", name="B"))
    npcs = mgr.list_npcs()
    assert "npc_a" in npcs
    assert "npc_b" in npcs


def test_append_and_read_memory(tmp_project: Path):
    mgr = NPCMemoryManager(tmp_project)
    mgr.append_memory("guard_01", "user", "你好")
    mgr.append_memory("guard_01", "assistant", "尔来何事？")
    entries = mgr.read_memory("guard_01")
    assert len(entries) == 2
    assert entries[0]["role"] == "user"
    assert entries[0]["content"] == "你好"
    assert entries[1]["role"] == "assistant"
    assert entries[1]["content"] == "尔来何事？"


def test_read_memory_limit(tmp_project: Path):
    mgr = NPCMemoryManager(tmp_project)
    for i in range(20):
        mgr.append_memory("npc", "user", f"line {i}")
    entries = mgr.read_memory("npc", n=5)
    assert len(entries) == 5
    assert entries[0]["content"] == "line 15"


def test_get_context_string(tmp_project: Path):
    mgr = NPCMemoryManager(tmp_project)
    mgr.append_memory("npc", "user", "你好")
    mgr.append_memory("npc", "assistant", "尔来何事？")
    ctx = mgr.get_context_string("npc")
    assert "user: 你好" in ctx
    assert "assistant: 尔来何事？" in ctx


def test_clear_memory(tmp_project: Path):
    mgr = NPCMemoryManager(tmp_project)
    mgr.append_memory("npc", "user", "hello")
    assert len(mgr.read_memory("npc")) == 1
    mgr.clear_memory("npc")
    assert len(mgr.read_memory("npc")) == 0


def test_config_to_from_dict():
    cfg = NPCConfig(
        npc_id="test", name="Test", persona="p",
        model="m", temperature=0.5, max_tokens=100,
    )
    d = cfg.to_dict()
    cfg2 = NPCConfig.from_dict(d)
    assert cfg2.npc_id == "test"
    assert cfg2.persona == "p"
    assert cfg2.temperature == 0.5
    assert cfg2.max_tokens == 100


def test_memory_with_metadata(tmp_project: Path):
    mgr = NPCMemoryManager(tmp_project)
    mgr.append_memory("npc", "user", "hello", {"location": "temple"})
    entries = mgr.read_memory("npc")
    assert entries[0]["metadata"]["location"] == "temple"