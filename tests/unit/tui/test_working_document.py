"""Tests migrated to unit/tui/test_working_document.py."""

from __future__ import annotations

from music_rig.tui.editable_domains import registry
from music_rig.tui.modes import parse_command
from music_rig.tui.working import WorkingDocument


def test_working_document_undo_redo():
    doc = WorkingDocument({"a": 1})
    doc.stage("x", 1)
    doc.stage("y", 2)
    assert doc.undo()
    assert "y" not in doc.mutations
    assert doc.redo()
    assert doc.get("y") == 2


def test_parse_command_aliases():
    assert parse_command(":w")[0] == "write"
    assert parse_command(":q!")[0] == "quit!"
    assert parse_command(":wq")[0] == "wq"


def test_registry_every_editable_has_adapter_and_coverage():
    domains = registry.editable_domains_with_adapters()
    for key in domains:
        cov = registry.coverage_for(key)
        assert cov is not None, f"missing coverage marker for {key}"
        assert cov["view"] == "yes"
        assert cov["round_trip"] in {"yes", "partial"}
        assert cov["vim_modal"] == "yes"
        if key == "patchbay":
            continue
        assert registry.get_adapter(key) is not None, f"missing adapter for {key}"


def test_debug_format_error():
    from music_rig.tui.debug import format_error, is_debug, set_debug

    set_debug(False)
    assert "boom" in format_error(RuntimeError("boom"))
    set_debug(True)
    assert is_debug()
    assert "boom" in format_error(RuntimeError("boom"))
    set_debug(False)
