"""路径白名单校验：realpath 检查路径穿越，Windows 大小写不敏感。"""

from __future__ import annotations

from pathlib import Path


def is_path_safe(target: Path, allowed_roots: list[Path]) -> bool:
    """检查 target 是否在 allowed_roots 之内（防路径穿越）。

    Windows 下大小写不敏感，用 resolve() 规范化后比较。
    """
    try:
        resolved = target.resolve()
    except (OSError, RuntimeError):
        return False
    for root in allowed_roots:
        try:
            resolved.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False
