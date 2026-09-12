"""Fallback for unknown / unsupported target domains."""

from __future__ import annotations

from typing import Any

from music_rig.models import OpenQuestion, QuestionStatus, ReconciliationState
from music_rig.reconciliation.adapters.base import ReconciliationAdapter
from music_rig.reconciliation.types import (
    Capability,
    Plan,
    VerificationStatus,
    VerifyResult,
)


class UnsupportedAdapter(ReconciliationAdapter):
    domain = "unsupported"
    capability = Capability.UNSUPPORTED

    def __init__(self, domain: str | None = None) -> None:
        if domain:
            self.domain = domain

    def read_current(self, question: OpenQuestion, *, paths: dict[str, Any]) -> Any:
        return None

    def plan(self, question: OpenQuestion, *, paths: dict[str, Any]) -> Plan:
        if question.reconciled_at is not None:
            state = ReconciliationState.RECONCILED
        elif question.status != QuestionStatus.RESOLVED or not question.answer.strip():
            state = ReconciliationState.NEEDS_ANSWER
        else:
            state = ReconciliationState.BLOCKED
        domain = (
            question.target.domain
            if question.target and question.target.domain
            else "(none)"
        )
        return Plan(
            artifact_type="question",
            artifact_id=question.id,
            state=state,
            capability=self.capability,
            blockers=[f"Unsupported reconciliation domain: {domain}"],
            suggested_commands=[
                "Add a service+CLI adapter under music_rig.reconciliation.adapters, "
                "then re-run reconcile plan"
            ],
        )

    def verify(self, question: OpenQuestion, *, paths: dict[str, Any]) -> VerifyResult:
        return VerifyResult(
            status=VerificationStatus.BLOCKED,
            message=f"Unsupported domain {self.domain}",
        )
