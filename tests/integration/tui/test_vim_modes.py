"""Tests migrated to integration/tui/test_vim_modes.py."""

from __future__ import annotations

import pytest

from music_rig.tui.app import RigApp
from music_rig.tui.modes import EditorMode
from music_rig.tui.save_outcome import SaveOutcome


@pytest.mark.asyncio
async def test_vim_navigation_and_modes(tui_fx):
    app = RigApp(route="question")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        banner = str(app.screen.query_one("#mode-banner").content)
        assert "NORMAL" in banner
        await pilot.press("j")
        await pilot.press("k")
        await pilot.press("G")
        await pilot.pause()
        await pilot.press("g")
        await pilot.press("g")
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        from music_rig.tui.screens.answer import AnswerScreen

        assert isinstance(app.screen, AnswerScreen)
        assert "INSERT" in str(app.screen.query_one("#mode-banner").content)
        await pilot.press("j")
        assert "j" in app.screen.query_one("#answer-input").text
        await pilot.press("escape")
        await pilot.pause()
        assert "NORMAL" in str(app.screen.query_one("#mode-banner").content)


@pytest.mark.asyncio
async def test_vim_command_q_refuses_dirty_qbang_discards(tui_fx):
    before = tui_fx["patchbays"].read_text(encoding="utf-8")
    app = RigApp(route="patchbay", object_id="PB-B")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()
        await pilot.press("colon")
        await pilot.pause()
        from music_rig.tui.dialogs import CommandLineModal

        assert isinstance(app.screen, CommandLineModal)
        app.screen.query_one("#modal-input").value = ":q"
        await pilot.press("enter")
        await pilot.pause()
        from music_rig.tui.screens.patchbays import PatchbayEditorScreen

        assert isinstance(app.screen, PatchbayEditorScreen)
        await pilot.press("colon")
        await pilot.pause()
        app.screen.query_one("#modal-input").value = ":q!"
        await pilot.press("enter")
        await pilot.pause()
    assert tui_fx["patchbays"].read_text(encoding="utf-8") == before


@pytest.mark.asyncio
async def test_vim_undo_staged(tui_fx):
    app = RigApp(route="patchbay", object_id="PB-B")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()
        assert "unsaved" in str(app.screen.query_one("#dirty-label").content)
        await pilot.press("u")
        await pilot.pause()
        dirty = str(app.screen.query_one("#dirty-label").content)
        assert "unsaved" not in dirty


def test_save_outcome_enum():
    assert SaveOutcome.SUCCESS.ok
    assert not SaveOutcome.FAILED.ok


def test_ctrl_s_binding_has_priority():
    from music_rig.tui.editable_domains.todo import TodoEditableAdapter
    from music_rig.tui.forms import RecordEditScreen

    bindings = RecordEditScreen(TodoEditableAdapter(), "RIG-001").BINDINGS
    ctrl_s = [b for b in bindings if getattr(b, "key", None) == "ctrl+s"]
    assert ctrl_s and ctrl_s[0].priority is True


@pytest.mark.asyncio
async def test_mode_banner_on_editable(tui_fx):
    app = RigApp(route="todo")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        banner = str(app.screen.query_one("#mode-banner").content)
        assert EditorMode.NORMAL.value in banner
