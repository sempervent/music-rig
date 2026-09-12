"""routing.verify — VERIFY_ONLY (path status); mutations → NEEDS_AGENT_ACTION."""

from __future__ import annotations

from typing import Any

from music_rig import routing_state
from music_rig.models import OpenQuestion, QuestionStatus, ReconciliationState
from music_rig.reconciliation.adapters.base import ReconciliationAdapter
from music_rig.reconciliation.types import (
    Capability,
    Plan,
    VerificationStatus,
    VerifyResult,
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
                "label": named.label,
                "notes": named.notes,
                "route_ref": named.route_ref,
            }
        named = data.get("named_paths") or {}
        return {"paths": sorted(named.keys()) if isinstance(named, dict) else []}

    def plan(self, question: OpenQuestion, *, paths: dict[str, Any]) -> Plan:
        current = self.read_current(question, paths=paths)
        path = question.target.path if question.target else None
        if question.reconciled_at is not None:
            state = ReconciliationState.RECONCILED
        elif question.status != QuestionStatus.RESOLVED or not question.answer.strip():
            state = ReconciliationState.NEEDS_ANSWER
        else:
            # VERIFY_ONLY — cannot auto-apply; agent uses path/verify CLIs then finalize
            state = ReconciliationState.NEEDS_AGENT_ACTION
        cmds = []
        if path:
            cmds.append(f"uv run rig path show {path}")
            cmds.append(f"uv run rig current path verify {path}")
        cmds.append(f"uv run rig reconcile verify question {question.id}")
        cmds.append(
            f"uv run rig reconcile finalize question {question.id} "
            f"--no-current-change --note \"verified path\" --yes"
        )
        return Plan(
            artifact_type="question",
            artifact_id=question.id,
            state=state,
            capability=self.capability,
            current=current,
            desired=question.answer.strip() or None,
            blockers=(
                ["VERIFY_ONLY: use path/verify CLIs; finalize with --no-current-change"]
                if state == ReconciliationState.NEEDS_AGENT_ACTION
                else []
            ),
            suggested_commands=cmds,
            postconditions=["Path documentation reviewed; INTENDED not auto-promoted"],
        )

    def verify(self, question: OpenQuestion, *, paths: dict[str, Any]) -> VerifyResult:
        current = self.read_current(question, paths=paths)
        if isinstance(current, dict) and current.get("error"):
            return VerifyResult(
                status=VerificationStatus.BLOCKED,
                current=current,
                message=str(current["error"]),
            )
        if question.status != QuestionStatus.RESOLVED:
            return VerifyResult(
                status=VerificationStatus.UNVERIFIABLE,
                current=current,
                message="Question not RESOLVED",
            )
        # VERIFY_ONLY: report CURRENT path snapshot; do not NLP-match freeform answers
        return VerifyResult(
            status=VerificationStatus.UNVERIFIABLE,
            current=current,
            expected=question.answer,
            message=(
                "routing.verify is VERIFY_ONLY — inspect CURRENT path; "
                "do not auto-match freeform answers or promote INTENDED→VERIFIED"
            ),
        )
