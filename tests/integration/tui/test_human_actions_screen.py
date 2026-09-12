"""TUI Human actions screen — list pending navigation smoke."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import yaml

from music_rig.models import (
    AnswerActor,
    HumanActionRequest,
    HumanActionType,
    OpenQuestion,
    QuestionStatus,
    QuestionVerification,
)
from music_rig.tui.app import RigApp
from music_rig.tui.screens.human_actions import HumanActionsScreen


@pytest.mark.asyncio
async def test_human_actions_screen_lists_pending(tmp_path, monkeypatch):
    from music_rig import store as store_mod

    har = tmp_path / "human-actions.yaml"
    qpath = tmp_path / "open-questions.yaml"
    todo_path = tmp_path / "todo.yaml"
    q = OpenQuestion(
        id="Q-999",
        question="Modes?",
        area="Test",
        status=QuestionStatus.OPEN,
        answer="draft",
        answer_actor=AnswerActor.BOT,
        verification=QuestionVerification(kind="PATCHBAY_MODE", answer_type="TEXT", prompt="p"),
    )
    qpath.write_text(
        yaml.safe_dump({"questions": [q.model_dump(mode="json")]}, sort_keys=False),
        encoding="utf-8",
    )
    todo_path.write_text("next_session: []\ntasks: []\n", encoding="utf-8")
    req = HumanActionRequest(
        id="HAR-001",
        action_type=HumanActionType.QUESTION_ANSWER,
        artifact_id="Q-999",
        prompt="Modes?",
        proposed_value="all normal",
        explanation="bot prep",
        created_at=datetime(2026, 9, 12, tzinfo=UTC),
    )
    har.write_text(
        yaml.safe_dump(
            {"items": [req.model_dump(mode="json")]},
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(store_mod, "HUMAN_ACTIONS_PATH", har)
    monkeypatch.setattr(store_mod, "QUESTIONS_PATH", qpath)
    monkeypatch.setattr(store_mod, "TODO_PATH", todo_path)

    app = RigApp(route="human")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, HumanActionsScreen)
        table = app.screen.query_one("#list-table")
        assert table.row_count >= 1
        detail = str(app.screen.query_one("#detail").content)
        assert "HAR-001" in detail or "Q-999" in detail
