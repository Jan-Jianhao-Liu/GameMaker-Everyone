"""Repository 抽象接口。Phase 1-2 由 SQLiteRepo 实现，Phase 3 可迁移到 ArcadeRepo。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Repository(ABC):
    """持久化仓库抽象接口。"""

    @abstractmethod
    def save_task_memory(
        self, agent: str, task_id: str, action: str, outcome: str, lesson: str
    ) -> None: ...

    @abstractmethod
    def query_task_memory(self, task_id: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    def acquire_lock(self, asset_id: str, holder: str) -> bool: ...

    @abstractmethod
    def release_lock(self, asset_id: str, holder: str) -> bool: ...

    @abstractmethod
    def log_audit(self, agent: str, tool: str, params: dict, status: str) -> None: ...
