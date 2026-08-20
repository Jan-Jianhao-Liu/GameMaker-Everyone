"""意图解析：从用户需求文本抽取 genre / core_loop / 资产需求摘要。

用云端 LLM 生成 GDD 草案摘要，展示给用户确认（4 个人工卡点之一）。
确认后启动 Prompt 5 的五角色流水线。
"""

from __future__ import annotations

from agents.common.json_utils import extract_json
from agents.common.llm import HybridLLM

_INTENT_PROMPT = """你是游戏策划。从用户需求中抽取游戏意图摘要，严格返回 JSON。

用户需求：{request}

返回格式：
```json
{{"game_title": "...", "genre": "...", "core_loop": "...",
  "asset_summary": ["model_...", "texture_..."]}}
```

只返回 JSON，不要解释文字。"""


def parse_intent(llm: HybridLLM, request: str) -> dict:
    """从用户需求抽取意图摘要。

    Returns:
        含 game_title / genre / core_loop / asset_summary 的 dict。
    """
    text = llm.chat(
        "designer",
        [{"role": "user", "content": _INTENT_PROMPT.format(request=request)}],
        temperature=0.3,
    )
    return extract_json(text)


def format_intent_for_review(intent: dict) -> str:
    """格式化意图摘要供用户确认。"""
    return (
        f"游戏标题: {intent.get('game_title', 'N/A')}\n"
        f"类型:     {intent.get('genre', 'N/A')}\n"
        f"核心循环: {intent.get('core_loop', 'N/A')}\n"
        f"资产需求: {', '.join(intent.get('asset_summary', []))}"
    )


def prompt_confirm(intent: dict, stream=None) -> bool:
    """展示意图摘要并等待用户确认。返回 True 表示确认。"""
    from gaf.progress import _emit

    _emit("\n请确认游戏设计意图：", stream)
    _emit(format_intent_for_review(intent), stream)
    _emit("\n确认启动流水线？[y/n/修改意见]: ", stream)
    try:
        answer = input().strip().lower()
    except EOFError:
        return False
    return answer in ("y", "yes", "是")
