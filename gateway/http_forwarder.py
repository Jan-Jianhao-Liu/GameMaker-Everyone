"""HTTP MCP 转发器 — 通过 streamable-http 协议调用 godot-ai MCP 服务器。

godot-ai 服务器启动方式:
  uvx --from "godot-ai==3.1.5" godot-ai --transport streamable-http --port 8001 --ws-port 9501

本模块实现 MCP 2025-06-18 streamable-http 客户端:
  POST /mcp  Content-Type: application/json  Accept: application/json, text/event-stream
  → 初始化 → 发送 tools/call → 返回结果
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import httpx


class HttpMcpForwarder:
    """HTTP streamable-http MCP 转发器。

    用法:
        fwd = HttpMcpForwarder("http://127.0.0.1:8001/mcp")
        result = fwd.call("godot_ai", "node_create", {"type": "Node3D", "name": "Level"})

    或作为 Gateway forwarder 的分发器:
        multi = MultiForwarder()
        multi.register("godot_ai", fwd)
        multi.register("blender", stdio_fwd)
    """

    def __init__(self, endpoint: str = "http://127.0.0.1:8001/mcp", timeout: float = 30.0) -> None:
        self._endpoint = endpoint
        self._timeout = timeout
        self._session: str | None = None
        self._initialized = False
        self._client: httpx.Client | None = None

    def _ensure_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self._timeout)
        return self._client

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        client = self._ensure_client()
        resp = client.post(
            self._endpoint,
            headers=self._headers(),
            json={
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "gaf-gateway", "version": "1.0.0"},
                },
            },
        )
        resp.raise_for_status()
        data = self._parse_response(resp)
        self._session = data.get("result", {}).get("_meta", {}).get("sessionId")
        self._initialized = True

        if self._session:
            client.post(
                self._endpoint,
                headers=self._headers(),
                json={
                    "jsonrpc": "2.0",
                    "id": str(uuid.uuid4()),
                    "method": "notifications/initialized",
                },
            )

    def _headers(self) -> dict[str, str]:
        h = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._session:
            h["Mcp-Session-Id"] = self._session
        return h

    @staticmethod
    def _parse_response(resp: httpx.Response) -> dict[str, Any]:
        ct = resp.headers.get("Content-Type", "")
        if "text/event-stream" in ct:
            for line in resp.text.splitlines():
                line = line.strip()
                if line.startswith("data:"):
                    return json.loads(line[5:].strip())
            return {}
        return resp.json()

    def call(self, server: str, tool: str, params: dict[str, Any]) -> dict[str, Any]:
        """调用 MCP 工具。server 参数用于日志，实际端点在构造时指定。"""
        self._ensure_initialized()
        client = self._ensure_client()
        resp = client.post(
            self._endpoint,
            headers=self._headers(),
            json={
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "tools/call",
                "params": {"name": tool, "arguments": params},
            },
        )
        resp.raise_for_status()
        data = self._parse_response(resp)
        if "error" in data:
            return {"status": "error", "error": data["error"].get("message", str(data["error"]))}
        result = data.get("result", {})
        if isinstance(result, dict) and result.get("isError"):
            texts = [
                c.get("text", "") for c in result.get("content", [])
                if c.get("type") == "text"
            ]
            return {"status": "error", "error": "\n".join(texts) or "工具返回错误"}
        return {"status": "ok", "result": result}

    def close(self) -> None:
        self._initialized = False
        self._session = None
        if self._client is not None:
            self._client.close()
            self._client = None


class MultiForwarder:
    """多服务器转发分发器 — 按 server name 路由到不同 forwarder。

    用法:
        multi = MultiForwarder()
        multi.register("godot_ai", HttpMcpForwarder("http://127.0.0.1:8001/mcp"))
        multi.register("blender", StdioForwarder(...))
        # Gateway 的 forwarder 参数直接传 multi.dispatch
    """

    def __init__(self) -> None:
        self._forwarders: dict[str, Any] = {}
        self._fallback: Any = None

    def register(self, server: str, forwarder: Any) -> None:
        self._forwarders[server] = forwarder

    def set_fallback(self, forwarder: Any) -> None:
        self._fallback = forwarder

    def dispatch(self, server: str, tool: str, params: dict[str, Any]) -> dict[str, Any]:
        fwd = self._forwarders.get(server)
        if fwd is not None:
            if hasattr(fwd, "call"):
                return fwd.call(server, tool, params)
            return fwd(server, tool, params)
        if self._fallback is not None:
            if hasattr(self._fallback, "call"):
                return self._fallback.call(server, tool, params)
            return self._fallback(server, tool, params)
        return {"status": "error", "error": f"无转发器注册 for server={server}"}

    def close_all(self) -> None:
        for fwd in self._forwarders.values():
            if hasattr(fwd, "close"):
                fwd.close()
