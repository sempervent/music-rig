"""Tests migrated to integration/reconciliation/test_reconcile_run.py."""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
import pytest
import yaml
from typer.testing import CliRunner
from music_rig.agent.cursor_provider import CursorProvider, parse_cursor_envelope
from music_rig.agent.errors import ProviderInvalidResponseError
from music_rig.agent.ollama_provider import OllamaProvider
from music_rig.agent.prompt import build_planner_prompt
from music_rig.agent.turns import AgentTurnKind, agent_turn_json_schema
from music_rig.agent.turns import agent_turn_json_schema as schema_fn
from music_rig.cli import app
from music_rig.local_config import load_local_config, update_agent_config
from music_rig.reconciliation.run import reconcile_run
from music_rig.reconciliation.types import Capability
from music_rig.models import ReconciliationState

runner = CliRunner()

def test_provider_use_writes_local_only(tmp_path, monkeypatch):
    root = tmp_path
    monkeypatch.setattr("music_rig.local_config.ROOT", root)
    monkeypatch.setattr("music_rig.store.ROOT", root)
    update_agent_config(provider="cursor", root=root)
    cfg = load_local_config(root=root)
    assert cfg is not None
    assert cfg.agent.provider == "cursor"
    # no data/ mutations
    assert not (root / "data").exists()

def test_reconcile_run_deterministic_no_provider(monkeypatch):
    calls = {"n": 0}

    def boom(*a, **k):
        calls["n"] += 1
        raise AssertionError("provider should not be called")

    monkeypatch.setattr(
        "music_rig.reconciliation.run.autonomous_reconcile", boom
    )
    from music_rig.reconciliation.types import Plan

    def fake_plan(qid, **kwargs):
        return Plan(
            artifact_type="question",
            artifact_id=qid,
            state=ReconciliationState.READY_TO_APPLY,
            capability=Capability.APPLY_AND_VERIFY,
            suggested_commands=[],
            blockers=[],
            operations=[],
        )

    monkeypatch.setattr(
        "music_rig.reconciliation.run.recon.plan_question", fake_plan
    )
    result = reconcile_run("Q-200")
    assert result["mode"] == "deterministic"
    assert result["provider_invoked"] is False
    assert calls["n"] == 0

def test_reconcile_run_missing_provider_guidance(monkeypatch):
    from music_rig.reconciliation.types import Plan

    def fake_plan(qid, **kwargs):
        return Plan(
            artifact_type="question",
            artifact_id=qid,
            state=ReconciliationState.NEEDS_AGENT_ACTION,
            capability=Capability.MANUAL,
            suggested_commands=[],
            blockers=[],
            operations=[],
        )

    monkeypatch.setattr(
        "music_rig.reconciliation.run.recon.plan_question", fake_plan
    )
    monkeypatch.setattr(
        "music_rig.reconciliation.run.provider_status",
        lambda root=None: {"configured": False},
    )
    monkeypatch.setattr(
        "music_rig.reconciliation.run.detect_providers",
        lambda root=None: {
            "cursor": {"available": True, "version": "x"},
            "ollama": {"available": True, "models": ["m"]},
        },
    )
    result = reconcile_run("Q-200")
    assert result["mode"] == "needs_provider"
    assert "provider setup" in result["message"].lower()

def test_cli_provider_use_cursor(tmp_path, monkeypatch):
    monkeypatch.setattr("music_rig.local_config.ROOT", tmp_path)
    # may fail if agent not found when resolving — use only writes config
    result = runner.invoke(app, ["agent", "provider", "use", "cursor"])
    # command writes config regardless of install
    assert result.exit_code == 0
    cfg = load_local_config(root=tmp_path)
    assert cfg.agent.provider == "cursor"

