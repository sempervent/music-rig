"""Tests migrated to unit/agent/test_operation_allowlist.py."""

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

def test_capabilities_includes_new_ops():
    caps = capabilities()
    kinds = caps["allowlisted_operations"]
    assert "channels.set_source" in kinds
    assert "channels.clear_source" in kinds
    assert "path.move" in kinds
    assert "path.set_evidence" in kinds
    assert "PLAN_ONLY" in caps["autonomy_levels"]

def test_allowlisted_includes_path_and_channels_clear():
    kinds = allowlisted_kinds(agent_only=True)
    assert "path.insert" in kinds
    assert "path.remove" in kinds
    assert "path.set_mode" in kinds
    assert "channels.clear_source" in kinds
    assert get_spec("channels.clear_source").agent_allowed is True

