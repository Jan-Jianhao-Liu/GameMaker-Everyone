"""交付契约校验器。

提供 GDD / 资产清单 / 美术规范的 Schema 校验，以及：
- validate_no_circular_deps：Kahn 拓扑排序检测资产依赖环
- suggest_naming：对不合规命名返回最接近的合规化建议
- validate_texture_size：贴图尺寸 POT 校验（含 UI 类型 NPOT 豁免）

所有文件路径使用 pathlib.Path，禁止硬编码分隔符。
"""

from __future__ import annotations

import re
from collections import deque
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

_SCHEMA_DIR = Path(__file__).resolve().parent

_NAMING_PATTERN = re.compile(r"^(model|texture|ui|audio|anim)_[a-z][a-z0-9]*(_[a-z][a-z0-9]*)*$")
_TYPE_PREFIXES = ("model", "texture", "ui", "audio", "anim")


class CircularDependencyError(ValueError):
    """资产依赖存在环。message 含环上 asset_id 链。"""


class TextureSizeError(ValueError):
    """贴图尺寸不合规。"""


def load_schema(name: str) -> dict[str, Any]:
    """按名称加载契约 Schema。

    Args:
        name: "gdd" | "asset-manifest" | "art-spec"

    Returns:
        Schema dict。
    """
    path = _SCHEMA_DIR / f"{name}.schema.json"
    import json

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(load_schema(name))


def validate_gdd(data: dict[str, Any]) -> dict[str, Any]:
    """校验 GDD 文档。返回 data 本身；不合规抛 jsonschema.ValidationError。"""
    _validator("gdd").validate(data)
    return data


def validate_asset_manifest(data: dict[str, Any]) -> dict[str, Any]:
    """校验资产清单。返回 data 本身；不合规抛 jsonschema.ValidationError。"""
    _validator("asset-manifest").validate(data)
    return data


def validate_art_spec(data: dict[str, Any]) -> dict[str, Any]:
    """校验美术规范。返回 data 本身；不合规抛 jsonschema.ValidationError。"""
    _validator("art-spec").validate(data)
    return data


def validate_no_circular_deps(manifest: dict[str, Any]) -> list[str]:
    """用 Kahn 算法做拓扑排序，检测资产依赖环。

    Args:
        manifest: 符合 asset-manifest.schema.json 的清单。

    Returns:
        拓扑排序后的 asset_id 列表（生产顺序）。

    Raises:
        CircularDependencyError: 检测到环，message 含环上 asset_id 链。
    """
    assets = manifest.get("assets", [])
    id_set = {a["asset_id"] for a in assets}

    adj: dict[str, set[str]] = {a["asset_id"]: set() for a in assets}
    indeg: dict[str, int] = {a["asset_id"]: 0 for a in assets}
    for a in assets:
        for dep in a.get("dependencies", []):
            if dep not in id_set:
                continue
            if dep not in adj[a["asset_id"]]:
                adj[a["asset_id"]].add(dep)
                indeg[a["asset_id"]] += 1

    queue = deque([aid for aid, d in indeg.items() if d == 0])
    order: list[str] = []
    indeg_work = dict(indeg)
    while queue:
        node = queue.popleft()
        order.append(node)
        for other, deps in adj.items():
            if node in deps:
                indeg_work[other] -= 1
                if indeg_work[other] == 0:
                    queue.append(other)

    if len(order) != len(id_set):
        cycle = _find_cycle(adj, id_set)
        raise CircularDependencyError(f"检测到资产依赖环: {' -> '.join(cycle)} -> {cycle[0]}")
    return order


def _find_cycle(adj: dict[str, set[str]], id_set: set[str]) -> list[str]:
    """DFS 找一条环路径，用于错误信息。"""
    color: dict[str, int] = {aid: 0 for aid in id_set}
    parent: dict[str, str | None] = {aid: None for aid in id_set}
    cycle: list[str] = []

    def dfs(u: str) -> bool:
        color[u] = 1
        for v in id_set:
            if u in adj.get(v, set()):
                if color[v] == 0:
                    parent[v] = u
                    if dfs(v):
                        return True
                elif color[v] == 1:
                    cur = u
                    cycle.append(v)
                    while cur is not None and cur != v:
                        cycle.append(cur)
                        cur = parent[cur]
                    cycle.append(v)
                    cycle.reverse()
                    return True
        color[u] = 2
        return False

    for aid in id_set:
        if color[aid] == 0:
            if dfs(aid):
                break
    return cycle or list(id_set)


def suggest_naming(asset_id: str) -> str:
    """对不合规命名返回最接近的合规化建议。

    策略：
    1. 全小写化
    2. 首段若不是类型枚举，尝试匹配最接近的类型前缀；匹配失败则用 "model" 兜底
    3. 去连续下划线、去结尾下划线、去开头下划线
    4. 每段首字符须为字母；数字开头的段前补 "a"
    5. 限制 2-4 段

    若已合规，原样返回。
    """
    if _NAMING_PATTERN.match(asset_id):
        return asset_id

    s = asset_id.lower().strip("_")
    s = re.sub(r"_+", "_", s)
    parts = [p for p in s.split("_") if p]

    if not parts:
        return "model_asset"

    if parts[0] not in _TYPE_PREFIXES:
        head = parts[0]
        match = None
        for p in _TYPE_PREFIXES:
            if head.startswith(p) or p.startswith(head):
                match = p
                break
        parts.insert(0, match or "model")

    cleaned: list[str] = []
    for i, p in enumerate(parts):
        if i > 0 and p and p[0].isdigit():
            p = "a" + p
        p = re.sub(r"[^a-z0-9]", "", p)
        if p:
            cleaned.append(p)

    if len(cleaned) > 4:
        cleaned = cleaned[:4]
    if len(cleaned) < 2:
        cleaned.append("asset")

    return "_".join(cleaned)


def _is_power_of_two(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


def validate_texture_size(
    width: int,
    height: int,
    asset_type: str,
    npot_flag: bool,
    art_spec: dict[str, Any],
) -> None:
    """贴图尺寸 POT 校验。

    Args:
        width, height: 贴图宽高。
        asset_type: 资产类型（model/texture/ui/audio/anim）。
        npot_flag: 资产是否显式标记 npot=true。
        art_spec: 符合 art-spec.schema.json 的规范。

    Raises:
        TextureSizeError: 尺寸不合规。
    """
    spec = art_spec["texture_spec"]
    require_pot = spec["require_power_of_two"]
    require_square = spec["require_square"]
    exc = spec["npot_exception"]
    allowed_types = exc["allowed_types"]
    requires_flag = exc["requires_flag"]

    is_pot = _is_power_of_two(width) and _is_power_of_two(height)
    is_square = width == height

    if require_pot and not is_pot:
        can_exempt = asset_type in allowed_types and (not requires_flag or npot_flag)
        if not can_exempt:
            raise TextureSizeError(
                f"贴图尺寸 {width}x{height} 非 2 的幂；"
                f"类型 {asset_type} 不在豁免列表或未显式标记 npot=true"
            )

    if require_square and not is_square:
        can_exempt = asset_type in allowed_types and (not requires_flag or npot_flag)
        if not can_exempt:
            raise TextureSizeError(
                f"贴图尺寸 {width}x{height} 非正方形；"
                f"类型 {asset_type} 不在豁免列表或未显式标记 npot=true"
            )


def self_check() -> dict[str, bool]:
    """三个 Schema 自检：用自身校验自身定义。供 just check 调用。"""
    results: dict[str, bool] = {}
    for name in ("gdd", "asset-manifest", "art-spec"):
        schema = load_schema(name)
        try:
            Draft202012Validator.check_schema(schema)
            results[name] = True
        except Exception:
            results[name] = False
    return results


if __name__ == "__main__":
    import json

    print("Schema 自检:", json.dumps(self_check(), ensure_ascii=False))
