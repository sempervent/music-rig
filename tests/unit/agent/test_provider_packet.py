"""Tests migrated to unit/agent/test_provider_packet.py."""

from __future__ import annotations

import json
import pytest
from music_rig.models import ReconciliationState
from music_rig.progress import CollectingProgress, ProgressEvent, ProgressPhase, ProgressTracker
from music_rig.reconciliation.dispatch import (
    DispatchMode,
    HUMAN_BLOCKER_CODES,
    classify_reconciliation_dispatch,
)
from music_rig.reconciliation.types import Capability, Plan

def test_ollama_prompt_omits_full_schema():
    from music_rig.agent.prompt import build_planner_prompt
    from music_rig.agent.turns import agent_turn_json_schema

    packet = {
        "artifact": {"type": "question", "id": "Q-X"},
        "final_human_answer": "ableton",
        "allowed_operation_kinds": [],
        "packet_hash": "x",
    }
    with_schema = build_planner_prompt(packet=packet, include_schema=True)
    without = build_planner_prompt(packet=packet, include_schema=False)
    schema_blob = json.dumps(agent_turn_json_schema())
    assert schema_blob in with_schema or "agent_turn" in with_schema.casefold() or '"properties"' in with_schema
    assert len(without) < len(with_schema)
    # Ollama path should not embed the full schema document
    assert '"$defs"' not in without and without.count('"properties"') < with_schema.count(
        '"properties"'
    )

def test_provider_packet_compaction_drops_duplicate_aliases():
    from music_rig.agent.provider_packet import project_provider_packet

    packet = {
        "artifact": {"id": "Q-1"},
        "final_human_answer": "ableton",
        "human_answer": "ableton",  # alias not projected
        "relevant_current_context": {
            "midi_clock": {"master": "ableton"},
            "current_snapshot": {"master": "ableton"},
        },
        "allowed_operation_kinds": ["x"],
        "packet_hash": "h",
    }
    view = project_provider_packet(packet)
    assert "human_answer" not in view
    assert view["final_human_answer"] == "ableton"
    assert "midi_clock" in view["current_facts"]

