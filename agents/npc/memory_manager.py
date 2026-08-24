"""NPC 记忆管理 — 桥接 agent 流水线与游戏内 NPC 对话系统。

读取/写入游戏项目中的 NPC JSONL 记忆文件，
让 designer/coder agent 能配置 NPC 人格、注入背景故事、检索对话历史。

文件布局:
  game_projects/<project>/npc_memory/<npc_id>.jsonl
  game_projects/<project>/npc_config/<npc_id>.json
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class NPCConfig:
    """NPC 配置（人格 + 模型参数）。"""

    npc_id: str
    name: str
    persona: str = ""
    model: str = "my-qwen4b-no-think:latest"
    temperature: float = 0.7
    max_tokens: int = 256
    interaction_range: float = 3.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "npc_id": self.npc_id,
            "name": self.name,
            "persona": self.persona,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "interaction_range": self.interaction_range,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> NPCConfig:
        return cls(
            npc_id=d["npc_id"],
            name=d.get("name", d["npc_id"]),
            persona=d.get("persona", ""),
            model=d.get("model", "my-qwen4b-no-think:latest"),
            temperature=d.get("temperature", 0.7),
            max_tokens=d.get("max_tokens", 256),
            interaction_range=d.get("interaction_range", 3.0),
            metadata=d.get("metadata", {}),
        )


class NPCMemoryManager:
    """管理游戏项目中所有 NPC 的配置和记忆。"""

    def __init__(self, project_root: Path) -> None:
        self._root = project_root
        self._memory_dir = project_root / "npc_memory"
        self._config_dir = project_root / "npc_config"
        self._memory_dir.mkdir(parents=True, exist_ok=True)
        self._config_dir.mkdir(parents=True, exist_ok=True)

    def save_config(self, config: NPCConfig) -> Path:
        path = self._config_dir / f"{config.npc_id}.json"
        path.write_text(
            json.dumps(config.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def load_config(self, npc_id: str) -> NPCConfig | None:
        path = self._config_dir / f"{npc_id}.json"
        if not path.exists():
            return None
        return NPCConfig.from_dict(
            json.loads(path.read_text(encoding="utf-8"))
        )

    def list_npcs(self) -> list[str]:
        return [
            p.stem for p in self._config_dir.glob("*.json")
        ]

    def append_memory(
        self, npc_id: str, role: str, content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        import time
        entry = {
            "ts": time.time(),
            "role": role,
            "content": content,
            "metadata": metadata or {},
        }
        path = self._memory_dir / f"{npc_id}.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def read_memory(self, npc_id: str, n: int = 50) -> list[dict[str, Any]]:
        path = self._memory_dir / f"{npc_id}.jsonl"
        if not path.exists():
            return []
        entries: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries[-n:] if len(entries) > n else entries

    def get_context_string(self, npc_id: str, n: int = 10) -> str:
        entries = self.read_memory(npc_id, n)
        return "\n".join(
            f"{e.get('role', 'unknown')}: {e.get('content', '')}"
            for e in entries
        )

    def clear_memory(self, npc_id: str) -> None:
        path = self._memory_dir / f"{npc_id}.jsonl"
        if path.exists():
            path.unlink()