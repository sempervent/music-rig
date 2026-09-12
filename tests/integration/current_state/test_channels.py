"""Tests migrated to integration/current_state/test_channels.py."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import pytest
import yaml
from typer.testing import CliRunner
from music_rig import channel_state, question_service, todo_service
from music_rig.channel_state import propose_set_source, validate_channel_map
from music_rig.cli import app
from music_rig.models import AnswerState, QuestionStatus, ReconciliationState, TodoStatus
from music_rig.reconciliation import service as reconcile_service
from music_rig.store import StoreError, load_questions, load_todo
from music_rig.tui.app import RigApp
from music_rig.tui.screens.answer import AnswerScreen

def test_channel_set_source_status_current(fx19):
    preview, data = propose_set_source("alesis", 1, "B send", path=fx19["channels"])
    assert preview.after["source"] == "B send"
    assert preview.after["status"] == "CURRENT"
    assert validate_channel_map(data) == []

def test_channel_clear_source_unassigned(fx19):
    _, data = propose_set_source("alesis", 1, "B send", path=fx19["channels"])
    channel_state.save_raw(data, path=fx19["channels"])
    preview, data2 = channel_state.clear_source("alesis", 1, path=fx19["channels"])
    assert preview.after["source"] is None
    assert preview.after["status"] == "UNASSIGNED"
    assert validate_channel_map(data2) == []

def test_channel_contradiction_fails_validate_and_cleanup(fx19):
    bad = {
        "tascam": {1: {"type": "line", "status": "UNASSIGNED", "source": "leak"}},
        "alesis": {1: {"status": "CURRENT", "source": None}},
    }
    errs = validate_channel_map(bad)
    assert any("source/status" in e for e in errs)
    fx19["channels"].write_text(yaml.safe_dump(bad), encoding="utf-8")
    issues = reconcile_service.cleanup_reconciliation_issues(
        questions_path=fx19["questions"],
        todo_path=fx19["todo"],
    )
    codes = {i["code"] for i in issues}
    assert "channel_source_status_contradiction" in codes

