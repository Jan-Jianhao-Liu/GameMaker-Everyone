"""最小验证脚本（约 50 行）：无头 Blender 内验证 socket 桥完整链路。

用法：
    blender --background --python minimal_verify.py -- --out C:/tmp/test.fbx

流程：注册 addon（启动 socket+timer）→ 子线程做 socket 客户端发
create_primitive → export_fbx → 校验落盘 → 打印结果 → 退出。
"""

from __future__ import annotations

import json
import socket
import sys
import threading
import time
import uuid
from pathlib import Path


def _send_cmd(port: int, tool: str, **params):
    s = socket.create_connection(("127.0.0.1", port), timeout=10)
    req = {"req_id": str(uuid.uuid4()), "tool": tool, "params": params}
    s.sendall((json.dumps(req) + "\n").encode())
    buf = b""
    while b"\n" not in buf:
        buf += s.recv(4096)
    s.close()
    return json.loads(buf.strip())


def _client_thread(port: int, out_path: str, results: list):
    time.sleep(1.0)
    try:
        r1 = _send_cmd(port, "create_primitive", prim_type="CUBE",
                       name="model_test_cube", dimensions=[2, 2, 2])
        r2 = _send_cmd(port, "export_fbx", asset_id="model_test_cube",
                       path=out_path)
        results.append((r1, r2))
    except Exception as e:  # noqa: BLE001
        results.append({"error": str(e)})


def main() -> None:
    out = Path("test_verify.fbx")
    if "--out" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--out") + 1])
    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 19876

    import game_agent_factory  # noqa: F401
    game_agent_factory.register()

    results: list = []
    t = threading.Thread(target=_client_thread, args=(port, str(out), results))
    t.start()
    t.join(timeout=30)

    game_agent_factory.unregister()

    if results and "error" not in results[0]:
        r1, r2 = results[0]
        ok = out.exists() and out.stat().st_size > 0
        print(f"[VERIFY] create_primitive: {r1['status']}")
        print(f"[VERIFY] export_fbx: {r2['status']}")
        print(f"[VERIFY] FBX 落盘: {ok} ({out}, {out.stat().st_size if ok else 0} bytes)")
        sys.exit(0 if ok else 1)
    else:
        print(f"[VERIFY] 失败: {results}")
        sys.exit(1)


if __name__ == "__main__":
    main()