"""ableton.template — VERIFY_ONLY / MANUAL."""

from __future__ import annotations

from typing import Any

from music_rig import ableton_state
from music_rig.models import OpenQuestion, QuestionStatus, ReconciliationState
from music_rig.reconciliation.adapters.base import ReconciliationAdapter
from music_rig.reconciliation.types import (
    Capability,
    Plan,
    VerificationStatus,
    VerifyResult,
)


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
        if question.reconciled_at is not None:
            state = ReconciliationState.RECONCILED
        elif question.status != QuestionStatus.RESOLVED or not question.answer.strip():
            state = ReconciliationState.NEEDS_ANSWER
        else:
            state = ReconciliationState.NEEDS_AGENT_ACTION
        cmds = ["uv run rig ableton targets"]
        if path_key:
            cmds.append(f"uv run rig ableton template {path_key}")
        cmds.append(
            f"uv run rig reconcile finalize question {question.id} "
            f"--no-current-change --note \"template reviewed\" --yes"
        )
        return Plan(
            artifact_type="question",
            artifact_id=question.id,
            state=state,
            capability=self.capability,
            current=current,
            desired=question.answer.strip() or None,
            blockers=(
                [
                    "VERIFY_ONLY/MANUAL: confirm Live set offline; "
                    "do not promote INTENDED→VERIFIED here"
                ]
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
                "ableton.template is VERIFY_ONLY/MANUAL — freeform answers not auto-matched"
            ),
        )
