"""controls.verify — VERIFY_ONLY controller evidence."""

from __future__ import annotations

from typing import Any

from music_rig import control_state
from music_rig.models import OpenQuestion, QuestionStatus, ReconciliationState
from music_rig.reconciliation.adapters.base import ReconciliationAdapter
from music_rig.reconciliation.types import (
    Capability,
    Plan,
    VerificationStatus,
    VerifyResult,
)


class ControlsVerifyAdapter(ReconciliationAdapter):
    domain = "controls.verify"
    capability = Capability.VERIFY_ONLY

    def read_current(self, question: OpenQuestion, *, paths: dict[str, Any]) -> Any:
        data = control_state.load_raw(paths.get("controllers"))
        gear = question.target.gear if question.target else None
        controllers = data.get("controllers") or []
        if not isinstance(controllers, list):
            return {"error": "controllers must be a list"}
        if gear:
            for body in controllers:
                if isinstance(body, dict) and body.get("gear_ref") == gear:
                    return {
                        "gear_ref": gear,
                        "contexts": [
                            c.get("id")
                            for c in (body.get("contexts") or [])
                            if isinstance(c, dict)
                        ],
                        "notes": body.get("notes"),
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
        if question.reconciled_at is not None:
            state = ReconciliationState.RECONCILED
        elif question.status != QuestionStatus.RESOLVED or not question.answer.strip():
            state = ReconciliationState.NEEDS_ANSWER
        else:
            state = ReconciliationState.NEEDS_AGENT_ACTION
        cmds = ["uv run rig controls summary"]
        if gear:
            cmds.append(f"uv run rig current controls verify {gear}")
            cmds.append(f"uv run rig controls show {gear}")
        cmds.append(
            f"uv run rig reconcile finalize question {question.id} "
            f"--no-current-change --note \"controls reviewed\" --yes"
        )
        return Plan(
            artifact_type="question",
            artifact_id=question.id,
            state=state,
            capability=self.capability,
            current=current,
            desired=question.answer.strip() or None,
            blockers=(
                ["VERIFY_ONLY: use controls verify CLI; finalize with --no-current-change"]
                if state == ReconciliationState.NEEDS_AGENT_ACTION
                else []
            ),
            suggested_commands=cmds,
        )

    def verify(self, question: OpenQuestion, *, paths: dict[str, Any]) -> VerifyResult:
        return VerifyResult(
            status=VerificationStatus.UNVERIFIABLE,
            current=self.read_current(question, paths=paths),
            expected=question.answer,
            message=(
                "controls.verify is VERIFY_ONLY — freeform answers are not auto-matched"
            ),
        )
