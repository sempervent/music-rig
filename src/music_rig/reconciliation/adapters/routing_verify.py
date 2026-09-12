"""routing.verify — path evidence after human observation (NamedPath.evidence)."""

from __future__ import annotations

from typing import Any

from music_rig import current_service, routing_state
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


class RoutingVerifyAdapter(ReconciliationAdapter):
    domain = "routing.verify"
    capability = Capability.VERIFY_ONLY

    def read_current(self, question: OpenQuestion, *, paths: dict[str, Any]) -> Any:
        target = question.target
        data = routing_state.load_raw(paths.get("routing"))
        if target and target.path:
            try:
                pid, named = routing_state.get_named_path(data, target.path)
            except StoreError as exc:
                return {"error": str(exc)}
            return {
                "path": pid,
                "status": named.status,
                "evidence": named.evidence.value if named.evidence else None,
                "label": named.label,
                "notes": named.notes,
                "route_ref": named.route_ref,
            }
        named = data.get("named_paths") or {}
        return {"paths": sorted(named.keys()) if isinstance(named, dict) else []}

    def plan(self, question: OpenQuestion, *, paths: dict[str, Any]) -> Plan:
        current = self.read_current(question, paths=paths)
        path = question.target.path if question.target else None
        vr = question.verification_result
        answer = question.answer.strip().upper()
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
        elif (
            has_positive_observation(question)
            and path
            and answer in {"YES", "Y"}
        ):
            if evidence == MidiEvidenceStatus.VERIFIED.value:
                state = ReconciliationState.CURRENT_MATCHES
            else:
                state = ReconciliationState.READY_TO_APPLY
        elif has_positive_observation(question) and answer in {"NO", "N"}:
            state = ReconciliationState.NEEDS_AGENT_ACTION
        else:
            state = ReconciliationState.NEEDS_AGENT_ACTION

        operations: list[dict[str, Any]] = []
        if (
            has_positive_observation(question)
            and path
            and answer in {"YES", "Y"}
        ):
            operations.append(
                op(
                    PlanOperationKind.SET_EVIDENCE_VERIFIED,
                    target=f"routing.path:{path}",
                    before=evidence,
                    after=MidiEvidenceStatus.VERIFIED.value,
                )
            )
        elif vr and vr.outcome == VerificationOutcome.FAILED_TEST:
            operations.append(
                op(PlanOperationKind.RECORD_FAILED_VERIFICATION, note=vr.note or "")
            )
        elif has_positive_observation(question) and answer in {"NO", "N"}:
            operations.append(
                op(
                    PlanOperationKind.NO_CURRENT_CHANGE,
                    note="path differs — agent must update topology via path CLIs",
                )
            )

        from music_rig.reconciliation.suggestions import (
            ActionSuggestion,
            SuggestionKind,
            suggest_finalize,
            suggest_verify_record,
        )

        suggestions: list[ActionSuggestion] = []
        if path:
            suggestions.append(
                ActionSuggestion(
                    kind=SuggestionKind.INSPECT,
                    intent=f"path show {path}",
                    description=f"Show named path {path}",
                    code="path_show",
                    params={"path": path},
                )
            )
            suggestions.append(
                ActionSuggestion(
                    kind=SuggestionKind.VERIFY,
                    intent=f"current path verify {path}",
                    description=f"Verify path {path}",
                    code="path_verify",
                    params={"path": path},
                )
            )
            suggestions.append(
                ActionSuggestion(
                    kind=SuggestionKind.CLI_HINT,
                    intent=f"current path set-evidence {path} VERIFIED",
                    description=f"Set path {path} evidence VERIFIED",
                    code="path_set_evidence",
                    params={"path": path},
                )
            )
        suggestions.append(
            ActionSuggestion(
                kind=SuggestionKind.VERIFY,
                intent=f"reconcile verify question {question.id}",
                description=f"Verify reconciliation for {question.id}",
                code="reconcile_verify",
                params={"question_id": question.id},
            )
        )
        suggestions.append(
            suggest_finalize(
                question.id, no_current_change=True, note="verified path"
            )
        )

        details: dict[str, Any] = {}
        blockers: list[Any] = []
        if state == ReconciliationState.NEEDS_AGENT_ACTION and (
            question.status == QuestionStatus.RESOLVED
            or (vr and vr.outcome == VerificationOutcome.FAILED_TEST)
        ):
            details["action_packet"] = build_action_packet(
                question,
                current_snapshot=current,
                suggested_command_families=[
                    "rig current path set-evidence",
                    "rig path show",
                    "rig verify record",
                    "rig reconcile apply",
                ],
                postcondition=(
                    f"path {path} evidence == VERIFIED"
                    if path
                    else "named path evidence VERIFIED"
                ),
            )
            if not has_positive_observation(question):
                blockers.append(
                    {
                        "code": "needs_human_observation",
                        "message": "Record confirm/correct via verify record",
                        "suggestions": [
                            suggest_verify_record(question.id).to_dict()
                        ],
                    }
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
                [f"path {path} evidence == VERIFIED"] if path else []
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
                f"{question.id} routing.verify apply requires "
                "verification_result CONFIRMED or CORRECTED"
            )
        if question.answer.strip().upper() not in {"YES", "Y"}:
            raise StoreError(
                "routing.verify evidence apply only when answer YES (path matches)"
            )
        if not yes and not dry_run:
            raise StoreError("apply requires --yes (or --dry-run)")
        path = question.target.path if question.target else None
        if not path:
            raise StoreError("routing.verify apply requires target.path")
        preview, data = routing_state.propose_set_path_evidence(
            path,
            MidiEvidenceStatus.VERIFIED,
            routing_path=paths.get("routing"),
        )
        if dry_run:
            return {
                "applied": False,
                "dry_run": True,
                "preview": preview.model_dump(mode="json"),
            }
        from music_rig import store as store_mod

        committed = current_service.commit_routing(
            data,
            preview,
            dry_run=False,
            render=False,
            question_id=question.id,
            resolve_q=False,
            routing_path=paths.get("routing") or store_mod.ROUTING_PATH,
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
        if isinstance(current, dict) and current.get("error"):
            return VerifyResult(
                status=VerificationStatus.BLOCKED,
                current=current,
                message=str(current["error"]),
            )
        if question.verification_result and (
            question.verification_result.outcome == VerificationOutcome.FAILED_TEST
        ):
            return VerifyResult(
                status=VerificationStatus.MISMATCH,
                current=current,
                message="FAILED_TEST — path not verified",
            )
        if question.status != QuestionStatus.RESOLVED:
            return VerifyResult(
                status=VerificationStatus.UNVERIFIABLE,
                current=current,
                message="Question not RESOLVED",
            )
        if (
            has_positive_observation(question)
            and question.answer.strip().upper() in {"YES", "Y"}
            and isinstance(current, dict)
            and current.get("evidence") == MidiEvidenceStatus.VERIFIED.value
        ):
            return VerifyResult(
                status=VerificationStatus.MATCH,
                current=current,
                expected=MidiEvidenceStatus.VERIFIED.value,
                message="path evidence VERIFIED",
            )
        if has_positive_observation(question) and question.answer.strip().upper() in {
            "YES",
            "Y",
        }:
            return VerifyResult(
                status=VerificationStatus.MISMATCH,
                current=current,
                expected=MidiEvidenceStatus.VERIFIED.value,
                message=f"path evidence is {current.get('evidence')!r}",
            )
        return VerifyResult(
            status=VerificationStatus.UNVERIFIABLE,
            current=current,
            expected=question.answer,
            message=(
                "routing.verify — inspect CURRENT path; "
                "CONFIRM observation + YES unlocks evidence VERIFIED"
            ),
        )
