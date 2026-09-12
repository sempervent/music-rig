"""Tests migrated to smoke/test_cli_help.py."""

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

def test_cli_reconcile_run_help():
    result = runner.invoke(app, ["reconcile", "--help"])
    assert result.exit_code == 0
    assert "run" in result.stdout

