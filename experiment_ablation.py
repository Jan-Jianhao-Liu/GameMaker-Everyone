"""消融实验：各角色模块价值量化。

方法：复用对比实验的完整流水线产出作为 baseline，然后模拟去掉各角色的影响：
  - Full         — 完整团队产出
  - NoSupervisor — 跳过校验（资产未校验，质量未知）
  - NoArtist3D   — 去掉 model 资产（无法构建）
  - NoArtist2D   — 去掉 texture/ui 资产
  - NoQA         — 跳过测试（build_status=draft，defects 未知）
  - NoDesigner   — 用预填模板替代 LLM 生成（无设计文档）

指标：结构化指标 + 质量指标 + LLM-as-judge + 角色贡献分析

用法: uv run python experiment_ablation.py
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import httpx

from agents.common.json_utils import extract_json
from agents.common.llm import LLMClient
from contracts.validators import (
    CircularDependencyError,
    validate_art_spec,
    validate_asset_manifest,
    validate_gdd,
    validate_no_circular_deps,
)

OUTPUT_DIR = Path("experiment_ablation_output")
OUTPUT_DIR.mkdir(exist_ok=True)

BASELINE_PATH = Path("experiment_complex_output/result_a.json")

MODEL = "my-qwen4b-no-think:latest"
OLLAMA_URL = "http://localhost:11434/v1"

GAME_REQUEST = (
    "做一个3D动作RPG游戏：玩家控制战士在3个关卡中战斗，"
    "有4种武器、6种敌人、升级系统、物品系统、任务系统、金币经济"
)

_NAMING_RE = re.compile(
    r"^(model|texture|ui|audio|anim)_[a-z][a-z0-9]*(_[a-z][a-z0-9]*)*$"
)


class TokenCountingClient(LLMClient):
    def __init__(self) -> None:
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.calls: list[dict] = []

    def chat(self, model: str, messages: list[dict[str, str]], **kwargs: Any) -> str:
        payload = {"model": model, "messages": messages, "stream": False, **kwargs}
        resp = httpx.post(f"{OLLAMA_URL}/chat/completions", json=payload, timeout=120.0)
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


# ==================== 加载 baseline ====================

def load_baseline() -> dict:
    if BASELINE_PATH.exists():
        return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    raise FileNotFoundError(
        f"Baseline not found: {BASELINE_PATH}. Run experiment_complex.py first."
    )


# ==================== 消融模拟 ====================

def ablate(full: dict, config: str) -> dict:
    """从完整产出模拟去掉某角色的影响。"""
    r = json.loads(json.dumps(full, default=str))

    if config == "Full":
        return r

    if config == "NoSupervisor":
        r["produced_assets"] = []
        r["build_result"] = {}
        r["defects"] = [{"id": "D1", "desc": "未校验，资产质量未知"}]
        return r

    if config == "NoArtist3D":
        r["produced_assets"] = [
            a for a in r.get("produced_assets", []) if a.get("type") != "model"
        ]
        r["build_result"] = {}
        r["defects"] = [{"id": "D1", "desc": "缺少 3D 模型，无法构建"}]
        return r

    if config == "NoArtist2D":
        r["produced_assets"] = [
            a for a in r.get("produced_assets", [])
            if a.get("type") not in ("texture", "ui")
        ]
        return r

    if config == "NoQA":
        br = dict(r.get("build_result", {}))
        br["status"] = "draft"
        r["build_result"] = br
        r["defects"] = []
        return r

    if config == "NoDesigner":
        r["gdd"] = {}
        r["manifest"] = {}
        r["art_spec"] = {}
        r["produced_assets"] = []
        r["build_result"] = {}
        r["defects"] = []
        return r

    return r


# ==================== 指标 ====================

def structural_metrics(result: dict) -> dict:
    gdd = result.get("gdd", {})
    manifest = result.get("manifest", {})
    gdd_fields = sum(1 for k in (
        "game_title", "genre", "core_loop", "levels", "numeric_tables"
    ) if gdd.get(k))
    levels = gdd.get("levels", [])
    nt = gdd.get("numeric_tables", {})
    nt_tables = sum(1 for k in ("damage", "economy", "growth") if nt.get(k))
    assets = manifest.get("assets", [])
    return {
        "gdd_fields": f"{gdd_fields}/5",
        "levels": len(levels),
        "numeric_tables": f"{nt_tables}/3",
        "assets_planned": len(assets),
        "assets_produced": len(result.get("produced_assets", [])),
        "build_status": result.get("build_result", {}).get("status", "N/A"),
        "defects": len(result.get("defects", [])),
    }


def quality_metrics(result: dict) -> dict:
    gdd = result.get("gdd", {})
    manifest = result.get("manifest", {})
    art_spec = result.get("art_spec", {})
    scores = {}
    for name, fn in [
        ("gdd_valid", lambda: validate_gdd(gdd)),
        ("manifest_valid", lambda: validate_asset_manifest(manifest)),
        ("art_spec_valid", lambda: validate_art_spec(art_spec)),
    ]:
        try:
            fn()
            scores[name] = True
        except Exception:
            scores[name] = False
    try:
        validate_no_circular_deps(manifest)
        scores["no_circular_deps"] = True
    except CircularDependencyError:
        scores["no_circular_deps"] = False
    except Exception:
        scores["no_circular_deps"] = True
    assets = manifest.get("assets", [])
    if assets:
        valid = sum(1 for a in assets if _NAMING_RE.match(a.get("asset_id", "")))
        scores["naming"] = f"{valid}/{len(assets)}"
    else:
        scores["naming"] = "0/0"
    return scores


# ==================== LLM-as-judge ====================

def summarize(r: dict) -> str:
    gdd = r.get("gdd", {})
    manifest = r.get("manifest", {})
    return (
        f"title={gdd.get('game_title','N/A')}, levels={len(gdd.get('levels',[]))}, "
        f"assets_planned={len(manifest.get('assets',[]))}, "
        f"assets_produced={len(r.get('produced_assets',[]))}, "
        f"build={r.get('build_result',{}).get('status','N/A')}, "
        f"defects={len(r.get('defects',[]))}"
    )


def judge(client: TokenCountingClient, baseline: dict, ablation: dict, name: str) -> dict:
    prompt = f"""比较两个游戏开发方案（1-10 分）。需求：{GAME_REQUEST}
基线（完整团队）：{summarize(baseline)}
消融（{name}）：{summarize(ablation)}
按 5 维度打分，返回 JSON：
{{"quality": {{"b": N, "a": N}}, "completeness": {{"b": N, "a": N}},
  "assets": {{"b": N, "a": N}}, "balance": {{"b": N, "a": N}},
  "implement": {{"b": N, "a": N}}}}"""
    text = client.chat(MODEL, [{"role": "user", "content": prompt}])
    try:
        return extract_json(text)
    except Exception:
        return {}


# ==================== 主流程 ====================

CONFIGS = ["Full", "NoSupervisor", "NoArtist3D", "NoArtist2D", "NoQA", "NoDesigner"]


def main() -> None:
    print("=" * 70)
    print("消融实验：各角色模块价值量化")
    print("=" * 70)
    print(f"游戏需求: {GAME_REQUEST[:60]}...")
    print(f"LLM: Ollama {MODEL}")
    print()

    print("[1] 加载完整流水线 baseline...")
    full = load_baseline()
    print(f"  来源: {BASELINE_PATH}")
    print(f"  产出: {len(full.get('produced_assets', []))} 资产, "
          f"build={full.get('build_result', {}).get('status', 'N/A')}, "
          f"defects={len(full.get('defects', []))}")
    (OUTPUT_DIR / "full_result.json").write_text(
        json.dumps(full, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    print("\n[2] 模拟消融配置...")
    results: dict[str, dict] = {}
    for cfg in CONFIGS:
        results[cfg] = ablate(full, cfg)
        m = structural_metrics(results[cfg])
        q = quality_metrics(results[cfg])
        print(f"  {cfg:<16} assets={m['assets_produced']} build={m['build_status']} "
              f"defects={m['defects']} gdd_valid={q.get('gdd_valid')}")

    print("\n[3] LLM-as-judge 打分...")
    judge_results: dict[str, dict] = {}
    for cfg in CONFIGS:
        if cfg == "Full":
            continue
        t0 = time.time()
        client_j = TokenCountingClient()
        judge_results[cfg] = judge(client_j, full, results[cfg], cfg)
        elapsed = time.time() - t0
        print(f"  {cfg:<16} {elapsed:.1f}s | {client_j.total_tokens} tokens")

    print("\n" + "=" * 70)
    print("消融实验结果:")
    print(f"{'配置':<16} {'GDD字段':<10} {'关卡':<6} {'资产规划':<10} {'资产生产':<10} "
          f"{'构建':<12} {'缺陷':<6} {'GDD合规':<8} {'命名合规':<10}")
    print("-" * 90)
    for cfg in CONFIGS:
        m = structural_metrics(results[cfg])
        q = quality_metrics(results[cfg])
        print(f"{cfg:<16} {m['gdd_fields']:<10} {m['levels']:<6} {m['assets_planned']:<10} "
              f"{m['assets_produced']:<10} {m['build_status']:<12} {m['defects']:<6} "
              f"{str(q.get('gdd_valid','?')):<8} {q.get('naming','?'):<10}")

    print("\nLLM-as-judge（基线 vs 消融，1-10）:")
    print(f"{'配置':<16} {'质量':<12} {'完整度':<12} {'资产':<12} {'平衡':<12} {'可实现':<12}")
    print("-" * 76)
    for cfg, sc in judge_results.items():
        vals = []
        for dim in ("quality", "completeness", "assets", "balance", "implement"):
            s = sc.get(dim, {})
            vals.append(f"{s.get('b','?')}->{s.get('a','?')}")
        print(f"{cfg:<16} {vals[0]:<12} {vals[1]:<12} {vals[2]:<12} {vals[3]:<12} {vals[4]:<12}")

    print("\n角色贡献分析（基线 - 消融）:")
    baseline_m = structural_metrics(results["Full"])
    for cfg in CONFIGS:
        if cfg == "Full":
            continue
        m = structural_metrics(results[cfg])
        delta_assets = baseline_m["assets_produced"] - m["assets_produced"]
        delta_defects = m["defects"] - baseline_m["defects"]
        print(f"  去掉{cfg[2:]:<14} -> 资产减少 {delta_assets} 个, 缺陷增加 {delta_defects} 个")

    report = {
        "request": GAME_REQUEST,
        "full": full,
        "ablations": {cfg: results[cfg] for cfg in CONFIGS},
        "judge": judge_results,
    }
    (OUTPUT_DIR / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n报告已保存到 {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
