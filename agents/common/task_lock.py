"""资产任务锁上下文管理器。

基于 storage.SQLiteRepo.acquire_lock / release_lock。
同一 asset_id 同时只允许一个智能体操作。

用法：
    with AssetLock(repo, "asset_001", "artist3d"):
        # 生产资产
        ...

若抢锁失败抛 LockError，由调用方决定退避或转 supervisor。
"""

from __future__ import annotations

from types import TracebackType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from storage.sqlite_repo import SQLiteRepo


class LockError(RuntimeError):
    """抢锁失败。"""


class AssetLock:
    """资产互斥锁上下文管理器。"""

    def __init__(self, repo: SQLiteRepo, asset_id: str, holder: str) -> None:
        self._repo = repo
        self._asset_id = asset_id
        self._holder = holder
        self._acquired = False

    def __enter__(self) -> AssetLock:
        if not self._repo.acquire_lock(self._asset_id, self._holder):
            raise LockError(
                f"资产 {self._asset_id} 已被其他智能体锁定，{self._holder} 无法获取"
            )
        self._acquired = True
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._acquired:
            self._repo.release_lock(self._asset_id, self._holder)
