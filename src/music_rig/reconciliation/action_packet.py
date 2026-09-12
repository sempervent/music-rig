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
) -> dict[str, Any]:
    """Enrich plan JSON for agent handoff after human observation/answer."""
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
    packet: dict[str, Any] = {
        "artifact": {"type": "question", "id": question.id},
        "human_answer": question.answer,
        "observation": observation,
        "typed_target": target,
        "current_snapshot": current_snapshot,
        "related_ids": related_ids
        or {
            "todos": list(question.related_todos),
            "changes": list(question.related_changes),
        },
        "suggested_command_families": suggested_command_families,
        "postcondition": postcondition,
        "linked_todos": list(question.related_todos),
        "linked_changes": list(question.related_changes),
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
