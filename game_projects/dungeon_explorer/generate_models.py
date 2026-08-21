"""Blender 脚本：为地牢探险者游戏生成 3D 模型。

生成资产：
  - player.fbx    玩家角色（胶囊体+头部）
  - enemy.fbx     敌人（红色方块体）
  - dungeon.fbx   地牢房间（地板+墙壁）
  - sword.fbx     武器（长条形）

用法: blender --background --python generate_models.py
"""
import bpy
import bmesh
import math
import os
from mathutils import Vector

OUTPUT_DIR = os.path.join(os.path.dirname(bpy.data.filepath) if bpy.data.filepath else os.getcwd(), "assets", "models")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for mesh in bpy.data.meshes:
        bpy.data.meshes.remove(mesh)
    for mat in bpy.data.materials:
        bpy.data.materials.remove(mat)


def make_material(name, color, roughness=0.5, metallic=0.0):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
    return mat


def export_fbx(objects, filename):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True)
    filepath = os.path.join(OUTPUT_DIR, filename)
    bpy.ops.export_scene.fbx(
        filepath=filepath,
        use_selection=True,
        apply_unit_scale=True,
        axis_forward='Y', axis_up='Z',
        object_types={'MESH'},
    )
    print(f"Exported: {filepath}")
    return filepath


def create_player():
    clear_scene()
    body_mat = make_material("PlayerBody", (0.2, 0.5, 0.9), roughness=0.4)
    head_mat = make_material("PlayerHead", (0.9, 0.7, 0.5), roughness=0.6)

    bpy.ops.mesh.primitive_cylinder_add(radius=0.4, depth=1.2, location=(0, 0, 0.6))
    body = bpy.context.active_object
    body.name = "PlayerBody"
    body.data.materials.append(body_mat)

    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.3, location=(0, 0, 1.5))
    head = bpy.context.active_object
    head.name = "PlayerHead"
    head.data.materials.append(head_mat)

    bpy.ops.mesh.primitive_cube_add(size=0.6, location=(0.5, 0, 0.8))
    arm = bpy.context.active_object
    arm.name = "PlayerArm"
    arm.data.materials.append(body_mat)

    return [body, head, arm]


def create_enemy():
    clear_scene()
    enemy_mat = make_material("EnemyBody", (0.8, 0.2, 0.2), roughness=0.5)
    eye_mat = make_material("EnemyEye", (1.0, 1.0, 0.0), roughness=0.2)

    bpy.ops.mesh.primitive_cube_add(size=0.8, location=(0, 0, 0.4))
    body = bpy.context.active_object
    body.name = "EnemyBody"
    body.data.materials.append(enemy_mat)

    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.1, location=(0.2, -0.3, 0.5))
    eye1 = bpy.context.active_object
    eye1.name = "EnemyEye1"
    eye1.data.materials.append(eye_mat)

    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.1, location=(-0.2, -0.3, 0.5))
    eye2 = bpy.context.active_object
    eye2.name = "EnemyEye2"
    eye2.data.materials.append(eye_mat)

    return [body, eye1, eye2]


def create_dungeon():
    clear_scene()
    floor_mat = make_material("Floor", (0.3, 0.3, 0.35), roughness=0.8)
    wall_mat = make_material("Wall", (0.4, 0.35, 0.3), roughness=0.7)

    bpy.ops.mesh.primitive_plane_add(size=10, location=(0, 0, 0))
    floor = bpy.context.active_object
    floor.name = "Floor"
    floor.data.materials.append(floor_mat)

    walls = []
    wall_positions = [
        (5, 0, 1.5, 0.2, 10, 3),
        (-5, 0, 1.5, 0.2, 10, 3),
        (0, 5, 1.5, 10, 0.2, 3),
        (0, -5, 1.5, 10, 0.2, 3),
    ]
    for i, (x, y, z, sx, sy, sz) in enumerate(wall_positions):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, z))
        wall = bpy.context.active_object
        wall.name = f"Wall_{i}"
        wall.scale = (sx, sy, sz)
        wall.data.materials.append(wall_mat)
        walls.append(wall)

    return [floor] + walls


def create_sword():
    clear_scene()
    blade_mat = make_material("Blade", (0.8, 0.8, 0.85), roughness=0.2, metallic=0.9)
    hilt_mat = make_material("Hilt", (0.3, 0.2, 0.1), roughness=0.8)

    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.5))
    blade = bpy.context.active_object
    blade.name = "Blade"
    blade.scale = (0.05, 0.02, 1.0)
    blade.data.materials.append(blade_mat)

    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.05))
    hilt = bpy.context.active_object
    hilt.name = "Hilt"
    hilt.scale = (0.15, 0.05, 0.1)
    hilt.data.materials.append(hilt_mat)

    return [blade, hilt]


def create_pickup():
    clear_scene()
    mat = make_material("Pickup", (1.0, 0.84, 0.0), roughness=0.3, metallic=0.7)
    bpy.ops.mesh.primitive_ico_sphere_add(radius=0.25, location=(0, 0, 0.3))
    obj = bpy.context.active_object
    obj.name = "Pickup"
    obj.data.materials.append(mat)
    return [obj]


if __name__ == "__main__":
    print("=" * 50)
    print("Generating 3D models for Dungeon Explorer")
    print("=" * 50)

    objs = create_player()
    export_fbx(objs, "player.fbx")

    objs = create_enemy()
    export_fbx(objs, "enemy.fbx")

    objs = create_dungeon()
    export_fbx(objs, "dungeon.fbx")

    objs = create_sword()
    export_fbx(objs, "sword.fbx")

    objs = create_pickup()
    export_fbx(objs, "pickup.fbx")

    print(f"\nAll models exported to: {OUTPUT_DIR}")
    print("Done!")