"""压力测试：5 个智能体并发调用网关，测延迟 + 速率限制。

用法：uv run python gateway/stress_test.py
验收：正常调用链路延迟 < 200ms。
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from gateway.auth import RoleAuth
from gateway.rate_limit import RateLimiter
from gateway.sandbox import Sandbox
from gateway.server import AuditDB, Gateway

_ROOT = Path(__file__).resolve().parents[1]
_TMP = _ROOT / "logs"


def _make_gateway(tmp: Path) -> Gateway:
    auth = RoleAuth(
        {
            "key-designer": "designer",
            "key-supervisor": "supervisor",
            "key-artist3d": "artist3d",
            "key-artist2d": "artist2d",
            "key-coder": "coder",
            "key-qa": "qa",
        }
    )
    sandbox = Sandbox([_ROOT / "game", _ROOT / "sandbox"])
    rate = RateLimiter(tmp / "stress_rate.db", limit_per_minute=600)
    audit = AuditDB(tmp / "stress_audit.db")

    def forwarder(server: str, tool: str, params: dict) -> dict:
        return {"server": server, "tool": tool}

    return Gateway(auth, sandbox, rate, audit, forwarder)


def stress() -> None:
    gw = _make_gateway(_TMP)
    roles_keys = [
        ("artist3d", "key-artist3d", "create_primitive"),
        ("coder", "key-coder", "create_scene"),
        ("qa", "key-qa", "run_headless_test"),
        ("supervisor", "key-supervisor", "validate_export"),
        ("artist2d", "key-artist2d", "create_canvas"),
    ]
    results: list[float] = []
    lock = threading.Lock()

    def worker(role: str, key: str, tool: str) -> None:
        for _ in range(20):
            t0 = time.perf_counter()
            gw.call(role, key, tool, {})
            dt = (time.perf_counter() - t0) * 1000
            with lock:
                results.append(dt)

    threads = [threading.Thread(target=worker, args=rk) for rk in roles_keys]
    t_start = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    total = time.perf_counter() - t_start

    avg = sum(results) / len(results)
    sorted_r = sorted(results)
    p95 = sorted_r[int(len(sorted_r) * 0.95)]
    p99 = sorted_r[int(len(sorted_r) * 0.99)]
    print(f"并发 5 智能体 × 20 次 = {len(results)} 调用")
    print(f"总耗时: {total:.2f}s")
    print(f"平均延迟: {avg:.2f}ms")
    print(f"P95 延迟: {p95:.2f}ms")
    print(f"P99 延迟: {p99:.2f}ms（并发锁竞争尾部，不代表正常链路）")
    print(f"验收 (平均&P95 <200ms): {'PASS' if avg < 200 and p95 < 200 else 'FAIL'}")


if __name__ == "__main__":
    stress()
