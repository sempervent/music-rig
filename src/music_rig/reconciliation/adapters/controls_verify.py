"""controls.verify — scoped controller evidence after human observation."""

from __future__ import annotations

from typing import Any

from music_rig import control_state, current_service
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


class ControlsVerifyAdapter(ReconciliationAdapter):
    domain = "controls.verify"
    capability = Capability.VERIFY_ONLY

    def read_current(self, question: OpenQuestion, *, paths: dict[str, Any]) -> Any:
        data = control_state.load_raw(paths.get("controllers"))
        gear = question.target.gear if question.target else None
        context = question.target.context if question.target else None
        controllers = data.get("controllers") or []
        if not isinstance(controllers, list):
            return {"error": "controllers must be a list"}
        if gear:
            for body in controllers:
                if isinstance(body, dict) and body.get("gear_ref") == gear:
                    contexts = [
                        c
                        for c in (body.get("contexts") or [])
                        if isinstance(c, dict)
                    ]
                    scoped = None
                    if context:
                        scoped = next(
                            (c for c in contexts if c.get("id") == context), None
                        )
                    return {
                        "gear_ref": gear,
                        "context": context,
                        "contexts": [c.get("id") for c in contexts],
                        "scoped_context": scoped,
                        "notes": body.get("notes"),
                        "coverage": body.get("coverage"),
                    }
            return {"gear_ref": gear, "found": False}
        return {
            "gears": [
                b.get("gear_ref")
                for b in controllers
                if isinstance(b, dict) and b.get("gear_ref")
            ]
        }

    def plan(self, question: OpenQuestion, *, paths: dict[str, Any]) -> Plan:
        current = self.read_current(question, paths=paths)
        gear = question.target.gear if question.target else None
        context = question.target.context if question.target else None
        vr = question.verification_result

        if question.reconciled_at is not None:
            state = ReconciliationState.RECONCILED
        elif question.status != QuestionStatus.RESOLVED or not question.answer.strip():
            if vr and vr.outcome == VerificationOutcome.FAILED_TEST:
                state = ReconciliationState.NEEDS_AGENT_ACTION
            else:
                state = ReconciliationState.NEEDS_ANSWER
        elif vr and vr.outcome == VerificationOutcome.FAILED_TEST:
            state = ReconciliationState.NEEDS_AGENT_ACTION
        elif has_positive_observation(question) and gear and context:
            scoped = (current or {}).get("scoped_context") or {}
            if scoped.get("evidence") == MidiEvidenceStatus.VERIFIED.value:
                state = ReconciliationState.CURRENT_MATCHES
            else:
                state = ReconciliationState.READY_TO_APPLY
        elif has_positive_observation(question) and gear and not context:
            # Gear-only: do not mark whole controller VERIFIED
            state = ReconciliationState.NEEDS_AGENT_ACTION
        else:
            state = ReconciliationState.NEEDS_AGENT_ACTION

        operations: list[dict[str, Any]] = []
        if vr and vr.outcome == VerificationOutcome.FAILED_TEST:
            operations.append(
                op(
                    PlanOperationKind.RECORD_FAILED_VERIFICATION,
                    target=f"controls:{gear or '?'}",
                    note=vr.note or "mapping test failed",
                )
            )
        elif has_positive_observation(question) and gear and context:
            scoped = (current or {}).get("scoped_context") or {}
            operations.append(
                op(
                    PlanOperationKind.SET_EVIDENCE_VERIFIED,
                    target=f"{gear}/{context}",
                    before=scoped.get("evidence"),
                    after=MidiEvidenceStatus.VERIFIED.value,
                    note="context-scoped only; not whole controller",
                )
            )
        elif has_positive_observation(question) and gear and not context:
            operations.append(
                op(
                    PlanOperationKind.NO_CURRENT_CHANGE,
                    note=(
                        "target.context required to set evidence; "
                        "one control/context ≠ whole controller"
                    ),
                )
            )

        cmds = ["uv run rig controls summary"]
        if gear:
            cmds.append(f"uv run rig current controls verify {gear}")
            cmds.append(f"uv run rig controls show {gear}")
            if context:
                cmds.append(
                    f"uv run rig current controls set-evidence {gear} {context} "
                    f"<control> VERIFIED"
                )
        cmds.append(
            f"uv run rig reconcile finalize question {question.id} "
            f"--no-current-change --note \"controls reviewed\" --yes"
        )

        details: dict[str, Any] = {}
        blockers: list[Any] = []
        if state == ReconciliationState.NEEDS_AGENT_ACTION and (
            question.status == QuestionStatus.RESOLVED
            or (vr and vr.outcome == VerificationOutcome.FAILED_TEST)
        ):
            missing = None
            families = [
                "rig current controls set-evidence",
                "rig verify record",
                "rig controls show",
            ]
            if has_positive_observation(question) and gear and not context:
                missing = "controls.verify requires target.context (and preferably control) for evidence apply"
                blockers.append(
                    {
                        "code": "missing_target_field",
                        "field": "context",
                        "message": missing,
                        "suggested_commands": [
                            f"uv run rig question target set {question.id} "
                            f"--context <context-id> --yes"
                        ],
                    }
                )
            elif not has_positive_observation(question):
                blockers.append(
                    {
                        "code": "needs_human_observation",
                        "message": "Record CONFIRMED/CORRECTED/FAILED_TEST via verify record",
                    }
                )
            details["action_packet"] = build_action_packet(
                question,
                current_snapshot=current,
                suggested_command_families=families,
                postcondition=(
                    f"{gear}/{context} evidence == VERIFIED"
                    if gear and context
                    else "scoped control/context evidence VERIFIED (not whole controller)"
                ),
                missing_capability=missing,
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
            suggested_commands=cmds,
            details=details,
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
                f"{question.id} controls.verify apply requires "
                "verification_result CONFIRMED or CORRECTED"
            )
        if not yes and not dry_run:
            raise StoreError("apply requires --yes (or --dry-run)")
        gear = question.target.gear if question.target else None
        context = question.target.context if question.target else None
        if not gear or not context:
            raise StoreError(
                "controls.verify apply requires target.gear and target.context "
                "(granularity: not whole controller)"
            )
        preview, data = control_state.propose_set_context_evidence(
            gear,
            context,
            MidiEvidenceStatus.VERIFIED,
            controllers_path=paths.get("controllers"),
        )
        if dry_run:
            return {
                "applied": False,
                "dry_run": True,
                "preview": preview.model_dump(mode="json"),
            }
        from music_rig import store as store_mod

        committed = current_service.commit_controllers(
            data,
            preview,
            dry_run=False,
            render=False,
            question_id=question.id,
            resolve_q=False,
            controllers_path=paths.get("controllers") or store_mod.CONTROLLERS_PATH,
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
                message="FAILED_TEST — mapping not verified",
            )
        context = question.target.context if question.target else None
        if has_positive_observation(question) and context:
            scoped = (current or {}).get("scoped_context") or {}
            if scoped.get("evidence") == MidiEvidenceStatus.VERIFIED.value:
                return VerifyResult(
                    status=VerificationStatus.MATCH,
                    current=current,
                    expected=MidiEvidenceStatus.VERIFIED.value,
                    message="scoped context evidence VERIFIED",
                )
            return VerifyResult(
                status=VerificationStatus.MISMATCH,
                current=current,
                expected=MidiEvidenceStatus.VERIFIED.value,
                message=f"context evidence is {scoped.get('evidence')!r}",
            )
        return VerifyResult(
            status=VerificationStatus.UNVERIFIABLE,
            current=current,
            expected=question.answer,
            message=(
                "controls.verify — freeform answers not auto-matched; "
                "scoped evidence requires observation + context"
            ),
        )
