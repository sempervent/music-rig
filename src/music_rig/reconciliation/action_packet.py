"""Structured NEEDS_AGENT_ACTION handoff packets (no YAML-edit suggestions)."""

from __future__ import annotations

from typing import Any

from music_rig.models import OpenQuestion, VerificationOutcome


def build_action_packet(
    question: OpenQuestion,
    *,
    current_snapshot: Any,
    suggested_command_families: list[str],
    postcondition: str,
    related_ids: dict[str, list[str]] | None = None,
    missing_capability: str | None = None,
    requires_agent_interpretation: bool = True,
    manual_finalize_allowed: bool = True,
    candidate_operations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Enrich plan JSON for agent handoff after human observation/answer."""
    from music_rig.reconciliation.operation_renderer import render_cli
    from music_rig.reconciliation.operations import RigOperation

    vr = question.verification_result
    observation = None
    if vr is not None:
        observation = {
            "outcome": vr.outcome.value,
            "observed_at": vr.observed_at.isoformat(),
            "observed_value": vr.observed_value,
            "note": vr.note,
            "source": vr.source,
        }
    target = None
    if question.target is not None:
        target = {
            k: v
            for k, v in question.target.model_dump().items()
            if v is not None
        }
    finalize_op = RigOperation(
        namespace="question",
        action="finalize_manual",
        args={
            "question_id": question.id,
            "note": "…",
            "complete_linked_todos": True,
            "confirm_dod": True,
        },
        description="Manual/agent-interpreted finalize",
    )
    finalize_template = render_cli(finalize_op)
    packet: dict[str, Any] = {
        "artifact": {"type": "question", "id": question.id},
        "human_answer": question.answer,
        "final_human_answer": question.answer,
        "observation": observation,
        "typed_target": target,
        "current_snapshot": current_snapshot,
        "relevant_current_entities": current_snapshot,
        "related_ids": related_ids
        or {
            "todos": list(question.related_todos),
            "changes": list(question.related_changes),
        },
        "suggested_command_families": suggested_command_families,
        "suggested_current_commands": list(suggested_command_families),
        "candidate_operations": candidate_operations or [],
        "finalize_operation": finalize_op.to_dict(),
        "postcondition": postcondition,
        "linked_todos": list(question.related_todos),
        "linked_changes": list(question.related_changes),
        "requires_agent_interpretation": requires_agent_interpretation,
        "manual_finalize_allowed": manual_finalize_allowed,
        "required_confirmation": "--confirm-current-reconciled",
        "finalize_command_template": finalize_template,
    }
    if missing_capability:
        packet["missing_capability"] = missing_capability
    # Guard: never suggest raw YAML edits
    for fam in suggested_command_families:
        if "yaml" in fam.casefold() and "edit" in fam.casefold():
            raise ValueError("action packets must not suggest YAML edits")
    return packet


def observation_blocks_success(question: OpenQuestion) -> bool:
    """FAILED_TEST must not be treated as successful verification for sweep."""
    vr = question.verification_result
    return vr is not None and vr.outcome == VerificationOutcome.FAILED_TEST


def has_positive_observation(question: OpenQuestion) -> bool:
    vr = question.verification_result
    if vr is None:
        return False
    return vr.outcome in {
        VerificationOutcome.CONFIRMED,
        VerificationOutcome.CORRECTED,
    }
