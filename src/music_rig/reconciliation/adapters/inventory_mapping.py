"""inventory.patchbay_mapping — MANUAL / NEEDS_AGENT_ACTION."""

from __future__ import annotations

from typing import Any

from music_rig import patchbay_state
from music_rig.models import OpenQuestion, QuestionStatus, ReconciliationState
from music_rig.reconciliation.adapters.base import ReconciliationAdapter
from music_rig.reconciliation.types import (
    Capability,
    Plan,
    VerificationStatus,
    VerifyResult,
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
                    "Physical unit→PB letter mapping is MANUAL; "
                    "record observed models via set-model then finalize"
                ]
            ),
            suggested_commands=[
                "uv run rig patchbay list",
                f"uv run rig current patchbay set-model PB-A \"<observed model>\" "
                f"--question {question.id}",
                f"uv run rig reconcile finalize question {question.id} "
                f"--no-current-change --note \"...\" --yes",
            ],
        )

    def verify(self, question: OpenQuestion, *, paths: dict[str, Any]) -> VerifyResult:
        return VerifyResult(
            status=VerificationStatus.UNVERIFIABLE,
            current=self.read_current(question, paths=paths),
            expected=question.answer,
            message="inventory.patchbay_mapping is MANUAL — no automatic CURRENT match",
        )
