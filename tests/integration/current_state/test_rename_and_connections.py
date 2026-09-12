"""Tests migrated to integration/current_state/test_rename_and_connections.py."""

from __future__ import annotations

import yaml

from music_rig import question_service, rename_service
from music_rig.patchbay_state import load_raw, propose_set_connection, save_raw


def test_update_question_fields(iso):
    updated = question_service.update_question_fields(
        "Q-100", notes="edited", area="Docs", render=False
    )
    assert updated.notes == "edited"
    assert updated.area == "Docs"
    assert updated.status.value == "OPEN"


def test_propose_set_connection(iso, monkeypatch):
    from music_rig import patchbay_state

    monkeypatch.setattr(patchbay_state, "PATCHBAYS_PATH", iso["patchbays"])
    preview, data = propose_set_connection(
        "PB-Z", "1", upper_connection="NEW-U", lower_connection="NEW-L"
    )
    assert preview.changed
    save_raw(data, iso["patchbays"])
    raw = load_raw(iso["patchbays"])
    jacks = raw["patchbays"]["PB-Z"]["jacks"]
    assert jacks[1]["connection"] == "NEW-U"
    assert jacks[25]["connection"] == "NEW-L"


def test_rename_deferred_domains():
    preview = rename_service.analyze_rename("question", "Q-100", "Q-200")
    assert not preview.ok
    assert "deferred" in preview.errors[0].lower() or "Deferred" in preview.errors[0]


def test_rename_gear_ok(iso):
    preview = rename_service.analyze_rename("gear", "iso-gear", "iso-gear-2")
    assert preview.ok
    applied = rename_service.apply_rename("gear", "iso-gear", "iso-gear-2")
    assert applied.ok
    inv = yaml.safe_load(iso["inventory"].read_text(encoding="utf-8"))
    assert inv["items"][0]["id"] == "iso-gear-2"


def test_working_record_stages(iso):
    from music_rig.tui.editable_domains.questions import QuestionsEditableAdapter

    adapter = QuestionsEditableAdapter()
    working = adapter.create_working("Q-100")
    working.stage("notes", "x")
    assert working.is_dirty
    rows = adapter.diff(working)
    assert rows
    working.stage("notes", "n")  # back to baseline
    assert not working.is_dirty
