"""Tests migrated to integration/tui/test_target_edit.py."""

from __future__ import annotations

from fixtures.stage_repos import _clock
import json
from datetime import datetime, timezone
from pathlib import Path
import pytest
import yaml
from typer.testing import CliRunner
from music_rig import inspect_service, patchbay_state, question_service, store
from music_rig.cli import app
from music_rig.models import QuestionStatus, ReconciliationState, TodoStatus
from music_rig.presentation import format_domains_table, format_reconcile_queue_table
from music_rig.reconciliation import service as reconcile_service
from music_rig.reconciliation.types import Capability, VerificationStatus
from music_rig.store import StoreError, load_changes, load_questions, load_todo

def test_tui_reconcile_edit_target_binding_exists():
    from music_rig.tui.screens.reconcile import ReconcileScreen

    keys = {b.key for b in ReconcileScreen.BINDINGS}
    assert "e" in keys

@pytest.mark.asyncio
async def test_tui_target_edit_pair_picker_pilot(fx15):
    """Pilot: reconcile Edit Target sets fixture pair via picker (not prod)."""
    from music_rig.tui.app import RigApp
    from music_rig.tui.pickers import ReferencePickerModal
    from music_rig.tui.screens.reconcile import ReconcileScreen

    question_service.answer_question(
        "Q-080", "half-normal", clock=_clock, render=False
    )
    assert load_questions().question_map()["Q-080"].target.pair is None

    app_inst = RigApp(route="reconcile", object_id="Q-080")
    async with app_inst.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        # Pop home → reconcile may be top; find ReconcileScreen
        reconcile = None
        for s in app_inst.screen_stack:
            if isinstance(s, ReconcileScreen):
                reconcile = s
                break
        assert reconcile is not None
        # Ensure Q-080 selected
        assert reconcile._selected() is not None
        assert reconcile._selected().artifact_id == "Q-080"
        reconcile.action_edit_target()
        await pilot.pause()
        assert isinstance(app_inst.screen, ReferencePickerModal)
        picker = app_inst.screen
        assert picker._row_ids, "expected pair candidates"
        # Simulate single-select dismiss with first pair
        picker.dismiss([picker._row_ids[0]])
        await pilot.pause()

    q = load_questions().question_map()["Q-080"]
    assert q.target is not None
    assert q.target.pair == "1/25"

