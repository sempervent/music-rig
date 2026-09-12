"""Compact provider-facing projection of the rich agent packet."""

from __future__ import annotations

from typing import Any


def project_provider_packet(packet: dict[str, Any]) -> dict[str, Any]:
    """Strip aliases/duplication for LLM input while keeping stable IDs.

    Canonical ``build_agent_packet`` remains rich for audit/debug; this view
    is what providers should see.
    """
    context = packet.get("relevant_current_context") or {}
    # Prefer a single CURRENT snapshot; drop near-duplicates.
    current_facts: dict[str, Any] = {}
    for key in (
        "midi_clock",
        "midi",
        "patchbay_models",
        "routing_path_ids",
        "channel_devices",
        "related_todo_summaries",
    ):
        if key in context and context[key] is not None:
            current_facts[key] = context[key]
    # Flatten common nested current if present under aliases
    for alias in ("current_snapshot", "relevant_current_entities"):
        if alias in context and alias not in current_facts:
            current_facts[alias] = context[alias]

    view: dict[str, Any] = {
        "artifact": packet.get("artifact"),
        "question": packet.get("question"),
        "final_human_answer": packet.get("final_human_answer"),
        "answer_state": packet.get("answer_state"),
        "question_status": packet.get("question_status"),
        "verification_result": packet.get("verification_result"),
        "typed_target": packet.get("typed_target"),
        "reconciliation_state": packet.get("reconciliation_state"),
        "capability": packet.get("capability"),
        "current_facts": current_facts,
        "related_todos": packet.get("related_todos") or [],
        "related_changes": packet.get("related_changes") or [],
        "allowed_operation_kinds": packet.get("allowed_operation_kinds") or [],
        "candidate_operations": packet.get("candidate_operations") or [],
        "required_postconditions": packet.get("required_postconditions") or [],
        "forbidden_claims": packet.get("forbidden_claims") or [],
        "plan_blockers": packet.get("plan_blockers") or [],
        "packet_hash": packet.get("packet_hash"),
    }
    # Keep truth boundaries short
    tb = packet.get("truth_boundaries")
    if isinstance(tb, list):
        view["truth_boundaries"] = tb[:12]
    elif tb:
        view["truth_boundaries"] = tb
    return view
