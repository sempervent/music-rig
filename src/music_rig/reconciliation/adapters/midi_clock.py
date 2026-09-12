"""midi.clock_master — human attestation or explicit observation.

Human FINAL answers (answer_actor=HUMAN) are factual attestation under
MIDI_CLOCK ANSWER_ATTESTATION_SUFFICIENT policy. Explicit verification_result
remains supported for behavioral/post-change observation workflows.
Never invent verification_result; evidence basis is derived separately.
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
    has_apply_authority,
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
from music_rig.verification_policy import (
    VerificationPolicy,
    evidence_basis_for,
    has_bot_answer,
    verification_policy_for,
)


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
    answer = question.answer.strip()
    if not answer:
        return None
    ep = _normalize_endpoint(answer)
    if ep:
        return ep
    # Match verification ENUM choices mentioned in prose answers
    choices = (
        list(question.verification.choices)
        if question.verification and question.verification.choices
        else []
    )
    low = answer.casefold()
    hits = [str(c) for c in choices if str(c).upper() != "UNKNOWN" and str(c).casefold() in low]
    if len(hits) == 1:
        return hits[0]
    return None


class MidiClockAdapter(ReconciliationAdapter):
    domain = "midi.clock_master"
    capability = Capability.VERIFY_ONLY

    def read_current(self, question: OpenQuestion, *, paths: dict[str, Any]) -> Any:
        data = midi_state.load_raw(paths.get("midi"))
        clock = data.get("clock") if isinstance(data.get("clock"), dict) else {}
        master = clock.get("master") if isinstance(clock.get("master"), dict) else {}
        endpoint = master.get("endpoint_ref") or master.get("gear_ref") or master.get("device_ref")
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
        policy = verification_policy_for(question)
        basis = evidence_basis_for(question)
        authority = has_apply_authority(question)

        if question.reconciled_at is not None:
            state = ReconciliationState.RECONCILED
        elif question.status == QuestionStatus.OPEN and question.answer.strip():
            state = ReconciliationState.DRAFT_ANSWER
        elif question.status != QuestionStatus.RESOLVED or not question.answer.strip():
            if vr and vr.outcome == VerificationOutcome.UNKNOWN:
                state = ReconciliationState.NEEDS_ANSWER
            elif vr and vr.outcome == VerificationOutcome.FAILED_TEST:
                state = ReconciliationState.NEEDS_AGENT_ACTION
            else:
                state = ReconciliationState.NEEDS_ANSWER
        elif vr and vr.outcome == VerificationOutcome.FAILED_TEST:
            state = ReconciliationState.NEEDS_AGENT_ACTION
        elif has_bot_answer(question):
            # Bot text is not human authority
            state = ReconciliationState.NEEDS_ANSWER
        elif authority and endpoint:
            if cur_master == endpoint and cur_status == MidiEvidenceStatus.VERIFIED.value:
                state = ReconciliationState.CURRENT_MATCHES
            else:
                state = ReconciliationState.READY_TO_APPLY
        elif (
            policy is VerificationPolicy.EXPLICIT_OBSERVATION_REQUIRED
            and not has_positive_observation(question)
        ):
            state = ReconciliationState.NEEDS_AGENT_ACTION
        elif endpoint and not authority:
            # Human/legacy answer exists but lacks attestation authority for evidence
            state = ReconciliationState.NEEDS_AGENT_ACTION
        elif endpoint:
            state = ReconciliationState.NEEDS_AGENT_ACTION
        else:
            # Prose answer needs agent interpretation / clarification
            state = ReconciliationState.NEEDS_AGENT_ACTION

        operations: list[dict[str, Any]] = []
        if authority and endpoint:
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
                        note=f"evidence_basis={basis.value}",
                    )
                )
            if not operations:
                operations.append(
                    op(
                        PlanOperationKind.NO_CURRENT_CHANGE,
                        note="master already VERIFIED and matches attested/observed value",
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
            operations.append(op(PlanOperationKind.NO_CURRENT_CHANGE, note="observation UNKNOWN"))

        from music_rig.reconciliation.suggestions import (
            ActionSuggestion,
            SuggestionKind,
            render_suggestions,
            suggest_answer,
            suggest_finalize,
            suggest_verify_record,
        )

        suggestions: list[ActionSuggestion] = [
            ActionSuggestion(
                kind=SuggestionKind.VERIFY,
                intent="current midi verify",
                description="Inspect MIDI clock / topology evidence",
                code="midi_verify",
            ),
            ActionSuggestion(
                kind=SuggestionKind.INSPECT,
                intent="midi clock",
                description="Show MIDI clock master",
                code="midi_clock",
            ),
        ]
        if endpoint:
            suggestions.append(
                ActionSuggestion(
                    kind=SuggestionKind.CLI_HINT,
                    intent=(f"current midi set-clock-master {endpoint} --question {question.id}"),
                    description=f"Set clock master to {endpoint}",
                    code="set_clock_master",
                    params={"endpoint": endpoint, "question_id": question.id},
                )
            )
            suggestions.append(
                ActionSuggestion(
                    kind=SuggestionKind.INSPECT,
                    intent=f"reconcile apply question {question.id} --dry-run --json",
                    description="Dry-run apply for clock master",
                    code="apply_dry_run",
                    params={"question_id": question.id},
                )
            )
        suggestions.append(suggest_finalize(question.id))

        blockers: list[Any] = []
        details: dict[str, Any] = {
            "capability_reason": (
                "MIDI clock master: HUMAN answer attestation or explicit "
                "observation may authorize VERIFIED evidence"
            ),
            "verification_policy": policy.value,
            "evidence_basis": basis.value,
            "answer_actor": (question.answer_actor.value if question.answer_actor else None),
        }
        if has_bot_answer(question):
            ans = [suggest_answer(question.id)]
            blockers.append(
                {
                    "code": "needs_human_answer",
                    "field": "answer_actor",
                    "message": (
                        "BOT answer is not human factual authority. A human must Answer & Resolve."
                    ),
                    "suggestions": [s.to_dict() for s in ans],
                    "suggested_commands": render_suggestions(ans),
                }
            )
        elif (
            policy is VerificationPolicy.EXPLICIT_OBSERVATION_REQUIRED
            and question.status == QuestionStatus.RESOLVED
            and not has_positive_observation(question)
        ):
            obs = [suggest_verify_record(question.id, outcome="confirmed", value=endpoint or "…")]
            blockers.append(
                {
                    "code": "needs_human_observation",
                    "field": "verification_result",
                    "message": (
                        "This verification kind requires an explicit physical/software "
                        "test observation (not answer attestation alone)."
                    ),
                    "suggestions": [s.to_dict() for s in obs],
                    "suggested_commands": render_suggestions(obs),
                }
            )
        elif state == ReconciliationState.NEEDS_AGENT_ACTION and not endpoint:
            packet = build_action_packet(
                question,
                current_snapshot=current,
                suggested_command_families=[
                    "rig current midi set-clock-master",
                    "rig reconcile apply",
                    "rig reconcile finalize",
                ],
                postcondition="clock.master matches human answer with appropriate evidence",
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
            suggestions=suggestions,
            postconditions=(
                [f"clock.master == {endpoint} AND status == VERIFIED"]
                if endpoint and authority
                else ([f"clock.master == {endpoint}"] if endpoint else [])
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
        if not has_apply_authority(question):
            raise StoreError(
                f"{question.id} midi.clock_master apply requires HUMAN answer "
                "attestation (answer_actor=HUMAN) or verification_result "
                "CONFIRMED/CORRECTED"
            )
        if not yes and not dry_run:
            raise StoreError("apply requires --yes (or --dry-run)")
        endpoint = _desired_endpoint(question)
        if not endpoint:
            raise StoreError("Cannot apply clock master without a normalized endpoint")
        basis = evidence_basis_for(question)
        preview, data = midi_state.propose_set_clock_master(
            endpoint,
            status=MidiEvidenceStatus.VERIFIED,
            midi_path=paths.get("midi"),
            notes=f"evidence_basis={basis.value}",
        )
        if dry_run:
            return {
                "applied": False,
                "dry_run": True,
                "evidence_basis": basis.value,
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
            "evidence_basis": basis.value,
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
                message="Answer/observation is not a resolvable endpoint id",
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
        if cur == endpoint and has_apply_authority(question):
            return VerifyResult(
                status=VerificationStatus.MISMATCH,
                current=current,
                expected=endpoint,
                message=(
                    f"master matches; evidence is {status!r}, expected VERIFIED "
                    f"(basis={evidence_basis_for(question).value})"
                ),
            )
        if cur == endpoint:
            return VerifyResult(
                status=VerificationStatus.UNVERIFIABLE,
                current=current,
                expected=endpoint,
                message=(
                    "master matches answer but lacks HUMAN attestation or "
                    "CONFIRMED/CORRECTED observation; INTENDED is not auto-promoted"
                ),
            )
        return VerifyResult(
            status=VerificationStatus.MISMATCH,
            current=current,
            expected=endpoint,
            message=f"clock master is {cur!r}, expected {endpoint!r}",
        )
