"""角色配置 — 从 config/team.json 加载智能体团队定义。

用户可在 team.json 中增删角色、配置每个角色的 LLM/插件/工具链/流转关系。
orchestrator 从 TeamConfig 动态构建 LangGraph 图。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_DEFAULT_CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


@dataclass
class RoleConfig:
    """单个角色配置。"""

    id: str
    label: str = ""
    icon: str = ""
    llm: str = "cloud"
    kind: str = "custom"
    next: str = ""
    plugin: str = ""
    chain: str = ""
    prompt: str = ""
    outputs: list[str] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    asset_type: str = ""
    asset_types: list[str] = field(default_factory=list)
    output_dir: str = ""
    build_output: str = ""
    gold_sample: bool = False
    validate: bool = False
    max_retries: int = 3
    next_on_pass: str = ""
    next_on_fail: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RoleConfig:
        known = {f for f in cls.__dataclass_fields__}
        return cls(
            id=d["id"],
            label=d.get("label", ""),
            icon=d.get("icon", ""),
            llm=d.get("llm", "cloud"),
            kind=d.get("kind", "custom"),
            next=d.get("next", ""),
            plugin=d.get("plugin", ""),
            chain=d.get("chain", ""),
            prompt=d.get("prompt", ""),
            outputs=d.get("outputs", []),
            inputs=d.get("inputs", []),
            tools=d.get("tools", []),
            asset_type=d.get("asset_type", ""),
            asset_types=d.get("asset_types", []),
            output_dir=d.get("output_dir", ""),
            build_output=d.get("build_output", ""),
            gold_sample=d.get("gold_sample", False),
            validate=d.get("validate", False),
            max_retries=d.get("max_retries", 3),
            next_on_pass=d.get("next_on_pass", ""),
            next_on_fail=d.get("next_on_fail", ""),
            extra={k: v for k, v in d.items() if k not in known},
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        for f in self.__dataclass_fields__:
            if f == "extra":
                continue
            d[f] = getattr(self, f)
        d.update(self.extra)
        return d


class TeamConfig:
    """团队配置 — 管理角色列表。

    用法:
        team = TeamConfig()
        team.load()                       # 从 config/team.json 加载
        roles = team.roles()              # 所有角色
        first = team.first_role()         # 第一个角色
        nxt = team.next_role("designer")  # designer 的下一个角色
    """

    def __init__(self, config_dir: Path | None = None) -> None:
        self._config_dir = config_dir or _DEFAULT_CONFIG_DIR
        self._roles: list[RoleConfig] = []
        self._by_id: dict[str, RoleConfig] = {}

    def load(self, config_file: str = "team.json") -> None:
        """从 JSON 加载团队配置。"""
        path = self._config_dir / config_file
        if not path.exists():
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        self._roles = [RoleConfig.from_dict(r) for r in data.get("roles", [])]
        self._by_id = {r.id: r for r in self._roles}

    def roles(self) -> list[RoleConfig]:
        return list(self._roles)

    def get(self, role_id: str) -> RoleConfig | None:
        return self._by_id.get(role_id)

    def first_role(self) -> RoleConfig | None:
        return self._roles[0] if self._roles else None

    def next_role(self, role_id: str) -> RoleConfig | None:
        role = self._by_id.get(role_id)
        if not role:
            return None
        nxt = role.next or role.next_on_pass
        return self._by_id.get(nxt) if nxt else None

    def ids(self) -> list[str]:
        return [r.id for r in self._roles]

    def save(self, config_file: str = "team.json") -> None:
        """保存配置到 JSON。"""
        path = self._config_dir / config_file
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"roles": [r.to_dict() for r in self._roles]}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
