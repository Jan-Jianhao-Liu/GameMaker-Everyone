"""对比实验：复杂 RPG 游戏 — 本软件（多智能体流水线） vs 直接 LLM。

指标基准：
  1. 结构化指标：GDD 字段完整度、关卡数、数值表覆盖、资产数、资产类型多样性
  2. 质量指标：schema 验证通过率、资产依赖无环、命名规范合规率
  3. LLM-as-judge：6 维度打分（设计完整度/资产规划/数值平衡/可实现性/文档质量/可玩性）
  4. 成本指标：token 消耗、耗时、LLM 调用次数
  5. 流水线指标：轮次、重试次数、缺陷数量

用法: uv run python experiment_complex.py
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import httpx

from agents.common.deps import AgentDeps
from agents.common.json_utils import extract_json
from agents.common.llm import HybridLLM, LLMClient
from agents.orchestrator import build_graph_with_checkpointer, make_checkpointer
from contracts.validators import (
    CircularDependencyError,
    validate_art_spec,
    validate_asset_manifest,
    validate_gdd,
    validate_no_circular_deps,
)
from storage.sqlite_repo import SQLiteRepo

OUTPUT_DIR = Path("experiment_complex_output")
OUTPUT_DIR.mkdir(exist_ok=True)

MODEL = "my-qwen4b-no-think:latest"
OLLAMA_URL = "http://localhost:11434/v1"

GAME_REQUEST = (
    "做一个3D动作RPG游戏：玩家控制战士角色在3个关卡中战斗，"
    "有4种武器（剑/弓/法杖/盾）、6种敌人（哥布林/骷髅/蜘蛛/狼/巨魔/龙BOSS）、"
    "升级系统（等级/技能树/属性点）、物品系统（药水/装备/材料）、"
    "任务系统（主线/支线）、金币经济、NPC对话"
)


class TokenCountingClient(LLMClient):
    def __init__(self) -> None:
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.calls: list[dict] = []

    def chat(self, model: str, messages: list[dict[str, str]], **kwargs: Any) -> str:
        payload = {"model": model, "messages": messages, "stream": False, **kwargs}
        resp = httpx.post(f"{OLLAMA_URL}/chat/completions", json=payload, timeout=300.0)
        resp.raise_for_status()
        data = resp.json()
        usage = data.get("usage", {})
        pt = usage.get("prompt_tokens", 0)
        ct = usage.get("completion_tokens", 0)
        self.total_prompt_tokens += pt
        self.total_completion_tokens += ct
        self.calls.append({"prompt_tokens": pt, "completion_tokens": ct})
        return data["choices"][0]["message"]["content"]

    @property
    def total_tokens(self) -> int:
        return self.total_prompt_tokens + self.total_completion_tokens


# ==================== 方式 A：本软件流水线 ====================

def run_pipeline_way(client: TokenCountingClient) -> dict:
    for role in ("designer", "supervisor", "coder", "artist3d", "artist2d", "qa"):
        os.environ[f"MODEL_{role.upper()}"] = MODEL

    ckpt = OUTPUT_DIR / "ckpt_a.db"
    repo_db = OUTPUT_DIR / "repo_a.db"
    for f in [ckpt, repo_db]:
        if f.exists():
            f.unlink()

    llm = HybridLLM(local_client=client)
    gw = MagicMock()
    gw.call.return_value = {"status": "ok", "result": {}}
    repo = SQLiteRepo(repo_db)
    deps = AgentDeps(
        llm=llm, gateway=gw, repo=repo,
        api_keys={r: f"k-{r}" for r in (
            "designer", "supervisor", "artist3d", "artist2d", "coder", "qa"
        )},
        max_retries=3,
    )
    config = {"configurable": {"thread_id": "expComplexA"}}
    saver = make_checkpointer(ckpt)
    graph = build_graph_with_checkpointer(deps, saver)
    state: dict = {
        "task_id": "expComplexA", "user_request": GAME_REQUEST,
        "current_role": "designer", "status": "running",
        "retries": {}, "produced_assets": [], "defects": [], "errors": [],
    }
    final = state
    rounds = 0
    while True:
        rounds += 1
        final = graph.invoke(state, config=config)
        status = final.get("status", "")
        if status == "paused_human":
            state = {"status": "running"}
            if rounds > 10:
                break
            continue
        break
    saver.conn.close()
    return {
        "gdd": final.get("gdd", {}),
        "manifest": final.get("manifest", {}),
        "art_spec": final.get("art_spec", {}),
        "produced_assets": final.get("produced_assets", []),
        "build_result": final.get("build_result", {}),
        "defects": final.get("defects", []),
        "retries": final.get("retries", {}),
        "rounds": rounds,
    }


# ==================== 方式 B：直接 LLM 一次性生成 ====================

DIRECT_PROMPT = """你是游戏策划+技术设计+美术指导。根据需求一次性生成完整游戏设计文档。

需求：{request}

请生成以下文档，严格返回 JSON：
1. gdd：游戏设计文档，含 game_title, genre, core_loop, levels（至少3关，每关有 level_id/name/difficulty/spawn_table）, numeric_tables（含 schema_version, damage/economy/growth 三表）
2. manifest：资产清单，含 assets 列表（每项 asset_id/type/target_scene/dependencies/status）
3. art_spec：美术规范，含 texture_spec, fbx_axis, naming_pattern, allowed_formats
4. code_outline：GDScript 代码框架

只返回 JSON：{{"gdd": {{...}}, "manifest": {{...}}, "art_spec": {{...}}, "code_outline": "..."}}
"""


def run_direct_way(client: TokenCountingClient) -> dict:
    prompt = DIRECT_PROMPT.format(request=GAME_REQUEST)
    text = client.chat(MODEL, [{"role": "user", "content": prompt}])
    try:
        bundle = extract_json(text)
    except Exception:
        bundle = {"gdd": {}, "manifest": {}, "art_spec": {}, "code_outline": text}
    return {
        "gdd": bundle.get("gdd", {}),
        "manifest": bundle.get("manifest", {}),
        "art_spec": bundle.get("art_spec", {}),
        "code_outline": bundle.get("code_outline", ""),
    }


# ==================== 结构化指标 ====================

def structural_metrics(result: dict) -> dict:
    gdd = result.get("gdd", {})
    manifest = result.get("manifest", {})
    art_spec = result.get("art_spec", {})
    gdd_fields = sum(1 for k in (
        "game_title", "genre", "core_loop", "levels", "numeric_tables"
    ) if gdd.get(k))
    levels = gdd.get("levels", [])
    nt = gdd.get("numeric_tables", {})
    nt_tables = sum(1 for k in ("damage", "economy", "growth") if nt.get(k))
    assets = manifest.get("assets", [])
    asset_types = set(a.get("type", "") for a in assets)
    art_fields = sum(1 for k in (
        "texture_spec", "fbx_axis", "naming_pattern", "allowed_formats"
    ) if art_spec.get(k))
    return {
        "gdd_field_coverage": f"{gdd_fields}/5",
        "level_count": len(levels),
        "numeric_table_coverage": f"{nt_tables}/3",
        "asset_count": len(assets),
        "asset_type_diversity": len(asset_types),
        "art_spec_coverage": f"{art_fields}/4",
        "has_code_outline": bool(result.get("code_outline")),
        "produced_asset_count": len(result.get("produced_assets", [])),
    }


# ==================== 质量指标 ====================

_NAMING_RE = re.compile(
    r"^(model|texture|ui|audio|anim)_[a-z][a-z0-9]*(_[a-z][a-z0-9]*)*$"
)


def quality_metrics(result: dict) -> dict:
    gdd = result.get("gdd", {})
    manifest = result.get("manifest", {})
    art_spec = result.get("art_spec", {})
    scores = {}
    try:
        validate_gdd(gdd)
        scores["gdd_schema_valid"] = True
    except Exception:
        scores["gdd_schema_valid"] = False
    try:
        validate_asset_manifest(manifest)
        scores["manifest_schema_valid"] = True
    except Exception:
        scores["manifest_schema_valid"] = False
    try:
        validate_art_spec(art_spec)
        scores["art_spec_schema_valid"] = True
    except Exception:
        scores["art_spec_schema_valid"] = False
    try:
        validate_no_circular_deps(manifest)
        scores["no_circular_deps"] = True
    except CircularDependencyError:
        scores["no_circular_deps"] = False
    except Exception:
        scores["no_circular_deps"] = True
    assets = manifest.get("assets", [])
    if assets:
        valid_names = sum(1 for a in assets if _NAMING_RE.match(a.get("asset_id", "")))
        scores["naming_compliance_rate"] = f"{valid_names}/{len(assets)}"
    else:
        scores["naming_compliance_rate"] = "0/0"
    all_deps = []
    for a in assets:
        for dep in a.get("dependencies", []):
            all_deps.append(dep)
    asset_ids = {a.get("asset_id") for a in assets}
    if all_deps:
        resolved = sum(1 for d in all_deps if d in asset_ids)
        scores["dep_resolution_rate"] = f"{resolved}/{len(all_deps)}"
    else:
        scores["dep_resolution_rate"] = "N/A"
    return scores


# ==================== LLM-as-judge ====================

JUDGE_PROMPT = """你是资深游戏设计评审。对以下两个游戏设计方案打分（1-10 分，整数）。

需求：{request}

方案一（A）：
{plan_a}

方案二（B）：
{plan_b}

按以下 6 个维度分别打分，严格返回 JSON：
{{"design_completeness": {{"a": N, "b": N, "reason": "..."}},
  "asset_planning": {{"a": N, "b": N, "reason": "..."}},
  "balance": {{"a": N, "b": N, "reason": "..."}},
  "implementability": {{"a": N, "b": N, "reason": "..."}},
  "doc_quality": {{"a": N, "b": N, "reason": "..."}},
  "playability": {{"a": N, "b": N, "reason": "..."}}}}
"""


def llm_judge(client: TokenCountingClient, result_a: dict, result_b: dict) -> dict:
    def summarize(r: dict) -> str:
        gdd = r.get("gdd", {})
        manifest = r.get("manifest", {})
        lines = [
            f"game_title: {gdd.get('game_title', 'N/A')}",
            f"genre: {gdd.get('genre', 'N/A')}",
            f"core_loop: {str(gdd.get('core_loop', 'N/A'))[:100]}",
            f"levels: {len(gdd.get('levels', []))} 关",
            f"numeric_tables: {list(gdd.get('numeric_tables', {}).keys())}",
            f"assets: {len(manifest.get('assets', []))} 个",
            f"asset_types: {set(a.get('type','') for a in manifest.get('assets',[]))}",
        ]
        if r.get("produced_assets"):
            lines.append(f"produced: {len(r['produced_assets'])} 个")
        if r.get("build_result"):
            lines.append(f"build: {r['build_result']}")
        if r.get("code_outline"):
            lines.append(f"code: {len(r['code_outline'])} 字符")
        return "\n".join(lines)

    prompt = JUDGE_PROMPT.format(
        request=GAME_REQUEST,
        plan_a=summarize(result_a),
        plan_b=summarize(result_b),
    )
    text = client.chat(MODEL, [{"role": "user", "content": prompt}])
    try:
        return extract_json(text)
    except Exception:
        return {"raw": text[:500]}


# ==================== 主流程 ====================

def main() -> None:
    print("=" * 70)
    print("对比实验：复杂 RPG 游戏 — 本软件 vs 直接 LLM")
    print("=" * 70)
    print(f"游戏需求: {GAME_REQUEST[:80]}...")
    print(f"LLM: Ollama {MODEL}")
    print()

    client_a = TokenCountingClient()
    t0 = time.time()
    print("[方式 A] 运行多智能体流水线...")
    result_a = run_pipeline_way(client_a)
    time_a = time.time() - t0
    print(f"  完成: {time_a:.1f}s | {len(client_a.calls)} 次 LLM 调用 | {client_a.total_tokens} tokens")
    (OUTPUT_DIR / "result_a.json").write_text(
        json.dumps(result_a, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    client_b = TokenCountingClient()
    t0 = time.time()
    print("[方式 B] 直接 LLM 一次性生成...")
    result_b = run_direct_way(client_b)
    time_b = time.time() - t0
    print(f"  完成: {time_b:.1f}s | {len(client_b.calls)} 次 LLM 调用 | {client_b.total_tokens} tokens")
    (OUTPUT_DIR / "result_b.json").write_text(
        json.dumps(result_b, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    print("\n[评估] 结构化指标...")
    metrics_a = structural_metrics(result_a)
    metrics_b = structural_metrics(result_b)

    print("[评估] 质量指标...")
    quality_a = quality_metrics(result_a)
    quality_b = quality_metrics(result_b)

    print("[评估] LLM-as-judge 打分...")
    client_j = TokenCountingClient()
    judge = llm_judge(client_j, result_a, result_b)

    print("\n" + "=" * 70)
    print("结构化指标对比:")
    print(f"{'指标':<25} {'方式A(本软件)':<20} {'方式B(直接LLM)':<20}")
    print("-" * 65)
    for k in metrics_a:
        print(f"{k:<25} {str(metrics_a[k]):<20} {str(metrics_b[k]):<20}")

    print("\n质量指标对比:")
    print(f"{'指标':<25} {'方式A(本软件)':<20} {'方式B(直接LLM)':<20}")
    print("-" * 65)
    for k in quality_a:
        print(f"{k:<25} {str(quality_a[k]):<20} {str(quality_b[k]):<20}")

    print("\nLLM-as-judge 打分（1-10）:")
    print(f"{'维度':<25} {'方式A':<8} {'方式B':<8} {'说明'}")
    print("-" * 70)
    total_a = total_b = 0
    for dim, scores in judge.items():
        if not isinstance(scores, dict):
            continue
        a = scores.get("a", "?")
        b = scores.get("b", "?")
        reason = str(scores.get("reason", ""))[:40]
        print(f"{dim:<25} {a:<8} {b:<8} {reason}")
        if isinstance(a, int):
            total_a += a
        if isinstance(b, int):
            total_b += b
    print(f"{'总计':<25} {total_a:<8} {total_b:<8}")

    print("\n成本对比:")
    print(f"{'指标':<25} {'方式A(本软件)':<20} {'方式B(直接LLM)':<20}")
    print("-" * 65)
    print(f"{'耗时(秒)':<25} {time_a:<20.1f} {time_b:<20.1f}")
    print(f"{'LLM调用次数':<25} {len(client_a.calls):<20} {len(client_b.calls):<20}")
    print(f"{'total_tokens':<25} {client_a.total_tokens:<20} {client_b.total_tokens:<20}")
    print(f"{'流水线轮次':<25} {result_a.get('rounds', '-'):<20} {'1':<20}")
    print(f"{'缺陷数量':<25} {len(result_a.get('defects', [])):<20} {'N/A':<20}")
    print(f"{'重试次数':<25} {sum(result_a.get('retries', {}).values()):<20} {'N/A':<20}")

    report = {
        "request": GAME_REQUEST,
        "metrics_a": metrics_a, "metrics_b": metrics_b,
        "quality_a": quality_a, "quality_b": quality_b,
        "judge": judge,
        "cost": {
            "a": {"time_s": time_a, "calls": len(client_a.calls), "tokens": client_a.total_tokens},
            "b": {"time_s": time_b, "calls": len(client_b.calls), "tokens": client_b.total_tokens},
        },
    }
    (OUTPUT_DIR / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n报告已保存到 {OUTPUT_DIR}/report.json")


if __name__ == "__main__":
    main()
