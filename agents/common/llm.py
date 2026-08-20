"""混合模式 LLM 接入。

按 DECISIONS.md §1.1 模型分流：
- designer / supervisor / coder → 云端 API（GLM-4 Air / DeepSeek / Qwen Plus）
- artist3d / artist2d → 本地 Ollama qwen3.5:4b
- qa → 本地 Ollama qwen3.5:2b

云端与本地均走 OpenAI 兼容接口（/v1/chat/completions），用 httpx 同步调用。
配置从环境变量读取（infra/llm.env 由 cli 在启动时注入 os.environ）。

LLMClient 为抽象基类，便于测试注入 mock。
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any

import httpx

_DEFAULT_TIMEOUT = 60.0


class LLMClient(ABC):
    """LLM 客户端抽象基类。"""

    @abstractmethod
    def chat(
        self, model: str, messages: list[dict[str, str]], **kwargs: Any
    ) -> str: ...


class OllamaClient(LLMClient):
    """本地 Ollama（OpenAI 兼容接口）。"""

    def __init__(self, base_url: str | None = None, timeout: float = _DEFAULT_TIMEOUT) -> None:
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        self.timeout = timeout

    def chat(self, model: str, messages: list[dict[str, str]], **kwargs: Any) -> str:
        payload = {"model": model, "messages": messages, "stream": False, **kwargs}
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


class CloudClient(LLMClient):
    """云端 API（OpenAI 兼容接口）。"""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self.api_key = api_key or os.getenv("LLM_CLOUD_API_KEY", "")
        self.base_url = base_url or os.getenv(
            "LLM_CLOUD_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"
        )
        self.timeout = timeout
        if not self.api_key:
            raise RuntimeError(
                "LLM_CLOUD_API_KEY 未配置。请设置环境变量或通过 cli --api-key 注入。"
            )

    def chat(self, model: str, messages: list[dict[str, str]], **kwargs: Any) -> str:
        payload = {"model": model, "messages": messages, "stream": False, **kwargs}
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


# 角色到模型分流配置（值 "cloud" 表示走云端，其他值视为本地模型名）
_ROLE_MODEL_ENV = {
    "designer": "MODEL_DESIGNER",
    "supervisor": "MODEL_SUPERVISOR",
    "coder": "MODEL_CODER",
    "artist3d": "MODEL_ARTIST3D",
    "artist2d": "MODEL_ARTIST2D",
    "qa": "MODEL_QA",
}

# 云端模型名（按 provider 选）
_CLOUD_MODEL_BY_PROVIDER = {
    "glm": "glm-4-air",
    "deepseek": "deepseek-chat",
    "qwen": "qwen-plus",
}


class HybridLLM:
    """混合模式 LLM 路由器。根据角色选本地/云端。

    用法：
        llm = HybridLLM()
        text = llm.chat("designer", [{"role": "user", "content": "..."}])

    测试时注入 mock：
        llm = HybridLLM(local_client=FakeClient(), cloud_client=FakeClient())
    """

    def __init__(
        self,
        local_client: LLMClient | None = None,
        cloud_client: LLMClient | None = None,
    ) -> None:
        self._local = local_client or OllamaClient()
        self._cloud = cloud_client
        self._cloud_model = _CLOUD_MODEL_BY_PROVIDER.get(
            os.getenv("LLM_CLOUD_PROVIDER", "glm"), "glm-4-air"
        )

    def _resolve(self, role: str) -> tuple[LLMClient, str]:
        env_var = _ROLE_MODEL_ENV.get(role)
        if env_var is None:
            raise ValueError(f"未知角色: {role}")
        model = os.getenv(env_var, "cloud")
        if model == "cloud":
            if self._cloud is None:
                self._cloud = CloudClient()
            return self._cloud, self._cloud_model
        return self._local, model

    def chat(self, role: str, messages: list[dict[str, str]], **kwargs: Any) -> str:
        client, model = self._resolve(role)
        return client.chat(model, messages, **kwargs)
