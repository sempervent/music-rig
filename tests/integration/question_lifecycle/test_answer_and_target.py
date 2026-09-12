"""Tests migrated to integration/question_lifecycle/test_answer_and_target.py."""

from __future__ import annotations

from fixtures.repo_fixtures import _clock
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
    # HUMAN answer attestation (MIDI_CLOCK policy) → deterministic evidence apply
    assert plan.state == ReconciliationState.READY_TO_APPLY
    from music_rig.reconciliation.action_packet import has_apply_authority

    assert has_apply_authority(question_service.get_question("Q-081"))
    # Legacy / non-HUMAN answers still cannot escalate evidence
    from music_rig.models import AnswerActor, OpenQuestion, OpenQuestionsDocument
    from music_rig.store import load_questions, write_documents

    qdoc = load_questions()
    q = qdoc.question_map()["Q-081"]
    legacy = OpenQuestion.model_validate(
        {**q.model_dump(), "answer_actor": AnswerActor.LEGACY_UNKNOWN}
    )
    write_documents(
        questions=OpenQuestionsDocument(
            questions=[legacy if x.id == "Q-081" else x for x in qdoc.questions]
        ),
        questions_path=None,
    )
    assert not has_apply_authority(question_service.get_question("Q-081"))

    question_service.answer_question("Q-082", "ART P48", clock=_clock, render=False)
    plan_map = reconcile_service.plan_question("Q-082")
    assert plan_map.capability == Capability.MANUAL
    assert plan_map.state == ReconciliationState.NEEDS_AGENT_ACTION
    assert any(
        isinstance(b, dict) and "gear_ref" in str(b.get("message", ""))
        for b in plan_map.blockers
    )

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

