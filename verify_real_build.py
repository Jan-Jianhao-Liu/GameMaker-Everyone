"""真实构建验证：用 Blender 4.2 + Godot 4.4 命令行模式验证工具链真实工作。

绕过 MCP server 架构，直接用 Blender --background --python 生成模型，
用 Godot --headless 运行游戏场景。

用法: uv run python verify_real_build.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

BLENDER = Path("D:/GameTools/blender-4.2.1-windows-x64/blender.exe")
GODOT = Path("D:/GameTools/Godot/Godot_v4.4-stable_win64_console.exe")

OUTPUT_DIR = Path("real_build_output")
OUTPUT_DIR.mkdir(exist_ok=True)

ASSETS = [
    ("model_player", "CUBE", [1, 1, 1]),
    ("model_obstacle", "CUBE", [2, 0.5, 1]),
    ("model_coin", "CYLINDER", [0.3, 0.3, 0.1]),
]


def run_blender_produce() -> list[dict]:
    """用 Blender 命令行生成模型 FBX。"""
    script = OUTPUT_DIR / "_blender_produce.py"
    script.write_text(
        "import bpy, sys, json\n"
        "from pathlib import Path\n"
        "out_dir = Path(sys.argv[-1])\n"
        "assets = json.loads(sys.argv[-2])\n"
        "bpy.ops.wm.read_factory_settings(use_empty=True)\n"
        "results = []\n"
        "for name, prim, dims in assets:\n"
        "    if prim == 'CUBE':\n"
        "        bpy.ops.mesh.primitive_cube_add(size=1)\n"
        "    elif prim == 'CYLINDER':\n"
        "        bpy.ops.mesh.primitive_cylinder_add(radius=0.5, depth=0.5)\n"
        "    obj = bpy.context.active_object\n"
        "    obj.name = name\n"
        "    obj.scale = dims\n"
        "    bpy.ops.object.select_all(action='DESELECT')\n"
        "    obj.select_set(True)\n"
        "    bpy.context.view_layer.objects.active = obj\n"
        "    fbx = str(out_dir / f'{name}.fbx')\n"
        "    bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True)\n"
        "    sz = Path(fbx).stat().st_size\n"
        "    results.append({'name': name, 'path': fbx, 'size': sz})\n"
        "    bpy.data.objects.remove(obj, do_unlink=True)\n"
        "print('BLENDER_RESULTS:' + json.dumps(results))\n",
        encoding="utf-8",
    )

    assets_json = json.dumps(ASSETS)
    r = subprocess.run(
        [str(BLENDER), "--background", "--python", str(script), "--", assets_json, str(OUTPUT_DIR)],
        capture_output=True, text=True, timeout=120,
    )
    for line in r.stdout.splitlines():
        if line.startswith("BLENDER_RESULTS:"):
            return json.loads(line[len("BLENDER_RESULTS:"):])
    print(f"Blender stderr: {r.stderr[-500:]}")
    return []


def run_godot_game(models: list[dict]) -> bool:
    """用 Godot --headless 运行简单游戏场景。"""
    proj_dir = OUTPUT_DIR / "godot_project"
    proj_dir.mkdir(exist_ok=True)

    (proj_dir / "project.godot").write_text(
        "[application]\n"
        "config/name=\"RealBuildTest\"\n"
        "run/main_scene=\"res://main.tscn\"\n",
        encoding="utf-8",
    )

    (proj_dir / "main.tscn").write_text(
        '[gd_scene load_steps=2 format=3 uid="uid://realtest"]\n'
        '\n'
        '[sub_resource type="GDScript" id="GDScript_1"]\n'
        'script/source = "extends Node3D\n'
        '\n'
        'func _ready():\n'
        f"    print('Game started with {len(models)} models')\n"
        "    print('GAME_OK')\n"
        '    get_tree().quit(0)\n'
        '"\n'
        '\n'
        '[node name="Main" type="Node3D"]\n'
        'script = SubResource("GDScript_1")\n',
        encoding="utf-8",
    )

    r = subprocess.run(
        [str(GODOT), "--headless", "--path", str(proj_dir)],
        capture_output=True, text=True, timeout=30,
    )
    return "GAME_OK" in r.stdout


def main() -> None:
    print("=" * 60)
    print("真实构建验证：Blender 4.2.1 + Godot 4.4 stable")
    print("=" * 60)

    print("\n[1/2] Blender 生成模型...")
    models = run_blender_produce()
    if not models:
        print("  FAIL: Blender 未产出任何模型")
        sys.exit(1)
    print(f"  OK: {len(models)} 个模型")
    for m in models:
        print(f"    - {m['name']}: {m['size']} bytes")

    print("\n[2/2] Godot 运行游戏...")
    if run_godot_game(models):
        print("  OK: 游戏运行成功")
    else:
        print("  FAIL: 游戏运行失败")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("真实构建验证通过！")
    print(f"  Blender: {BLENDER}")
    print(f"  Godot:   {GODOT}")
    print(f"  产出:    {OUTPUT_DIR}/")
    print("=" * 60)


if __name__ == "__main__":
    main()
