"""插件注册表 — 从 config/plugins.json 加载，动态管理可用插件。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from plugins.base import PluginBase

_DEFAULT_CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


class PluginRegistry:
    """插件注册表。

    用法:
        registry = PluginRegistry()
        registry.load()                    # 从 config/plugins.json 加载
        blender = registry.get("blender")  # 获取插件实例
        editors = registry.by_type("3d_editor")
    """

    def __init__(self, config_dir: Path | None = None) -> None:
        self._config_dir = config_dir or _DEFAULT_CONFIG_DIR
        self._plugins: dict[str, PluginBase] = {}
        self._raw_config: list[dict[str, Any]] = []

    def load(self, config_file: str = "plugins.json") -> None:
        """从 JSON 配置加载插件。

        配置格式:
          [{"id": "blender", "class": "plugins.builtin.blender.BlenderPlugin",
            "name": "Blender 4.2", "type": "3d_editor", "port": 19876,
            "enabled": true, "config": {...}}]
        """
        path = self._config_dir / config_file
        if not path.exists():
            return
        self._raw_config = json.loads(path.read_text(encoding="utf-8"))
        for entry in self._raw_config:
            if not entry.get("enabled", True):
                continue
            plugin = self._instantiate(entry)
            if plugin is not None:
                self._plugins[plugin.plugin_id] = plugin

    def _instantiate(self, entry: dict[str, Any]) -> PluginBase | None:
        """从配置条目实例化插件。"""
        cls_path = entry.get("class", "")
        if not cls_path:
            return None
        module_path, cls_name = cls_path.rsplit(".", 1)
        try:
            import importlib

            mod = importlib.import_module(module_path)
            cls = getattr(mod, cls_name)
            plugin = cls()
            plugin.plugin_id = entry.get("id", plugin.plugin_id)
            plugin.name = entry.get("name", plugin.name)
            plugin.plugin_type = entry.get("type", plugin.plugin_type)
            plugin.port = entry.get("port", plugin.port)
            plugin.enabled = entry.get("enabled", True)
            plugin.config = entry.get("config", {})
            return plugin
        except Exception:
            return None

    def get(self, plugin_id: str) -> PluginBase | None:
        """按 ID 获取插件。"""
        return self._plugins.get(plugin_id)

    def all(self) -> list[PluginBase]:
        """所有已加载插件。"""
        return list(self._plugins.values())

    def by_type(self, plugin_type: str) -> list[PluginBase]:
        """按类型筛选插件。"""
        return [p for p in self._plugins.values() if p.plugin_type == plugin_type]

    def ids(self) -> list[str]:
        """所有插件 ID。"""
        return list(self._plugins.keys())

    def save(self, config_file: str = "plugins.json") -> None:
        """保存当前配置到 JSON。"""
        path = self._config_dir / config_file
        path.parent.mkdir(parents=True, exist_ok=True)
        entries = []
        for p in self._plugins.values():
            entries.append({
                "id": p.plugin_id, "name": p.name, "type": p.plugin_type,
                "port": p.port, "enabled": p.enabled, "config": p.config,
                "class": f"{p.__class__.__module__}.{p.__class__.__name__}",
            })
        path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
