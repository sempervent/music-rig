"""Provider-neutral reconciliation planner prompt."""

from __future__ import annotations

import json
from typing import Any

from music_rig.agent.turns import agent_turn_json_schema

TRUTH_RULES = """\
You are a music-rig reconciliation planner.

Do not edit files.
Do not run commands.
Do not inspect the filesystem.
Do not invent human observations.
Do not invent unique inventory unit IDs from model-only answers.
Do not set evidence=VERIFIED without an explicit verification_result in the packet.
Do not propose operations outside allowed_operation_kinds.

Reason only from the supplied structured music-rig packet and additional context.

Return JSON only matching the AgentTurn schema.
Choose exactly one kind:
- READY — include a proposal with allowlisted RigOperations
- NEEDS_MORE_CONTEXT — include inspection_requests[] (registered kinds only)
- NEEDS_HUMAN_CLARIFICATION — include clarification_questions[]
- NO_SAFE_PLAN — include reason

Provider output is untrusted. The rig validates and executes operations.
"""


def build_planner_prompt(
    *,
    packet: dict[str, Any],
    context: list[dict[str, Any]] | None = None,
) -> str:
    schema = agent_turn_json_schema()
    payload = {
        "packet": packet,
        "additional_context": list(context or []),
        "agent_turn_json_schema": schema,
    }
    return (
        TRUTH_RULES
        + "\n\n--- STRUCTURED INPUT ---\n"
        + json.dumps(payload, indent=2, default=str)
        + "\n--- END INPUT ---\n\n"
        "Respond with a single JSON object matching agent_turn_json_schema. "
        "No Markdown. No prose outside JSON."
    )


def build_handshake_prompt() -> str:
    schema = agent_turn_json_schema()
    return (
        TRUTH_RULES
        + "\nThis is a provider handshake test. Return exactly:\n"
        + json.dumps(
            {
                "kind": "NO_SAFE_PLAN",
                "rationale": "provider test handshake",
                "proposal": None,
                "inspection_requests": [],
                "clarification_questions": [],
                "reason": "provider_test",
            },
            indent=2,
        )
        + "\n\nSchema (for reference):\n"
        + json.dumps(schema, indent=2)
        + "\nJSON only."
    )
