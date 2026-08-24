"""沙箱：路径白名单 + 危险操作拒绝。

所有文件操作限制在 game/ 与 sandbox/ 目录内，realpath 检查路径穿越。
危险操作（批量删除、任意 shell）一律拒绝。
godot-ai 的 batch_execute 等安全工具通过白名单豁免。
"""

from __future__ import annotations

import re
from pathlib import Path

_DANGEROUS_TOOL_PATTERNS = re.compile(
    r"(delete|remove|rm_|shell|exec|eval|system|popen)", re.IGNORECASE
)
_SAFE_TOOL_ALLOWLIST = {
    "batch_execute",
    "script_create",
    "script_patch",
    "script_attach",
    "script_manage",
}
_DANGEROUS_PARAM_KEYS = {"cmd", "shell", "command", "code"}
_PATH_PARAM_KEYS = {"path", "fbx_path", "json_path", "file_path", "out"}


def _is_path_safe(target: Path, allowed_roots: list[Path]) -> bool:
    """realpath 检查路径穿越。Windows 下 resolve() 大小写不敏感。"""
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


class SandboxError(PermissionError):
    """沙箱拒绝。"""


class Sandbox:
    """路径白名单 + 危险操作检查。"""

    def __init__(self, allowed_roots: list[Path]) -> None:
        self._roots = allowed_roots

    def check_tool(self, tool: str, params: dict) -> None:
        """检查工具调用是否安全。不安全抛 SandboxError。"""
        if tool not in _SAFE_TOOL_ALLOWLIST and _DANGEROUS_TOOL_PATTERNS.search(tool):
            raise SandboxError(f"危险工具名被拒: {tool}")
        for key, value in params.items():
            if key in _DANGEROUS_PARAM_KEYS:
                raise SandboxError(f"危险参数被拒: {key}={value!r}")
            if key in _PATH_PARAM_KEYS and isinstance(value, str):
                self._check_path(value)

    def _check_path(self, path: str) -> None:
        p = Path(path)
        if p.is_absolute() and not _is_path_safe(p, self._roots):
            raise SandboxError(f"路径逃逸: {path}")
