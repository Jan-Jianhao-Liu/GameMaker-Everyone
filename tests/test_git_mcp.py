"""Prompt 8 git-mcp 单元测试：真实 tmp_path git 仓库 + LFS 检测 + 权限。"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_COMMON = str(_ROOT / "mcp-servers" / "common")
_GIT_MCP = str(_ROOT / "mcp-servers" / "git-mcp")
for _p in (_COMMON, _GIT_MCP):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "git_mcp_server", _ROOT / "mcp-servers" / "git-mcp" / "server.py"
)
git_server = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(git_server)

# ---------- 纯函数 ----------


def test_is_lfs_path():
    assert git_server._is_lfs_path(Path("model_hero.fbx"))
    assert git_server._is_lfs_path(Path("texture_bg.png"))
    assert git_server._is_lfs_path(Path("sfx_jump.wav"))
    assert not git_server._is_lfs_path(Path("scene.tscn"))
    assert not git_server._is_lfs_path(Path("script.gd"))


def test_meta_message():
    msg = git_server._meta_message("产出方块", "T001", "artist3d", "blender-mcp")
    assert "产出方块" in msg
    assert "task=T001" in msg
    assert "agent=artist3d" in msg
    assert "source=blender-mcp" in msg


# ---------- LFS 检测 ----------


def test_check_lfs_missing_raises():
    repo = MagicMock()
    import git

    repo.git.lfs.side_effect = git.GitCommandError("lfs", 1, "not found")
    with pytest.raises(RuntimeError, match="Git LFS 未安装"):
        git_server._check_lfs(repo)


def test_check_lfs_ok():
    repo = MagicMock()
    repo.git.lfs.return_value = "git-lfs/3.0"
    git_server._check_lfs(repo)


# ---------- rollback 权限（不需 repo） ----------


def test_rollback_rejects_non_supervisor():
    result = git_server.rollback(
        asset_id="model_hero.fbx", version="abc123", caller_role="artist3d"
    )
    assert result["status"] == "error"
    assert "权限拒绝" in result["error"]


# ---------- 真实 git 仓库（跳过 LFS） ----------


@pytest.fixture
def fake_repo(tmp_path, monkeypatch):
    """建真实 git 仓库，patch _GAME_DIR + 跳过 LFS 检测。"""
    import git

    repo_dir = tmp_path / "game"
    repo_dir.mkdir()
    repo = git.Repo.init(repo_dir)
    (repo_dir / ".gitattributes").write_text("*.fbx filter=lfs diff=lfs merge=lfs\n")
    repo.index.add([".gitattributes"])
    repo.index.commit("init")
    monkeypatch.setattr(git_server, "_GAME_DIR", repo_dir)
    monkeypatch.setattr(git_server, "_check_lfs", lambda r: None)
    return repo_dir


def test_commit_asset_ok(fake_repo):
    (fake_repo / "scene.tscn").write_text("test")
    result = git_server.commit_asset(
        asset_id="scene",
        file_paths=["scene.tscn"],
        message="add scene",
        task_id="T001",
        agent="coder",
    )
    assert result["status"] == "ok"
    assert "commit" in result["result"]


def test_snapshot_ok(fake_repo):
    result = git_server.snapshot(branch_name="snap-001")
    assert result["status"] == "ok"
    assert result["result"]["branch"] == "snap-001"


def test_snapshot_duplicate_rejected(fake_repo):
    git_server.snapshot(branch_name="snap-001")
    result = git_server.snapshot(branch_name="snap-001")
    assert result["status"] == "error"


def test_diff_status_ok(fake_repo):
    (fake_repo / "model_hero.fbx").write_text("binary")
    git_server.commit_asset(
        asset_id="model_hero",
        file_paths=["model_hero.fbx"],
        message="add hero",
        task_id="T002",
        agent="artist3d",
    )
    result = git_server.diff_status(asset_id="model_hero.fbx")
    assert result["status"] == "ok"
    assert len(result["result"]["history"]) >= 1


def test_rollback_supervisor_ok(fake_repo):
    (fake_repo / "ui_btn.png").write_text("v1")
    r1 = git_server.commit_asset(
        asset_id="ui_btn",
        file_paths=["ui_btn.png"],
        message="v1",
        task_id="T003",
        agent="artist2d",
    )
    commit1 = r1["result"]["commit"]
    (fake_repo / "ui_btn.png").write_text("v2")
    git_server.commit_asset(
        asset_id="ui_btn",
        file_paths=["ui_btn.png"],
        message="v2",
        task_id="T004",
        agent="artist2d",
    )
    result = git_server.rollback(asset_id="ui_btn.png", version=commit1, caller_role="supervisor")
    assert result["status"] == "ok"
    assert (fake_repo / "ui_btn.png").read_text() == "v1"
