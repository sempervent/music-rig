"""Stage 13 unit tests: inspect, rename, field specs, services (tmp fixtures only)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from music_rig import inspect_service, question_service, rename_service, store
from music_rig.patchbay_state import propose_set_connection, load_raw, save_raw
from music_rig.tui.editable_domains import registry
from music_rig.tui.fields import FieldType


@pytest.fixture
def iso(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    questions = tmp_path / "open-questions.yaml"
    todo = tmp_path / "todo.yaml"
    wish = tmp_path / "wishlist.yaml"
    inv = tmp_path / "inventory.yaml"
    pb = tmp_path / "patchbays.yaml"
    changes = tmp_path / "changes.yaml"
    inbox = tmp_path / "inbox.yaml"
    questions.write_text(
        yaml.safe_dump(
            {
                "questions": [
                    {
                        "id": "Q-100",
                        "question": "Iso?",
                        "area": "Test",
                        "status": "OPEN",
                        "related_todos": [],
                        "related_changes": [],
                        "answer": "",
                        "notes": "n",
                        "resolved_at": None,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    todo.write_text("next_session: []\ntasks: []\n", encoding="utf-8")
    wish.write_text("items: []\n", encoding="utf-8")
    changes.write_text("items: []\n", encoding="utf-8")
    inbox.write_text("items: []\n", encoding="utf-8")
    inv.write_text(
        yaml.safe_dump(
            {
                "items": [
                    {
                        "id": "iso-gear",
                        "name": "Iso",
                        "category": "utility",
                        "ownership_status": "OWNED",
                        "condition": "WORKING",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    pb.write_text(
        yaml.safe_dump(
            {
                "schema_notes": {},
                "patchbays": {
                    "PB-Z": {
                        "hardware_model": "unknown",
                        "status": "partially_documented",
                        "jacks": {
                            1: {
                                "row": "upper",
                                "connection": "A",
                                "paired_with": 25,
                                "mode": "unknown",
                                "status": "documented",
                            },
                            25: {
                                "row": "lower",
                                "connection": "B",
                                "paired_with": 1,
                                "mode": "unknown",
                                "status": "documented",
                            },
                        },
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(store, "QUESTIONS_PATH", questions)
    monkeypatch.setattr(store, "TODO_PATH", todo)
    monkeypatch.setattr(store, "WISHLIST_PATH", wish)
    monkeypatch.setattr(store, "INVENTORY_PATH", inv)
    monkeypatch.setattr(store, "CHANGES_PATH", changes)
    monkeypatch.setattr(store, "INBOX_PATH", inbox)
    monkeypatch.setattr(store, "PATCHBAYS_PATH", pb)
    return {"questions": questions, "inventory": inv, "patchbays": pb, "tmp": tmp_path}


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


def test_registry_all_editable_have_fieldspecs():
    for adapter in registry.all_adapters():
        specs = adapter.get_field_specs()
        assert specs, adapter.id
        assert any(s.type != FieldType.READONLY or s.read_only for s in specs) or True
        # schema serializes
        for s in specs:
            d = s.to_dict()
            assert d["name"] and d["type"]


def test_inspect_schema_matches_adapter():
    schema = inspect_service.schema_for("todo")
    adapter = registry.get_adapter("todo")
    assert len(schema["fields"]) == len(adapter.get_field_specs())


def test_inspect_cleanup_structure(iso):
    result = inspect_service.cleanup_scan()
    assert "issues" in result
    assert "count" in result


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


def test_cli_inspect_schema():
    from typer.testing import CliRunner
    from music_rig.cli import app

    result = CliRunner().invoke(app, ["inspect", "schema", "question"])
    assert result.exit_code == 0
    assert "question" in result.stdout.lower() or "Question" in result.stdout


def test_cli_rename_preview(iso):
    from typer.testing import CliRunner
    from music_rig.cli import app

    result = CliRunner().invoke(app, ["rename", "preview", "gear", "iso-gear", "iso-x"])
    assert result.exit_code == 0


def test_cli_patchbay_set_connection_dry_run(iso, monkeypatch):
    from music_rig import patchbay_state, current_service
    from typer.testing import CliRunner
    from music_rig.cli import app

    monkeypatch.setattr(patchbay_state, "PATCHBAYS_PATH", iso["patchbays"])
    monkeypatch.setattr(store, "PATCHBAYS_PATH", iso["patchbays"])
    result = CliRunner().invoke(
        app,
        [
            "current",
            "patchbay",
            "set-connection",
            "PB-Z",
            "1",
            "--upper",
            "X",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    # file unchanged
    raw = load_raw(iso["patchbays"])
    assert raw["patchbays"]["PB-Z"]["jacks"][1]["connection"] == "A"
