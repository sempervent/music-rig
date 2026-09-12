"""ableton.template — VERIFY_ONLY / human-verify-then-apply template evidence."""

from __future__ import annotations

from typing import Any

from music_rig import ableton_state, current_service
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


class AbletonTemplateAdapter(ReconciliationAdapter):
    domain = "ableton.template"
    capability = Capability.VERIFY_ONLY

    def read_current(self, question: OpenQuestion, *, paths: dict[str, Any]) -> Any:
        doc = ableton_state.load_document(paths.get("ableton"))
        path_key = question.target.path if question.target else None
        if path_key:
            template = next((t for t in doc.templates if t.id == path_key), None)
            if template is not None:
                return {
                    "template": template.id,
                    "label": template.label,
                    "evidence": template.evidence.value,
                    "track_count": len(template.tracks),
                    "notes": template.notes,
                }
            return {
                "path": path_key,
                "found": False,
                "template_ids": [t.id for t in doc.templates],
                "note": "Ableton YAML is target registry evidence; not a Live Set dump",
            }
        return {
            "path": path_key,
            "track_count": len(doc.tracks),
            "template_ids": [t.id for t in doc.templates],
            "note": "Ableton YAML is target registry evidence; not a Live Set dump",
        }

    def plan(self, question: OpenQuestion, *, paths: dict[str, Any]) -> Plan:
        current = self.read_current(question, paths=paths)
        path_key = question.target.path if question.target else None
        vr = question.verification_result
        evidence = current.get("evidence") if isinstance(current, dict) else None

        if question.reconciled_at is not None:
            state = ReconciliationState.RECONCILED
        elif question.status == QuestionStatus.OPEN and question.answer.strip():
            state = ReconciliationState.DRAFT_ANSWER
        elif question.status != QuestionStatus.RESOLVED or not question.answer.strip():
            if vr and vr.outcome == VerificationOutcome.FAILED_TEST:
                state = ReconciliationState.NEEDS_AGENT_ACTION
            else:
                state = ReconciliationState.NEEDS_ANSWER
        elif vr and vr.outcome == VerificationOutcome.FAILED_TEST:
            state = ReconciliationState.NEEDS_AGENT_ACTION
        elif has_positive_observation(question) and path_key and current.get("found") is not False:
            if evidence == MidiEvidenceStatus.VERIFIED.value:
                state = ReconciliationState.CURRENT_MATCHES
            else:
                state = ReconciliationState.READY_TO_APPLY
        else:
            state = ReconciliationState.NEEDS_AGENT_ACTION

        operations: list[dict[str, Any]] = []
        if has_positive_observation(question) and path_key:
            if evidence != MidiEvidenceStatus.VERIFIED.value:
                operations.append(
                    op(
                        PlanOperationKind.SET_EVIDENCE_VERIFIED,
                        target=f"ableton.template:{path_key}",
                        before=evidence,
                        after=MidiEvidenceStatus.VERIFIED.value,
                        note="template-scoped only; not whole Live Set",
                    )
                )
            else:
                operations.append(
                    op(PlanOperationKind.NO_CURRENT_CHANGE, note="template already VERIFIED")
                )
        elif vr and vr.outcome == VerificationOutcome.FAILED_TEST:
            operations.append(
                op(PlanOperationKind.RECORD_FAILED_VERIFICATION, note=vr.note or "")
            )

        from music_rig.reconciliation.suggestions import (
            ActionSuggestion,
            SuggestionKind,
            suggest_finalize,
            suggest_verify_record,
        )

        suggestions: list[ActionSuggestion] = [
            ActionSuggestion(
                kind=SuggestionKind.INSPECT,
                intent="ableton targets",
                description="List Ableton template targets",
                code="ableton_targets",
            )
        ]
        if path_key:
            suggestions.append(
                ActionSuggestion(
                    kind=SuggestionKind.INSPECT,
                    intent=f"ableton template {path_key}",
                    description=f"Show template {path_key}",
                    code="ableton_template",
                    params={"path": path_key},
                )
            )
            suggestions.append(
                ActionSuggestion(
                    kind=SuggestionKind.CLI_HINT,
                    intent=(
                        f"current ableton set-template-evidence {path_key} VERIFIED"
                    ),
                    description=f"Set template {path_key} evidence VERIFIED",
                    code="set_template_evidence",
                    params={"path": path_key},
                )
            )
        suggestions.append(
            ActionSuggestion(
                kind=SuggestionKind.INSPECT,
                intent=f"reconcile apply question {question.id} --dry-run --json",
                description="Dry-run apply for template evidence",
                code="apply_dry_run",
                params={"question_id": question.id},
            )
        )
        suggestions.append(
            suggest_finalize(
                question.id, no_current_change=True, note="template reviewed"
            )
        )

        details: dict[str, Any] = {}
        blockers: list[Any] = []
        if state == ReconciliationState.NEEDS_AGENT_ACTION and (
            question.status == QuestionStatus.RESOLVED
            or (vr and vr.outcome == VerificationOutcome.FAILED_TEST)
        ):
            if not has_positive_observation(question):
                blockers.append(
                    {
                        "code": "needs_human_observation",
                        "message": (
                            "Confirm Live set offline, then "
                            "`rig verify record --outcome confirmed`"
                        ),
                        "suggestions": [
                            suggest_verify_record(question.id).to_dict()
                        ],
                    }
                )
            details["action_packet"] = build_action_packet(
                question,
                current_snapshot=current,
                suggested_command_families=[
                    "rig current ableton set-template-evidence",
                    "rig ableton template",
                    "rig verify record",
                    "rig reconcile apply",
                ],
                postcondition=(
                    f"template {path_key} evidence == VERIFIED"
                    if path_key
                    else "template evidence VERIFIED at scoped id"
                ),
            )

        return Plan(
            artifact_type="question",
            artifact_id=question.id,
            state=state,
            capability=self.capability,
            current=current,
            desired=question.answer.strip() or None,
            operations=operations,
            blockers=blockers,
            suggestions=suggestions,
            details=details,
            postconditions=(
                [f"{path_key} evidence == VERIFIED"] if path_key else []
            ),
            closable=list(question.related_todos) + list(question.related_changes),
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
                f"{question.id} ableton.template apply requires "
                "verification_result CONFIRMED or CORRECTED"
            )
        if not yes and not dry_run:
            raise StoreError("apply requires --yes (or --dry-run)")
        path_key = question.target.path if question.target else None
        if not path_key:
            raise StoreError("ableton.template apply requires target.path (template id)")
        preview, data = ableton_state.propose_set_template_evidence(
            path_key,
            MidiEvidenceStatus.VERIFIED,
            ableton_path=paths.get("ableton"),
        )
        if dry_run:
            return {
                "applied": False,
                "dry_run": True,
                "preview": preview.model_dump(mode="json"),
            }
        from music_rig import store as store_mod

        committed = current_service.commit_ableton(
            data,
            preview,
            dry_run=False,
            render=False,
            question_id=question.id,
            resolve_q=False,
            ableton_path=paths.get("ableton") or store_mod.ABLETON_PATH,
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
                message="FAILED_TEST — template not verified",
            )
        if has_positive_observation(question) and isinstance(current, dict):
            if current.get("evidence") == MidiEvidenceStatus.VERIFIED.value:
                return VerifyResult(
                    status=VerificationStatus.MATCH,
                    current=current,
                    expected=MidiEvidenceStatus.VERIFIED.value,
                    message="template evidence VERIFIED",
                )
            return VerifyResult(
                status=VerificationStatus.MISMATCH,
                current=current,
                expected=MidiEvidenceStatus.VERIFIED.value,
                message=f"template evidence is {current.get('evidence')!r}",
            )
        return VerifyResult(
            status=VerificationStatus.UNVERIFIABLE,
            current=current,
            expected=question.answer,
            message=(
                "ableton.template needs CONFIRMED/CORRECTED observation "
                "before evidence MATCH"
            ),
        )
