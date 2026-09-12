"""HANDOFF PACKETS for NEEDS_AGENT_ACTION (structured ops first; CLI is presentation).

Prefer ``candidate_operations`` / structured suggestions. ``finalize_command_template``
and ``suggested_current_commands`` are rendered compatibility fields only.
"""

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
    from music_rig.reconciliation.suggestions import (
        ActionSuggestion,
        SuggestionKind,
        render_suggestion,
        suggest_finalize,
    )

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
        target = {k: v for k, v in question.target.model_dump().items() if v is not None}
    finalize_suggestion = suggest_finalize(
        question.id,
        confirm_current_reconciled=True,
        note="…",
    )
    finalize_op = finalize_suggestion.operation or RigOperation(
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
    # PRESENTATION ONLY — not the source of truth for intent.
    finalize_template = render_cli(finalize_op)
    family_suggestions = [
        ActionSuggestion(
            kind=SuggestionKind.CLI_HINT,
            intent=fam if fam.startswith("rig") else f"rig {fam}",
            description="Suggested command family for agent interpretation",
            code="command_family",
        )
        for fam in suggested_command_families
    ]
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
        # PRESENTATION: rendered from families for older agent JSON consumers.
        "suggested_current_commands": [render_suggestion(s) for s in family_suggestions],
        "suggestions": [s.to_dict() for s in family_suggestions],
        "candidate_operations": candidate_operations or [],
        "finalize_operation": finalize_op.to_dict(),
        "finalize_suggestion": finalize_suggestion.to_dict(),
        "postcondition": postcondition,
        "linked_todos": list(question.related_todos),
        "linked_changes": list(question.related_changes),
        "requires_agent_interpretation": requires_agent_interpretation,
        "manual_finalize_allowed": manual_finalize_allowed,
        "required_confirmation": "--confirm-current-reconciled",
        # PRESENTATION ONLY.
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


def has_apply_authority(question: OpenQuestion) -> bool:
    """Observation OR (policy-attestation + HUMAN answer)."""
    from music_rig.verification_policy import has_evidence_authority

    return has_evidence_authority(question)
