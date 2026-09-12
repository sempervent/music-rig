"""Tests migrated to integration/tui/test_answer_flow.py."""

from __future__ import annotations

import pytest

from music_rig.models import QuestionStatus
from music_rig.store import load_questions
from music_rig.tui.app import RigApp
from music_rig.tui.screens.answer import AnswerScreen


@pytest.mark.asyncio
async def test_tui_save_draft(fx19):
    app_ui = RigApp(route="question", object_id="Q-191")
    async with app_ui.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        assert isinstance(app_ui.screen, AnswerScreen)
        await pilot.press(*list("draft-from-tui"))
        await pilot.press("ctrl+s")
        await pilot.pause()
    q = load_questions(fx19["questions"]).question_map()["Q-191"]
    assert q.answer == "draft-from-tui"
    assert q.status == QuestionStatus.OPEN
    assert q.resolved_at is None
    assert q.verification_result is None


@pytest.mark.asyncio
async def test_tui_answer_and_resolve(fx19):
    app_ui = RigApp(route="question", object_id="Q-191")
    async with app_ui.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        await pilot.press(*list("final-from-tui"))
        await pilot.click("#btn-resolve")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
    q = load_questions(fx19["questions"]).question_map()["Q-191"]
    assert q.status == QuestionStatus.RESOLVED
    assert q.answer == "final-from-tui"
    assert q.resolved_at is not None
    assert q.reconciled_at is None
    assert q.verification_result is None
