"""Prompt 2b krita-mcp 单元测试：mock libkis + 白名单分发。"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_COMMON = str(_ROOT / "mcp-servers" / "common")
_KRITA_PLUGIN = str(_ROOT / "mcp-servers" / "krita-mcp" / "krita_plugin")
for _p in (_COMMON, _KRITA_PLUGIN):
    if _p not in sys.path:
        sys.path.insert(0, _p)

sys.modules.setdefault("krita", MagicMock())
sys.modules.setdefault("PyQt5", MagicMock())
sys.modules.setdefault("PyQt5.QtCore", MagicMock())

from game_agent_krita.command_executor import (  # noqa: E402
    DISPATCH,
    execute,
)


def test_dispatch_has_nine_tools():
    assert set(DISPATCH) == {
        "create_canvas",
        "draw_rect",
        "draw_circle",
        "draw_line",
        "fill_layer",
        "export_png",
        "export_sprite_sheet",
        "apply_palette",
        "get_canvas_info",
    }


def test_execute_unknown_tool_rejected():
    with pytest.raises(ValueError, match="未知工具"):
        execute("evil_shell", {"cmd": "rm -rf /"})


def test_execute_calls_create_canvas():
    import krita

    app = krita.Krita.instance.return_value
    doc = MagicMock(width=64, height=64)
    app.createDocument.return_value = doc
    result = execute(
        "create_canvas", {"width": 64, "height": 64, "dpi": 72, "color_space": "RGBA8"}
    )
    app.createDocument.assert_called_once()
    assert result["width"] == 64


def test_export_png_pot_ok():
    import krita

    doc = MagicMock()
    doc.width.return_value = 64
    doc.height.return_value = 64
    krita.Krita.instance.return_value.activeDocument.return_value = doc
    result = execute("export_png", {"asset_id": "texture_hero", "path": "test.png"})
    assert result["pot"] == [True, True]


def test_export_png_npot_non_ui_rejected():
    import krita

    doc = MagicMock()
    doc.width.return_value = 100
    doc.height.return_value = 100
    krita.Krita.instance.return_value.activeDocument.return_value = doc
    with pytest.raises(ValueError, match="非 2 的幂"):
        execute("export_png", {"asset_id": "texture_hero", "path": "test.png"})


def test_export_png_npot_ui_exempt():
    import krita

    doc = MagicMock()
    doc.width.return_value = 96
    doc.height.return_value = 32
    krita.Krita.instance.return_value.activeDocument.return_value = doc
    result = execute("export_png", {"asset_id": "ui_btn", "path": "test.png"})
    assert result["pot"] == [False, True]
