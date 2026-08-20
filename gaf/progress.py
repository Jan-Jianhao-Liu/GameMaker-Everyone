"""终端彩色进度展示。

每个智能体角色一个颜色，实时输出当前任务与产出物路径。
用 ANSI 色码（Windows 10+ Terminal 原生支持，无需 colorama）。
"""

from __future__ import annotations

import sys
from typing import Any

_ROLE_COLORS: dict[str, str] = {
    "designer": "\033[36m",    # cyan
    "supervisor": "\033[35m",  # magenta
    "artist3d": "\033[33m",    # yellow
    "artist2d": "\033[33m",    # yellow
    "coder": "\033[34m",       # blue
    "qa": "\033[32m",          # green
}
_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"


def _emit(msg: str, stream: Any = None) -> None:
    out = stream or sys.stdout
    print(msg, file=out, flush=True)


def info(msg: str, stream: Any = None) -> None:
    _emit(f"{_DIM}[gaf]{_RESET} {msg}", stream)


def role_event(role: str, action: str, detail: str = "", stream: Any = None) -> None:
    """输出某角色的当前任务。"""
    color = _ROLE_COLORS.get(role, "")
    line = f"{color}{_BOLD}[{role}]{_RESET} {action}"
    if detail:
        line += f" {color}→ {detail}{_RESET}"
    _emit(line, stream)


def checkpoint(msg: str, stream: Any = None) -> None:
    """人工卡点提示（醒目）。"""
    _emit(f"\n{_BOLD}\033[33m⚠ 人工卡点{_RESET} {msg}\n", stream)


def error(msg: str, stream: Any = None) -> None:
    _emit(f"\033[31m✗ {msg}{_RESET}", stream)


def success(msg: str, stream: Any = None) -> None:
    _emit(f"\033[32m✓ {msg}{_RESET}", stream)
