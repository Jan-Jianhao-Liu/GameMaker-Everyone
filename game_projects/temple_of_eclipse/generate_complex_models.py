"""Blender 脚本：为幽冥神殿生成复杂 3D 模型。

生成资产：
  - column.fbx        神殿石柱（带底座+柱身+柱头+凹槽细节）
  - statue.fbx        守卫雕像（人形+武器+底座）
  - arch.fbx          拱门（弧形顶部+两侧柱+装饰）
  - altar.fbx         祭坛（多层台阶+雕刻纹路+凹槽）
  - adventurer.fbx    冒险者角色（身体+头+四肢+斗篷+剑）
  - stone_guardian.fbx 石像守卫敌人（石头质感+发光眼睛）
  - flame_wraith.fbx   火焰幽灵（半透明+火焰形态）
  - torch.fbx          火把支架（金属杆+火焰托盘）
  - boss.fbx           BOSS神殿守护者（大型多臂雕像）
  - decorative_pillar.fbx 装饰柱（带螺旋纹路）

用法: blender --background --python generate_complex_models.py
"""
import bpy
import bmesh
import math
import os
from mathutils import Vector, Matrix

OUTPUT_DIR = os.path.join(os.path.dirname(bpy.data.filepath) if bpy.data.filepath else os.getcwd(), "assets", "models")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for mesh in bpy.data.meshes:
        bpy.data.meshes.remove(mesh)
    for mat in bpy.data.materials:
        bpy.data.materials.remove(mat)


def make_material(name, color, roughness=0.5, metallic=0.0, emission=None, alpha=1.0):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
        if alpha < 1.0:
            bsdf.inputs["Alpha"].default_value = alpha
            mat.blend_method = 'BLEND'
        if emission:
            if "Emission Color" in bsdf.inputs:
                bsdf.inputs["Emission Color"].default_value = (*emission, 1.0)
            elif "Emission" in bsdf.inputs:
                bsdf.inputs["Emission"].default_value = (*emission, 1.0)
            if "Emission Strength" in bsdf.inputs:
                bsdf.inputs["Emission Strength"].default_value = 2.0
    return mat


def add_subsurf(obj, levels=2):
    mod = obj.modifiers.new(name="Subsurf", type='SUBSURF')
    mod.levels = levels
    mod.render_levels = levels


def add_bevel(obj, width=0.02):
    mod = obj.modifiers.new(name="Bevel", type='BEVEL')
    mod.width = width
    mod.segments = 2


def export_fbx(objects, filename):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True)
    filepath = os.path.join(OUTPUT_DIR, filename)
    bpy.ops.export_scene.fbx(
        filepath=filepath,
        use_selection=True,
        apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_ALL',
        axis_forward='Y', axis_up='Z',
        object_types={'MESH'},
        bake_space_transform=True,
    )
    print(f"Exported: {filepath}")
    return filepath


# ==================== 神殿石柱 ====================
def create_column():
    clear_scene()
    stone_mat = make_material("StoneColumn", (0.35, 0.32, 0.28), roughness=0.85)
    dark_stone = make_material("DarkStone", (0.2, 0.18, 0.15), roughness=0.9)

    # 底座 (双层)
    bpy.ops.mesh.primitive_cube_add(size=1.2, location=(0, 0, 0.15))
    base1 = bpy.context.active_object
    base1.name = "ColumnBase1"
    base1.scale = (1, 1, 0.3)
    base1.data.materials.append(dark_stone)
    add_bevel(base1, 0.03)

    bpy.ops.mesh.primitive_cube_add(size=0.9, location=(0, 0, 0.4))
    base2 = bpy.context.active_object
    base2.name = "ColumnBase2"
    base2.scale = (1, 1, 0.2)
    base2.data.materials.append(stone_mat)
    add_bevel(base2, 0.02)

    # 柱身 (带凹槽细节)
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.35, depth=3.0, location=(0, 0, 2.0))
    shaft = bpy.context.active_object
    shaft.name = "ColumnShaft"
    shaft.data.materials.append(stone_mat)

    # 柱身凹槽 (4条竖槽)
    groove_objs = []
    for i in range(4):
        angle = i * math.pi / 2
        x = math.cos(angle) * 0.36
        y = math.sin(angle) * 0.36
        bpy.ops.mesh.primitive_cube_add(size=0.08, location=(x, y, 2.0))
        groove = bpy.context.active_object
        groove.name = f"Groove_{i}"
        groove.scale = (1, 1, 1.4)
        groove.rotation_euler = (0, 0, angle)
        groove.data.materials.append(dark_stone)
        groove_objs.append(groove)

    # 柱头 (带装饰)
    bpy.ops.mesh.primitive_cube_add(size=0.9, location=(0, 0, 3.7))
    cap1 = bpy.context.active_object
    cap1.name = "ColumnCap1"
    cap1.scale = (1, 1, 0.2)
    cap1.data.materials.append(stone_mat)
    add_bevel(cap1, 0.02)

    bpy.ops.mesh.primitive_cube_add(size=1.2, location=(0, 0, 3.95))
    cap2 = bpy.context.active_object
    cap2.name = "ColumnCap2"
    cap2.scale = (1, 1, 0.15)
    cap2.data.materials.append(dark_stone)
    add_bevel(cap2, 0.03)

    # 顶部装饰球
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.15, location=(0, 0, 4.15))
    orb = bpy.context.active_object
    orb.name = "ColumnOrb"
    orb.data.materials.append(stone_mat)

    return [base1, base2, shaft] + groove_objs + [cap1, cap2, orb]


# ==================== 守卫雕像 ====================
def create_statue():
    clear_scene()
    stone_mat = make_material("StatueStone", (0.4, 0.38, 0.35), roughness=0.8)
    dark_mat = make_material("StatueDark", (0.15, 0.14, 0.12), roughness=0.9)
    glow_mat = make_material("StatueGlow", (1.0, 0.3, 0.0), roughness=0.3, emission=(1.0, 0.3, 0.0))

    # 底座
    bpy.ops.mesh.primitive_cube_add(size=1.5, location=(0, 0, 0.3))
    pedestal = bpy.context.active_object
    pedestal.name = "StatuePedestal"
    pedestal.scale = (1, 1, 0.4)
    pedestal.data.materials.append(dark_mat)
    add_bevel(pedestal, 0.05)

    # 双腿
    for side in [-0.2, 0.2]:
        bpy.ops.mesh.primitive_cube_add(size=0.35, location=(side, 0, 1.0))
        leg = bpy.context.active_object
        leg.name = f"StatueLeg_{'L' if side < 0 else 'R'}"
        leg.scale = (1, 1, 1.5)
        leg.data.materials.append(stone_mat)
        add_bevel(leg, 0.02)

    # 躯干
    bpy.ops.mesh.primitive_cube_add(size=0.7, location=(0, 0, 2.2))
    torso = bpy.context.active_object
    torso.name = "StatueTorso"
    torso.scale = (1, 0.6, 1.2)
    torso.data.materials.append(stone_mat)
    add_bevel(torso, 0.03)

    # 肩甲
    bpy.ops.mesh.primitive_cube_add(size=0.8, location=(0, 0, 2.8))
    shoulder = bpy.context.active_object
    shoulder.name = "StatueShoulder"
    shoulder.scale = (1.2, 0.5, 0.3)
    shoulder.data.materials.append(dark_mat)
    add_bevel(shoulder, 0.03)

    # 头
    bpy.ops.mesh.primitive_cube_add(size=0.45, location=(0, 0, 3.3))
    head = bpy.context.active_object
    head.name = "StatueHead"
    head.data.materials.append(stone_mat)
    add_bevel(head, 0.03)

    # 发光眼睛
    for side in [-0.1, 0.1]:
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.05, location=(side, -0.2, 3.35))
        eye = bpy.context.active_object
        eye.name = f"StatueEye_{'L' if side < 0 else 'R'}"
        eye.data.materials.append(glow_mat)

    # 双臂持剑
    for side in [-0.45, 0.45]:
        bpy.ops.mesh.primitive_cube_add(size=0.25, location=(side, 0, 2.2))
        arm = bpy.context.active_object
        arm.name = f"StatueArm_{'L' if side < 0 else 'R'}"
        arm.scale = (1, 0.8, 1.5)
        arm.data.materials.append(stone_mat)
        add_bevel(arm, 0.02)

    # 剑
    bpy.ops.mesh.primitive_cube_add(size=0.1, location=(0, 0.3, 3.5))
    sword = bpy.context.active_object
    sword.name = "StatueSword"
    sword.scale = (1, 1, 2.5)
    sword.data.materials.append(dark_mat)

    # 剑柄
    bpy.ops.mesh.primitive_cube_add(size=0.3, location=(0, 0.3, 2.5))
    hilt = bpy.context.active_object
    hilt.name = "StatueHilt"
    hilt.scale = (1, 0.3, 0.3)
    hilt.data.materials.append(dark_mat)

    return [pedestal, torso, shoulder, head, sword, hilt]


# ==================== 拱门 ====================
def create_arch():
    clear_scene()
    stone_mat = make_material("ArchStone", (0.38, 0.35, 0.30), roughness=0.85)
    dark_mat = make_material("ArchDark", (0.2, 0.18, 0.15), roughness=0.9)

    objs = []

    # 两侧柱基
    for side in [-2, 2]:
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(side, 0, 0.5))
        base = bpy.context.active_object
        base.name = f"ArchBase_{'L' if side < 0 else 'R'}"
        base.scale = (1, 1.5, 1)
        base.data.materials.append(dark_mat)
        add_bevel(base, 0.05)
        objs.append(base)

    # 两侧柱身
    for side in [-2, 2]:
        bpy.ops.mesh.primitive_cube_add(size=0.7, location=(side, 0, 3.0))
        pillar = bpy.context.active_object
        pillar.name = f"ArchPillar_{'L' if side < 0 else 'R'}"
        pillar.scale = (1, 1, 4)
        pillar.data.materials.append(stone_mat)
        add_bevel(pillar, 0.03)
        objs.append(pillar)

    # 拱顶 (用多个旋转的方块组成弧形)
    num_segments = 12
    for i in range(num_segments):
        angle = math.pi * (i + 0.5) / num_segments
        x = math.cos(angle) * 2.5
        z = 5.5 + math.sin(angle) * 1.5
        bpy.ops.mesh.primitive_cube_add(size=0.8, location=(x, 0, z))
        seg = bpy.context.active_object
        seg.name = f"ArchSegment_{i}"
        seg.scale = (0.8, 1.5, 0.8)
        seg.rotation_euler = (0, angle - math.pi/2, 0)
        seg.data.materials.append(stone_mat)
        add_bevel(seg, 0.02)
        objs.append(seg)

    # 拱顶中央装饰
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.3, location=(0, 0, 7.2))
    keystone = bpy.context.active_object
    keystone.name = "ArchKeystone"
    keystone.data.materials.append(dark_mat)
    objs.append(keystone)

    return objs


# ==================== 祭坛 ====================
def create_altar():
    clear_scene()
    stone_mat = make_material("AltarStone", (0.3, 0.28, 0.25), roughness=0.8)
    dark_mat = make_material("AltarDark", (0.15, 0.13, 0.10), roughness=0.9)
    glow_mat = make_material("AltarGlow", (0.2, 0.8, 1.0), roughness=0.2, emission=(0.2, 0.8, 1.0))

    objs = []

    # 三层台阶
    for i, (size, z) in enumerate([(3.0, 0.2), (2.4, 0.5), (1.8, 0.8)]):
        bpy.ops.mesh.primitive_cube_add(size=size, location=(0, 0, z))
        step = bpy.context.active_object
        step.name = f"AltarStep_{i}"
        step.scale = (1, 1, 0.3)
        step.data.materials.append(stone_mat)
        add_bevel(step, 0.05)
        objs.append(step)

    # 祭坛主体
    bpy.ops.mesh.primitive_cube_add(size=1.4, location=(0, 0, 1.3))
    body = bpy.context.active_object
    body.name = "AltarBody"
    body.scale = (1, 1, 0.8)
    body.data.materials.append(dark_mat)
    add_bevel(body, 0.04)
    objs.append(body)

    # 顶部凹槽 (放宝石的地方)
    bpy.ops.mesh.primitive_cube_add(size=0.6, location=(0, 0, 1.75))
    groove = bpy.context.active_object
    groove.name = "AltarGroove"
    groove.scale = (1, 1, 0.2)
    groove.data.materials.append(stone_mat)
    objs.append(groove)

    # 发光宝石
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=0.2, location=(0, 0, 1.9))
    gem = bpy.context.active_object
    gem.name = "AltarGem"
    gem.data.materials.append(glow_mat)
    add_subsurf(gem, 2)
    objs.append(gem)

    # 四角装饰柱
    for x, y in [(0.6, 0.6), (-0.6, 0.6), (0.6, -0.6), (-0.6, -0.6)]:
        bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.08, depth=0.6, location=(x, y, 1.5))
        dec = bpy.context.active_object
        dec.name = f"AltarDec_{x}_{y}"
        dec.data.materials.append(dark_mat)
        objs.append(dec)

    return objs


# ==================== 冒险者角色 ====================
def create_adventurer():
    clear_scene()
    skin_mat = make_material("Skin", (0.85, 0.7, 0.55), roughness=0.6)
    cloth_mat = make_material("Cloth", (0.3, 0.25, 0.15), roughness=0.9)
    armor_mat = make_material("Armor", (0.5, 0.5, 0.55), roughness=0.3, metallic=0.7)
    leather_mat = make_material("Leather", (0.2, 0.12, 0.08), roughness=0.8)
    blade_mat = make_material("Blade", (0.85, 0.85, 0.9), roughness=0.1, metallic=0.95)

    objs = []

    # 头部
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.18, location=(0, 0, 1.7))
    head = bpy.context.active_object
    head.name = "AdvHead"
    head.data.materials.append(skin_mat)
    add_subsurf(head, 2)
    objs.append(head)

    # 兜帽
    bpy.ops.mesh.primitive_cone_add(vertices=12, radius1=0.25, radius2=0.05, depth=0.4, location=(0, 0.05, 1.75))
    hood = bpy.context.active_object
    hood.name = "AdvHood"
    hood.data.materials.append(cloth_mat)
    objs.append(hood)

    # 躯干
    bpy.ops.mesh.primitive_cube_add(size=0.45, location=(0, 0, 1.25))
    torso = bpy.context.active_object
    torso.name = "AdvTorso"
    torso.scale = (1, 0.7, 1.2)
    torso.data.materials.append(cloth_mat)
    add_bevel(torso, 0.03)
    objs.append(torso)

    # 胸甲
    bpy.ops.mesh.primitive_cube_add(size=0.48, location=(0, -0.05, 1.35))
    chest = bpy.context.active_object
    chest.name = "AdvChestArmor"
    chest.scale = (1, 0.5, 0.8)
    chest.data.materials.append(armor_mat)
    add_bevel(chest, 0.02)
    objs.append(chest)

    # 斗篷
    bpy.ops.mesh.primitive_cone_add(vertices=8, radius1=0.4, radius2=0.1, depth=1.2, location=(0, 0.15, 1.0))
    cloak = bpy.context.active_object
    cloak.name = "AdvCloak"
    cloak.data.materials.append(leather_mat)
    objs.append(cloak)

    # 双臂
    for side in [-0.3, 0.3]:
        bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.08, depth=0.7, location=(side, 0, 1.2))
        arm = bpy.context.active_object
        arm.name = f"AdvArm_{'L' if side < 0 else 'R'}"
        arm.rotation_euler = (math.pi/2, 0, 0)
        arm.data.materials.append(skin_mat)
        objs.append(arm)

        # 手套
        bpy.ops.mesh.primitive_cube_add(size=0.12, location=(side, 0.35, 1.2))
        glove = bpy.context.active_object
        glove.name = f"AdvGlove_{'L' if side < 0 else 'R'}"
        glove.data.materials.append(leather_mat)
        objs.append(glove)

    # 双腿
    for side in [-0.12, 0.12]:
        bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.1, depth=0.8, location=(side, 0, 0.4))
        leg = bpy.context.active_object
        leg.name = f"AdvLeg_{'L' if side < 0 else 'R'}"
        leg.data.materials.append(leather_mat)
        objs.append(leg)

        # 靴子
        bpy.ops.mesh.primitive_cube_add(size=0.18, location=(side, 0.05, 0.05))
        boot = bpy.context.active_object
        boot.name = f"AdvBoot_{'L' if side < 0 else 'R'}"
        boot.scale = (1, 1.3, 0.5)
        boot.data.materials.append(leather_mat)
        objs.append(boot)

    # 剑
    bpy.ops.mesh.primitive_cube_add(size=0.06, location=(0.35, 0.4, 1.5))
    blade = bpy.context.active_object
    blade.name = "AdvBlade"
    blade.scale = (1, 1, 4)
    blade.data.materials.append(blade_mat)
    objs.append(blade)

    # 剑柄
    bpy.ops.mesh.primitive_cube_add(size=0.2, location=(0.35, 0.4, 0.8))
    hilt = bpy.context.active_object
    hilt.name = "AdvHilt"
    hilt.scale = (1, 0.3, 0.3)
    hilt.data.materials.append(dark_mat := make_material("DarkMetal", (0.1, 0.08, 0.05), roughness=0.8))
    objs.append(hilt)

    # 剑格
    bpy.ops.mesh.primitive_cube_add(size=0.25, location=(0.35, 0.4, 1.0))
    guard = bpy.context.active_object
    guard.name = "AdvGuard"
    guard.scale = (1, 0.1, 0.1)
    guard.data.materials.append(armor_mat)
    objs.append(guard)

    return objs


# ==================== 石像守卫敌人 ====================
def create_stone_guardian():
    clear_scene()
    stone_mat = make_material("GuardianStone", (0.35, 0.33, 0.30), roughness=0.85)
    crack_mat = make_material("GuardianCrack", (0.8, 0.2, 0.0), roughness=0.4, emission=(0.5, 0.1, 0.0))
    eye_mat = make_material("GuardianEye", (1.0, 0.2, 0.0), roughness=0.2, emission=(1.0, 0.2, 0.0))

    objs = []

    # 下半身 (锥形底座)
    bpy.ops.mesh.primitive_cone_add(vertices=6, radius1=0.5, radius2=0.3, depth=0.6, location=(0, 0, 0.3))
    lower = bpy.context.active_object
    lower.name = "GuardianLower"
    lower.data.materials.append(stone_mat)
    add_bevel(lower, 0.03)
    objs.append(lower)

    # 躯干 (粗壮)
    bpy.ops.mesh.primitive_cube_add(size=0.7, location=(0, 0, 1.0))
    torso = bpy.context.active_object
    torso.name = "GuardianTorso"
    torso.scale = (1, 0.7, 1.3)
    torso.data.materials.append(stone_mat)
    add_bevel(torso, 0.04)
    objs.append(torso)

    # 肩甲
    bpy.ops.mesh.primitive_cube_add(size=0.85, location=(0, 0, 1.6))
    shoulder = bpy.context.active_object
    shoulder.name = "GuardianShoulder"
    shoulder.scale = (1.2, 0.6, 0.3)
    shoulder.data.materials.append(stone_mat)
    add_bevel(shoulder, 0.04)
    objs.append(shoulder)

    # 头 (方形)
    bpy.ops.mesh.primitive_cube_add(size=0.4, location=(0, 0, 2.1))
    head = bpy.context.active_object
    head.name = "GuardianHead"
    head.data.materials.append(stone_mat)
    add_bevel(head, 0.03)
    objs.append(head)

    # 发光眼睛
    for side in [-0.1, 0.1]:
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.06, location=(side, -0.18, 2.15))
        eye = bpy.context.active_object
        eye.name = f"GuardianEye_{'L' if side < 0 else 'R'}"
        eye.data.materials.append(eye_mat)
        objs.append(eye)

    # 裂缝纹路 (发光)
    bpy.ops.mesh.primitive_cube_add(size=0.03, location=(0, 0, 1.2))
    crack1 = bpy.context.active_object
    crack1.name = "GuardianCrack1"
    crack1.scale = (1, 1, 3)
    crack1.data.materials.append(crack_mat)
    objs.append(crack1)

    # 粗壮双臂
    for side in [-0.5, 0.5]:
        bpy.ops.mesh.primitive_cube_add(size=0.3, location=(side, 0, 1.1))
        arm = bpy.context.active_object
        arm.name = f"GuardianArm_{'L' if side < 0 else 'R'}"
        arm.scale = (1, 0.8, 1.8)
        arm.data.materials.append(stone_mat)
        add_bevel(arm, 0.03)
        objs.append(arm)

        # 拳头
        bpy.ops.mesh.primitive_cube_add(size=0.35, location=(side, 0, 0.4))
        fist = bpy.context.active_object
        fist.name = f"GuardianFist_{'L' if side < 0 else 'R'}"
        fist.data.materials.append(stone_mat)
        add_bevel(fist, 0.03)
        objs.append(fist)

    return objs


# ==================== 火焰幽灵 ====================
def create_flame_wraith():
    clear_scene()
    flame_mat = make_material("FlameBody", (0.9, 0.3, 0.1), roughness=0.2, emission=(0.9, 0.3, 0.1), alpha=0.7)
    core_mat = make_material("FlameCore", (1.0, 0.9, 0.3), roughness=0.1, emission=(1.0, 0.9, 0.3))
    eye_mat = make_material("WraithEye", (1.0, 1.0, 0.0), roughness=0.1, emission=(1.0, 1.0, 0.0))

    objs = []

    # 火焰主体 (锥形)
    bpy.ops.mesh.primitive_cone_add(vertices=8, radius1=0.4, radius2=0.0, depth=1.5, location=(0, 0, 0.75))
    body = bpy.context.active_object
    body.name = "WraithBody"
    body.data.materials.append(flame_mat)
    add_subsurf(body, 1)
    objs.append(body)

    # 核心
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.2, location=(0, 0, 0.5))
    core = bpy.context.active_object
    core.name = "WraithCore"
    core.data.materials.append(core_mat)
    objs.append(core)

    # 眼睛
    for side in [-0.12, 0.12]:
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.05, location=(side, -0.15, 1.0))
        eye = bpy.context.active_object
        eye.name = f"WraithEye_{'L' if side < 0 else 'R'}"
        eye.data.materials.append(eye_mat)
        objs.append(eye)

    # 火焰粒子 (小球散布)
    for i in range(8):
        angle = i * math.pi / 4
        r = 0.3 + (i % 3) * 0.1
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=0.08, location=(math.cos(angle)*r, math.sin(angle)*r, 0.3 + (i%2)*0.3))
        particle = bpy.context.active_object
        particle.name = f"WraithParticle_{i}"
        particle.data.materials.append(flame_mat)
        objs.append(particle)

    return objs


# ==================== 火把支架 ====================
def create_torch():
    clear_scene()
    metal_mat = make_material("TorchMetal", (0.3, 0.2, 0.1), roughness=0.6, metallic=0.5)
    wood_mat = make_material("TorchWood", (0.15, 0.08, 0.04), roughness=0.9)
    flame_mat = make_material("TorchFlame", (1.0, 0.6, 0.1), roughness=0.2, emission=(1.0, 0.6, 0.1))

    objs = []

    # 金属杆
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.04, depth=1.5, location=(0, 0, 0.75))
    pole = bpy.context.active_object
    pole.name = "TorchPole"
    pole.data.materials.append(metal_mat)
    objs.append(pole)

    # 底座
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.15, depth=0.1, location=(0, 0, 0.05))
    base = bpy.context.active_object
    base.name = "TorchBase"
    base.data.materials.append(metal_mat)
    objs.append(base)

    # 火焰托盘
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.12, depth=0.08, location=(0, 0, 1.55))
    bowl = bpy.context.active_object
    bowl.name = "TorchBowl"
    bowl.data.materials.append(metal_mat)
    objs.append(bowl)

    # 木把
    bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=0.05, depth=0.4, location=(0, 0, 1.7))
    wood = bpy.context.active_object
    wood.name = "TorchWood"
    wood.data.materials.append(wood_mat)
    objs.append(wood)

    # 火焰
    bpy.ops.mesh.primitive_cone_add(vertices=6, radius1=0.1, radius2=0, depth=0.3, location=(0, 0, 2.0))
    flame = bpy.context.active_object
    flame.name = "TorchFlame"
    flame.data.materials.append(flame_mat)
    objs.append(flame)

    return objs


# ==================== BOSS 神殿守护者 ====================
def create_boss():
    clear_scene()
    stone_mat = make_material("BossStone", (0.25, 0.22, 0.20), roughness=0.85)
    dark_mat = make_material("BossDark", (0.1, 0.08, 0.06), roughness=0.9)
    glow_mat = make_material("BossGlow", (0.8, 0.0, 0.0), roughness=0.2, emission=(0.8, 0.0, 0.0))
    gold_mat = make_material("BossGold", (0.8, 0.6, 0.2), roughness=0.3, metallic=0.8)

    objs = []

    # 巨大底座
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=2.0, depth=0.6, location=(0, 0, 0.3))
    base = bpy.context.active_object
    base.name = "BossBase"
    base.data.materials.append(dark_mat)
    add_bevel(base, 0.08)
    objs.append(base)

    # 底座装饰环
    bpy.ops.mesh.primitive_torus_add(major_radius=1.8, minor_radius=0.1, location=(0, 0, 0.6))
    ring = bpy.context.active_object
    ring.name = "BossRing"
    ring.data.materials.append(gold_mat)
    objs.append(ring)

    # 下半身
    bpy.ops.mesh.primitive_cone_add(vertices=8, radius1=1.2, radius2=0.8, depth=1.5, location=(0, 0, 1.4))
    lower = bpy.context.active_object
    lower.name = "BossLower"
    lower.data.materials.append(stone_mat)
    add_bevel(lower, 0.05)
    objs.append(lower)

    # 躯干
    bpy.ops.mesh.primitive_cube_add(size=1.5, location=(0, 0, 2.8))
    torso = bpy.context.active_object
    torso.name = "BossTorso"
    torso.scale = (1, 0.8, 1.5)
    torso.data.materials.append(stone_mat)
    add_bevel(torso, 0.06)
    objs.append(torso)

    # 胸甲装饰
    bpy.ops.mesh.primitive_cube_add(size=1.2, location=(0, -0.1, 3.0))
    chest = bpy.context.active_object
    chest.name = "BossChest"
    chest.scale = (1, 0.3, 1.0)
    chest.data.materials.append(gold_mat)
    add_bevel(chest, 0.03)
    objs.append(chest)

    # 胸口发光宝石
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=0.2, location=(0, -0.3, 3.0))
    gem = bpy.context.active_object
    gem.name = "BossGem"
    gem.data.materials.append(glow_mat)
    add_subsurf(gem, 2)
    objs.append(gem)

    # 头
    bpy.ops.mesh.primitive_cube_add(size=0.7, location=(0, 0, 4.2))
    head = bpy.context.active_object
    head.name = "BossHead"
    head.data.materials.append(stone_mat)
    add_bevel(head, 0.05)
    objs.append(head)

    # 角
    for side in [-0.3, 0.3]:
        bpy.ops.mesh.primitive_cone_add(vertices=6, radius1=0.1, radius2=0, depth=0.5, location=(side, 0, 4.6))
        horn = bpy.context.active_object
        horn.name = f"BossHorn_{'L' if side < 0 else 'R'}"
        horn.rotation_euler = (math.pi/6 if side > 0 else -math.pi/6, 0, 0)
        horn.data.materials.append(dark_mat)
        objs.append(horn)

    # 发光眼睛
    for side in [-0.15, 0.15]:
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.08, location=(side, -0.3, 4.3))
        eye = bpy.context.active_object
        eye.name = f"BossEye_{'L' if side < 0 else 'R'}"
        eye.data.materials.append(glow_mat)
        objs.append(eye)

    # 四条手臂
    for i, angle in enumerate([0, math.pi/2, math.pi, 3*math.pi/2]):
        x = math.cos(angle) * 1.0
        y = math.sin(angle) * 1.0
        bpy.ops.mesh.primitive_cube_add(size=0.4, location=(x, y, 2.8))
        arm = bpy.context.active_object
        arm.name = f"BossArm_{i}"
        arm.scale = (1, 1, 2.5)
        arm.rotation_euler = (0, 0, angle)
        arm.data.materials.append(stone_mat)
        add_bevel(arm, 0.04)
        objs.append(arm)

        # 拳头
        fx = math.cos(angle) * 1.5
        fy = math.sin(angle) * 1.5
        bpy.ops.mesh.primitive_cube_add(size=0.5, location=(fx, fy, 2.0))
        fist = bpy.context.active_object
        fist.name = f"BossFist_{i}"
        fist.data.materials.append(stone_mat)
        add_bevel(fist, 0.04)
        objs.append(fist)

    return objs


# ==================== 装饰柱 ====================
def create_decorative_pillar():
    clear_scene()
    stone_mat = make_material("DecStone", (0.4, 0.37, 0.33), roughness=0.8)
    gold_mat = make_material("DecGold", (0.7, 0.55, 0.2), roughness=0.3, metallic=0.7)

    objs = []

    # 底座
    bpy.ops.mesh.primitive_cube_add(size=0.8, location=(0, 0, 0.2))
    base = bpy.context.active_object
    base.name = "DecPillarBase"
    base.scale = (1, 1, 0.4)
    base.data.materials.append(stone_mat)
    add_bevel(base, 0.03)
    objs.append(base)

    # 螺旋柱身 (用多个旋转的扁方块叠加)
    num_segments = 20
    for i in range(num_segments):
        z = 0.5 + i * 0.15
        angle = i * math.pi / 4
        bpy.ops.mesh.primitive_cube_add(size=0.5, location=(0, 0, z))
        seg = bpy.context.active_object
        seg.name = f"DecSeg_{i}"
        seg.scale = (1, 0.3, 0.15)
        seg.rotation_euler = (0, 0, angle)
        seg.data.materials.append(stone_mat)
        objs.append(seg)

    # 金色装饰环
    for z in [0.5, 1.5, 2.5, 3.5]:
        bpy.ops.mesh.primitive_torus_add(major_radius=0.28, minor_radius=0.03, location=(0, 0, z))
        ring = bpy.context.active_object
        ring.name = f"DecRing_{z}"
        ring.data.materials.append(gold_mat)
        objs.append(ring)

    # 顶部
    bpy.ops.mesh.primitive_cube_add(size=0.8, location=(0, 0, 3.7))
    top = bpy.context.active_object
    top.name = "DecPillarTop"
    top.scale = (1, 1, 0.3)
    top.data.materials.append(stone_mat)
    add_bevel(top, 0.03)
    objs.append(top)

    # 顶部金球
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.15, location=(0, 0, 4.0))
    orb = bpy.context.active_object
    orb.name = "DecPillarOrb"
    orb.data.materials.append(gold_mat)
    objs.append(orb)

    return objs


if __name__ == "__main__":
    print("=" * 60)
    print("Generating complex 3D models for Temple of Eclipse")
    print("=" * 60)

    models = [
        ("column.fbx", create_column),
        ("statue.fbx", create_statue),
        ("arch.fbx", create_arch),
        ("altar.fbx", create_altar),
        ("adventurer.fbx", create_adventurer),
        ("stone_guardian.fbx", create_stone_guardian),
        ("flame_wraith.fbx", create_flame_wraith),
        ("torch.fbx", create_torch),
        ("boss.fbx", create_boss),
        ("decorative_pillar.fbx", create_decorative_pillar),
    ]

    for filename, create_fn in models:
        print(f"\n--- Generating {filename} ---")
        objs = create_fn()
        export_fbx(objs, filename)

    print(f"\nAll {len(models)} models exported to: {OUTPUT_DIR}")
    print("Done!")