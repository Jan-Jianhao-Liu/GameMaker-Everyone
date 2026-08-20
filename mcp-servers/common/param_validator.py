"""参数校验：用 pydantic 模型定义各白名单工具的参数 Schema。

各 MCP Server 继承 BaseToolParams 定义自己的工具参数模型，
确保只接受结构化参数，禁止透传任意代码。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError, field_validator


class BaseToolParams(BaseModel):
    """工具参数基类。子类定义具体字段。"""

    model_config = {"extra": "forbid"}


def validate_params(model_cls: type[BaseToolParams], raw: dict[str, Any]) -> Any:
    """校验原始参数 dict，返回模型实例。失败抛 ValueError。"""
    try:
        return model_cls(**raw)
    except ValidationError as e:
        raise ValueError(f"参数校验失败: {e}") from e