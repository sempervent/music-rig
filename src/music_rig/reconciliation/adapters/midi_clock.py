"""midi.clock_master — VERIFY_ONLY; set-clock-master → NEEDS_AGENT_ACTION."""

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


def _normalize_endpoint(raw: str) -> str | None:
    """Accept bare endpoint ids only (slug-like). Reject prose."""
    cleaned = raw.strip()
    if not cleaned:
        return None
    # Deterministic: single token / slug, no spaces or sentence punctuation
    if any(ch in cleaned for ch in " .?!\n\t"):
        return None
    if len(cleaned.split()) != 1:
        return None
    return cleaned


class MidiClockAdapter(ReconciliationAdapter):
    domain = "midi.clock_master"
    capability = Capability.VERIFY_ONLY

    def read_current(self, question: OpenQuestion, *, paths: dict[str, Any]) -> Any:
        data = midi_state.load_raw(paths.get("midi"))
        clock = data.get("clock") if isinstance(data.get("clock"), dict) else {}
        master = clock.get("master") if isinstance(clock.get("master"), dict) else {}
        endpoint = (
            master.get("endpoint_ref")
            or master.get("gear_ref")
            or master.get("device_ref")
        )
        return {
            "master": endpoint,
            "status": master.get("status"),
            "notes": master.get("notes"),
            "raw_master": master or None,
        }

    def plan(self, question: OpenQuestion, *, paths: dict[str, Any]) -> Plan:
        current = self.read_current(question, paths=paths)
        if question.reconciled_at is not None:
            state = ReconciliationState.RECONCILED
        elif question.status != QuestionStatus.RESOLVED or not question.answer.strip():
            state = ReconciliationState.NEEDS_ANSWER
        else:
            endpoint = _normalize_endpoint(question.answer)
            cur_master = (current or {}).get("master")
            if endpoint and cur_master and endpoint == str(cur_master):
                state = ReconciliationState.CURRENT_MATCHES
            elif endpoint:
                state = ReconciliationState.NEEDS_AGENT_ACTION
            else:
                state = ReconciliationState.NEEDS_AGENT_ACTION
        endpoint = _normalize_endpoint(question.answer) if question.answer.strip() else None
        cmds = [
            "uv run rig current midi verify",
            "uv run rig midi clock",
        ]
        if endpoint and state == ReconciliationState.NEEDS_AGENT_ACTION:
            cmds.append(
                f"uv run rig current midi set-clock-master {endpoint} "
                f"--question {question.id}"
            )
        cmds.append(f"uv run rig reconcile finalize question {question.id} --yes")
        return Plan(
            artifact_type="question",
            artifact_id=question.id,
            state=state,
            capability=self.capability,
            current=current,
            desired=endpoint or question.answer.strip() or None,
            blockers=(
                ["Use set-clock-master CLI then verify; adapter is VERIFY_ONLY"]
                if state == ReconciliationState.NEEDS_AGENT_ACTION
                and question.status == QuestionStatus.RESOLVED
                else []
            ),
            suggested_commands=cmds,
        )

    def verify(self, question: OpenQuestion, *, paths: dict[str, Any]) -> VerifyResult:
        current = self.read_current(question, paths=paths)
        endpoint = _normalize_endpoint(question.answer) if question.answer.strip() else None
        if endpoint is None:
            return VerifyResult(
                status=VerificationStatus.UNVERIFIABLE,
                current=current,
                expected=question.answer,
                message="Answer is not a single endpoint id (reject prose)",
            )
        cur = str((current or {}).get("master") or "")
        if cur == endpoint:
            return VerifyResult(
                status=VerificationStatus.MATCH,
                current=current,
                expected=endpoint,
                message=f"clock master is {endpoint}",
            )
        return VerifyResult(
            status=VerificationStatus.MISMATCH,
            current=current,
            expected=endpoint,
            message=f"clock master is {cur!r}, expected {endpoint!r}",
        )
