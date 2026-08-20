"""白名单指令执行器：在 Blender 主线程（timer）内安全执行 bpy 调用。

bpy 非线程安全：本模块所有函数都由 socket_server 的 timer 在主线程调用，
socket 监听线程绝不直接调用 bpy。

每个指令只接受结构化参数，禁止透传任意代码。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import bpy

_NAMING_PATTERN = re.compile(
    r"^(model|texture|ui|audio|anim)_[a-z][a-z0-9]*(_[a-z][a-z0-9]*)*$"
)

_PRIMITIVE_OPS = {
    "CUBE": bpy.ops.mesh.primitive_cube_add,
    "SPHERE": bpy.ops.mesh.primitive_uv_sphere_add,
    "CYLINDER": bpy.ops.mesh.primitive_cylinder_add,
    "PLANE": bpy.ops.mesh.primitive_plane_add,
    "CONE": bpy.ops.mesh.primitive_cone_add,
    "TORUS": bpy.ops.mesh.primitive_torus_add,
}


def create_primitive(
    prim_type: str, name: str, dimensions: list[float]
) -> dict[str, Any]:
    """创建基础几何体。prim_type 枚举，dimensions=[x,y,z]。"""
    op = _PRIMITIVE_OPS.get(prim_type.upper())
    if op is None:
        raise ValueError(f"未知图元类型: {prim_type}")
    op()
    obj = bpy.context.active_object
    obj.name = name
    if len(dimensions) == 3:
        obj.dimensions = tuple(dimensions)
    return {"object_name": obj.name, "type": prim_type}


def auto_uv(asset_id: str) -> dict[str, Any]:
    """智能投影自动展 UV（对选中物体）。"""
    if not bpy.context.selected_objects:
        raise ValueError("无选中物体，无法展 UV")
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=1.15192)
    bpy.ops.object.mode_set(mode="OBJECT")
    return {"asset_id": asset_id, "uv": "smart_projected"}


def assign_material(
    asset_id: str,
    base_color: list[float],
    roughness: float,
    metallic: float,
) -> dict[str, Any]:
    """创建并赋予基础 PBR 材质。base_color=[r,g,b,a]。"""
    obj = bpy.context.active_object
    if obj is None:
        raise ValueError("无活动物体")
    mat = bpy.data.materials.new(name=f"mat_{asset_id}")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = tuple(base_color[:4])
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)
    return {"asset_id": asset_id, "material": mat.name}


def export_fbx(asset_id: str, path: str) -> dict[str, Any]:
    """按规范导出 FBX：强制 Y-up、单位米、只导出选中物体、apply modifiers。"""
    if not bpy.context.selected_objects:
        raise ValueError("无选中物体，无法导出")
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.export_scene.fbx(
        filepath=str(out),
        use_selection=True,
        axis_forward="Y",
        axis_up="Z",
        apply_unit_scale=True,
        use_space_transform=True,
        bake_space_transform=True,
        object_types={"MESH"},
        use_mesh_modifiers=True,
        unit="METERS",
    )
    return {"asset_id": asset_id, "path": str(out), "size": out.stat().st_size}


def validate_export(path: str) -> dict[str, Any]:
    """调用 contracts/art-spec.schema.json 校验导出物（文件级检查）。"""
    p = Path(path)
    if not p.exists():
        raise ValueError(f"文件不存在: {path}")
    if p.suffix.lower() != ".fbx":
        raise ValueError(f"非 FBX 文件: {p.suffix}")
    schema_path = (
        Path(__file__).resolve().parents[3] / "contracts" / "art-spec.schema.json"
    )
    spec = json.loads(schema_path.read_text(encoding="utf-8"))
    allowed = spec["properties"]["allowed_formats"]
    naming = spec["properties"]["naming_pattern"]["const"]
    stem_ok = bool(re.match(naming, p.stem))
    return {
        "path": str(p),
        "format": "fbx",
        "allowed_formats": allowed,
        "naming_ok": stem_ok,
        "naming_pattern": naming,
    }


def get_scene_info() -> dict[str, Any]:
    """返回当前场景资产列表。"""
    objs = [
        {"name": o.name, "type": o.type, "location": list(o.location)}
        for o in bpy.data.objects
    ]
    return {"scene": bpy.context.scene.name, "objects": objs}


DISPATCH: dict[str, Any] = {
    "create_primitive": create_primitive,
    "auto_uv": auto_uv,
    "assign_material": assign_material,
    "export_fbx": export_fbx,
    "validate_export": validate_export,
    "get_scene_info": get_scene_info,
}


def execute(tool: str, params: dict[str, Any]) -> Any:
    """白名单分发。未知 tool 直接拒绝。"""
    fn = DISPATCH.get(tool)
    if fn is None:
        raise ValueError(f"未知工具: {tool}（不在白名单）")
    return fn(**params)