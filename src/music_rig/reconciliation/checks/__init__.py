"""Read-only reconciliation checks — inspect / classify / recommend only."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Protocol

from music_rig.models import ChangeStatus, QuestionStatus, ReconciliationState
from music_rig.reconciliation.action_packet import observation_blocks_success
from music_rig.reconciliation.adapters import get_adapter
from music_rig.reconciliation.context import ReconciliationContext
from music_rig.reconciliation.operations import RigOperation
from music_rig.reconciliation.types import VerificationStatus
from music_rig.store import load_changes, load_questions, load_todo


class FindingStatus(str, Enum):
    OK = "OK"
    READY = "READY"
    BLOCKED = "BLOCKED"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"


@dataclass
class Finding:
    check_id: str
    artifact_type: str
    artifact_id: str
    status: FindingStatus
    summary: str
    state: str | None = None
    recommended_operations: list[RigOperation] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "artifact_type": self.artifact_type,
            "artifact_id": self.artifact_id,
            "status": self.status.value,
            "summary": self.summary,
            "state": self.state,
            "recommended_operations": [o.to_dict() for o in self.recommended_operations],
            "details": self.details,
        }


class ReconciliationCheck(Protocol):
    id: str

    def inspect(self, ctx: ReconciliationContext) -> list[Finding]:
        ...


class QuestionConvergenceCheck:
    """Classify each Question's reconciliation readiness (read-only)."""

    id = "question_convergence"

    def inspect(self, ctx: ReconciliationContext) -> list[Finding]:
        findings: list[Finding] = []
        try:
            qdoc = load_questions(ctx.paths.questions)
        except Exception as exc:  # noqa: BLE001 — isolate load failure
            return [
                Finding(
                    check_id=self.id,
                    artifact_type="questions",
                    artifact_id="*",
                    status=FindingStatus.ERROR,
                    summary=f"failed to load questions: {exc}",
                )
            ]
        paths = ctx.path_dict()
        for q in qdoc.questions:
            try:
                findings.append(self._inspect_one(q, paths))
            except Exception as exc:  # noqa: BLE001 — per-artifact isolation
                findings.append(
                    Finding(
                        check_id=self.id,
                        artifact_type="question",
                        artifact_id=q.id,
                        status=FindingStatus.ERROR,
                        summary=f"inspect failed: {exc}",
                        details={"error_type": type(exc).__name__},
                    )
                )
        return findings

    def _inspect_one(self, q, paths: dict[str, Any]) -> Finding:
        from music_rig.reconciliation.service import question_state

        if q.reconciled_at is not None:
            return Finding(
                check_id=self.id,
                artifact_type="question",
                artifact_id=q.id,
                status=FindingStatus.OK,
                summary="already reconciled",
                state=ReconciliationState.RECONCILED.value,
            )
        if q.status == QuestionStatus.OPEN:
            if q.answer.strip():
                return Finding(
                    check_id=self.id,
                    artifact_type="question",
                    artifact_id=q.id,
                    status=FindingStatus.BLOCKED,
                    summary="OPEN draft — resolve before reconcile",
                    state=ReconciliationState.DRAFT_ANSWER.value,
                    recommended_operations=[
                        RigOperation(
                            namespace="question",
                            action="resolve",
                            args={"question_id": q.id},
                            description=f"Resolve draft {q.id}",
                        )
                    ],
                )
            return Finding(
                check_id=self.id,
                artifact_type="question",
                artifact_id=q.id,
                status=FindingStatus.BLOCKED,
                summary="OPEN — needs human answer",
                state=ReconciliationState.NEEDS_ANSWER.value,
            )
        if observation_blocks_success(q):
            return Finding(
                check_id=self.id,
                artifact_type="question",
                artifact_id=q.id,
                status=FindingStatus.BLOCKED,
                summary="FAILED_TEST — must not finalize as success",
                state=ReconciliationState.NEEDS_AGENT_ACTION.value,
            )
        adapter = get_adapter(q.target.domain if q.target else None)
        st = question_state(q, paths=paths)
        verify = adapter.verify(q, paths=paths)
        plan = adapter.plan(q, paths=paths)
        if st in {
            ReconciliationState.CURRENT_MATCHES,
            ReconciliationState.READY_TO_FINALIZE,
        } or (
            verify.status == VerificationStatus.MATCH
            and st
            in {
                ReconciliationState.READY_TO_FINALIZE,
                ReconciliationState.CURRENT_MATCHES,
                ReconciliationState.READY_TO_APPLY,
            }
        ):
            if st == ReconciliationState.READY_TO_APPLY and verify.status != VerificationStatus.MATCH:
                return Finding(
                    check_id=self.id,
                    artifact_type="question",
                    artifact_id=q.id,
                    status=FindingStatus.BLOCKED,
                    summary=f"state {st.value}",
                    state=st.value,
                )
            if st not in {
                ReconciliationState.CURRENT_MATCHES,
                ReconciliationState.READY_TO_FINALIZE,
            } and verify.status != VerificationStatus.MATCH:
                return Finding(
                    check_id=self.id,
                    artifact_type="question",
                    artifact_id=q.id,
                    status=FindingStatus.BLOCKED,
                    summary=f"state {st.value}",
                    state=st.value,
                )
            if st == ReconciliationState.CURRENT_MATCHES or verify.status == VerificationStatus.MATCH:
                return Finding(
                    check_id=self.id,
                    artifact_type="question",
                    artifact_id=q.id,
                    status=FindingStatus.READY,
                    summary="CURRENT matches — ready to finalize",
                    state=st.value,
                    recommended_operations=[
                        RigOperation(
                            namespace="question",
                            action="finalize_manual",
                            args={
                                "question_id": q.id,
                                "note": "sweep: CURRENT already matches / verified",
                                "complete_linked_todos": True,
                                "apply_linked_changes": True,
                                "confirm_dod": True,
                            },
                            description=f"Finalize {q.id}",
                        )
                    ],
                    details={"verify": verify.to_dict()},
                )
        if st == ReconciliationState.NEEDS_AGENT_ACTION:
            return Finding(
                check_id=self.id,
                artifact_type="question",
                artifact_id=q.id,
                status=FindingStatus.BLOCKED,
                summary="needs agent-assisted CURRENT updates",
                state=st.value,
                details={"capability": plan.capability.value},
            )
        return Finding(
            check_id=self.id,
            artifact_type="question",
            artifact_id=q.id,
            status=FindingStatus.BLOCKED,
            summary=f"state {st.value}",
            state=st.value,
        )


class ChangeConvergenceCheck:
    id = "change_convergence"

    def inspect(self, ctx: ReconciliationContext) -> list[Finding]:
        findings: list[Finding] = []
        try:
            cdoc = load_changes(ctx.paths.changes)
        except Exception as exc:  # noqa: BLE001
            return [
                Finding(
                    check_id=self.id,
                    artifact_type="changes",
                    artifact_id="*",
                    status=FindingStatus.ERROR,
                    summary=f"failed to load changes: {exc}",
                )
            ]
        for ch in cdoc.items:
            try:
                if ch.status == ChangeStatus.APPLIED:
                    findings.append(
                        Finding(
                            check_id=self.id,
                            artifact_type="change",
                            artifact_id=ch.id,
                            status=FindingStatus.OK,
                            summary="already applied",
                            state=ch.status.value,
                        )
                    )
                elif ch.status == ChangeStatus.OPEN:
                    findings.append(
                        Finding(
                            check_id=self.id,
                            artifact_type="change",
                            artifact_id=ch.id,
                            status=FindingStatus.BLOCKED,
                            summary="change OPEN — not auto-applied by sweep",
                            state=ch.status.value,
                        )
                    )
                else:
                    findings.append(
                        Finding(
                            check_id=self.id,
                            artifact_type="change",
                            artifact_id=ch.id,
                            status=FindingStatus.SKIPPED,
                            summary=f"status {ch.status.value}",
                            state=ch.status.value,
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                findings.append(
                    Finding(
                        check_id=self.id,
                        artifact_type="change",
                        artifact_id=getattr(ch, "id", "?"),
                        status=FindingStatus.ERROR,
                        summary=f"inspect failed: {exc}",
                    )
                )
        return findings


class TodoCompletionCheck:
    id = "todo_completion"

    def inspect(self, ctx: ReconciliationContext) -> list[Finding]:
        findings: list[Finding] = []
        try:
            tdoc = load_todo(ctx.paths.todo)
        except Exception as exc:  # noqa: BLE001
            return [
                Finding(
                    check_id=self.id,
                    artifact_type="todo",
                    artifact_id="*",
                    status=FindingStatus.ERROR,
                    summary=f"failed to load todo: {exc}",
                )
            ]
        for tid in tdoc.next_session:
            task = tdoc.task_map().get(tid)
            if task is None:
                findings.append(
                    Finding(
                        check_id=self.id,
                        artifact_type="todo",
                        artifact_id=tid,
                        status=FindingStatus.ERROR,
                        summary="next_session references missing TODO",
                    )
                )
                continue
            findings.append(
                Finding(
                    check_id=self.id,
                    artifact_type="todo",
                    artifact_id=tid,
                    status=FindingStatus.OK
                    if task.status.value == "DONE"
                    else FindingStatus.BLOCKED,
                    summary=f"next_session task status={task.status.value}",
                    state=task.status.value,
                )
            )
        return findings


DEFAULT_CHECKS: list[ReconciliationCheck] = [
    QuestionConvergenceCheck(),
    ChangeConvergenceCheck(),
    TodoCompletionCheck(),
]


def run_checks(
    ctx: ReconciliationContext,
    *,
    checks: list[ReconciliationCheck] | None = None,
) -> list[Finding]:
    out: list[Finding] = []
    for check in checks or DEFAULT_CHECKS:
        out.extend(check.inspect(ctx))
    return out


def group_findings(findings: list[Finding]) -> dict[str, dict[str, list[dict[str, Any]]]]:
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for f in findings:
        bucket = grouped.setdefault(
            f.check_id, {"ready": [], "blocked": [], "errors": [], "ok": [], "skipped": []}
        )
        key = {
            FindingStatus.READY: "ready",
            FindingStatus.BLOCKED: "blocked",
            FindingStatus.ERROR: "errors",
            FindingStatus.OK: "ok",
            FindingStatus.SKIPPED: "skipped",
        }[f.status]
        bucket[key].append(f.to_dict())
    return grouped


def build_finalize_plan(findings: list[Finding]) -> list[RigOperation]:
    """Freeze READY question finalizations into an explicit plan (no rediscovery)."""
    ops: list[RigOperation] = []
    for f in findings:
        if f.status is FindingStatus.READY and f.check_id == "question_convergence":
            ops.extend(f.recommended_operations)
    return ops
