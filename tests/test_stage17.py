"""Stage 17 — verification_result + evidence reconciliation. Fixtures only."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from music_rig import (
    ableton_state,
    midi_state,
    question_service,
    store,
    verification_service,
)
from music_rig.cli import app
from music_rig.models import (
    MidiEvidenceStatus,
    QuestionStatus,
    ReconciliationState,
    VerificationOutcome,
    VerificationResult,
)
from music_rig.reconciliation import service as reconcile_service
from music_rig.reconciliation.adapters import get_adapter
from music_rig.reconciliation.adapters.unsupported import MANUAL_CLASSIFICATION
from music_rig.reconciliation.types import Capability, PlanOperationKind, VerificationStatus
from music_rig.store import StoreError, load_changes, load_questions


def _clock():
    return datetime(2026, 9, 11, 23, 0, 0, tzinfo=timezone.utc)


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
def fx17(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
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
                "next_session": [],
                "tasks": [
                    {
                        "id": "RIG-170",
                        "task": "Stage 17 clock",
                        "area": "MIDI",
                        "priority": "P1",
                        "status": "READY",
                        "depends_on": [],
                        "definition_of_done": "clock verified",
                        "notes": "",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    wish.write_text("items: []\n", encoding="utf-8")
    inbox.write_text("items: []\n", encoding="utf-8")
    changes.write_text("items: []\n", encoding="utf-8")
    inventory.write_text(
        yaml.safe_dump(
            {
                "items": [
                    {
                        "id": "ableton",
                        "name": "Ableton",
                        "category": "software",
                        "ownership_status": "OWNED",
                        "condition": "WORKING",
                        "quantity": 1,
                        "units": [{"id": "ableton-1"}],
                    },
                    {
                        "id": "behringer-fcb1010",
                        "name": "FCB1010",
                        "category": "controller",
                        "ownership_status": "OWNED",
                        "condition": "WORKING",
                        "quantity": 1,
                        "units": [{"id": "behringer-fcb1010-1"}],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    patchbays.write_text(
        yaml.safe_dump({"schema_notes": {}, "patchbays": {}}), encoding="utf-8"
    )
    routing.write_text(
        yaml.safe_dump(
            {
                "routes": {},
                "named_paths": {
                    "kaoss": {
                        "label": "KAOSS",
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
                "connections": [],
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
                "endpoints": [
                    {"id": "ableton", "kind": "software", "name": "Ableton"},
                    {"id": "kaoss", "kind": "host", "name": "KAOSS"},
                ],
            }
        ),
        encoding="utf-8",
    )
    controllers.write_text(
        yaml.safe_dump(
            {
                "controllers": [
                    {
                        "gear_ref": "behringer-fcb1010",
                        "coverage": "PARTIAL",
                        "related_todos": [],
                        "notes": "",
                        "contexts": [
                            {
                                "id": "bank-00",
                                "label": "Bank 00",
                                "kind": "BANK",
                                "evidence": "INTENDED",
                                "notes": "",
                                "controls": [
                                    {
                                        "id": "sw1",
                                        "label": "Switch 1",
                                        "physical_type": "FOOTSWITCH",
                                        "availability": "AVAILABLE",
                                        "evidence": "INTENDED",
                                        "messages": [],
                                        "target": {"state": "UNASSIGNED"},
                                    }
                                ],
                            },
                            {
                                "id": "bank-01",
                                "label": "Bank 01",
                                "kind": "BANK",
                                "evidence": "INTENDED",
                                "notes": "",
                                "controls": [],
                            },
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    ableton.write_text(
        yaml.safe_dump(
            {
                "tracks": [],
                "sends": [],
                "actions": [],
                "templates": [
                    {
                        "id": "pfl-jam",
                        "label": "PFL Jam",
                        "evidence": "INTENDED",
                        "related_todos": [],
                        "notes": "",
                        "tracks": [],
                        "sends": [],
                        "requirements": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    questions.write_text(
        yaml.safe_dump(
            {
                "questions": [
                    {
                        "id": "Q-170",
                        "question": "Is Ableton the MIDI clock master in practice?",
                        "area": "MIDI",
                        "status": "OPEN",
                        "related_todos": ["RIG-170"],
                        "related_changes": [],
                        "answer": "",
                        "notes": "",
                        "resolved_at": None,
                        "reconciled_at": None,
                        "reconciliation_note": "",
                        "target": {"domain": "midi.clock_master"},
                        "verification": {
                            "kind": "MIDI_CLOCK",
                            "prompt": "Check who leads clock",
                            "answer_type": "ENUM",
                            "choices": ["ableton", "kaoss", "UNKNOWN"],
                            "ref_domain": None,
                        },
                        "verification_note": "",
                        "verification_result": None,
                    },
                    {
                        "id": "Q-171",
                        "question": "Does FCB bank-00 work?",
                        "area": "MIDI",
                        "status": "OPEN",
                        "related_todos": [],
                        "related_changes": [],
                        "answer": "",
                        "notes": "",
                        "resolved_at": None,
                        "reconciled_at": None,
                        "reconciliation_note": "",
                        "target": {
                            "domain": "controls.verify",
                            "gear": "behringer-fcb1010",
                            "context": "bank-00",
                        },
                        "verification": {
                            "kind": "CONTROLLER_MAPPING",
                            "prompt": "Test switch",
                            "answer_type": "TEXT",
                            "choices": [],
                            "ref_domain": None,
                        },
                        "verification_note": "",
                    },
                    {
                        "id": "Q-172",
                        "question": "PFL jam template tracks?",
                        "area": "Ableton",
                        "status": "OPEN",
                        "related_todos": [],
                        "related_changes": [],
                        "answer": "",
                        "notes": "",
                        "resolved_at": None,
                        "reconciled_at": None,
                        "reconciliation_note": "",
                        "target": {"domain": "ableton.template", "path": "pfl-jam"},
                        "verification": {
                            "kind": "ABLETON_SETTING",
                            "prompt": "Open Live set",
                            "answer_type": "TEXT",
                            "choices": [],
                            "ref_domain": None,
                        },
                        "verification_note": "",
                    },
                    {
                        "id": "Q-173",
                        "question": "Does kaoss path match?",
                        "area": "Routing",
                        "status": "OPEN",
                        "related_todos": [],
                        "related_changes": [],
                        "answer": "",
                        "notes": "",
                        "resolved_at": None,
                        "reconciled_at": None,
                        "reconciliation_note": "",
                        "target": {"domain": "routing.verify", "path": "kaoss"},
                        "verification": {
                            "kind": "ROUTING_COMPARE",
                            "prompt": "Trace path",
                            "answer_type": "BOOL",
                            "choices": ["YES", "NO", "UNKNOWN"],
                            "ref_domain": None,
                        },
                        "verification_note": "",
                    },
                    {
                        "id": "Q-174",
                        "question": "Freeform topology?",
                        "area": "Routing",
                        "status": "OPEN",
                        "related_todos": [],
                        "related_changes": [],
                        "answer": "",
                        "notes": "",
                        "resolved_at": None,
                        "reconciled_at": None,
                        "reconciliation_note": "",
                        "verification": {
                            "kind": "ROUTING_VISUAL",
                            "prompt": "Describe",
                            "answer_type": "TEXT",
                            "choices": [],
                            "ref_domain": None,
                        },
                        "verification_note": "",
                    },
                ]
            }
        ),
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

    from music_rig import (
        ableton_state as ableton_mod,
        control_state as control_mod,
        current_service as current_mod,
        midi_state as midi_mod,
        routing_state as routing_mod,
    )
    from music_rig import render as render_mod

    monkeypatch.setattr(midi_mod, "MIDI_PATH", midi)
    monkeypatch.setattr(control_mod, "CONTROLLERS_PATH", controllers)
    monkeypatch.setattr(control_mod, "MIDI_PATH", midi)
    monkeypatch.setattr(control_mod, "ABLETON_PATH", ableton)
    monkeypatch.setattr(ableton_mod, "ABLETON_PATH", ableton)
    monkeypatch.setattr(routing_mod, "ROUTING_PATH", routing)
    monkeypatch.setattr(current_mod, "MIDI_PATH", midi)
    monkeypatch.setattr(current_mod, "CONTROLLERS_PATH", controllers)
    monkeypatch.setattr(current_mod, "ABLETON_PATH", ableton)
    monkeypatch.setattr(current_mod, "ROUTING_PATH", routing)
    monkeypatch.setattr(current_mod, "INVENTORY_PATH", inventory)
    monkeypatch.setattr(current_mod, "QUESTIONS_PATH", questions)
    monkeypatch.setattr(current_mod, "CHANGES_PATH", changes)
    for attr, path in [
        ("MIDI_PATH", midi),
        ("CONTROLLERS_PATH", controllers),
        ("ABLETON_PATH", ableton),
        ("INVENTORY_PATH", inventory),
        ("ROUTING_PATH", routing),
        ("QUESTIONS_PATH", questions),
    ]:
        if hasattr(render_mod, attr):
            monkeypatch.setattr(render_mod, attr, path)

    # Avoid performance validation pulling production files
    perf = tmp_path / "performance.yaml"
    perf.write_text(
        yaml.safe_dump(
            {
                "modes": [],
                "actions": [],
                "bindings": [],
                "recovery": [],
                "requirements": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(store, "PERFORMANCE_PATH", perf)
    if hasattr(control_mod, "PERFORMANCE_PATH"):
        monkeypatch.setattr(control_mod, "PERFORMANCE_PATH", perf)

    return {
        "questions": questions,
        "midi": midi,
        "ableton": ableton,
        "controllers": controllers,
        "routing": routing,
        "changes": changes,
    }


def test_verification_result_model_serialization():
    vr = VerificationResult(
        outcome=VerificationOutcome.CONFIRMED,
        observed_at=_clock(),
        observed_value="ableton",
        note="checked",
    )
    data = vr.model_dump(mode="json")
    assert data["outcome"] == "CONFIRMED"
    assert data["source"] == "HUMAN"
    roundtrip = VerificationResult.model_validate(data)
    assert roundtrip.outcome == VerificationOutcome.CONFIRMED


def test_confirmed_clock_intended_to_verified(fx17):
    verification_service.record_observation(
        "Q-170",
        "confirmed",
        value="ableton",
        clock=_clock,
        render=False,
    )
    q = question_service.get_question("Q-170")
    assert q.verification_result is not None
    assert q.verification_result.outcome == VerificationOutcome.CONFIRMED
    assert q.status == QuestionStatus.RESOLVED
    assert q.answer == "ableton"

    plan = reconcile_service.plan_question("Q-170")
    assert plan.state == ReconciliationState.READY_TO_APPLY
    ops = [o["op"] for o in plan.operations]
    assert PlanOperationKind.SET_EVIDENCE_VERIFIED.value in ops
    assert PlanOperationKind.SET_CURRENT_VALUE.value not in ops

    applied = reconcile_service.apply_question("Q-170", dry_run=False, yes=True)
    assert applied["apply"]["applied"] is True
    raw = midi_state.load_raw()
    assert raw["clock"]["master"]["endpoint_ref"] == "ableton"
    assert raw["clock"]["master"]["status"] == "VERIFIED"

    verified = reconcile_service.verify_question("Q-170")
    assert verified["verification"] == VerificationStatus.MATCH.value


def test_corrected_clock_value_and_verified(fx17):
    # Ensure kaoss is a valid endpoint-like token for clock master
    verification_service.record_observation(
        "Q-170",
        "corrected",
        value="kaoss",
        clock=_clock,
        render=False,
    )
    plan = reconcile_service.plan_question("Q-170")
    ops = {o["op"]: o for o in plan.operations}
    assert PlanOperationKind.SET_CURRENT_VALUE.value in ops
    assert PlanOperationKind.SET_EVIDENCE_VERIFIED.value in ops
    assert ops[PlanOperationKind.SET_CURRENT_VALUE.value]["after"] == "kaoss"

    reconcile_service.apply_question("Q-170", dry_run=False, yes=True)
    raw = midi_state.load_raw()
    assert raw["clock"]["master"]["endpoint_ref"] == "kaoss"
    assert raw["clock"]["master"]["status"] == "VERIFIED"


def test_unknown_observation_no_mutation(fx17):
    before = midi_state.load_raw()["clock"]["master"]["status"]
    verification_service.record_observation(
        "Q-170",
        "unknown",
        clock=_clock,
        render=False,
    )
    q = question_service.get_question("Q-170")
    assert q.verification_result.outcome == VerificationOutcome.UNKNOWN
    assert q.status == QuestionStatus.OPEN
    assert midi_state.load_raw()["clock"]["master"]["status"] == before
    with pytest.raises(StoreError):
        reconcile_service.apply_question("Q-170", dry_run=False, yes=True)


def test_failed_test_no_verified_optional_change(fx17):
    verification_service.record_observation(
        "Q-171",
        "failed_test",
        value="did not trigger",
        note="needs two presses",
        create_change=True,
        clock=_clock,
        render=False,
    )
    q = question_service.get_question("Q-171")
    assert q.verification_result.outcome == VerificationOutcome.FAILED_TEST
    assert q.status == QuestionStatus.OPEN
    assert q.related_changes
    chg = load_changes().item_map()[q.related_changes[0]]
    assert "expected" in chg.details.casefold() or "Expected" in chg.details
    plan = reconcile_service.plan_question("Q-171")
    assert any(
        o["op"] == PlanOperationKind.RECORD_FAILED_VERIFICATION.value
        for o in plan.operations
    )
    raw = yaml.safe_load(fx17["controllers"].read_text(encoding="utf-8"))
    ctx = raw["controllers"][0]["contexts"][0]
    assert ctx["evidence"] == "INTENDED"
    ctl = ctx["controls"][0]
    assert ctl["evidence"] == "INTENDED"


def test_granularity_one_context_not_whole_controller(fx17):
    verification_service.record_observation(
        "Q-171",
        "confirmed",
        value="bank-00 works",
        clock=_clock,
        render=False,
    )
    reconcile_service.apply_question("Q-171", dry_run=False, yes=True)
    raw = yaml.safe_load(fx17["controllers"].read_text(encoding="utf-8"))
    contexts = {c["id"]: c for c in raw["controllers"][0]["contexts"]}
    assert contexts["bank-00"]["evidence"] == "VERIFIED"
    assert contexts["bank-01"]["evidence"] == "INTENDED"
    assert contexts["bank-00"]["controls"][0]["evidence"] == "INTENDED"


def test_ableton_template_confirmed_evidence(fx17):
    verification_service.record_observation(
        "Q-172",
        "confirmed",
        value="tracks match",
        clock=_clock,
        render=False,
    )
    plan = reconcile_service.plan_question("Q-172")
    assert plan.state == ReconciliationState.READY_TO_APPLY
    reconcile_service.apply_question("Q-172", dry_run=False, yes=True)
    doc = ableton_state.load_document()
    tmpl = next(t for t in doc.templates if t.id == "pfl-jam")
    assert tmpl.evidence == MidiEvidenceStatus.VERIFIED


def test_routing_yes_confirmed_sets_path_evidence(fx17):
    verification_service.record_observation(
        "Q-173",
        "confirmed",
        value="YES",
        clock=_clock,
        render=False,
    )
    reconcile_service.apply_question("Q-173", dry_run=False, yes=True)
    data = yaml.safe_load(fx17["routing"].read_text(encoding="utf-8"))
    assert data["named_paths"]["kaoss"]["evidence"] == "VERIFIED"


def test_action_packet_contents(fx17):
    question_service.answer_question(
        "Q-174", "splitter goes to pedalboard", clock=_clock, render=False
    )
    plan = reconcile_service.plan_question("Q-174")
    packet = (plan.details or {}).get("action_packet")
    assert packet is not None
    assert "human_answer" in packet
    assert "suggested_command_families" in packet
    assert "postcondition" in packet
    assert "related_ids" in packet
    joined = " ".join(packet["suggested_command_families"]).casefold()
    assert "yaml" not in joined or "edit" not in joined


def test_sweep_unlock_and_failed_test_guard(fx17):
    verification_service.record_observation(
        "Q-170",
        "confirmed",
        value="ableton",
        clock=_clock,
        render=False,
    )
    reconcile_service.apply_question("Q-170", dry_run=False, yes=True)
    sweep = reconcile_service.sweep(dry_run=True, yes=True, confirm_dod=True)
    assert "Q-170" in sweep.get("would_finalize", []) or sweep["counts"][
        "ready_to_finalize"
    ] >= 1

    # FAILED_TEST leaves question OPEN — never finalized as success
    verification_service.record_observation(
        "Q-171",
        "failed_test",
        note="broken",
        clock=_clock,
        render=False,
    )
    assert question_service.get_question("Q-171").status == QuestionStatus.OPEN
    sweep2 = reconcile_service.sweep(dry_run=True, yes=True, confirm_dod=True)
    assert "Q-171" not in sweep2.get("would_finalize", [])
    assert "Q-171" not in sweep2.get("finalized", [])

    # Also guard RESOLVED + FAILED_TEST observation
    question_service.answer_question(
        "Q-171", "map documented", clock=_clock, render=False
    )
    verification_service.record_observation(
        "Q-171",
        "failed_test",
        value="did not work",
        note="broken",
        clock=_clock,
        render=False,
    )
    sweep3 = reconcile_service.sweep(dry_run=True, yes=True, confirm_dod=True)
    skipped = {s["id"]: s.get("reason", "") for s in sweep3["skipped"]}
    assert "Q-171" in skipped
    assert "FAILED_TEST" in skipped["Q-171"]
    assert "Q-171" not in sweep3.get("would_finalize", [])


def test_verify_record_cli_dry_run(fx17):
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "verify",
            "record",
            "Q-170",
            "--outcome",
            "confirmed",
            "--value",
            "ableton",
            "--dry-run",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["result"]["dry_run"] is True
    assert load_questions().question_map()["Q-170"].verification_result is None


def test_current_ableton_set_template_evidence_cli(fx17):
    runner = CliRunner()
    # dry-run only — never write production; fixture paths cover service path
    result = runner.invoke(
        app,
        [
            "current",
            "ableton",
            "set-template-evidence",
            "pfl-jam",
            "VERIFIED",
            "--dry-run",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["result"]["dry_run"] is True
    preview = payload["result"]["preview"]
    assert preview["after"]["evidence"] == "VERIFIED"
    # Fixture file unchanged until explicit yes-path via service
    doc = ableton_state.load_document()
    assert next(t for t in doc.templates if t.id == "pfl-jam").evidence.value == "INTENDED"

    preview2, data = ableton_state.propose_set_template_evidence(
        "pfl-jam", "VERIFIED", ableton_path=fx17["ableton"]
    )
    assert preview2.after["evidence"] == "VERIFIED"
    from music_rig import current_service

    current_service.commit_ableton(
        data,
        preview2,
        dry_run=False,
        render=False,
        ableton_path=fx17["ableton"],
    )
    doc2 = ableton_state.load_document(fx17["ableton"])
    assert next(t for t in doc2.templates if t.id == "pfl-jam").evidence.value == "VERIFIED"


def test_manual_classification_complete():
    assert len(MANUAL_CLASSIFICATION) == 13
    assert MANUAL_CLASSIFICATION["Q-012"] == "STRUCTURABLE_NOW"
    assert MANUAL_CLASSIFICATION["Q-007"] == "NEEDS_SMALL_SERVICE"


def test_production_verification_result_null():
    """Production questions must not have fabricated observations."""
    # Load real production path (not monkeypatched) — skip if fixture polluted
    from music_rig.store import QUESTIONS_PATH

    # Use repo data path explicitly
    repo = Path(__file__).resolve().parents[1] / "data" / "open-questions.yaml"
    doc = load_questions(repo)
    for q in doc.questions:
        assert q.verification_result is None, f"{q.id} has fabricated observation"


def test_answer_without_observation_does_not_apply_evidence(fx17):
    """LEGACY answers (no HUMAN actor) cannot escalate INTENDED→VERIFIED alone."""
    from music_rig.models import AnswerActor, OpenQuestion, OpenQuestionsDocument
    from music_rig.store import load_questions, write_documents

    question_service.answer_question("Q-170", "ableton", clock=_clock, render=False)
    qdoc = load_questions()
    q = qdoc.question_map()["Q-170"]
    legacy = OpenQuestion.model_validate(
        {**q.model_dump(), "answer_actor": AnswerActor.LEGACY_UNKNOWN}
    )
    write_documents(
        questions=OpenQuestionsDocument(
            questions=[legacy if x.id == "Q-170" else x for x in qdoc.questions]
        )
    )
    with pytest.raises(StoreError):
        reconcile_service.apply_question("Q-170", dry_run=False, yes=True)
    assert midi_state.load_raw()["clock"]["master"]["status"] == "INTENDED"


def test_human_attestation_may_apply_clock_evidence(fx17):
    """HUMAN answer under ANSWER_ATTESTATION_SUFFICIENT may dry-run evidence apply."""
    question_service.answer_question("Q-170", "ableton", clock=_clock, render=False)
    out = reconcile_service.apply_question("Q-170", dry_run=True, yes=True)
    assert out.get("dry_run") is True
    assert midi_state.load_raw()["clock"]["master"]["status"] == "INTENDED"


@pytest.mark.asyncio
async def test_tui_verify_failed_binding(fx17):
    from music_rig.tui.app import RigApp
    from music_rig.tui.screens.verify import VerifyScreen

    app_tui = RigApp()
    async with app_tui.run_test() as pilot:
        app_tui.push_screen(VerifyScreen())
        await pilot.pause()
        assert isinstance(app_tui.screen, VerifyScreen)
        # Select Q-171 if present
        screen: VerifyScreen = app_tui.screen
        screen.action_refresh()
        await pilot.pause()
        ids = [i.question_id for i in screen._items]
        if "Q-171" in ids:
            idx = ids.index("Q-171")
            screen.query_one("#list-table").move_cursor(row=idx)
            await pilot.pause()
            # Trigger fail confirm then accept
            from music_rig.tui.dialogs import ConfirmModal

            screen.action_fail()
            await pilot.pause()
            if isinstance(app_tui.screen, ConfirmModal):
                await pilot.press("enter")
                await pilot.pause()
            q = question_service.get_question("Q-171")
            assert q.verification_result is not None
            assert q.verification_result.outcome == VerificationOutcome.FAILED_TEST
