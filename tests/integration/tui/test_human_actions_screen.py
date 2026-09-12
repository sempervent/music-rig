"""TUI Human actions screen — list pending navigation smoke."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import yaml

from music_rig.models import HumanActionRequest, HumanActionType
from music_rig.tui.app import RigApp
from music_rig.tui.screens.human_actions import HumanActionsScreen


@pytest.mark.asyncio
async def test_human_actions_screen_lists_pending(tmp_path, monkeypatch):
    from music_rig import store as store_mod

    har = tmp_path / "human-actions.yaml"
    req = HumanActionRequest(
        id="HAR-001",
        action_type=HumanActionType.QUESTION_ANSWER,
        artifact_id="Q-008",
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

    app = RigApp(route="human")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, HumanActionsScreen)
        table = app.screen.query_one("#list-table")
        assert table.row_count >= 1
        detail = str(app.screen.query_one("#detail").content)
        assert "HAR-001" in detail or "Q-008" in detail
