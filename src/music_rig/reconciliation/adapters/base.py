"""Base adapter protocol for reconciliation domains."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from music_rig.models import OpenQuestion, ReconciliationState
from music_rig.reconciliation.types import Capability, Plan, VerifyResult


class ReconciliationAdapter(ABC):
    domain: str
    capability: Capability

    @abstractmethod
    def read_current(self, question: OpenQuestion, *, paths: dict[str, Any]) -> Any:
        """Return CURRENT value at the question target (deterministic)."""

    @abstractmethod
    def plan(self, question: OpenQuestion, *, paths: dict[str, Any]) -> Plan:
        """Build a no-write plan for the question."""

    def apply(
        self,
        question: OpenQuestion,
        *,
        paths: dict[str, Any],
        dry_run: bool = True,
        yes: bool = False,
    ) -> dict[str, Any]:
        raise NotImplementedError(
            f"{self.domain} does not support apply (capability={self.capability.value})"
        )

    @abstractmethod
    def verify(self, question: OpenQuestion, *, paths: dict[str, Any]) -> VerifyResult:
        """Compare answer / desired to CURRENT. Never promotes INTENDED→VERIFIED."""

    def derive_state(
        self,
        question: OpenQuestion,
        *,
        paths: dict[str, Any],
        plan: Plan | None = None,
    ) -> ReconciliationState:
        if question.reconciled_at is not None:
            return ReconciliationState.RECONCILED
        from music_rig.models import QuestionStatus

        if question.status == QuestionStatus.OPEN and not question.answer.strip():
            return ReconciliationState.NEEDS_ANSWER
        p = plan or self.plan(question, paths=paths)
        return p.state
