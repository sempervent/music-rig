"""Tests migrated to integration/inspect/test_inspect_cli.py."""

from __future__ import annotations

from music_rig import inspect_service, store
from music_rig.patchbay_state import load_raw
from music_rig.tui.editable_domains import registry


def test_inspect_schema_matches_adapter():
    schema = inspect_service.schema_for("todo")
    adapter = registry.get_adapter("todo")
    assert len(schema["fields"]) == len(adapter.get_field_specs())


def test_inspect_cleanup_structure(iso):
    result = inspect_service.cleanup_scan()
    assert "issues" in result
    assert "count" in result


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
    from typer.testing import CliRunner

    from music_rig import patchbay_state
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
