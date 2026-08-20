"""storage 包：Repository 抽象层。"""

from storage.base import Repository
from storage.sqlite_repo import SQLiteRepo

__all__ = ["Repository", "SQLiteRepo"]
