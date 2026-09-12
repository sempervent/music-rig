"""midi.verify — topology evidence; link-scoped only (never whole topology)."""

from __future__ import annotations

from typing import Any

from music_rig import midi_state
from music_rig.models import (
    OpenQuestion,
    QuestionStatus,
    ReconciliationState,
    VerificationOutcome,
)
from music_rig.reconciliation.action_packet import build_action_packet, has_positive_observation
from music_rig.reconciliation.adapters.base import ReconciliationAdapter
from music_rig.reconciliation.suggestions import (
    ActionSuggestion,
    SuggestionKind,
    suggest_finalize,
)
from music_rig.reconciliation.types import (
    Capability,
    Plan,
    PlanOperationKind,
    VerificationStatus,
    VerifyResult,
    op,
)


def _link_id(question: OpenQuestion) -> str | None:
    """Use target.path as link id when sufficiently specific."""
    if question.target and question.target.path:
        pid = question.target.path.strip()
        if pid.startswith("midi-link-") or pid.startswith("link-"):
            return pid
    return None


class MidiVerifyAdapter(ReconciliationAdapter):
    domain = "midi.verify"
    capability = Capability.VERIFY_ONLY

    def read_current(self, question: OpenQuestion, *, paths: dict[str, Any]) -> Any:
        data = midi_state.load_raw(paths.get("midi"))
        devices = data.get("devices") or []
        # Canonical schema uses connections; older fixtures may use links
        links = data.get("connections") or data.get("links") or []
        link_id = _link_id(question)
        snapshot: dict[str, Any] = {
            "device_count": len(devices) if isinstance(devices, list) else 0,
            "link_count": len(links) if isinstance(links, list) else 0,
            "clock": data.get("clock"),
        }
        if link_id and isinstance(links, list):
            match = next(
                (
                    L
                    for L in links
                    if isinstance(L, dict) and L.get("id") == link_id
                ),
                None,
            )
            snapshot["link_id"] = link_id
            snapshot["link"] = match
            snapshot["link_status"] = (match or {}).get("status") if match else None
        return snapshot

    def plan(self, question: OpenQuestion, *, paths: dict[str, Any]) -> Plan:
        current = self.read_current(question, paths=paths)
        link_id = _link_id(question)
        vr = question.verification_result

        if question.reconciled_at is not None:
            state = ReconciliationState.RECONCILED
        elif question.status == QuestionStatus.OPEN and question.answer.strip():
            state = ReconciliationState.DRAFT_ANSWER
        elif question.status != QuestionStatus.RESOLVED or not question.answer.strip():
            if vr and vr.outcome == VerificationOutcome.FAILED_TEST:
                state = ReconciliationState.NEEDS_AGENT_ACTION
            else:
                state = ReconciliationState.NEEDS_ANSWER
        else:
            # Even with observation, gear-level midi.verify stays agent unless link-scoped
            state = ReconciliationState.NEEDS_AGENT_ACTION

        operations: list[dict[str, Any]] = []
        if vr and vr.outcome == VerificationOutcome.FAILED_TEST:
            operations.append(
                op(PlanOperationKind.RECORD_FAILED_VERIFICATION, note=vr.note or "")
            )
        elif has_positive_observation(question) and not link_id:
            operations.append(
                op(
                    PlanOperationKind.NO_CURRENT_CHANGE,
                    note=(
                        "midi.verify observation recorded; "
                        "do NOT mark whole topology VERIFIED — need link id target"
                    ),
                )
            )
        elif has_positive_observation(question) and link_id:
            operations.append(
                op(
                    PlanOperationKind.SET_EVIDENCE_VERIFIED,
                    target=f"midi.link:{link_id}",
                    before=current.get("link_status"),
                    after="VERIFIED",
                    note="link-scoped only",
                )
            )

        missing = None
        if has_positive_observation(question) and not link_id:
            missing = (
                "midi.verify evidence apply requires target.path = midi-link-NNN; "
                "one cable check ≠ whole topology VERIFIED"
            )

        details = {
            "action_packet": build_action_packet(
                question,
                current_snapshot=current,
                suggested_command_families=[
                    "rig current midi verify",
                    "rig midi summary",
                    "rig question target set",
                    "rig verify record",
                ],
                postcondition=(
                    f"link {link_id} status == VERIFIED"
                    if link_id
                    else "scoped link VERIFIED (never whole topology)"
                ),
                missing_capability=missing,
            )
        }

        return Plan(
            artifact_type="question",
            artifact_id=question.id,
            state=state,
            capability=self.capability,
            current=current,
            desired=question.answer.strip() or None,
            operations=operations,
            blockers=(
                [
                    {
                        "code": "missing_target_field" if missing else "needs_agent_action",
                        "field": "path",
                        "message": missing
                        or "Inspect midi topology; finalize with --no-current-change",
                    }
                ]
                if state == ReconciliationState.NEEDS_AGENT_ACTION
                and (
                    question.status == QuestionStatus.RESOLVED
                    or (vr and vr.outcome == VerificationOutcome.FAILED_TEST)
                )
                else []
            ),
            suggestions=[
                ActionSuggestion(
                    kind=SuggestionKind.VERIFY,
                    intent="current midi verify",
                    description="Inspect MIDI topology evidence",
                    code="midi_verify",
                ),
                ActionSuggestion(
                    kind=SuggestionKind.INSPECT,
                    intent="midi summary",
                    description="Show MIDI summary",
                    code="midi_summary",
                ),
                suggest_finalize(
                    question.id,
                    no_current_change=True,
                    note="topology reviewed",
                ),
            ],
            details=details,
        )

    def verify(self, question: OpenQuestion, *, paths: dict[str, Any]) -> VerifyResult:
        current = self.read_current(question, paths=paths)
        if question.verification_result and (
            question.verification_result.outcome == VerificationOutcome.FAILED_TEST
        ):
            return VerifyResult(
                status=VerificationStatus.MISMATCH,
                current=current,
                message="FAILED_TEST — topology check failed",
            )
        link_id = _link_id(question)
        if (
            has_positive_observation(question)
            and link_id
            and current.get("link_status") == "VERIFIED"
        ):
            return VerifyResult(
                status=VerificationStatus.MATCH,
                current=current,
                expected="VERIFIED",
                message=f"link {link_id} VERIFIED",
            )
        return VerifyResult(
            status=VerificationStatus.UNVERIFIABLE,
            current=current,
            expected=question.answer,
            message=(
                "midi.verify — freeform answers are not auto-matched; "
                "INTENDED evidence is never promoted to VERIFIED for whole topology"
            ),
        )
