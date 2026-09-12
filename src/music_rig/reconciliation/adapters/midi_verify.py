"""midi.verify — VERIFY_ONLY topology evidence."""

from __future__ import annotations

from typing import Any

from music_rig import midi_state
from music_rig.models import OpenQuestion, QuestionStatus, ReconciliationState
from music_rig.reconciliation.adapters.base import ReconciliationAdapter
from music_rig.reconciliation.types import (
    Capability,
    Plan,
    VerificationStatus,
    VerifyResult,
)


class MidiVerifyAdapter(ReconciliationAdapter):
    domain = "midi.verify"
    capability = Capability.VERIFY_ONLY

    def read_current(self, question: OpenQuestion, *, paths: dict[str, Any]) -> Any:
        data = midi_state.load_raw(paths.get("midi"))
        devices = data.get("devices") or []
        links = data.get("links") or []
        return {
            "device_count": len(devices) if isinstance(devices, list) else 0,
            "link_count": len(links) if isinstance(links, list) else 0,
            "clock": data.get("clock"),
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
                ["VERIFY_ONLY: inspect midi verify; finalize with --no-current-change"]
                if state == ReconciliationState.NEEDS_AGENT_ACTION
                else []
            ),
            suggested_commands=[
                "uv run rig current midi verify",
                "uv run rig midi summary",
                f"uv run rig reconcile finalize question {question.id} "
                f"--no-current-change --note \"topology reviewed\" --yes",
            ],
        )

    def verify(self, question: OpenQuestion, *, paths: dict[str, Any]) -> VerifyResult:
        return VerifyResult(
            status=VerificationStatus.UNVERIFIABLE,
            current=self.read_current(question, paths=paths),
            expected=question.answer,
            message=(
                "midi.verify is VERIFY_ONLY — freeform answers are not auto-matched; "
                "INTENDED evidence is never promoted to VERIFIED"
            ),
        )
