"""思考过程事件总线。

线程安全、可选的事件发射器。各 agent 通过 ThoughtBus 向 Web 界面
实时广播思考过程（正在做什么、LLM 返回了什么、校验结果等）。

用法：
    bus = ThoughtBus(emit_callback)
    bus.think("designer", "正在分析用户需求...")
    bus.act("designer", "调用 LLM 生成契约文档", prompt_len=500)
    bus.result("designer", "契约生成完成", gdd_fields=5, assets=9)

emit_callback 签名: (role: str, phase: str, data: dict) -> None
None 时为静默模式（CLI / 测试用）。
"""

from __future__ import annotations

import threading
from collections.abc import Callable


class ThoughtBus:
    """思考过程事件总线。线程安全，可选。"""

    def __init__(
        self, emit: Callable[[str, str, dict], None] | None = None,
    ) -> None:
        self._emit_fn = emit
        self._lock = threading.Lock()

    def emit(self, role: str, phase: str, data: dict) -> None:
        """发射事件。phase: thinking | action | result | error | question。"""
        if self._emit_fn is None:
            return
        with self._lock:
            self._emit_fn(role, phase, data)

    def think(self, role: str, message: str, **extra: object) -> None:
        """发射思考事件（正在想什么）。"""
        self.emit(role, "thinking", {"message": message, **extra})

    def act(self, role: str, message: str, **extra: object) -> None:
        """发射行动事件（正在做什么）。"""
        self.emit(role, "action", {"message": message, **extra})

    def result(self, role: str, message: str, **extra: object) -> None:
        """发射结果事件（做完了什么）。"""
        self.emit(role, "result", {"message": message, **extra})

    def error(self, role: str, message: str, **extra: object) -> None:
        """发射错误事件。"""
        self.emit(role, "error", {"message": message, **extra})


_bus: ThoughtBus | None = None


def get_bus() -> ThoughtBus | None:
    """获取全局 ThoughtBus（agent 内部便捷调用）。"""
    return _bus


def set_bus(bus: ThoughtBus | None) -> None:
    """设置全局 ThoughtBus。"""
    global _bus
    _bus = bus
