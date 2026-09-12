"""midi.clock_master — VERIFY_ONLY (physical practice; do not auto-apply).

Q-014 asks whether Ableton is master *in practice* (KAOSS/SL-2 may lead).
`rig current midi set-clock-master` can document CURRENT, but reconcile apply
must not promote INTENDED→VERIFIED or invent physical verification. Leave
VERIFY_ONLY; agent runs set-clock-master + finalize with --no-current-change
when appropriate.
"""

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
                [
                    {
                        "code": "verify_only",
                        "field": "clock.master",
                        "message": (
                            "midi.clock_master is VERIFY_ONLY (physical practice). "
                            "Use set-clock-master to document CURRENT, then finalize; "
                            "reconcile apply will not auto-write or promote INTENDED→VERIFIED."
                        ),
                        "candidates": [endpoint] if endpoint else [],
                        "suggested_commands": [
                            c
                            for c in cmds
                            if "set-clock-master" in c or "finalize" in c
                        ],
                    }
                ]
                if state == ReconciliationState.NEEDS_AGENT_ACTION
                and question.status == QuestionStatus.RESOLVED
                else []
            ),
            suggested_commands=cmds,
            details={
                "capability_reason": (
                    "Q semantics are physical verification of clock leadership; "
                    "not a pure documented-CURRENT set"
                ),
            },
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
