"""Tests migrated to unit/agent/test_provider_ollama.py."""

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

def test_prompt_builder_includes_schema():
    text = build_planner_prompt(packet={"artifact": {"id": "Q-001"}}, context=[])
    assert "AgentTurn" in text or "kind" in text
    assert "allowed_operation_kinds" in text or "Do not edit files" in text
    schema = schema_fn()
    assert "properties" in schema

def test_ollama_sends_format_schema(tmp_path):
    seen = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            seen["body"] = json.loads(raw.decode())
            payload = {
                "message": {
                    "content": json.dumps(
                        {
                            "kind": "NO_SAFE_PLAN",
                            "rationale": "ok",
                            "proposal": None,
                            "inspection_requests": [],
                            "clarification_questions": [],
                            "reason": "provider_test",
                        }
                    )
                }
            }
            data = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):  # noqa: D401
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        prov = OllamaProvider(
            base_url=f"http://127.0.0.1:{port}",
            model="test-model",
            timeout_seconds=5,
        )
        turn, diag = prov.handshake()
        assert turn.kind is AgentTurnKind.NO_SAFE_PLAN
        assert seen["body"]["stream"] is False
        assert seen["body"]["format"] == agent_turn_json_schema()
        assert seen["body"]["options"]["temperature"] == 0.0
        assert diag["format_schema"] == "AgentTurn.model_json_schema()"
    finally:
        server.shutdown()

