"""Store load/save error-path coverage on temp files."""

from __future__ import annotations

from pathlib import Path

import pytest

from music_rig import store
from music_rig.models import TodoDocument
from music_rig.store import StoreError, write_text_files


def test_write_text_files_empty_and_cleanup(tmp_path: Path, monkeypatch):
    write_text_files([])
    target = tmp_path / "out.yaml"
    # force failure after staging by making replace explode
    payloads = [(target, "a: 1\n")]
    real_replace = Path.replace

    def boom(self, other):
        raise OSError("boom")

    monkeypatch.setattr(Path, "replace", boom)
    with pytest.raises(OSError):
        write_text_files(payloads)
    # temp cleaned up
    assert not list(tmp_path.glob("*.tmp"))
    monkeypatch.setattr(Path, "replace", real_replace)
    write_text_files([(target, "a: 1\n")])
    assert target.read_text(encoding="utf-8") == "a: 1\n"


def test_load_mapping_errors(tmp_path: Path):
    missing = tmp_path / "nope.yaml"
    with pytest.raises(StoreError, match="Missing"):
        store._load_mapping(missing, "TODO")

    bad = tmp_path / "bad.yaml"
    bad.write_text(": [\n", encoding="utf-8")
    with pytest.raises(StoreError, match="Invalid YAML"):
        store._load_mapping(bad, "TODO")

    not_map = tmp_path / "list.yaml"
    not_map.write_text("- 1\n", encoding="utf-8")
    with pytest.raises(StoreError, match="mapping"):
        store._load_mapping(not_map, "TODO")


def test_load_save_schema_failures_and_missing_optional(tmp_path: Path):
    todo = tmp_path / "todo.yaml"
    todo.write_text("next_session: []\ntasks: [{id: bad}]\n", encoding="utf-8")
    with pytest.raises(StoreError, match="TODO schema"):
        store.load_todo(todo)

    wish = tmp_path / "wish.yaml"
    wish.write_text("items: [{item: x, status: NOPE}]\n", encoding="utf-8")
    with pytest.raises(StoreError, match="Wishlist schema"):
        store.load_wishlist(wish)

    inbox = tmp_path / "inbox.yaml"
    assert store.load_inbox(inbox).items == []
    inbox.write_text("items: [{id: 1}]\n", encoding="utf-8")
    with pytest.raises(StoreError, match="Inbox schema"):
        store.load_inbox(inbox)

    changes = tmp_path / "changes.yaml"
    assert store.load_changes(changes).items == []
    changes.write_text("items: [{id: CHG-1}]\n", encoding="utf-8")
    with pytest.raises(StoreError, match="Changes schema"):
        store.load_changes(changes)

    questions = tmp_path / "q.yaml"
    questions.write_text("questions: [{id: Q-1}]\n", encoding="utf-8")
    with pytest.raises(StoreError, match="Open questions schema"):
        store.load_questions(questions)

    for name, loader, label in [
        ("routing.yaml", store.load_routing, "Routing"),
        ("inventory.yaml", store.load_inventory, "Inventory"),
        ("midi.yaml", store.load_midi, "MIDI"),
        ("controllers.yaml", store.load_controllers, "Controllers"),
        ("ableton.yaml", store.load_ableton, "Ableton"),
        ("performance.yaml", store.load_performance, "Performance"),
        ("control-surfaces.yaml", store.load_control_surfaces, "Control surfaces"),
        ("backups.yaml", store.load_backups, "Backups"),
    ]:
        path = tmp_path / name
        path.write_text("not_valid: true\nitems: bad\n", encoding="utf-8")
        # Some docs accept odd shapes; force clearly invalid list root via rewrite
        path.write_text("[]\n", encoding="utf-8")
        with pytest.raises(StoreError):
            loader(path)


def test_save_roundtrips_minimal_todo(tmp_path: Path):
    path = tmp_path / "todo.yaml"
    doc = TodoDocument(next_session=[], tasks=[])
    store.save_todo(doc, path)
    assert store.load_todo(path).tasks == []


def test_list_sessions_missing_and_load_error(tmp_path: Path):
    assert store.list_session_files(tmp_path / "missing") == []
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    bad = sessions / "SES-001.yaml"
    bad.write_text("[]\n", encoding="utf-8")
    with pytest.raises(StoreError, match="mapping|Session"):
        store.load_session("SES-001", sessions)
