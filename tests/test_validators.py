"""Prompt 1 验收测试：Schema 自检 + 检环 + 命名建议 + 贴图尺寸。"""

from __future__ import annotations

import pytest

from contracts.validators import (
    CircularDependencyError,
    TextureSizeError,
    load_schema,
    self_check,
    suggest_naming,
    validate_art_spec,
    validate_asset_manifest,
    validate_gdd,
    validate_no_circular_deps,
    validate_texture_size,
)

ART_SPEC = {
    "texture_spec": {
        "require_power_of_two": True,
        "require_square": False,
        "npot_exception": {"allowed_types": ["ui"], "requires_flag": True},
    },
    "fbx_axis": "Y_UP",
    "naming_pattern": r"^(model|texture|ui|audio|anim)_[a-z][a-z0-9]*(_[a-z][a-z0-9]*)*$",
    "allowed_formats": ["fbx", "png", "wav"],
}


def test_schema_self_check():
    results = self_check()
    assert results == {"gdd": True, "asset-manifest": True, "art-spec": True}


def test_load_schema():
    for name in ("gdd", "asset-manifest", "art-spec"):
        schema = load_schema(name)
        assert "$schema" in schema


def test_validate_gdd_ok():
    data = {
        "game_title": "方块跳跃",
        "genre": "platformer",
        "core_loop": "跳跃避障到达终点",
        "levels": [
            {
                "level_id": "lvl_00",
                "name": "第一关",
                "difficulty": 1,
                "spawn_table": [
                    {
                        "entity_id": "e1",
                        "asset_id": "model_hero",
                        "position": {"x": 0, "y": 0, "z": 0},
                        "count": 1,
                    }
                ],
            }
        ],
        "numeric_tables": {
            "schema_version": 1,
            "damage": {"entries": []},
            "economy": {"entries": []},
            "growth": {"entries": []},
        },
    }
    assert validate_gdd(data) is data


def test_validate_asset_manifest_ok():
    data = {
        "assets": [
            {
                "asset_id": "model_hero",
                "type": "model",
                "target_scene": "lvl_00",
                "dependencies": [],
                "status": "pending",
            }
        ]
    }
    assert validate_asset_manifest(data) is data


def test_validate_art_spec_ok():
    assert validate_art_spec(ART_SPEC) is ART_SPEC


def test_no_circular_deps_ok():
    manifest = {
        "assets": [
            {
                "asset_id": "model_a",
                "type": "model",
                "target_scene": "s",
                "dependencies": [],
                "status": "pending",
            },
            {
                "asset_id": "model_b",
                "type": "model",
                "target_scene": "s",
                "dependencies": ["model_a"],
                "status": "pending",
            },
            {
                "asset_id": "model_c",
                "type": "model",
                "target_scene": "s",
                "dependencies": ["model_a", "model_b"],
                "status": "pending",
            },
        ]
    }
    order = validate_no_circular_deps(manifest)
    assert set(order) == {"model_a", "model_b", "model_c"}
    assert order.index("model_a") < order.index("model_b")
    assert order.index("model_a") < order.index("model_c")
    assert order.index("model_b") < order.index("model_c")


def test_circular_deps_detected():
    manifest = {
        "assets": [
            {
                "asset_id": "model_a",
                "type": "model",
                "target_scene": "s",
                "dependencies": ["model_c"],
                "status": "pending",
            },
            {
                "asset_id": "model_b",
                "type": "model",
                "target_scene": "s",
                "dependencies": ["model_a"],
                "status": "pending",
            },
            {
                "asset_id": "model_c",
                "type": "model",
                "target_scene": "s",
                "dependencies": ["model_b"],
                "status": "pending",
            },
        ]
    }
    with pytest.raises(CircularDependencyError) as exc_info:
        validate_no_circular_deps(manifest)
    msg = str(exc_info.value)
    assert "model_a" in msg and "model_b" in msg and "model_c" in msg


@pytest.mark.parametrize(
    "bad,good",
    [
        ("Model_Hero", "model_hero"),
        ("hero_body", "model_hero_body"),
        ("texture_UI_btn", "texture_ui_btn"),
        ("model__hero", "model_hero"),
        ("model_hero_", "model_hero"),
        ("123hero", "model_a123hero"),
        ("texture_123", "texture_a123"),
    ],
)
def test_suggest_naming(bad, good):
    assert suggest_naming(bad) == good


def test_suggest_naming_already_valid():
    assert suggest_naming("model_hero_body") == "model_hero_body"


def test_texture_size_pot_ok():
    validate_texture_size(1024, 512, "texture", False, ART_SPEC)


def test_texture_size_npot_rejected():
    with pytest.raises(TextureSizeError):
        validate_texture_size(100, 100, "texture", False, ART_SPEC)


def test_texture_size_ui_npot_exempt():
    validate_texture_size(96, 32, "ui", True, ART_SPEC)


def test_texture_size_ui_npot_without_flag_rejected():
    with pytest.raises(TextureSizeError):
        validate_texture_size(96, 32, "ui", False, ART_SPEC)
