"""Tests migrated to integration/verification/test_record_outcomes.py."""

from __future__ import annotations

from fixtures.repo_fixtures import _clock
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

runner = CliRunner()

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

