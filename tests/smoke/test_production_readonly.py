"""Tests migrated to smoke/test_production_readonly.py."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import pytest
import yaml
from typer.testing import CliRunner
from music_rig import channel_state, question_service, todo_service
from music_rig.channel_state import propose_set_source, validate_channel_map
from music_rig.cli import app
from music_rig.models import AnswerState, QuestionStatus, ReconciliationState, TodoStatus
from music_rig.reconciliation import service as reconcile_service
from music_rig.store import StoreError, load_questions, load_todo
from music_rig.tui.app import RigApp
from music_rig.tui.screens.answer import AnswerScreen
import shutil
import subprocess
import sys
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
from music_rig.reconciliation.context import ReconciliationContext
from music_rig.reconciliation.operation_registry import allowlisted_kinds, get_spec
from music_rig.reconciliation.operations import RigOperation
from music_rig.store import StoreError, ROOT, load_questions

def test_production_q001_baseline_preserved():
    """Do not undo Stage 18 Q-001 reconciliation during Stage 19."""
    doc = load_questions()
    q1 = doc.question_map()["Q-001"]
    assert q1.status == QuestionStatus.RESOLVED
    assert q1.answer.strip()
    assert q1.resolved_at is not None
    assert q1.reconciled_at is not None
    assert "Alesis 2" in q1.answer and "Alesis 1" in q1.answer
    assert question_service.derive_answer_state(q1) == AnswerState.FINAL
    assert question_service.lifecycle_label(q1) == "RESOLVED/RECONCILED"

    for qid in ("Q-002", "Q-003", "Q-004", "Q-006"):
        q = doc.question_map()[qid]
        assert q.status == QuestionStatus.RESOLVED
        assert q.reconciled_at is not None

    todo = load_todo()
    r3 = todo.task_map()["RIG-003"]
    assert r3.status == TodoStatus.DONE
    assert "RIG-003" not in todo.next_session


def test_production_readonly_packet_q007():
    """Read-only production packet — no mutation."""
    before = question_service.get_question("Q-007")
    packet = build_agent_packet("Q-007")
    assert "ART P48" in packet["final_human_answer"]
    assert "Behringer PX3000" in packet["final_human_answer"]
    assert packet["relevant_current_context"].get("unit_identity_note")
    after = question_service.get_question("Q-007")
    assert after.answer == before.answer
    assert after.reconciled_at == before.reconciled_at

