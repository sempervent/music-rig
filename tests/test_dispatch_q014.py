"""Q-014-shaped dispatch: HUMAN attestation → deterministic, not observation."""

from __future__ import annotations

from music_rig.models import AnswerActor, ReconciliationState
from music_rig.reconciliation.dispatch import (
    DispatchMode,
    NextActor,
    classify_reconciliation_dispatch,
)
from music_rig.reconciliation.types import Capability, Plan


def _q014_plan(*, actor: AnswerActor = AnswerActor.HUMAN) -> Plan:
    if actor is AnswerActor.HUMAN:
        return Plan(
            artifact_type="question",
            artifact_id="Q-014",
            state=ReconciliationState.READY_TO_APPLY,
            capability=Capability.VERIFY_ONLY,
            current={"master": "ableton", "status": "INTENDED"},
            desired="Ableton is definitely the master clock; nothing else is master currently",
            operations=[
                {
                    "op": "SET_EVIDENCE_VERIFIED",
                    "target": "midi.clock.master",
                    "after": "VERIFIED",
                }
            ],
            blockers=[],
            suggested_commands=[],
            details={
                "verification_policy": "ANSWER_ATTESTATION_SUFFICIENT",
                "evidence_basis": "HUMAN_ANSWER",
                "answer_actor": "HUMAN",
            },
        )
    return Plan(
        artifact_type="question",
        artifact_id="Q-014",
        state=ReconciliationState.NEEDS_ANSWER,
        capability=Capability.VERIFY_ONLY,
        current={"master": "ableton", "status": "INTENDED"},
        desired="Ableton is definitely the master clock; nothing else is master currently",
        operations=[],
        blockers=[
            {
                "code": "needs_human_answer",
                "field": "answer_actor",
                "message": "BOT answer is not human factual authority.",
            }
        ],
        suggested_commands=[],
        details={"answer_actor": "BOT"},
    )


def test_q014_human_attestation_dispatch_deterministic():
    d = classify_reconciliation_dispatch(_q014_plan(actor=AnswerActor.HUMAN))
    assert d.mode is DispatchMode.DETERMINISTIC
    assert d.provider_eligible is False
    assert d.next_actor is NextActor.DETERMINISTIC_ENGINE


def test_q014_bot_answer_needs_human():
    d = classify_reconciliation_dispatch(_q014_plan(actor=AnswerActor.BOT))
    assert d.mode is DispatchMode.HUMAN_ANSWER
    assert d.provider_eligible is False


def test_reconcile_run_q014_shaped_never_calls_provider(monkeypatch):
    from music_rig.reconciliation import run as run_mod

    calls = {"n": 0}

    def boom(*a, **k):
        calls["n"] += 1
        raise AssertionError("provider must not be invoked")

    monkeypatch.setattr(run_mod, "autonomous_reconcile", boom)
    monkeypatch.setattr(
        run_mod.recon, "plan_question", lambda *a, **k: _q014_plan()
    )

    result = run_mod.reconcile_run("Q-014")
    assert calls["n"] == 0
    assert result["provider_invoked"] is False
    assert result["mode"] == "deterministic"
    assert "clarification" not in (result.get("message") or "").casefold()
    assert "observation" not in (result.get("message") or "").casefold() or (
        "evidence basis" in (result.get("message") or "").casefold()
    )
