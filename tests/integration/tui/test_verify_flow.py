"""Tests migrated to integration/tui/test_verify_flow.py."""

from __future__ import annotations

import pytest

from music_rig import (
    question_service,
)
from music_rig.models import (
    VerificationOutcome,
)


@pytest.mark.asyncio
async def test_tui_verify_failed_binding(fx17):
    from music_rig.tui.app import RigApp
    from music_rig.tui.screens.verify import VerifyScreen

    app_tui = RigApp()
    async with app_tui.run_test() as pilot:
        app_tui.push_screen(VerifyScreen())
        await pilot.pause()
        assert isinstance(app_tui.screen, VerifyScreen)
        # Select Q-171 if present
        screen: VerifyScreen = app_tui.screen
        screen.action_refresh()
        await pilot.pause()
        ids = [i.question_id for i in screen._items]
        if "Q-171" in ids:
            idx = ids.index("Q-171")
            screen.query_one("#list-table").move_cursor(row=idx)
            await pilot.pause()
            # Trigger fail confirm then accept
            from music_rig.tui.dialogs import ConfirmModal

            screen.action_fail()
            await pilot.pause()
            if isinstance(app_tui.screen, ConfirmModal):
                await pilot.press("enter")
                await pilot.pause()
            q = question_service.get_question("Q-171")
            assert q.verification_result is not None
            assert q.verification_result.outcome == VerificationOutcome.FAILED_TEST
