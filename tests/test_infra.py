"""Prompt 7 infra 单元测试：LFS 检测 + Gitea 种子 + 离线导出 + .gitattributes。"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from infra.scripts.check_lfs import check_lfs
from infra.scripts.export_offline import export_ollama_models
from infra.scripts.seed_gitea import _GITATTRIBUTES, init_game_repo

# ---------- .gitattributes ----------


def test_gitattributes_content_has_fbx_lfs():
    assert "*.fbx filter=lfs diff=lfs merge=lfs -text" in _GITATTRIBUTES


def test_gitattributes_content_has_png_lfs():
    assert "*.png filter=lfs" in _GITATTRIBUTES


def test_gitattributes_content_has_wav_lfs():
    assert "*.wav filter=lfs" in _GITATTRIBUTES


def test_game_gitattributes_exists():
    """game/.gitattributes 文件存在且含 LFS 规则。"""
    attrs = Path(__file__).resolve().parents[1] / "game" / ".gitattributes"
    assert attrs.exists()
    content = attrs.read_text(encoding="utf-8")
    assert "*.fbx" in content
    assert "*.png" in content


# ---------- check_lfs ----------


def test_check_lfs_returns_bool():
    """check_lfs 返回 bool（不关心真实环境是否装了 LFS）。"""
    result = check_lfs()
    assert isinstance(result, bool)


# ---------- seed_gitea ----------


@pytest.mark.skipif(
    subprocess.run(["git", "--version"], capture_output=True).returncode != 0,
    reason="git 未安装",
)
def test_init_game_repo_creates_gitattributes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """init_game_repo 在目标目录创建 .gitattributes。"""
    import infra.scripts.seed_gitea as mod

    fake_game = tmp_path / "game"
    fake_game.mkdir()
    monkeypatch.setattr(mod, "_GAME_DIR", fake_game)
    ok = init_game_repo()
    assert ok
    assert (fake_game / ".gitattributes").exists()
    assert (fake_game / ".gitignore").exists()
    assert (fake_game / ".git").exists()


# ---------- export_offline ----------


def test_export_ollama_models_writes_manifest(tmp_path: Path):
    ok = export_ollama_models(tmp_path)
    assert ok
    manifest = tmp_path / "ollama-models.txt"
    assert manifest.exists()
    content = manifest.read_text(encoding="utf-8")
    assert "qwen3.5:4b" in content
    assert "qwen3.5:2b" in content


# ---------- docker-compose ----------


def test_docker_compose_exists():
    compose = Path(__file__).resolve().parents[1] / "infra" / "docker-compose.yml"
    assert compose.exists()


def test_docker_compose_binds_localhost():
    """docker-compose 绑定 127.0.0.1（安全要求）。"""
    compose = Path(__file__).resolve().parents[1] / "infra" / "docker-compose.yml"
    content = compose.read_text(encoding="utf-8")
    assert "127.0.0.1:13000" in content
    assert "127.0.0.1:18080" in content


# ---------- SECURITY.md ----------


def test_security_doc_exists():
    sec = Path(__file__).resolve().parents[1] / "infra" / "SECURITY.md"
    assert sec.exists()
    content = sec.read_text(encoding="utf-8")
    assert "127.0.0.1" in content
    assert "API Key" in content
