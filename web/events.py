"""WebSocket 事件协议。

前端 → 后端（ClientEvent）：
  chat              自由对话
  make_game         触发 make-game 流水线
  checkpoint_response  人工卡点确认
  resume            恢复中断的流水线

后端 → 前端（ServerEvent）：
  team_reply        团队回复文本
  role_status       角色状态更新
  progress          节点完成进度
  checkpoint        人工卡点请求
  complete          流水线完成
  error             错误
  history           历史会话
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ClientEvent:
    """前端发来的事件。解析后分发到对应 handler。"""

    type: str
    text: str = ""
    request: str = ""
    task_id: str = ""
    accept: bool = True
    feedback: str = ""
    api_key: str = ""
    cloud_provider: str = ""
    base_url: str = ""
    provider_id: str = ""
    model: str = ""


@dataclass
class ServerEvent:
    """后端推送的事件。序列化为 JSON 发给前端。"""

    type: str
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, **self.data}


def team_reply(text: str) -> ServerEvent:
    return ServerEvent("team_reply", {"text": text})


def role_status(role: str, status: str, detail: str = "") -> ServerEvent:
    return ServerEvent("role_status", {"role": role, "status": status, "detail": detail})


def progress(node: str, update: dict[str, Any]) -> ServerEvent:
    return ServerEvent("progress", {"node": node, "update": update})


def checkpoint(task_id: str, message: str) -> ServerEvent:
    return ServerEvent("checkpoint", {"task_id": task_id, "message": message})


def complete(task_id: str, summary: dict[str, Any]) -> ServerEvent:
    return ServerEvent("complete", {"task_id": task_id, "summary": summary})


def error_event(message: str) -> ServerEvent:
    return ServerEvent("error", {"message": message})


def history(messages: list[dict[str, Any]]) -> ServerEvent:
    return ServerEvent("history", {"messages": messages})


def config_saved(api_key_set: bool, cloud_provider: str) -> ServerEvent:
    return ServerEvent(
        "config_saved", {"api_key_set": api_key_set, "cloud_provider": cloud_provider}
    )


def connection_test_result(
    provider_id: str, success: bool, models: list[str] | None = None, error: str = ""
) -> ServerEvent:
    return ServerEvent("connection_test", {
        "provider_id": provider_id, "success": success,
        "models": models or [], "error": error,
    })


def ollama_status(connected: bool, models: list[str] | None = None) -> ServerEvent:
    return ServerEvent("ollama_status", {"connected": connected, "models": models or []})


def parse_client(raw: dict[str, Any]) -> ClientEvent:
    """从 WebSocket JSON 解析 ClientEvent。"""
    return ClientEvent(
        type=raw.get("type", ""),
        text=raw.get("text", ""),
        request=raw.get("request", ""),
        task_id=raw.get("task_id", ""),
        accept=raw.get("accept", True),
        feedback=raw.get("feedback", ""),
        api_key=raw.get("api_key", ""),
        cloud_provider=raw.get("cloud_provider", ""),
        base_url=raw.get("base_url", ""),
        provider_id=raw.get("provider_id", ""),
        model=raw.get("model", ""),
    )
