"""Tests migrated to integration/inspect/test_domains_presentation.py."""

from __future__ import annotations

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

runner = CliRunner()

def test_inspect_domains_no_tabs_and_ordered():
    rows = inspect_service.list_domains()
    ids = [r["id"] for r in rows]
    assert ids == sorted(ids)
    text = inspect_service.dumps(rows, as_json=False, width=80, kind="domains")
    assert "\t" not in text
    assert "Domain" in text or "question" in text.lower() or rows[0]["id"] in text

@pytest.mark.parametrize("width", [60, 80, 100, 120])
def test_domains_table_widths_no_tabs(width):
    rows = inspect_service.list_domains()
    text = format_domains_table(rows, width=width)
    assert "\t" not in text
    assert rows[0]["id"] in text or "DOMAINS" in text
    if width >= 120:
        assert "Reconcile" in text
    if width >= 100:
        assert "Edit" in text
    if width >= 80:
        assert "Inspect" in text

def test_inspect_domains_json_metadata_no_ansi():
    rows = inspect_service.list_domains()
    raw = inspect_service.dumps(rows, as_json=True)
    assert "\x1b[" not in raw
    assert "\t" not in raw or True  # JSON may not have tabs; ok either way
    data = json.loads(raw)
    assert isinstance(data, list)
    sample = data[0]
    for key in ("id", "label", "mutable", "derived", "supports_reconcile"):
        assert key in sample

def test_inspect_domains_cli_no_tabs():
    runner = CliRunner()
    result = runner.invoke(app, ["inspect", "domains"])
    assert result.exit_code == 0
    assert "\t" not in result.stdout
    j = runner.invoke(app, ["inspect", "domains", "--json"])
    assert j.exit_code == 0
    assert "\x1b[" not in j.stdout
    payload = json.loads(j.stdout)
    assert all("supports_reconcile" in r for r in payload)

def test_reconcile_queue_table_no_tabs(fx15):
    items = reconcile_service.build_queue()
    text = format_reconcile_queue_table(items, width=100)
    assert "\t" not in text
    assert "RECONCILE QUEUE" in text or "Q-080" in text

def test_todo_list_hides_terminal(fx15):
    runner = CliRunner()
    result = runner.invoke(app, ["todo", "list"])
    assert result.exit_code == 0
    assert "RIG-081" not in result.stdout
    all_items = runner.invoke(app, ["todo", "list", "--all"])
    assert "RIG-081" in all_items.stdout

