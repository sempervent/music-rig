"""Dispatch classifier, provider eligibility, and progress isolation tests."""

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


def _plan(
    *,
    state: ReconciliationState,
    capability: Capability = Capability.MANUAL,
    blockers: list | None = None,
    current=None,
    desired: str = "",
    operations: list | None = None,
    details: dict | None = None,
) -> Plan:
    return Plan(
        artifact_type="question",
        artifact_id="Q-TEST",
        state=state,
        capability=capability,
        current=current,
        desired=desired,
        operations=operations or [],
        blockers=blockers or [],
        suggested_commands=[],
        details=details or {},
    )


@pytest.mark.parametrize(
    "state",
    [
        ReconciliationState.NEEDS_ANSWER,
        ReconciliationState.DRAFT_ANSWER,
        ReconciliationState.READY_TO_APPLY,
        ReconciliationState.CURRENT_MATCHES,
        ReconciliationState.READY_TO_FINALIZE,
        ReconciliationState.RECONCILED,
    ],
)
def test_non_agent_states_not_provider_eligible(state):
    d = classify_reconciliation_dispatch(_plan(state=state))
    assert d.provider_eligible is False


def test_human_observation_blocker_outranks_needs_agent_action():
    d = classify_reconciliation_dispatch(
        _plan(
            state=ReconciliationState.NEEDS_AGENT_ACTION,
            capability=Capability.VERIFY_ONLY,
            blockers=[{"code": "needs_human_observation"}],
            current={"master": "ableton"},
            desired="Ableton is master",
        )
    )
    assert d.mode is DispatchMode.HUMAN_OBSERVATION
    assert d.provider_eligible is False


def test_agent_eligible_for_manual_without_human_blockers():
    d = classify_reconciliation_dispatch(
        _plan(
            state=ReconciliationState.NEEDS_AGENT_ACTION,
            capability=Capability.MANUAL,
            blockers=[],
            desired="PB-A is ART P48",
        )
    )
    assert d.mode is DispatchMode.AGENT
    assert d.provider_eligible is True


def test_clarification_blocker():
    d = classify_reconciliation_dispatch(
        _plan(
            state=ReconciliationState.NEEDS_AGENT_ACTION,
            blockers=[{"code": "needs_human_clarification"}],
            desired="one of the patchbays is probably the Behringer",
        )
    )
    assert d.mode is DispatchMode.HUMAN_CLARIFICATION
    assert d.provider_eligible is False


@pytest.mark.parametrize("code", sorted(HUMAN_BLOCKER_CODES))
def test_hard_human_blocker_codes_block_provider(code):
    d = classify_reconciliation_dispatch(
        _plan(
            state=ReconciliationState.NEEDS_AGENT_ACTION,
            blockers=[{"code": code}],
        )
    )
    assert d.provider_eligible is False


def test_provider_call_counts_by_dispatch(monkeypatch):
    from music_rig.reconciliation import run as run_mod

    cases = [
        (
            _plan(state=ReconciliationState.NEEDS_ANSWER),
            0,
            "needs_human",
        ),
        (
            _plan(state=ReconciliationState.DRAFT_ANSWER),
            0,
            "needs_human",
        ),
        (
            _plan(
                state=ReconciliationState.NEEDS_AGENT_ACTION,
                capability=Capability.VERIFY_ONLY,
                blockers=[{"code": "needs_human_observation"}],
                current={"master": "ableton"},
                desired="ableton",
            ),
            0,
            "needs_verification",
        ),
        (
            _plan(
                state=ReconciliationState.NEEDS_AGENT_ACTION,
                blockers=[{"code": "needs_human_clarification"}],
            ),
            0,
            "needs_clarification",
        ),
        (
            _plan(state=ReconciliationState.READY_TO_APPLY, operations=[{"kind": "x"}]),
            0,
            "deterministic",
        ),
        (
            _plan(state=ReconciliationState.CURRENT_MATCHES),
            0,
            "deterministic",
        ),
        (
            _plan(state=ReconciliationState.RECONCILED),
            0,
            "already_reconciled",
        ),
    ]

    for plan, expected_calls, mode in cases:
        calls = {"n": 0}

        def boom(*a, **k):
            calls["n"] += 1
            raise AssertionError("provider invoked")

        monkeypatch.setattr(run_mod, "autonomous_reconcile", boom)
        monkeypatch.setattr(run_mod.recon, "plan_question", lambda *a, **k: plan)
        # Avoid finalize side effects for CURRENT_MATCHES
        monkeypatch.setattr(
            run_mod.recon,
            "finalize_question",
            lambda *a, **k: {"dry_run": True, "question_id": "Q-TEST"},
        )
        result = run_mod.reconcile_run("Q-TEST")
        assert calls["n"] == expected_calls, (mode, result)
        assert result["mode"] == mode
        assert result["provider_invoked"] is False


def test_agent_required_invokes_provider_once(monkeypatch):
    from music_rig.reconciliation import run as run_mod

    plan = _plan(
        state=ReconciliationState.NEEDS_AGENT_ACTION,
        capability=Capability.MANUAL,
        desired="PB-A is ART",
    )
    calls = {"n": 0}

    def fake_auto(*a, **k):
        calls["n"] += 1
        return {"ok": True, "message": "planned"}

    monkeypatch.setattr(run_mod, "autonomous_reconcile", fake_auto)
    monkeypatch.setattr(run_mod.recon, "plan_question", lambda *a, **k: plan)
    monkeypatch.setattr(
        run_mod,
        "provider_status",
        lambda **k: {"configured": True, "provider_type": "ollama"},
    )
    result = run_mod.reconcile_run("Q-TEST")
    assert calls["n"] == 1
    assert result["provider_invoked"] is True
    assert result["mode"] == "agent"


def test_yes_does_not_fabricate_observation(monkeypatch):
    from music_rig.reconciliation import run as run_mod

    plan = _plan(
        state=ReconciliationState.NEEDS_AGENT_ACTION,
        capability=Capability.VERIFY_ONLY,
        blockers=[{"code": "needs_human_observation"}],
        current={"master": "ableton"},
        desired="Ableton is master",
    )
    monkeypatch.setattr(run_mod.recon, "plan_question", lambda *a, **k: plan)
    monkeypatch.setattr(
        run_mod,
        "autonomous_reconcile",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no provider")),
    )
    result = run_mod.reconcile_run("Q-014", apply=True, yes=True)
    assert result["provider_invoked"] is False
    assert result["mode"] == "needs_verification"
    assert "--yes does not imply" in result["message"]


def test_progress_json_isolation():
    """Progress sink must not be required for JSON; CollectingProgress is clean."""
    sink = CollectingProgress()
    tracker = ProgressTracker(sink=sink, provider="Ollama", model="qwen")
    tracker.emit(ProgressPhase.PROVIDER_GENERATING, "generating")
    assert len(sink.events) == 1
    assert sink.events[0].message == "generating"
    # Event serializes without Rich markup
    blob = json.dumps(sink.events[0].to_dict())
    assert "generating" in blob


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


def test_ollama_metrics_parser():
    from music_rig.agent.ollama_provider import extract_ollama_metrics

    raw = {
        "total_duration": 34_200_000_000,
        "load_duration": 1_000_000_000,
        "prompt_eval_count": 2104,
        "prompt_eval_duration": 5_000_000_000,
        "eval_count": 167,
        "eval_duration": 28_000_000_000,
    }
    m = extract_ollama_metrics(raw)
    assert m["prompt_eval_count"] == 2104
    assert m["total_s"] == 34.2
    assert "invented" not in m


def test_benchmark_format_includes_header():
    from music_rig.agent.benchmark import format_benchmark_table

    text = format_benchmark_table(
        {
            "prompt_chars_ollama": 100,
            "prompt_chars_with_schema": 500,
            "rows": [
                {
                    "model": "qwen3.5:latest",
                    "warm_total_s": 12.3,
                    "prompt_tokens": 100,
                    "output_tokens": 20,
                    "schema_valid": True,
                }
            ],
            "fastest_valid": "qwen3.5:latest",
            "note": "note",
        }
    )
    assert "OLLAMA RECONCILIATION BENCHMARK" in text
    assert "qwen3.5:latest" in text
