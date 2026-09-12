"""Tests migrated to unit/reconciliation/test_dispatch.py."""

from __future__ import annotations

import json
import pytest
from music_rig.models import ReconciliationState
from music_rig.progress import CollectingProgress, ProgressEvent, ProgressPhase, ProgressTracker
from music_rig.reconciliation.dispatch import (
    DispatchMode,
    HUMAN_BLOCKER_CODES,
    classify_reconciliation_dispatch,
)
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

@pytest.mark.parametrize(
    "state",
    [
        ReconciliationState.NEEDS_ANSWER,
        ReconciliationState.DRAFT_ANSWER,
        ReconciliationState.READY_TO_APPLY,
        ReconciliationState.CURRENT_MATCHES,
        ReconciliationState.READY_TO_FINALIZE,
        ReconciliationState.RECONCILED,
    ],
)
def test_non_agent_states_not_provider_eligible(state):
    d = classify_reconciliation_dispatch(_plan(state=state))
    assert d.provider_eligible is False

def test_human_observation_blocker_outranks_needs_agent_action():
    d = classify_reconciliation_dispatch(
        _plan(
            state=ReconciliationState.NEEDS_AGENT_ACTION,
            capability=Capability.VERIFY_ONLY,
            blockers=[{"code": "needs_human_observation"}],
            current={"master": "ableton"},
            desired="Ableton is master",
        )
    )
    assert d.mode is DispatchMode.HUMAN_OBSERVATION
    assert d.provider_eligible is False

def test_agent_eligible_for_manual_without_human_blockers():
    d = classify_reconciliation_dispatch(
        _plan(
            state=ReconciliationState.NEEDS_AGENT_ACTION,
            capability=Capability.MANUAL,
            blockers=[],
            desired="PB-A is ART P48",
        )
    )
    assert d.mode is DispatchMode.AGENT
    assert d.provider_eligible is True

def test_clarification_blocker():
    d = classify_reconciliation_dispatch(
        _plan(
            state=ReconciliationState.NEEDS_AGENT_ACTION,
            blockers=[{"code": "needs_human_clarification"}],
            desired="one of the patchbays is probably the Behringer",
        )
    )
    assert d.mode is DispatchMode.HUMAN_CLARIFICATION
    assert d.provider_eligible is False

@pytest.mark.parametrize("code", sorted(HUMAN_BLOCKER_CODES))
def test_hard_human_blocker_codes_block_provider(code):
    d = classify_reconciliation_dispatch(
        _plan(
            state=ReconciliationState.NEEDS_AGENT_ACTION,
            blockers=[{"code": code}],
        )
    )
    assert d.provider_eligible is False

