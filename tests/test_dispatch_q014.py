"""Q-014-shaped dispatch: human observation must not invoke a provider."""

from __future__ import annotations

from music_rig.models import ReconciliationState
from music_rig.reconciliation.dispatch import (
    DispatchMode,
    NextActor,
    classify_reconciliation_dispatch,
)
from music_rig.reconciliation.types import Capability, Plan


def _q014_plan(*, with_observation: bool = False) -> Plan:
    blockers = []
    if not with_observation:
        blockers.append(
            {
                "code": "needs_human_observation",
                "field": "verification_result",
                "message": "Record explicit observation before evidence apply.",
                "suggested_commands": [
                    "uv run rig verify record Q-014 --outcome confirmed --value … --yes --json"
                ],
            }
        )
    details: dict = {
        "capability_reason": "Physical verification of clock leadership",
        "action_packet": {
            "observation": (
                {"outcome": "CONFIRMED", "observed_value": "ableton"}
                if with_observation
                else None
            ),
        },
    }
    state = (
        ReconciliationState.READY_TO_APPLY
        if with_observation
        else ReconciliationState.NEEDS_AGENT_ACTION
    )
    return Plan(
        artifact_type="question",
        artifact_id="Q-014",
        state=state,
        capability=Capability.VERIFY_ONLY,
        current={"master": "ableton", "status": "INTENDED"},
        desired="Ableton is definitely the master clock; nothing else is master currently",
        operations=(
            [
                {
                    "kind": "SET_EVIDENCE_VERIFIED",
                    "target": "clock.master",
                    "after": "VERIFIED",
                }
            ]
            if with_observation
            else []
        ),
        blockers=blockers,
        suggested_commands=["uv run rig current midi verify"],
        details=details,
    )


def test_q014_shaped_dispatch_is_human_observation_not_agent():
    plan = _q014_plan(with_observation=False)
    # This is the production-shaped trap: NEEDS_AGENT_ACTION + VERIFY_ONLY
    assert plan.state is ReconciliationState.NEEDS_AGENT_ACTION
    assert plan.capability is Capability.VERIFY_ONLY
    d = classify_reconciliation_dispatch(plan)
    assert d.mode is DispatchMode.HUMAN_OBSERVATION
    assert d.next_actor is NextActor.HUMAN_OBSERVATION
    assert d.provider_eligible is False
    assert "needs_human_observation" in d.human_blocker_codes
    assert d.value_match is True


def test_q014_after_observation_is_deterministic():
    plan = _q014_plan(with_observation=True)
    d = classify_reconciliation_dispatch(plan)
    assert d.mode is DispatchMode.DETERMINISTIC
    assert d.provider_eligible is False


def test_reconcile_run_q014_shaped_never_calls_provider(monkeypatch):
    from music_rig.reconciliation import run as run_mod

    calls = {"n": 0}

    def boom(*a, **k):
        calls["n"] += 1
        raise AssertionError("provider must not be invoked for human observation")

    monkeypatch.setattr(run_mod, "autonomous_reconcile", boom)
    monkeypatch.setattr(run_mod.recon, "plan_question", lambda *a, **k: _q014_plan())

    result = run_mod.reconcile_run("Q-014")
    assert calls["n"] == 0
    assert result["provider_invoked"] is False
    assert result["mode"] == "needs_verification"
    assert "clarification" not in (result.get("message") or "").casefold()
    assert "verification required" in (result.get("message") or "").casefold() or (
        "observation required" in (result.get("message") or "").casefold()
    )
