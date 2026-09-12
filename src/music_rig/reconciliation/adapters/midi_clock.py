"""midi.clock_master — HUMAN_VERIFY_THEN_APPLY (VERIFY_ONLY compat name).

After explicit CONFIRMED/CORRECTED observation, apply may set master value
and/or promote evidence INTENDED→VERIFIED via midi_state.propose_set_clock_master.
Without verification_result, apply is refused (no invented VERIFIED).
"""

from __future__ import annotations

from typing import Any

from music_rig import current_service, midi_state
from music_rig.models import (
    MidiEvidenceStatus,
    OpenQuestion,
    QuestionStatus,
    ReconciliationState,
    VerificationOutcome,
)
from music_rig.reconciliation.action_packet import (
    build_action_packet,
    has_positive_observation,
)
from music_rig.reconciliation.adapters.base import ReconciliationAdapter
from music_rig.reconciliation.types import (
    Capability,
    Plan,
    PlanOperationKind,
    VerificationStatus,
    VerifyResult,
    op,
)
from music_rig.store import StoreError


def _normalize_endpoint(raw: str) -> str | None:
    cleaned = raw.strip()
    if not cleaned:
        return None
    if any(ch in cleaned for ch in " .?!\n\t"):
        return None
    if len(cleaned.split()) != 1:
        return None
    return cleaned


def _desired_endpoint(question: OpenQuestion) -> str | None:
    vr = question.verification_result
    if vr and vr.observed_value.strip():
        ep = _normalize_endpoint(vr.observed_value)
        if ep:
            return ep
    if question.answer.strip():
        return _normalize_endpoint(question.answer)
    return None


class MidiClockAdapter(ReconciliationAdapter):
    domain = "midi.clock_master"
    capability = Capability.VERIFY_ONLY  # human-verify-then-apply after observation

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
        endpoint = _desired_endpoint(question)
        cur_master = str((current or {}).get("master") or "")
        cur_status = (current or {}).get("status")
        vr = question.verification_result

        if question.reconciled_at is not None:
            state = ReconciliationState.RECONCILED
        elif question.status != QuestionStatus.RESOLVED or not question.answer.strip():
            if vr and vr.outcome == VerificationOutcome.UNKNOWN:
                state = ReconciliationState.NEEDS_ANSWER
            elif vr and vr.outcome == VerificationOutcome.FAILED_TEST:
                state = ReconciliationState.NEEDS_AGENT_ACTION
            else:
                state = ReconciliationState.NEEDS_ANSWER
        elif vr and vr.outcome == VerificationOutcome.FAILED_TEST:
            state = ReconciliationState.NEEDS_AGENT_ACTION
        elif has_positive_observation(question) and endpoint:
            if cur_master == endpoint and cur_status == MidiEvidenceStatus.VERIFIED.value:
                state = ReconciliationState.CURRENT_MATCHES
            else:
                state = ReconciliationState.READY_TO_APPLY
        elif endpoint and cur_master and endpoint == cur_master:
            # Answer matches but no explicit observation → do not auto-verify
            state = ReconciliationState.NEEDS_AGENT_ACTION
        elif endpoint:
            state = ReconciliationState.NEEDS_AGENT_ACTION
        else:
            state = ReconciliationState.NEEDS_AGENT_ACTION

        operations: list[dict[str, Any]] = []
        if has_positive_observation(question) and endpoint:
            if cur_master != endpoint:
                operations.append(
                    op(
                        PlanOperationKind.SET_CURRENT_VALUE,
                        target="midi.clock.master",
                        before=cur_master or None,
                        after=endpoint,
                    )
                )
            if cur_status != MidiEvidenceStatus.VERIFIED.value:
                operations.append(
                    op(
                        PlanOperationKind.SET_EVIDENCE_VERIFIED,
                        target="midi.clock.master",
                        before=cur_status,
                        after=MidiEvidenceStatus.VERIFIED.value,
                    )
                )
            if not operations:
                operations.append(
                    op(
                        PlanOperationKind.NO_CURRENT_CHANGE,
                        note="master already VERIFIED and matches observation",
                    )
                )
        elif vr and vr.outcome == VerificationOutcome.FAILED_TEST:
            operations.append(
                op(
                    PlanOperationKind.RECORD_FAILED_VERIFICATION,
                    note=vr.note or "clock master test failed",
                )
            )
        elif vr and vr.outcome == VerificationOutcome.UNKNOWN:
            operations.append(
                op(PlanOperationKind.NO_CURRENT_CHANGE, note="observation UNKNOWN")
            )

        cmds = [
            "uv run rig current midi verify",
            "uv run rig midi clock",
        ]
        if endpoint:
            cmds.append(
                f"uv run rig current midi set-clock-master {endpoint} "
                f"--question {question.id}"
            )
            cmds.append(
                f"uv run rig reconcile apply question {question.id} --dry-run --json"
            )
        cmds.append(f"uv run rig reconcile finalize question {question.id} --yes")

        blockers: list[Any] = []
        details: dict[str, Any] = {
            "capability_reason": (
                "Physical verification of clock leadership; "
                "VERIFIED only after verification_result CONFIRMED/CORRECTED"
            ),
        }
        if state == ReconciliationState.NEEDS_AGENT_ACTION and (
            question.status == QuestionStatus.RESOLVED
            or (vr and vr.outcome == VerificationOutcome.FAILED_TEST)
        ):
            if not has_positive_observation(question):
                blockers.append(
                    {
                        "code": "needs_human_observation",
                        "field": "verification_result",
                        "message": (
                            "Record explicit observation via "
                            "`rig verify record … --outcome confirmed|corrected` "
                            "before evidence apply."
                        ),
                        "suggested_commands": [
                            f"uv run rig verify record {question.id} "
                            f"--outcome confirmed --value {endpoint or '…'} --yes --json"
                        ],
                    }
                )
            packet = build_action_packet(
                question,
                current_snapshot=current,
                suggested_command_families=[
                    "rig current midi set-clock-master",
                    "rig verify record",
                    "rig reconcile apply",
                    "rig reconcile finalize",
                ],
                postcondition="clock.master matches observed endpoint with status VERIFIED",
            )
            details["action_packet"] = packet

        return Plan(
            artifact_type="question",
            artifact_id=question.id,
            state=state,
            capability=self.capability,
            current=current,
            desired=endpoint or (question.answer.strip() or None),
            operations=operations,
            blockers=blockers,
            suggested_commands=cmds,
            postconditions=(
                [f"clock.master == {endpoint} AND status == VERIFIED"]
                if endpoint
                else []
            ),
            closable=list(question.related_todos) + list(question.related_changes),
            details=details,
        )

    def apply(
        self,
        question: OpenQuestion,
        *,
        paths: dict[str, Any],
        dry_run: bool = True,
        yes: bool = False,
    ) -> dict[str, Any]:
        if not has_positive_observation(question):
            raise StoreError(
                f"{question.id} midi.clock_master apply requires "
                "verification_result CONFIRMED or CORRECTED"
            )
        if not yes and not dry_run:
            raise StoreError("apply requires --yes (or --dry-run)")
        endpoint = _desired_endpoint(question)
        if not endpoint:
            raise StoreError("Cannot apply clock master without a normalized endpoint")
        preview, data = midi_state.propose_set_clock_master(
            endpoint,
            status=MidiEvidenceStatus.VERIFIED,
            midi_path=paths.get("midi"),
        )
        if dry_run:
            return {
                "applied": False,
                "dry_run": True,
                "preview": preview.model_dump(mode="json"),
            }
        from music_rig import store as store_mod

        committed = current_service.commit_midi(
            data,
            preview,
            dry_run=False,
            render=False,
            question_id=question.id,
            resolve_q=False,
            midi_path=paths.get("midi") or store_mod.MIDI_PATH,
            questions_path=paths.get("questions") or store_mod.QUESTIONS_PATH,
            changes_path=paths.get("changes") or store_mod.CHANGES_PATH,
        )
        return {
            "applied": committed.changed,
            "dry_run": False,
            "preview": committed.model_dump(mode="json"),
        }

    def verify(self, question: OpenQuestion, *, paths: dict[str, Any]) -> VerifyResult:
        current = self.read_current(question, paths=paths)
        if question.verification_result and (
            question.verification_result.outcome == VerificationOutcome.FAILED_TEST
        ):
            return VerifyResult(
                status=VerificationStatus.MISMATCH,
                current=current,
                expected=_desired_endpoint(question),
                message="FAILED_TEST observation — not verified",
            )
        endpoint = _desired_endpoint(question)
        if endpoint is None:
            return VerifyResult(
                status=VerificationStatus.UNVERIFIABLE,
                current=current,
                expected=question.answer,
                message="Answer/observation is not a single endpoint id",
            )
        cur = str((current or {}).get("master") or "")
        status = (current or {}).get("status")
        if cur == endpoint and status == MidiEvidenceStatus.VERIFIED.value:
            return VerifyResult(
                status=VerificationStatus.MATCH,
                current=current,
                expected=endpoint,
                message=f"clock master {endpoint} is VERIFIED",
            )
        if cur == endpoint and has_positive_observation(question):
            return VerifyResult(
                status=VerificationStatus.MISMATCH,
                current=current,
                expected=endpoint,
                message=f"master matches but evidence is {status!r}, expected VERIFIED",
            )
        if cur == endpoint:
            return VerifyResult(
                status=VerificationStatus.UNVERIFIABLE,
                current=current,
                expected=endpoint,
                message=(
                    "master matches answer but no CONFIRMED/CORRECTED observation; "
                    "INTENDED is not auto-promoted"
                ),
            )
        return VerifyResult(
            status=VerificationStatus.MISMATCH,
            current=current,
            expected=endpoint,
            message=f"clock master is {cur!r}, expected {endpoint!r}",
        )
