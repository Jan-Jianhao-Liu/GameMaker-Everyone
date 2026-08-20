"""JSON 提取工具。

LLM 返回的文本可能包裹在 ```json ... ``` 代码块里，或前后带说明文字。
本模块提供容错的 JSON 提取与解析。
"""

from __future__ import annotations

import json
import re
from typing import Any

_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL)


def extract_json(text: str) -> dict[str, Any]:
    """从 LLM 文本中提取第一个 JSON 对象。

    优先解析 ```json ... ``` 代码块；失败则尝试找第一个 {...} 段。
    解析失败抛 ValueError。
    """
    m = _FENCE_RE.search(text)
    if m:
        return json.loads(m.group(1))
    start = text.find("{")
    if start == -1:
        raise ValueError("LLM 响应中未找到 JSON 对象")
    depth = 0
    for i in range(start, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise ValueError("LLM 响应中 JSON 对象未闭合")
