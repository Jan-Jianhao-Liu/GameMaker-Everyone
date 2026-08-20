"""Gitea 初始化：创建 game/ 仓库 + 配置 .gitattributes（LFS 强制）。

用法：python -m infra.scripts.seed_gitea
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_GAME_DIR = _ROOT / "game"
_GITATTRIBUTES = """\
# Git LFS 规则：大文件走 LFS，避免仓库膨胀
*.fbx filter=lfs diff=lfs merge=lfs -text
*.png filter=lfs diff=lfs merge=lfs -text
*.wav filter=lfs diff=lfs merge=lfs -text
*.ogg filter=lfs diff=lfs merge=lfs -text
*.mp3 filter=lfs diff=lfs merge=lfs -text
*.tga filter=lfs diff=lfs merge=lfs -text
*.blend filter=lfs diff=lfs merge=lfs -text
*.glb filter=lfs diff=lfs merge=lfs -text
*.gltf filter=lfs diff=lfs merge=lfs -text
"""


def init_game_repo() -> bool:
    """初始化 game/ 为 git 仓库并配置 LFS。"""
    _GAME_DIR.mkdir(parents=True, exist_ok=True)
    gitignore = _GAME_DIR / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(
            "# Godot 编辑器生成\n.godot/\n# 构建产物\nbuild/\n", encoding="utf-8"
        )
    attrs = _GAME_DIR / ".gitattributes"
    attrs.write_text(_GITATTRIBUTES, encoding="utf-8")

    try:
        is_repo = (_GAME_DIR / ".git").exists()
        if not is_repo:
            subprocess.run(
                ["git", "init"], cwd=str(_GAME_DIR), check=True, capture_output=True
            )
        subprocess.run(
            ["git", "lfs", "install"], cwd=str(_GAME_DIR),
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "add", ".gitattributes", ".gitignore"],
            cwd=str(_GAME_DIR), check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "初始化 game 仓库 + LFS 规则"],
            cwd=str(_GAME_DIR), check=False, capture_output=True,
        )
    except subprocess.SubprocessError as e:
        print(f"✗ 初始化失败: {e}", file=sys.stderr)
        return False
    print(f"✓ game/ 仓库已初始化，LFS 规则已配置（{_GAME_DIR}）")
    return True


if __name__ == "__main__":
    sys.exit(0 if init_game_repo() else 1)
