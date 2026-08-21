"""ThoughtBus + 智能体追问 测试。"""

from __future__ import annotations

from agents.common.questioning import (
    Question,
    QuestionOption,
    check_question,
    designer_question,
    should_ask,
)
from agents.common.thought_bus import ThoughtBus


class TestThoughtBus:
    def test_silent_when_no_emit(self):
        bus = ThoughtBus(None)
        bus.think("designer", "thinking...")
        bus.act("designer", "acting...")
        bus.result("designer", "done")
        bus.error("designer", "failed")

    def test_emits_events(self):
        events: list[tuple[str, str, dict]] = []

        def emit(role: str, phase: str, data: dict) -> None:
            events.append((role, phase, data))

        bus = ThoughtBus(emit)
        bus.think("designer", "analyzing", request="test")
        bus.act("designer", "calling LLM")
        bus.result("designer", "done", assets=5)
        bus.error("qa", "test failed")

        assert len(events) == 4
        assert events[0] == ("designer", "thinking", {"message": "analyzing", "request": "test"})
        assert events[1] == ("designer", "action", {"message": "calling LLM"})
        assert events[2] == ("designer", "result", {"message": "done", "assets": 5})
        assert events[3] == ("qa", "error", {"message": "test failed"})

    def test_thread_safe(self):
        import threading

        events: list[tuple[str, str, dict]] = []
        lock = threading.Lock()

        def emit(role: str, phase: str, data: dict) -> None:
            with lock:
                events.append((role, phase, data))

        bus = ThoughtBus(emit)

        def worker():
            for i in range(100):
                bus.think("designer", f"think {i}")

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(events) == 400


class TestQuestioning:
    def test_designer_question_for_vague_request(self):
        q = designer_question("做游戏")
        assert q is not None
        assert q.role == "designer"
        assert len(q.options) > 0

    def test_designer_no_question_for_clear_request(self):
        q = designer_question(
            "做一个3D动作RPG游戏：玩家控制战士在3个关卡中战斗，"
            "有4种武器、6种敌人、升级系统"
        )
        assert q is None

    def test_designer_no_question_for_short_but_clear(self):
        q = designer_question("做一个跳跃游戏")
        assert q is None

    def test_question_to_dict(self):
        q = Question(
            role="designer",
            header="test",
            question="what?",
            options=[QuestionOption("A", "desc A")],
            context={"k": "v"},
        )
        d = q.to_dict()
        assert d["role"] == "designer"
        assert d["header"] == "test"
        assert d["options"][0]["label"] == "A"
        assert d["options"][0]["description"] == "desc A"
        assert d["context"] == {"k": "v"}

    def test_check_question_unknown_role(self):
        assert check_question("unknown", {}) is None

    def test_check_question_artist2d_no_question(self):
        assert check_question("artist2d", {}) is None

    def test_should_ask_not_already_asked(self):
        state = {"user_request": "做游戏"}
        assert should_ask("designer", state) is True

    def test_should_ask_already_asked(self):
        state = {"user_request": "做游戏"}
        already = [{"role": "designer", "answer": "3D RPG"}]
        assert should_ask("designer", state, already_asked=already) is False

    def test_supervisor_question_no_errors(self):
        assert check_question("supervisor", {"errors": []}) is None

    def test_supervisor_question_with_errors(self):
        q = check_question("supervisor", {"errors": ["err1", "err2", "err3"]})
        assert q is not None
        assert q.role == "supervisor"

    def test_artist3d_question_no_art_spec(self):
        q = check_question("artist3d", {"art_spec": {}})
        assert q is not None
        assert q.role == "artist3d"

    def test_artist3d_question_with_art_spec(self):
        q = check_question("artist3d", {"art_spec": {"texture_spec": {"size": 256}}})
        assert q is None
