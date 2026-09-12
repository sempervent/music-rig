"""Tests migrated to integration/reconciliation/test_reconcile_run_dispatch.py."""

from __future__ import annotations

from music_rig.models import AnswerActor, ReconciliationState
from music_rig.reconciliation.types import Capability, Plan


def _plan(
    *,
    state: ReconciliationState,
    capability: Capability = Capability.MANUAL,
    blockers: list | None = None,
    current=None,
    desired: str = "",
    operations: list | None = None,
    details: dict | None = None,
) -> Plan:
    return Plan(
        artifact_type="question",
        artifact_id="Q-TEST",
        state=state,
        capability=capability,
        current=current,
        desired=desired,
        operations=operations or [],
        blockers=blockers or [],
        suggested_commands=[],
        details=details or {},
    )


def test_provider_call_counts_by_dispatch(monkeypatch):
    from music_rig.reconciliation import run as run_mod

    cases = [
        (
            _plan(state=ReconciliationState.NEEDS_ANSWER),
            0,
            "needs_human",
        ),
        (
            _plan(state=ReconciliationState.DRAFT_ANSWER),
            0,
            "needs_human",
        ),
        (
            _plan(
                state=ReconciliationState.NEEDS_AGENT_ACTION,
                capability=Capability.VERIFY_ONLY,
                blockers=[{"code": "needs_human_observation"}],
                current={"master": "ableton"},
                desired="ableton",
            ),
            0,
            "needs_verification",
        ),
        (
            _plan(
                state=ReconciliationState.NEEDS_AGENT_ACTION,
                blockers=[{"code": "needs_human_clarification"}],
            ),
            0,
            "needs_clarification",
        ),
        (
            _plan(state=ReconciliationState.READY_TO_APPLY, operations=[{"kind": "x"}]),
            0,
            "deterministic",
        ),
        (
            _plan(state=ReconciliationState.CURRENT_MATCHES),
            0,
            "deterministic",
        ),
        (
            _plan(state=ReconciliationState.RECONCILED),
            0,
            "already_reconciled",
        ),
    ]

    for plan, expected_calls, mode in cases:
        calls = {"n": 0}

        def boom(*a, **k):
            calls["n"] += 1
            raise AssertionError("provider invoked")

        monkeypatch.setattr(run_mod, "autonomous_reconcile", boom)
        monkeypatch.setattr(run_mod.recon, "plan_question", lambda *a, **k: plan)
        # Avoid finalize side effects for CURRENT_MATCHES
        monkeypatch.setattr(
            run_mod.recon,
            "finalize_question",
            lambda *a, **k: {"dry_run": True, "question_id": "Q-TEST"},
        )
        result = run_mod.reconcile_run("Q-TEST")
        assert calls["n"] == expected_calls, (mode, result)
        assert result["mode"] == mode
        assert result["provider_invoked"] is False


def test_agent_required_invokes_provider_once(monkeypatch):
    from music_rig.reconciliation import run as run_mod

    plan = _plan(
        state=ReconciliationState.NEEDS_AGENT_ACTION,
        capability=Capability.MANUAL,
        desired="PB-A is ART",
    )
    calls = {"n": 0}

    def fake_auto(*a, **k):
        calls["n"] += 1
        return {"ok": True, "message": "planned"}

    monkeypatch.setattr(run_mod, "autonomous_reconcile", fake_auto)
    monkeypatch.setattr(run_mod.recon, "plan_question", lambda *a, **k: plan)
    monkeypatch.setattr(
        run_mod,
        "provider_status",
        lambda **k: {"configured": True, "provider_type": "ollama"},
    )
    result = run_mod.reconcile_run("Q-TEST")
    assert calls["n"] == 1
    assert result["provider_invoked"] is True
    assert result["mode"] == "agent"


def test_yes_does_not_fabricate_observation(monkeypatch):
    from music_rig.reconciliation import run as run_mod

    plan = _plan(
        state=ReconciliationState.NEEDS_AGENT_ACTION,
        capability=Capability.VERIFY_ONLY,
        blockers=[{"code": "needs_human_observation"}],
        current={"master": "ableton"},
        desired="Ableton is master",
    )
    monkeypatch.setattr(run_mod.recon, "plan_question", lambda *a, **k: plan)
    monkeypatch.setattr(
        run_mod,
        "autonomous_reconcile",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no provider")),
    )
    result = run_mod.reconcile_run("Q-014", apply=True, yes=True)
    assert result["provider_invoked"] is False
    assert result["mode"] == "needs_verification"
    assert "--yes does not imply" in result["message"]


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


def test_reconcile_run_q014_shaped_never_calls_provider(monkeypatch):
    from music_rig.reconciliation import run as run_mod

    calls = {"n": 0}

    def boom(*a, **k):
        calls["n"] += 1
        raise AssertionError("provider must not be invoked")

    monkeypatch.setattr(run_mod, "autonomous_reconcile", boom)
    monkeypatch.setattr(run_mod.recon, "plan_question", lambda *a, **k: _q014_plan())

    result = run_mod.reconcile_run("Q-014")
    assert calls["n"] == 0
    assert result["provider_invoked"] is False
    assert result["mode"] == "deterministic"
    assert "clarification" not in (result.get("message") or "").casefold()
    assert "observation" not in (result.get("message") or "").casefold() or (
        "evidence basis" in (result.get("message") or "").casefold()
    )
