"""Tests migrated to integration/agent/test_inspection.py."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
import pytest
import yaml
from typer.testing import CliRunner
from music_rig import channel_state, patchbay_state, question_service
from music_rig import store as store_mod
from music_rig.agent import (
    AgentReconciliationProposal,
    ProposalStatus,
    apply_proposal,
    build_agent_packet,
    capabilities,
    validate_proposal,
)
from music_rig.agent import transaction as transaction_mod
from music_rig.agent.errors import (
    ConcurrentModificationError,
    PlanConflictError,
    ProviderInvalidResponseError,
    ProviderTimeoutError,
)
from music_rig.agent.inspection import InspectionRequest, execute_inspection
from music_rig.agent.orchestrate import AutonomyLevel, autonomous_reconcile, run_provider_loop
from music_rig.agent.provider import CommandProvider
from music_rig.agent.transaction import (
    commit_transaction,
    evaluate_postconditions,
    prepare_transaction,
)
from music_rig.cli import app
from music_rig.reconciliation.context import ReconciliationContext
from music_rig.reconciliation.operation_registry import allowlisted_kinds, get_spec
from music_rig.reconciliation.operations import RigOperation
from music_rig.store import StoreError, ROOT, load_questions

runner = CliRunner()

def test_cli_provider_status(fx21, monkeypatch):
    monkeypatch.setattr("music_rig.store.ROOT", fx21["tmp"])
    monkeypatch.setattr("music_rig.local_config.ROOT", fx21["tmp"])
    r = runner.invoke(app, ["agent", "provider", "status", "--json"])
    assert r.exit_code == 0, r.output
    payload = json.loads(r.output)
    assert payload["ok"] is True
    assert "configured" in payload["result"]
    assert payload["result"]["configured"] is False

def test_inspection_routing_path(fx21):
    result = execute_inspection(
        InspectionRequest(kind="routing.path", id="dirty"),
        ctx=fx21["ctx"],
    )
    assert result["path_id"] == "dirty"
    assert result["path"]["label"] == "DIRTY"
    assert "branches" in result["path"]

