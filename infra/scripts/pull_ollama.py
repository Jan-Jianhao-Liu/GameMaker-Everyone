"""Ollama 模型预拉 + 健康检查。

预拉 qwen3.5:4b（artist3d/artist2d）和 qwen3.5:2b（qa）。
Ollama 跑宿主机原生（不进容器），默认 http://localhost:11434。

用法：python -m infra.scripts.pull_ollama
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

_MODELS = ["qwen3.5:4b", "qwen3.5:2b"]
_OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
_OLLAMA_PORT = int(os.getenv("OLLAMA_PORT", "11434"))


def check_ollama_running() -> bool:
    """检测 Ollama 服务是否在跑。"""
    import socket

    try:
        with socket.create_connection(("127.0.0.1", _OLLAMA_PORT), timeout=2):
            return True
    except (OSError, ConnectionRefusedError):
        return False


def pull_models() -> bool:
    """预拉模型。返回 True 表示全部成功。"""
    if not check_ollama_running():
        print(
            f"✗ Ollama 未在 127.0.0.1:{_OLLAMA_PORT} 运行\n"
            "请先启动 Ollama（Windows 原生版）：\n"
            "  1. 从 https://ollama.com 下载安装\n"
            "  2. 设置环境变量 OLLAMA_NUM_PARALLEL=2, OLLAMA_MAX_LOADED_MODELS=2\n"
            "  3. 启动 Ollama 服务",
            file=sys.stderr,
        )
        return False

    all_ok = True
    for model in _MODELS:
        print(f"拉取 {model} ...")
        try:
            r = subprocess.run(
                ["ollama", "pull", model], timeout=600,
                capture_output=True, text=True,
            )
            if r.returncode == 0:
                print(f"✓ {model} 已就绪")
            else:
                print(f"✗ {model} 拉取失败: {r.stderr.strip()}", file=sys.stderr)
                all_ok = False
        except subprocess.SubprocessError as e:
            print(f"✗ {model} 拉取异常: {e}", file=sys.stderr)
            all_ok = False
    return all_ok


def health_check() -> bool:
    """健康检查：Ollama 在线 + 模型已拉。"""
    if not check_ollama_running():
        return False
    try:
        r = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=10
        )
        if r.returncode != 0:
            return False
        installed = r.stdout
        for model in _MODELS:
            if model not in installed:
                return False
        print("✓ Ollama 健康检查通过")
        return True
    except subprocess.SubprocessError:
        return False


if __name__ == "__main__":
    if not pull_models():
        sys.exit(1)
    time.sleep(1)
    sys.exit(0 if health_check() else 1)
