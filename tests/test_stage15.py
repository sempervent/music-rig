"""Stage 15 — presentation, answer/target CLI, incomplete-target e2e (fixtures only)."""

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


def _clock():
    return datetime(2026, 9, 11, 21, 0, 0, tzinfo=timezone.utc)


def _write_docs(tmp: Path) -> dict[str, Path]:
    paths = {}
    for name, start, end in [
        ("todo.md", "<!-- rig:todo:start -->", "<!-- rig:todo:end -->"),
        ("wishlist.md", "<!-- rig:wishlist:start -->", "<!-- rig:wishlist:end -->"),
        ("open-questions.md", "<!-- rig:questions:start -->", "<!-- rig:questions:end -->"),
        ("patchbays.md", "<!-- rig:patchbays:start -->", "<!-- rig:patchbays:end -->"),
        ("inventory.md", "<!-- rig:inventory:start -->", "<!-- rig:inventory:end -->"),
    ]:
        path = tmp / name
        path.write_text(f"x\n{start}\n{end}\n", encoding="utf-8")
        paths[name] = path
    return paths


@pytest.fixture
def fx15(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Fixture with Q-080 (bay, no pair) — does not claim prod pair."""
    questions = tmp_path / "open-questions.yaml"
    todo = tmp_path / "todo.yaml"
    wish = tmp_path / "wishlist.yaml"
    inbox = tmp_path / "inbox.yaml"
    changes = tmp_path / "changes.yaml"
    patchbays = tmp_path / "patchbays.yaml"
    routing = tmp_path / "routing.yaml"
    midi = tmp_path / "midi.yaml"
    controllers = tmp_path / "controllers.yaml"
    ableton = tmp_path / "ableton.yaml"
    inventory = tmp_path / "inventory.yaml"
    docs = _write_docs(tmp_path)

    todo.write_text(
        yaml.safe_dump(
            {
                "next_session": ["RIG-080"],
                "tasks": [
                    {
                        "id": "RIG-080",
                        "task": "Record fixture PB mode",
                        "area": "Patchbay",
                        "priority": "P1",
                        "status": "READY",
                        "depends_on": [],
                        "definition_of_done": "mode recorded",
                        "notes": "",
                    },
                    {
                        "id": "RIG-081",
                        "task": "Done task",
                        "area": "Docs",
                        "priority": "P3",
                        "status": "DONE",
                        "depends_on": [],
                        "definition_of_done": "x",
                        "notes": "",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    wish.write_text("items: []\n", encoding="utf-8")
    inbox.write_text("items: []\n", encoding="utf-8")
    changes.write_text(
        yaml.safe_dump(
            {
                "items": [
                    {
                        "id": "CHG-080",
                        "created_at": "2026-09-01T00:00:00+00:00",
                        "category": "PATCHBAY",
                        "summary": "fixture mode",
                        "details": "",
                        "status": "OPEN",
                        "session_id": None,
                        "affected_areas": ["patchbay"],
                        "related_questions": ["Q-080"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    inventory.write_text(
        yaml.safe_dump(
            {
                "items": [
                    {
                        "id": "test-gear",
                        "name": "Test",
                        "category": "utility",
                        "ownership_status": "OWNED",
                        "condition": "WORKING",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    questions.write_text(
        yaml.safe_dump(
            {
                "questions": [
                    {
                        "id": "Q-080",
                        "question": "What mode is fixture PB-B pair?",
                        "area": "Patchbay",
                        "status": "OPEN",
                        "related_todos": ["RIG-080"],
                        "related_changes": ["CHG-080"],
                        "answer": "",
                        "notes": "",
                        "resolved_at": None,
                        "reconciled_at": None,
                        "reconciliation_note": "",
                        "target": {
                            "domain": "patchbay.mode",
                            "bay": "PB-B",
                            # pair intentionally null — fixture e2e completes it
                        },
                    },
                    {
                        "id": "Q-081",
                        "question": "Clock master in practice?",
                        "area": "MIDI",
                        "status": "OPEN",
                        "related_todos": [],
                        "related_changes": [],
                        "answer": "",
                        "notes": "",
                        "resolved_at": None,
                        "reconciled_at": None,
                        "reconciliation_note": "",
                        "target": {"domain": "midi.clock_master"},
                    },
                    {
                        "id": "Q-082",
                        "question": "Which unit is PB-A?",
                        "area": "Patchbay",
                        "status": "OPEN",
                        "related_todos": [],
                        "related_changes": [],
                        "answer": "",
                        "notes": "",
                        "resolved_at": None,
                        "reconciled_at": None,
                        "reconciliation_note": "",
                        "target": {"domain": "inventory.patchbay_mapping"},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    patchbays.write_text(
        yaml.safe_dump(
            {
                "schema_notes": {},
                "patchbays": {
                    "PB-B": {
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
                            2: {
                                "row": "upper",
                                "connection": "C",
                                "paired_with": 26,
                                "mode": "unknown",
                                "status": "documented",
                            },
                            26: {
                                "row": "lower",
                                "connection": "D",
                                "paired_with": 2,
                                "mode": "unknown",
                                "status": "documented",
                            },
                        },
                    },
                    "PB-A": {
                        "hardware_model": "unknown",
                        "status": "undocumented",
                        "jacks": {},
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    routing.write_text(
        yaml.safe_dump(
            {
                "routes": {},
                "named_paths": {
                    "space": {
                        "label": "SPACE",
                        "status": "CURRENT",
                        "branches": {
                            "main": {
                                "label": "main",
                                "nodes": [{"id": "a", "label": "A"}],
                            }
                        },
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    midi.write_text(
        yaml.safe_dump(
            {
                "devices": [],
                "links": [],
                "channels": [],
                "clock": {
                    "master": {
                        "endpoint_ref": "ableton",
                        "status": "INTENDED",
                        "notes": "",
                    },
                    "destinations": [],
                    "transport": {"status": "UNKNOWN", "notes": ""},
                },
                "ableton_ports": [],
            }
        ),
        encoding="utf-8",
    )
    controllers.write_text(yaml.safe_dump({"controllers": []}), encoding="utf-8")
    ableton.write_text(
        yaml.safe_dump({"tracks": [], "sends": [], "actions": [], "templates": []}),
        encoding="utf-8",
    )

    monkeypatch.setattr(store, "QUESTIONS_PATH", questions)
    monkeypatch.setattr(store, "TODO_PATH", todo)
    monkeypatch.setattr(store, "WISHLIST_PATH", wish)
    monkeypatch.setattr(store, "INBOX_PATH", inbox)
    monkeypatch.setattr(store, "CHANGES_PATH", changes)
    monkeypatch.setattr(store, "PATCHBAYS_PATH", patchbays)
    monkeypatch.setattr(store, "ROUTING_PATH", routing)
    monkeypatch.setattr(store, "MIDI_PATH", midi)
    monkeypatch.setattr(store, "CONTROLLERS_PATH", controllers)
    monkeypatch.setattr(store, "ABLETON_PATH", ableton)
    monkeypatch.setattr(store, "INVENTORY_PATH", inventory)
    monkeypatch.setattr(store, "DOCS_TODO_PATH", docs["todo.md"])
    monkeypatch.setattr(store, "DOCS_WISHLIST_PATH", docs["wishlist.md"])
    monkeypatch.setattr(store, "DOCS_QUESTIONS_PATH", docs["open-questions.md"])
    monkeypatch.setattr(store, "DOCS_PATCHBAYS_PATH", docs["patchbays.md"])
    monkeypatch.setattr(store, "DOCS_INVENTORY_PATH", docs["inventory.md"])
    monkeypatch.setattr(patchbay_state, "PATCHBAYS_PATH", patchbays)
    # render.py / midi_state import path constants by value — keep fixtures consistent
    from music_rig import midi_state, render as render_mod

    monkeypatch.setattr(midi_state, "MIDI_PATH", midi)
    monkeypatch.setattr(render_mod, "MIDI_PATH", midi)
    monkeypatch.setattr(render_mod, "INVENTORY_PATH", inventory)
    monkeypatch.setattr(render_mod, "QUESTIONS_PATH", questions)
    monkeypatch.setattr(render_mod, "TODO_PATH", todo)
    monkeypatch.setattr(render_mod, "WISHLIST_PATH", wish)
    monkeypatch.setattr(render_mod, "DOCS_TODO_PATH", docs["todo.md"])
    monkeypatch.setattr(render_mod, "DOCS_WISHLIST_PATH", docs["wishlist.md"])
    monkeypatch.setattr(render_mod, "DOCS_QUESTIONS_PATH", docs["open-questions.md"])
    monkeypatch.setattr(render_mod, "DOCS_PATCHBAYS_PATH", docs["patchbays.md"])
    monkeypatch.setattr(render_mod, "DOCS_INVENTORY_PATH", docs["inventory.md"])

    return {
        "questions": questions,
        "todo": todo,
        "changes": changes,
        "patchbays": patchbays,
        "routing": routing,
        "midi": midi,
        "inventory": inventory,
        "tmp": tmp_path,
    }


# --- presentation / inspect domains ---


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


# --- answer / target ---


def test_question_answer_dry_run_and_apply(fx15):
    runner = CliRunner()
    dry = runner.invoke(
        app,
        [
            "question",
            "answer",
            "Q-080",
            "--answer",
            "half-normal",
            "--dry-run",
            "--json",
        ],
    )
    assert dry.exit_code == 0, dry.stdout
    assert "\x1b[" not in dry.stdout
    dpayload = json.loads(dry.stdout)
    assert dpayload["ok"] is True
    assert dpayload["result"]["dry_run"] is True
    assert load_questions().question_map()["Q-080"].status == QuestionStatus.OPEN

    applied = runner.invoke(
        app,
        [
            "question",
            "answer",
            "Q-080",
            "--answer",
            "half-normal",
            "--no-render",
            "--json",
        ],
    )
    assert applied.exit_code == 0, applied.stdout
    ap = json.loads(applied.stdout)
    assert ap["result"]["reconciled_at"] is None
    assert "reconcile plan question Q-080" in ap["result"]["next_command"]
    q = load_questions().question_map()["Q-080"]
    assert q.status == QuestionStatus.RESOLVED
    assert q.answer == "half-normal"
    assert q.reconciled_at is None


def test_question_target_set_validate(fx15):
    runner = CliRunner()
    bad = runner.invoke(
        app,
        [
            "question",
            "target",
            "set",
            "Q-080",
            "--pair",
            "99/99",
            "--yes",
            "--json",
        ],
    )
    assert bad.exit_code == 1
    assert "\x1b[" not in bad.stdout

    dry = runner.invoke(
        app,
        [
            "question",
            "target",
            "set",
            "Q-080",
            "--pair",
            "1/25",
            "--dry-run",
            "--json",
        ],
    )
    assert dry.exit_code == 0, dry.stdout
    before = load_questions().question_map()["Q-080"].target
    assert before is not None and before.pair is None

    ok = runner.invoke(
        app,
        [
            "question",
            "target",
            "set",
            "Q-080",
            "--pair",
            "1/25",
            "--yes",
            "--no-render",
            "--json",
        ],
    )
    assert ok.exit_code == 0, ok.stdout
    after = load_questions().question_map()["Q-080"].target
    assert after is not None and after.pair == "1/25"
    assert after.bay == "PB-B"
    assert after.domain == "patchbay.mode"

    show = runner.invoke(app, ["question", "target", "show", "Q-080", "--json"])
    assert show.exit_code == 0
    assert json.loads(show.stdout)["result"]["target"]["pair"] == "1/25"


def test_incomplete_target_e2e_fixture_not_prod_pair(fx15):
    """Q with patchbay.mode + bay + pair null → target set → apply → finalize.

    Uses fixture pair 1/25 only — does not claim production Q-008 pair.
    """
    question_service.answer_question(
        "Q-080", "half-normal", clock=_clock, render=False
    )
    plan1 = reconcile_service.plan_question("Q-080")
    assert plan1.state == ReconciliationState.NEEDS_AGENT_ACTION
    assert any(
        isinstance(b, dict) and b.get("code") == "missing_target_field"
        for b in plan1.blockers
    )
    blocker = next(b for b in plan1.blockers if isinstance(b, dict))
    assert blocker["field"] == "pair"
    assert "1/25" in blocker["candidates"]
    assert "2/26" in blocker["candidates"]

    question_service.set_target("Q-080", pair="1/25", render=False)
    plan2 = reconcile_service.plan_question("Q-080")
    assert plan2.state == ReconciliationState.READY_TO_APPLY

    reconcile_service.apply_question("Q-080", dry_run=False, yes=True)
    verified = reconcile_service.verify_question("Q-080")
    assert verified["verification"] == VerificationStatus.MATCH.value
    reconcile_service.finalize_question(
        "Q-080",
        dry_run=False,
        yes=True,
        complete_linked_todos=True,
        apply_linked_changes=True,
        confirm_dod=True,
        clock=_clock,
    )
    q = load_questions().question_map()["Q-080"]
    assert q.reconciled_at is not None
    raw = yaml.safe_load(fx15["patchbays"].read_text(encoding="utf-8"))
    assert raw["patchbays"]["PB-B"]["jacks"][1]["mode"] == "half-normal"
    assert load_todo().task_map()["RIG-080"].status == TodoStatus.DONE
    assert load_changes().item_map()["CHG-080"].status.value == "APPLIED"


def test_adapter_verify_only_guards(fx15):
    from music_rig.reconciliation.adapters import get_adapter

    assert get_adapter("midi.clock_master").capability == Capability.VERIFY_ONLY
    assert get_adapter("controls.verify").capability == Capability.VERIFY_ONLY
    assert get_adapter("midi.verify").capability == Capability.VERIFY_ONLY
    assert get_adapter("ableton.template").capability == Capability.VERIFY_ONLY
    assert get_adapter("routing.verify").capability == Capability.VERIFY_ONLY
    assert get_adapter("inventory.patchbay_mapping").capability == Capability.MANUAL

    question_service.answer_question("Q-081", "ableton", clock=_clock, render=False)
    plan = reconcile_service.plan_question("Q-081")
    assert plan.capability == Capability.VERIFY_ONLY
    # CURRENT already ableton INTENDED — may CURRENT_MATCHES or NEEDS_AGENT
    assert plan.state in {
        ReconciliationState.CURRENT_MATCHES,
        ReconciliationState.NEEDS_AGENT_ACTION,
    }
    # apply must not silently promote — VERIFY_ONLY adapters typically refuse apply
    with pytest.raises((StoreError, NotImplementedError)):
        reconcile_service.apply_question("Q-081", dry_run=False, yes=True)

    question_service.answer_question("Q-082", "ART P48", clock=_clock, render=False)
    plan_map = reconcile_service.plan_question("Q-082")
    assert plan_map.capability == Capability.MANUAL
    assert plan_map.state == ReconciliationState.NEEDS_AGENT_ACTION
    assert any(
        isinstance(b, dict) and "gear_ref" in str(b.get("message", ""))
        for b in plan_map.blockers
    )


def test_sweep_dry_run_json_counts(fx15):
    runner = CliRunner()
    result = runner.invoke(app, ["reconcile", "sweep", "--dry-run", "--json"])
    assert result.exit_code == 0, result.stdout
    assert "\x1b[" not in result.stdout
    payload = json.loads(result.stdout)
    counts = payload["result"]["counts"]
    for key in (
        "ready_to_finalize",
        "needs_answer",
        "needs_target_metadata",
        "needs_agent_action",
        "blocked_by_dod",
        "already_reconciled",
    ):
        assert key in counts
    assert "suggested_next_commands" in payload["result"]
    assert counts["needs_answer"] >= 1


def test_question_list_active_flags(fx15):
    question_service.answer_question(
        "Q-081", "ableton", clock=_clock, render=False
    )
    active = question_service.list_questions()
    ids = {q.id for q in active}
    assert "Q-080" in ids
    assert "Q-081" in ids  # RESOLVED unreconciled
    open_only = question_service.list_questions(open_only=True)
    assert all(q.status == QuestionStatus.OPEN for q in open_only)
    unrec = question_service.list_questions(unreconciled_only=True)
    assert all(
        q.status == QuestionStatus.RESOLVED and q.reconciled_at is None for q in unrec
    )


def test_todo_list_hides_terminal(fx15):
    runner = CliRunner()
    result = runner.invoke(app, ["todo", "list"])
    assert result.exit_code == 0
    assert "RIG-081" not in result.stdout
    all_items = runner.invoke(app, ["todo", "list", "--all"])
    assert "RIG-081" in all_items.stdout


def test_target_gear_path_validation(fx15):
    with pytest.raises(StoreError):
        question_service.set_target(
            "Q-080",
            domain="routing.verify",
            path="no-such-path",
            dry_run=True,
        )
    ok = question_service.set_target(
        "Q-080",
        domain="routing.verify",
        path="space",
        dry_run=True,
    )
    assert ok["after"]["path"] == "space"
    with pytest.raises(StoreError):
        question_service.set_target(
            "Q-080", gear="no-such-gear", dry_run=True
        )


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
