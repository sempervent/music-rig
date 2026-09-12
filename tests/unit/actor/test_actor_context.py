"""Tests migrated to unit/actor/test_actor_context.py."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner
from music_rig.actor import ActorKind, get_actor, reset_actor, set_actor
from music_rig.cli import app
from music_rig.models import AnswerActor, ReconciliationState
from music_rig.reconciliation.dispatch import DispatchMode, classify_reconciliation_dispatch
from music_rig.reconciliation.types import Capability, Plan
from music_rig.verification_policy import (
    VerificationPolicy,
    evidence_basis_for,
    has_evidence_authority,
    has_human_attestation,
    policy_matrix,
    verification_policy_for,
)

runner = CliRunner()

@pytest.fixture(autouse=True)
def _reset_actor():
    reset_actor()
    yield
    reset_actor()

def test_root_am_bot_sets_bot_actor():
    r = runner.invoke(app, ["--am-bot", "agent", "capabilities", "--json"])
    assert r.exit_code == 0, r.output
    assert get_actor() is ActorKind.BOT

def test_root_help_documents_am_bot():
    import re

    r = runner.invoke(app, ["--help"])
    assert r.exit_code == 0, r.output
    # Rich may inject ANSI / wrap cells; strip SGR before substring checks.
    plain = re.sub(r"\x1b\[[0-9;]*m", "", r.output)
    assert "--am-bot" in plain

def test_human_default_actor():
    assert get_actor() is ActorKind.HUMAN
    set_actor(ActorKind.BOT)
    assert get_actor() is ActorKind.BOT
    reset_actor()
    assert get_actor() is ActorKind.HUMAN

def test_am_bot_tui_rejected():
    r = runner.invoke(app, ["--am-bot", "tui"])
    assert r.exit_code != 0
    assert "not supported" in (r.output + str(r.exception)).casefold()

