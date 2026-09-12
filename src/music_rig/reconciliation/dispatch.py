"""Authoritative reconciliation dispatch — who can make progress next."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from music_rig.models import ReconciliationState
from music_rig.reconciliation.types import Capability, Plan

# Blockers that only a human can satisfy — never invoke a provider.
HUMAN_BLOCKER_CODES = frozenset(
    {
        "needs_human_observation",
        "needs_human_answer",
        "needs_human_clarification",
        "needs_dod_confirmation",
        "physical_verification_required",
        "needs_answer",
        "draft_answer",
    }
)

OBSERVATION_CODES = frozenset(
    {
        "needs_human_observation",
        "physical_verification_required",
    }
)

CLARIFICATION_CODES = frozenset(
    {
        "needs_human_clarification",
    }
)

ANSWER_CODES = frozenset(
    {
        "needs_human_answer",
        "needs_answer",
        "draft_answer",
    }
)


class DispatchMode(str, Enum):
    DONE = "DONE"
    HUMAN_ANSWER = "HUMAN_ANSWER"
    HUMAN_OBSERVATION = "HUMAN_OBSERVATION"
    HUMAN_CLARIFICATION = "HUMAN_CLARIFICATION"
    DETERMINISTIC = "DETERMINISTIC"
    FINALIZE = "FINALIZE"
    AGENT = "AGENT"
    BLOCKED = "BLOCKED"


class NextActor(str, Enum):
    NONE = "NONE"
    HUMAN_ANSWER = "HUMAN_ANSWER"
    HUMAN_OBSERVATION = "HUMAN_OBSERVATION"
    HUMAN_CLARIFICATION = "HUMAN_CLARIFICATION"
    AGENT = "AGENT"
    DETERMINISTIC_ENGINE = "DETERMINISTIC_ENGINE"
    FINALIZER = "FINALIZER"


@dataclass(frozen=True, slots=True)
class ReconciliationDispatch:
    mode: DispatchMode
    reason: str
    next_actor: NextActor
    human_blocker_codes: tuple[str, ...] = ()
    value_match: bool | None = None

    @property
    def provider_eligible(self) -> bool:
        return self.mode is DispatchMode.AGENT

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "reason": self.reason,
            "next_actor": self.next_actor.value,
            "human_blocker_codes": list(self.human_blocker_codes),
            "value_match": self.value_match,
            "provider_eligible": self.provider_eligible,
        }


def _blocker_codes(plan: Plan) -> list[str]:
    codes: list[str] = []
    for b in plan.blockers or []:
        if isinstance(b, dict):
            code = str(b.get("code") or "").strip()
            if code:
                codes.append(code)
        elif isinstance(b, str):
            low = b.casefold()
            if "observation" in low or "verification_result" in low:
                codes.append("needs_human_observation")
            elif "clarif" in low:
                codes.append("needs_human_clarification")
            elif "answer" in low:
                codes.append("needs_human_answer")
    return codes


def _infer_value_match(plan: Plan) -> bool | None:
    """Best-effort: MATCH when CURRENT value aligns with final answer tokens."""
    current = plan.current
    desired = str(plan.desired or "")
    if current is None or not desired.strip():
        return None
    if isinstance(current, dict):
        master = current.get("master") or current.get("endpoint_ref")
        if master:
            if str(master).casefold() in desired.casefold():
                return True
            return False
    if isinstance(current, str) and current.strip():
        return current.casefold() in desired.casefold()
    return None


def classify_reconciliation_dispatch(plan: Plan) -> ReconciliationDispatch:
    """Decide who acts next. Explicit blockers outrank coarse state labels.

    VERIFY_ONLY alone does NOT imply HUMAN_OBSERVATION — that requires an
    explicit observation blocker from verification policy.
    """
    state = plan.state
    codes = _blocker_codes(plan)
    human_codes = tuple(c for c in codes if c in HUMAN_BLOCKER_CODES)
    value_match = _infer_value_match(plan)

    if state is ReconciliationState.RECONCILED:
        return ReconciliationDispatch(
            mode=DispatchMode.DONE,
            reason="already reconciled",
            next_actor=NextActor.NONE,
            value_match=value_match,
        )

    if state is ReconciliationState.NEEDS_ANSWER or any(c in ANSWER_CODES for c in codes):
        return ReconciliationDispatch(
            mode=DispatchMode.HUMAN_ANSWER,
            reason="final human answer required",
            next_actor=NextActor.HUMAN_ANSWER,
            human_blocker_codes=human_codes or ("needs_human_answer",),
            value_match=value_match,
        )

    if state is ReconciliationState.DRAFT_ANSWER:
        return ReconciliationDispatch(
            mode=DispatchMode.HUMAN_ANSWER,
            reason="draft answer must be resolved to FINAL by a human",
            next_actor=NextActor.HUMAN_ANSWER,
            human_blocker_codes=human_codes or ("draft_answer",),
            value_match=value_match,
        )

    # Explicit observation blockers only (policy-driven)
    if any(c in OBSERVATION_CODES for c in codes):
        return ReconciliationDispatch(
            mode=DispatchMode.HUMAN_OBSERVATION,
            reason="explicit human observation/test required",
            next_actor=NextActor.HUMAN_OBSERVATION,
            human_blocker_codes=human_codes,
            value_match=value_match,
        )

    if any(c in CLARIFICATION_CODES for c in codes):
        return ReconciliationDispatch(
            mode=DispatchMode.HUMAN_CLARIFICATION,
            reason="human clarification required",
            next_actor=NextActor.HUMAN_CLARIFICATION,
            human_blocker_codes=human_codes,
            value_match=value_match,
        )

    if any(c == "needs_dod_confirmation" for c in codes):
        return ReconciliationDispatch(
            mode=DispatchMode.HUMAN_CLARIFICATION,
            reason="definition-of-done confirmation required",
            next_actor=NextActor.HUMAN_CLARIFICATION,
            human_blocker_codes=human_codes,
            value_match=value_match,
        )

    if state is ReconciliationState.READY_TO_APPLY:
        return ReconciliationDispatch(
            mode=DispatchMode.DETERMINISTIC,
            reason="deterministic adapter can apply",
            next_actor=NextActor.DETERMINISTIC_ENGINE,
            value_match=value_match,
        )

    if state in {
        ReconciliationState.CURRENT_MATCHES,
        ReconciliationState.READY_TO_FINALIZE,
    }:
        return ReconciliationDispatch(
            mode=DispatchMode.FINALIZE,
            reason="CURRENT matches; finalize when guards satisfied",
            next_actor=NextActor.FINALIZER,
            value_match=True if value_match is None else value_match,
        )

    if state is ReconciliationState.NEEDS_AGENT_ACTION or plan.capability in {
        Capability.MANUAL,
        Capability.UNSUPPORTED,
    }:
        return ReconciliationDispatch(
            mode=DispatchMode.AGENT,
            reason="agent interpretation can map CURRENT operations",
            next_actor=NextActor.AGENT,
            value_match=value_match,
        )

    if state is ReconciliationState.BLOCKED:
        return ReconciliationDispatch(
            mode=DispatchMode.BLOCKED,
            reason="blocked",
            next_actor=NextActor.NONE,
            human_blocker_codes=human_codes,
            value_match=value_match,
        )

    return ReconciliationDispatch(
        mode=DispatchMode.BLOCKED,
        reason=f"unsupported state {state.value}",
        next_actor=NextActor.NONE,
        human_blocker_codes=human_codes,
        value_match=value_match,
    )
