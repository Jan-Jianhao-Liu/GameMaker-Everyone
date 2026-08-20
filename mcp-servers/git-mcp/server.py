"""Git MCP Server：FastMCP + 4 白名单工具 + stdio。

用 GitPython 操作 game/ 仓库，禁止 subprocess 直接拼 git 命令（防注入）。
LFS 未安装时启动即报错并给出 Windows 安装指引，不静默降级。

启动：uv run python mcp-servers/git-mcp/server.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_COMMON = Path(__file__).resolve().parents[1] / "common"
sys.path.insert(0, str(_COMMON))

from audit import AuditLogger  # noqa: E402
from param_validator import BaseToolParams, validate_params  # noqa: E402
from path_whitelist import is_path_safe  # noqa: E402

import git  # noqa: E402
from fastmcp import FastMCP  # noqa: E402
from pydantic import Field  # noqa: E402

_GAME_DIR = Path(__file__).resolve().parents[2] / "game"
_LFS_PATTERNS = ("*.fbx", "*.png", "*.wav")
_LFS_INSTALL_HINT = (
    "Git LFS 未安装或未初始化。Windows 安装指引：\n"
    "  1. 下载 https://git-lfs.com/\n"
    "  2. git lfs install\n"
    "  3. 在 game/ 仓库执行 git lfs install\n"
    "不静默降级为普通提交，请安装后重启。"
)

mcp = FastMCP("git-mcp")
audit = AuditLogger("git-mcp")


def _check_lfs(repo: git.Repo) -> None:
    """检测 LFS 可用，不可用抛 RuntimeError。"""
    try:
        repo.git.lfs("version")
    except git.GitCommandError as e:
        raise RuntimeError(_LFS_INSTALL_HINT) from e


def _ensure_repo() -> git.Repo:
    if not _GAME_DIR.exists():
        raise RuntimeError(f"game/ 仓库不存在: {_GAME_DIR}")
    try:
        repo = git.Repo(_GAME_DIR)
    except git.InvalidGitRepositoryError as e:
        raise RuntimeError(f"game/ 不是 git 仓库: {_GAME_DIR}") from e
    _check_lfs(repo)
    return repo


def _meta_message(message: str, task_id: str, agent: str, source: str) -> str:
    return f"{message}\n\n[meta] task={task_id} agent={agent} source={source}"


def _is_lfs_path(path: Path) -> bool:
    return any(path.match(p) for p in _LFS_PATTERNS)


class CommitAssetParams(BaseToolParams):
    asset_id: str = Field(min_length=1)
    file_paths: list[str] = Field(min_length=1)
    message: str = Field(min_length=1)
    task_id: str = Field(default="unknown")
    agent: str = Field(default="unknown")
    source: str = Field(default="git-mcp")


class SnapshotParams(BaseToolParams):
    branch_name: str = Field(min_length=1)


class DiffStatusParams(BaseToolParams):
    asset_id: str = Field(min_length=1)


class RollbackParams(BaseToolParams):
    asset_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    caller_role: str = Field(default="supervisor")


@mcp.tool
def commit_asset(
    asset_id: str,
    file_paths: list[str],
    message: str,
    task_id: str = "unknown",
    agent: str = "unknown",
    source: str = "git-mcp",
) -> dict:
    """将资产加入暂存并提交；自动检测 .fbx/.png/.wav 走 LFS。"""
    p = validate_params(CommitAssetParams, locals())
    try:
        repo = _ensure_repo()
        roots = [_GAME_DIR]
        for fp in p.file_paths:
            full = _GAME_DIR / fp
            if not is_path_safe(full, roots):
                raise ValueError(f"路径逃逸: {fp}")
        for fp in p.file_paths:
            full = _GAME_DIR / fp
            if _is_lfs_path(full):
                repo.git.lfs("track", str(Path(fp).name))
        repo.index.add(p.file_paths)
        commit = repo.index.commit(_meta_message(
            p.message, p.task_id, p.agent, p.source
        ))
        result = {"commit": commit.hexsha[:12], "files": p.file_paths}
        audit.info("commit_asset", params=locals(), result=result)
        return {"status": "ok", "result": result}
    except Exception as e:  # noqa: BLE001
        audit.error("commit_asset", str(e), params=locals())
        return {"status": "error", "error": str(e)}


@mcp.tool
def snapshot(branch_name: str) -> dict:
    """为当前 game/ 创建分支快照（每轮智能体施工前调用，失败可回滚）。"""
    p = validate_params(SnapshotParams, {"branch_name": branch_name})
    try:
        repo = _ensure_repo()
        if branch_name in [h.name for h in repo.heads]:
            raise ValueError(f"分支已存在: {branch_name}")
        head = repo.create_head(branch_name)
        result = {"branch": branch_name, "from": repo.active_branch.name}
        audit.info("snapshot", params={"branch_name": branch_name}, result=result)
        return {"status": "ok", "result": result}
    except Exception as e:  # noqa: BLE001
        audit.error("snapshot", str(e), params={"branch_name": branch_name})
        return {"status": "error", "error": str(e)}


@mcp.tool
def diff_status(asset_id: str) -> dict:
    """返回指定资产的版本历史摘要（版本号、修改者、变更类型）。"""
    p = validate_params(DiffStatusParams, {"asset_id": asset_id})
    try:
        repo = _ensure_repo()
        commits = list(repo.iter_commits(paths=p.asset_id, max_count=20))
        history = [
            {
                "version": c.hexsha[:12],
                "author": c.author.name,
                "date": c.committed_datetime.isoformat(),
                "message": c.message.strip().split("\n")[0],
            }
            for c in commits
        ]
        result = {"asset_id": p.asset_id, "history": history}
        audit.info("diff_status", params={"asset_id": asset_id}, result=result)
        return {"status": "ok", "result": result}
    except Exception as e:  # noqa: BLE001
        audit.error("diff_status", str(e), params={"asset_id": asset_id})
        return {"status": "error", "error": str(e)}


@mcp.tool
def rollback(asset_id: str, version: str, caller_role: str = "supervisor") -> dict:
    """回滚单个资产到指定版本（仅 supervisor 角色有权，由网关做角色校验）。"""
    p = validate_params(RollbackParams, locals())
    if p.caller_role != "supervisor":
        msg = f"权限拒绝：rollback 仅 supervisor 可调用，当前角色 {p.caller_role}"
        audit.error("rollback", msg, params=locals())
        return {"status": "error", "error": msg}
    try:
        repo = _ensure_repo()
        repo.git.checkout(p.version, "--", p.asset_id)
        result = {"asset_id": p.asset_id, "restored_to": p.version}
        audit.info("rollback", params=locals(), result=result)
        return {"status": "ok", "result": result}
    except Exception as e:  # noqa: BLE001
        audit.error("rollback", str(e), params=locals())
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    mcp.run(transport="stdio")