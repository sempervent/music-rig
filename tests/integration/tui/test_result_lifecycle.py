"""Stage 19 repair — TUI screen/modal result lifecycle (single-shot dismiss).

Pre-fix failure (documented): AnswerScreen.open_domain(reconcile) then
dismiss() popped ReconcileScreen instead of AnswerScreen, leaving AnswerScreen
with a finished result Future. A later Esc → InvalidStateError on set_result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from textual.app import App

from music_rig.models import QuestionStatus
from music_rig.store import load_questions
from music_rig.tui.app import RigApp
from music_rig.tui.dialogs import ConfirmModal, InputModal, SelectModeModal
from music_rig.tui.screens.answer import AnswerScreen
from music_rig.tui.screens.home import HomeScreen
from music_rig.tui.screens.questions import QuestionsScreen
from music_rig.tui.screens.reconcile import ReconcileScreen
from music_rig.tui.screen_results import AnswerNextAction, AnswerResult


@dataclass
class CallbackProbe:
    """Records result-callback invocations for exactly-once assertions."""

    calls: list[Any] = field(default_factory=list)

    def __call__(self, result: Any) -> None:
        self.calls.append(result)

    @property
    def count(self) -> int:
        return len(self.calls)

    def assert_once(self) -> Any:
        assert self.count == 1, f"expected 1 callback, got {self.count}: {self.calls!r}"
        return self.calls[0]


@pytest.mark.asyncio
async def test_confirm_modal_enter_callback_once():
    probe = CallbackProbe()

    class A(App):
        def on_mount(self) -> None:
            self.push_screen(ConfirmModal("t", "b", confirm_label="OK"), probe)

    app = A()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
    assert probe.assert_once() is True


@pytest.mark.asyncio
async def test_confirm_modal_rapid_enter_y():
    probe = CallbackProbe()

    class A(App):
        def on_mount(self) -> None:
            self.push_screen(ConfirmModal("t", "b"), probe)

    app = A()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("y")
        await pilot.press("enter")
        await pilot.press("y")
        await pilot.pause()
    assert probe.assert_once() is True


@pytest.mark.asyncio
async def test_confirm_modal_rapid_esc_n():
    probe = CallbackProbe()

    class A(App):
        def on_mount(self) -> None:
            self.push_screen(ConfirmModal("t", "b"), probe)

    app = A()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.press("escape")
        await pilot.press("n")
        await pilot.pause()
    assert probe.assert_once() is False


@pytest.mark.asyncio
async def test_confirm_modal_click_then_enter():
    probe = CallbackProbe()

    class A(App):
        def on_mount(self) -> None:
            self.push_screen(ConfirmModal("t", "b"), probe)

    app = A()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.click("#confirm")
        await pilot.press("enter")
        await pilot.pause()
    assert probe.assert_once() is True


@pytest.mark.asyncio
async def test_select_mode_modal_keyboard_and_numeric_once():
    for keys, expected in (
        (["enter"], "normal"),
        (["2"], "half-normal"),
        (["escape"], None),
    ):
        probe = CallbackProbe()

        class A(App):
            def on_mount(self) -> None:
                self.push_screen(SelectModeModal("PB-B 1/25", "unknown"), probe)

        app = A()
        async with app.run_test(size=(80, 28)) as pilot:
            await pilot.pause()
            for k in keys:
                await pilot.press(k)
            await pilot.press("enter")
            await pilot.pause()
        assert probe.assert_once() == expected


@pytest.mark.asyncio
async def test_input_modal_submit_once():
    probe = CallbackProbe()

    class A(App):
        def on_mount(self) -> None:
            self.push_screen(InputModal("Name", default="x"), probe)

    app = A()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.press("enter")
        await pilot.pause()
    assert probe.assert_once() == "x"


@pytest.mark.filterwarnings("error")
@pytest.mark.asyncio
async def test_answer_resolve_later_callback_once(tui_fx):
    """Human-failure regression: Answer & Resolve → Later must not InvalidStateError."""
    app = RigApp(route="question", object_id="Q-001")
    answer_callbacks: list[AnswerResult] = []

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, QuestionsScreen)
        await pilot.press("a")
        await pilot.pause()
        assert isinstance(app.screen, AnswerScreen)
        ans = app.screen
        assert isinstance(ans, AnswerScreen)
        rc = ans._result_callbacks[-1]
        orig_cb = rc.callback

        def wrapped(result: AnswerResult) -> None:
            answer_callbacks.append(result)
            if orig_cb is not None:
                orig_cb(result)

        rc.callback = wrapped  # type: ignore[assignment]

        await pilot.press(*list("later-path-answer"))
        await pilot.click("#btn-resolve")
        await pilot.pause()
        await pilot.press("enter")  # confirm Answer & Resolve
        await pilot.pause()
        await pilot.press("escape")  # Later
        for _ in range(20):
            await pilot.pause()
            if isinstance(app.screen, QuestionsScreen) and not any(
                isinstance(s, AnswerScreen) for s in app.screen_stack
            ):
                break
        assert not any(isinstance(s, AnswerScreen) for s in app.screen_stack)
        # Esc on the post-answer modal must not also pop Questions in the same turn.
        # Allow a brief settle; if we landed on Home, that is a regression.
        assert isinstance(app.screen, QuestionsScreen), type(app.screen).__name__

    assert len(answer_callbacks) == 1
    result = answer_callbacks[0]
    assert result.outcome.value == "SUCCESS"
    assert result.question_id == "Q-001"
    assert result.next_action is AnswerNextAction.NONE

    q = load_questions(tui_fx["questions"]).question_map()["Q-001"]
    assert q.status == QuestionStatus.RESOLVED
    assert q.answer == "later-path-answer"
    assert q.resolved_at is not None
    assert q.reconciled_at is None
    assert q.verification_result is None


@pytest.mark.filterwarnings("error")
@pytest.mark.asyncio
async def test_answer_resolve_reconcile_now_opens_once(tui_fx):
    """Reconcile Now: AnswerScreen dismisses first; parent opens Reconcile once."""
    app = RigApp(route="question", object_id="Q-002")
    answer_callbacks: list[AnswerResult] = []

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        ans = app.screen
        assert isinstance(ans, AnswerScreen)
        rc = ans._result_callbacks[-1]
        orig_cb = rc.callback

        def wrapped(result: AnswerResult) -> None:
            answer_callbacks.append(result)
            if orig_cb is not None:
                orig_cb(result)

        rc.callback = wrapped  # type: ignore[assignment]

        await pilot.press(*list("reconcile-now-answer"))
        await pilot.click("#btn-resolve")
        await pilot.pause()
        await pilot.press("enter")  # confirm resolve
        await pilot.pause()
        await pilot.press("enter")  # Reconcile Now
        await pilot.pause()

        assert len(answer_callbacks) == 1
        assert answer_callbacks[0].next_action is AnswerNextAction.RECONCILE
        assert not any(isinstance(s, AnswerScreen) for s in app.screen_stack)
        recon_screens = [s for s in app.screen_stack if isinstance(s, ReconcileScreen)]
        assert len(recon_screens) == 1
        assert isinstance(app.screen, ReconcileScreen)

    q = load_questions(tui_fx["questions"]).question_map()["Q-002"]
    assert q.status == QuestionStatus.RESOLVED
    assert q.answer == "reconcile-now-answer"
    assert q.reconciled_at is None


@pytest.mark.filterwarnings("error::RuntimeWarning")
@pytest.mark.asyncio
async def test_combined_answer_patchbay_stress(tui_fx):
    """Mixed navigation stress with warnings-as-errors."""
    app = RigApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, HomeScreen)
        for i, qid in enumerate(("Q-001", "Q-002")):
            app.open_domain("question", qid)
            await pilot.pause()
            await pilot.press("a")
            await pilot.pause()
            assert isinstance(app.screen, AnswerScreen)
            await pilot.press("escape")  # insert → normal
            await pilot.press("escape")  # cancel
            await pilot.pause()
            await pilot.press("a")
            await pilot.pause()
            await pilot.press(*list(f"draft-{i}"))
            await pilot.press("ctrl+s")
            await pilot.pause()
            # reopen for resolve (draft already saved)
            await pilot.press("a")
            await pilot.pause()
            await pilot.click("#btn-resolve")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            if i % 2 == 0:
                await pilot.press("escape")  # Later
            else:
                await pilot.press("enter")  # Reconcile Now
                await pilot.pause()
                if isinstance(app.screen, ReconcileScreen):
                    await pilot.press("escape")
            await pilot.pause()
            for _ in range(5):
                if isinstance(app.screen, QuestionsScreen):
                    break
                await pilot.press("escape")
                await pilot.pause()
            app.open_domain("patchbay", "PB-B")
            await pilot.pause()
            await pilot.press("e")
            await pilot.pause()
            if isinstance(app.screen, SelectModeModal):
                await pilot.press("escape")
                await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()


@pytest.mark.asyncio
async def test_patchbay_select_mode_modal_result_once(tui_fx):
    app = RigApp(route="patchbay", object_id="PB-B")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        top = app.screen
        if isinstance(top, SelectModeModal):
            probe_calls: list[Any] = []
            rc = top._result_callbacks[-1]
            orig = rc.callback

            def wrap(r: Any) -> None:
                probe_calls.append(r)
                if orig:
                    orig(r)

            rc.callback = wrap  # type: ignore[assignment]
            await pilot.press("enter")
            await pilot.pause()
            assert len(probe_calls) == 1
