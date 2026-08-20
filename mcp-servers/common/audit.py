"""审计日志：写入 logs/<name>.log，结构化错误码。"""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any


class AuditLogger:
    """线程安全的审计日志器。所有 MCP 工具调用都记录。"""

    def __init__(self, name: str, log_dir: Path | None = None) -> None:
        if log_dir is None:
            log_dir = Path(__file__).resolve().parents[2] / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        self._path = log_dir / f"{name}.log"
        self._lock = threading.Lock()

    def log(self, tool: str, params: dict[str, Any],
            status: str, result: Any = None, error: str | None = None) -> None:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "tool": tool,
            "params": params,
            "status": status,
            "result": result,
            "error": error,
        }
        line = json.dumps(entry, ensure_ascii=False, default=str)
        with self._lock:
            with self._path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")

    def info(self, tool: str, **fields: Any) -> None:
        self.log(tool, fields.pop("params", {}), "ok", **fields)

    def error(self, tool: str, error: str, **fields: Any) -> None:
        self.log(tool, fields.pop("params", {}), "error", error=error, **fields)