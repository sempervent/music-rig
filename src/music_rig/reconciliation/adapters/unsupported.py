"""Fallback for unknown / unsupported target domains."""

from __future__ import annotations

from typing import Any

from music_rig.models import OpenQuestion, QuestionStatus, ReconciliationState
from music_rig.reconciliation.action_packet import build_action_packet
from music_rig.reconciliation.adapters.base import ReconciliationAdapter
from music_rig.reconciliation.types import (
    Capability,
    Plan,
    PlanOperationKind,
    VerificationStatus,
    VerifyResult,
    op,
)

# Stage 17 MANUAL backlog classification (production Qs without APPLY adapters)
MANUAL_CLASSIFICATION: dict[str, str] = {
    "Q-001": "GENUINELY_AGENT_INTERPRETED",
    "Q-002": "GENUINELY_AGENT_INTERPRETED",
    "Q-003": "GENUINELY_AGENT_INTERPRETED",
    "Q-005": "GENUINELY_DESCRIPTIVE",
    "Q-006": "GENUINELY_DESCRIPTIVE",
    "Q-007": "NEEDS_SMALL_SERVICE",
    "Q-009": "GENUINELY_AGENT_INTERPRETED",
    "Q-010": "GENUINELY_AGENT_INTERPRETED",
    "Q-011": "GENUINELY_DESCRIPTIVE",
    "Q-012": "STRUCTURABLE_NOW",  # inventory.location + set-location per gear
    "Q-013": "NEEDS_SMALL_SERVICE",
    "Q-019": "GENUINELY_DESCRIPTIVE",
    "Q-020": "GENUINELY_DESCRIPTIVE",
}

_COMMAND_FAMILIES_BY_KIND: dict[str, list[str]] = {
    "ROUTING_VISUAL": ["rig path show", "rig current path", "rig inspect"],
    "MANUAL_FACT": ["rig inspect", "rig question answer", "rig change add"],
    "BOARD_COMPARE": ["rig path show", "rig inspect"],
    "INVENTORY_LOCATION": ["rig current gear set-location", "rig gear show"],
    "POWER_AUDIT": ["rig gear show", "rig inspect"],
    "CAMERA_AUDIT": ["rig inspect"],
    "WORKFLOW": ["rig inspect", "rig performance"],
    "PATCHBAY_UNIT": [
        "rig current patchbay set-model",
        "rig patchbay show",
        "rig gear list",
    ],
}


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
        elif question.status == QuestionStatus.OPEN and question.answer.strip():
            state = ReconciliationState.DRAFT_ANSWER
        elif question.status != QuestionStatus.RESOLVED or not question.answer.strip():
            state = ReconciliationState.NEEDS_ANSWER
        else:
            state = ReconciliationState.NEEDS_AGENT_ACTION

        domain = (
            question.target.domain
            if question.target and question.target.domain
            else "(none)"
        )
        kind = question.verification.kind if question.verification else ""
        families = list(
            _COMMAND_FAMILIES_BY_KIND.get(
                kind, ["rig inspect", "rig current", "rig path show"]
            )
        )
        # Prefer CURRENT mutation families for agent-interpreted recon
        if "rig current" not in " ".join(families):
            families = ["rig current path", "rig current channels", *families]
        classification = MANUAL_CLASSIFICATION.get(
            question.id, "GENUINELY_AGENT_INTERPRETED"
        )
        missing = None
        if classification in {"NEEDS_SMALL_SERVICE", "GENUINELY_DESCRIPTIVE"}:
            if domain == "(none)" and classification == "NEEDS_SMALL_SERVICE":
                missing = (
                    f"no CURRENT entrypoint for {question.id} / "
                    f"{kind or 'unknown kind'}"
                )
        elif classification == "STRUCTURABLE_NOW" and kind == "INVENTORY_LOCATION":
            families = [
                "rig current gear set-location",
                "rig gear show",
                "rig question target set",
            ]

        details: dict[str, Any] = {
            "manual_classification": classification,
        }
        if state == ReconciliationState.NEEDS_AGENT_ACTION:
            details["action_packet"] = build_action_packet(
                question,
                current_snapshot=None,
                suggested_command_families=families,
                postcondition=(
                    "Canonical CURRENT updated via supported rig CLI to reflect "
                    "the final human answer; then finalize with "
                    "--confirm-current-reconciled (not physical verification)"
                ),
                missing_capability=missing,
            )
            details["requires_agent_interpretation"] = True
            details["manual_finalize_allowed"] = True
            details["required_confirmation"] = "--confirm-current-reconciled"

        if state == ReconciliationState.DRAFT_ANSWER:
            from music_rig.reconciliation.suggestions import (
                suggest_answer,
                suggest_resolve,
            )

            suggestions = [
                suggest_resolve(question.id),
                suggest_answer(question.id),
            ]
            blockers: list[Any] = [
                {
                    "code": "draft_answer",
                    "message": (
                        "OPEN with draft answer — resolve before reconcile"
                    ),
                }
            ]
        elif state == ReconciliationState.NEEDS_AGENT_ACTION:
            from music_rig.reconciliation.suggestions import (
                suggest_finalize,
                suggest_plan,
            )

            suggestions = [
                suggest_plan(question.id),
                suggest_finalize(
                    question.id, confirm_current_reconciled=True, note="…"
                ),
            ]
            blockers = [
                {
                    "code": "needs_agent_action",
                    "message": (
                        f"Needs agent reconciliation (manual interpretation): "
                        f"{domain}"
                    ),
                    "classification": classification,
                }
            ]
        else:
            from music_rig.reconciliation.suggestions import suggest_plan

            suggestions = [suggest_plan(question.id)]
            blockers = []

        return Plan(
            artifact_type="question",
            artifact_id=question.id,
            state=state,
            capability=self.capability,
            operations=[
                op(
                    PlanOperationKind.NO_CURRENT_CHANGE,
                    note="agent interprets freeform / descriptive answer",
                )
            ]
            if state == ReconciliationState.NEEDS_AGENT_ACTION
            else [],
            blockers=blockers,
            suggestions=suggestions,
            details=details,
        )

    def verify(self, question: OpenQuestion, *, paths: dict[str, Any]) -> VerifyResult:
        return VerifyResult(
            status=VerificationStatus.BLOCKED,
            message=f"Unsupported domain {self.domain}",
        )
