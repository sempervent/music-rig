"""inventory.patchbay_mapping — MANUAL / NEEDS_AGENT_ACTION."""

from __future__ import annotations

from typing import Any

from music_rig import patchbay_state
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


class InventoryMappingAdapter(ReconciliationAdapter):
    domain = "inventory.patchbay_mapping"
    capability = Capability.MANUAL

    def read_current(self, question: OpenQuestion, *, paths: dict[str, Any]) -> Any:
        data = patchbay_state.load_raw(paths.get("patchbays"))
        bays = data.get("patchbays") or {}
        return {
            bay_id: {
                "hardware_model": (body or {}).get("hardware_model"),
                "status": (body or {}).get("status"),
            }
            for bay_id, body in sorted(bays.items())
            if isinstance(body, dict)
        }

    def plan(self, question: OpenQuestion, *, paths: dict[str, Any]) -> Plan:
        current = self.read_current(question, paths=paths)
        if question.reconciled_at is not None:
            state = ReconciliationState.RECONCILED
        elif question.status == QuestionStatus.OPEN and question.answer.strip():
            state = ReconciliationState.DRAFT_ANSWER
        elif question.status != QuestionStatus.RESOLVED or not question.answer.strip():
            state = ReconciliationState.NEEDS_ANSWER
        else:
            state = ReconciliationState.NEEDS_AGENT_ACTION
        return Plan(
            artifact_type="question",
            artifact_id=question.id,
            state=state,
            capability=self.capability,
            current=current,
            desired=question.answer.strip() or None,
            blockers=(
                []
                if state != ReconciliationState.NEEDS_AGENT_ACTION
                else [
                    {
                        "code": "manual_inventory_mapping",
                        "field": "hardware_model",
                        "message": (
                            "Physical unit→PB letter mapping is MANUAL. "
                            "Patchbays expose hardware_model (free text) only — "
                            "no gear_ref field yet; APPLY_AND_VERIFY / "
                            "rig current patchbay set-gear is not available. "
                            "Record observed models via set-model then finalize."
                        ),
                        "candidates": sorted(
                            [
                                bid
                                for bid, body in (
                                    (patchbay_state.load_raw(paths.get("patchbays")).get("patchbays") or {})
                                ).items()
                                if isinstance(body, dict)
                            ]
                        ),
                        "suggested_commands": [
                            "uv run rig patchbay list",
                            f"uv run rig current patchbay set-model PB-A "
                            f"\"<observed model>\" --question {question.id}",
                            f"uv run rig reconcile finalize question {question.id} "
                            f"--no-current-change --note \"...\" --yes",
                        ],
                    }
                ]
            ),
            suggested_commands=[
                "uv run rig patchbay list",
                f"uv run rig current patchbay set-model PB-A \"<observed model>\" "
                f"--question {question.id}",
                f"uv run rig reconcile finalize question {question.id} "
                f"--no-current-change --note \"...\" --yes",
            ],
            details={
                "gap": (
                    "inventory.patchbay_mapping stays MANUAL until patchbay "
                    "schema gains an optional gear_ref / set-gear CURRENT mutation"
                ),
                "manual_classification": "NEEDS_SMALL_SERVICE",
                "action_packet": build_action_packet(
                    question,
                    current_snapshot=current,
                    suggested_command_families=[
                        "rig current patchbay set-model",
                        "rig patchbay list",
                        "rig gear list",
                        "rig reconcile finalize",
                    ],
                    postcondition="each PB letter hardware_model matches observed unit",
                    missing_capability=(
                        "patchbay gear_ref / set-gear not available yet"
                    ),
                )
                if state == ReconciliationState.NEEDS_AGENT_ACTION
                else None,
            },
            operations=[
                op(
                    PlanOperationKind.NO_CURRENT_CHANGE,
                    note="use set-model then finalize — no auto gear_ref bind",
                )
            ]
            if state == ReconciliationState.NEEDS_AGENT_ACTION
            else [],
        )

    def verify(self, question: OpenQuestion, *, paths: dict[str, Any]) -> VerifyResult:
        return VerifyResult(
            status=VerificationStatus.UNVERIFIABLE,
            current=self.read_current(question, paths=paths),
            expected=question.answer,
            message="inventory.patchbay_mapping is MANUAL — no automatic CURRENT match",
        )
