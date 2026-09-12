"""Tests migrated to unit/reconciliation/test_operations_registry.py."""

from __future__ import annotations

import json
from pathlib import Path
import pytest
import yaml
from typer.testing import CliRunner
from music_rig import agent as agent_mod
from music_rig import patchbay_state, question_service
from music_rig.agent import (
    AgentReconciliationProposal,
    ProposalStatus,
    apply_proposal,
    build_agent_packet,
    validate_proposal,
)
from music_rig.cli import app
from music_rig.models import QuestionStatus
from music_rig.reconciliation.checks import (
    FindingStatus,
    QuestionConvergenceCheck,
    run_checks,
)
from music_rig.reconciliation.context import ReconciliationContext, ReconciliationPaths
from music_rig.reconciliation.operation_registry import (
    allowlisted_kinds,
    get_spec,
    validate_operation_shape,
)
from music_rig.reconciliation.operation_renderer import render_cli
from music_rig.reconciliation.operations import RigOperation
from music_rig.store import StoreError, load_questions
from music_rig import store as store_mod

def test_paths_default_matches_store():
    paths = ReconciliationPaths.default()
    assert paths.questions == store_mod.QUESTIONS_PATH
    assert paths.patchbays == store_mod.PATCHBAYS_PATH

def test_operation_renderer_quotes():
    op = RigOperation(
        namespace="patchbay",
        action="set_model",
        args={"bay_id": "PB-A", "model": "ART P48"},
    )
    cli = render_cli(op)
    assert "set-model" in cli
    assert "ART" in cli
    assert "uv run rig" in cli

def test_unregistered_operation_rejected():
    op = RigOperation(namespace="shell", action="rm", args={"path": "/"})
    with pytest.raises(StoreError, match="unregistered"):
        validate_operation_shape(op)

def test_evidence_verified_arg_rejected():
    op = RigOperation(
        namespace="patchbay",
        action="set_model",
        args={"bay_id": "PB-A", "model": "x", "evidence": "VERIFIED"},
    )
    with pytest.raises(StoreError, match="forbidden|VERIFIED"):
        validate_operation_shape(op)

def test_question_resolve_not_agent_allowed():
    op = RigOperation(
        namespace="question", action="resolve", args={"question_id": "Q-200"}
    )
    with pytest.raises(StoreError, match="not agent-allowed"):
        validate_operation_shape(op, agent=True)

def test_allowlisted_kinds_exclude_shell():
    kinds = allowlisted_kinds(agent_only=True)
    assert "patchbay.set_model" in kinds
    assert all("shell" not in k for k in kinds)
    assert "question.resolve" not in kinds

