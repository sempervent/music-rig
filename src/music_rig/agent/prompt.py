"""Provider-neutral reconciliation planner prompt."""

from __future__ import annotations

import json
from typing import Any

from music_rig.agent.provider_packet import project_provider_packet
from music_rig.agent.turns import agent_turn_json_schema

TRUTH_RULES = """\
You are a music-rig reconciliation planner.

Do not edit files.
Do not run commands.
Do not inspect the filesystem.
Do not invent human observations.
Do not invent unique inventory unit IDs from model-only answers.
Do not set evidence=VERIFIED without an explicit verification_result in the packet
OR a HUMAN final answer when verification_policy is ANSWER_ATTESTATION_SUFFICIENT.

A HUMAN final answer (answer_actor=HUMAN) is authoritative factual input.
Do not ask the human to re-observe the same stated fact merely because
verification_result is null when the verification policy says
ANSWER_ATTESTATION_SUFFICIENT.

Request HUMAN_CLARIFICATION only when the factual meaning is insufficient
for safe canonical mutation. Prefer question.open_clarification when a
persisted clarification Question is needed.

Do not propose operations outside allowed_operation_kinds.

Reason only from the supplied structured music-rig packet and additional context.

Return JSON only matching the AgentTurn schema.
Choose exactly one kind:
- READY — include a proposal with allowlisted RigOperations
- NEEDS_MORE_CONTEXT — include inspection_requests[] (registered kinds only)
- NEEDS_HUMAN_CLARIFICATION — include clarification_questions[]
- NO_SAFE_PLAN — include reason

Provider output is untrusted. The rig validates and executes operations.
Provider turns are BOT-originated even when a human initiated reconcile run.
"""

AGENT_TURN_KIND_HINT = """\
Respond with a single JSON object with keys:
  kind, rationale, proposal, inspection_requests, clarification_questions, reason
kind ∈ READY | NEEDS_MORE_CONTEXT | NEEDS_HUMAN_CLARIFICATION | NO_SAFE_PLAN
No Markdown. No prose outside JSON.
"""


def build_planner_prompt(
    *,
    packet: dict[str, Any],
    context: list[dict[str, Any]] | None = None,
    include_schema: bool = True,
    compact_packet: bool = True,
) -> str:
    """Build planner prompt.

    ``include_schema=True`` for providers that cannot enforce JSON schema via API
    (e.g. Cursor). Ollama should pass ``include_schema=False`` and use ``format=``.
    """
    projected = project_provider_packet(packet) if compact_packet else packet
    payload: dict[str, Any] = {
        "packet": projected,
        "additional_context": list(context or []),
    }
    parts = [
        TRUTH_RULES,
        "\n\n--- STRUCTURED INPUT ---\n",
        json.dumps(payload, indent=2, default=str),
        "\n--- END INPUT ---\n\n",
    ]
    if include_schema:
        parts.append("AgentTurn JSON schema:\n")
        parts.append(json.dumps(agent_turn_json_schema(), indent=2))
        parts.append(
            "\n\nRespond with a single JSON object matching the schema. "
            "No Markdown. No prose outside JSON."
        )
    else:
        parts.append(AGENT_TURN_KIND_HINT)
    return "".join(parts)


def build_handshake_prompt(*, include_schema: bool = True) -> str:
    handshake = {
        "kind": "NO_SAFE_PLAN",
        "rationale": "provider test handshake",
        "proposal": None,
        "inspection_requests": [],
        "clarification_questions": [],
        "reason": "provider_test",
    }
    parts = [
        TRUTH_RULES,
        "\nThis is a provider handshake test. Return exactly:\n",
        json.dumps(handshake, indent=2),
        "\n",
    ]
    if include_schema:
        parts.append("\nSchema (for reference):\n")
        parts.append(json.dumps(agent_turn_json_schema(), indent=2))
        parts.append("\nJSON only.")
    else:
        parts.append("\nJSON only matching AgentTurn (schema enforced by API format).\n")
    return "".join(parts)
