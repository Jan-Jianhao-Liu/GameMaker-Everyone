"""Prompt 5 SQLiteRepo 单元测试：任务记忆 + 资产锁 + 审计。"""

from __future__ import annotations

from pathlib import Path

import pytest

from storage.sqlite_repo import SQLiteRepo


@pytest.fixture()
def repo(tmp_path: Path) -> SQLiteRepo:
    return SQLiteRepo(tmp_path / "test.db")


# ---------- 任务记忆 ----------


def test_save_and_query_task_memory(repo: SQLiteRepo):
    repo.save_task_memory("artist3d", "T1", "create_primitive", "ok", "立方体生成成功")
    repo.save_task_memory("coder", "T1", "attach_script", "ok", "脚本挂载完成")
    rows = repo.query_task_memory("T1")
    assert len(rows) == 2
    assert rows[0]["agent"] == "artist3d"
    assert rows[0]["action"] == "create_primitive"
    assert rows[1]["agent"] == "coder"
    assert rows[1]["lesson"] == "脚本挂载完成"


def test_query_empty_task_memory(repo: SQLiteRepo):
    assert repo.query_task_memory("nonexistent") == []


def test_task_memory_isolated_by_task_id(repo: SQLiteRepo):
    repo.save_task_memory("artist3d", "T1", "a1", "ok", "l1")
    repo.save_task_memory("artist3d", "T2", "a2", "ok", "l2")
    assert len(repo.query_task_memory("T1")) == 1
    assert len(repo.query_task_memory("T2")) == 1


# ---------- 资产锁 ----------


def test_acquire_lock_success(repo: SQLiteRepo):
    assert repo.acquire_lock("asset_001", "artist3d") is True


def test_acquire_lock_blocks_second_holder(repo: SQLiteRepo):
    assert repo.acquire_lock("asset_001", "artist3d") is True
    assert repo.acquire_lock("asset_001", "artist2d") is False


def test_release_lock_by_holder(repo: SQLiteRepo):
    repo.acquire_lock("asset_001", "artist3d")
    assert repo.release_lock("asset_001", "artist3d") is True


def test_release_lock_rejected_for_non_holder(repo: SQLiteRepo):
    repo.acquire_lock("asset_001", "artist3d")
    assert repo.release_lock("asset_001", "artist2d") is False


def test_release_then_reacquire(repo: SQLiteRepo):
    repo.acquire_lock("asset_001", "artist3d")
    repo.release_lock("asset_001", "artist3d")
    assert repo.acquire_lock("asset_001", "artist2d") is True


def test_release_nonexistent_lock(repo: SQLiteRepo):
    assert repo.release_lock("never_locked", "artist3d") is False


def test_locks_isolated_by_asset_id(repo: SQLiteRepo):
    assert repo.acquire_lock("asset_A", "artist3d") is True
    assert repo.acquire_lock("asset_B", "artist2d") is True


# ---------- 审计 ----------


def test_log_and_query_audit(repo: SQLiteRepo):
    repo.log_audit("artist3d", "create_primitive", {"type": "cube"}, "ok")
    repo.log_audit("coder", "build_export", {"platform": "windows"}, "error")
    all_rows = repo.query_audit()
    assert len(all_rows) == 2
    assert all_rows[0]["agent"] == "coder"
    assert all_rows[0]["status"] == "error"
    assert all_rows[1]["agent"] == "artist3d"


def test_query_audit_filter_by_agent(repo: SQLiteRepo):
    repo.log_audit("artist3d", "create_primitive", {}, "ok")
    repo.log_audit("coder", "build_export", {}, "ok")
    rows = repo.query_audit(agent="artist3d")
    assert len(rows) == 1
    assert rows[0]["agent"] == "artist3d"


def test_query_audit_limit(repo: SQLiteRepo):
    for i in range(10):
        repo.log_audit("artist3d", "tool", {"i": i}, "ok")
    assert len(repo.query_audit(limit=3)) == 3


def test_audit_params_truncated(repo: SQLiteRepo):
    big = {"k": "v" * 1000}
    repo.log_audit("artist3d", "t", big, "ok")
    row = repo.query_audit()[0]
    assert len(row["params_json"]) <= 500


# ---------- 持久化 ----------


def test_persistence_across_instances(tmp_path: Path):
    db = tmp_path / "persist.db"
    r1 = SQLiteRepo(db)
    r1.save_task_memory("artist3d", "T1", "a", "ok", "l")
    r1.acquire_lock("asset_X", "artist3d")
    r1.close()
    r2 = SQLiteRepo(db)
    assert len(r2.query_task_memory("T1")) == 1
    assert r2.acquire_lock("asset_X", "artist2d") is False
