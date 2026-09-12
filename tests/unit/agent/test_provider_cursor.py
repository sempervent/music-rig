"""Tests migrated to unit/agent/test_provider_cursor.py."""

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

def _fake_cursor_script(tmp: Path, mode: str = "ok") -> Path:
    script = tmp / "fake_cursor.py"
    if mode == "ok":
        body = {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": json.dumps(
                {
                    "kind": "READY",
                    "rationale": "fake cursor",
                    "proposal": {
                        "artifact_id": "Q-200",
                        "status": "READY",
                        "operations": [
                            {
                                "namespace": "patchbay",
                                "action": "set_model",
                                "args": {
                                    "bay_id": "PB-A",
                                    "model": "ART P48",
                                    "question_id": "Q-200",
                                },
                            }
                        ],
                        "finalize": False,
                    },
                    "inspection_requests": [],
                    "clarification_questions": [],
                    "reason": None,
                }
            ),
        }
        code = f"import json,sys; print(json.dumps({body!r}))"
    elif mode == "prose":
        body = {
            "type": "result",
            "is_error": False,
            "result": "I edited the YAML already.",
        }
        code = f"import json; print(json.dumps({body!r}))"
    elif mode == "bad_turn":
        body = {
            "type": "result",
            "is_error": False,
            "result": json.dumps({"kind": "READY", "proposal": {"nope": True}}),
        }
        code = f"import json; print(json.dumps({body!r}))"
    elif mode == "nonzero":
        code = "import sys; sys.exit(2)"
    elif mode == "oversize":
        code = "print('x' * 2_000_000)"
    else:
        code = "print('not-json')"
    script.write_text(code, encoding="utf-8")
    script.chmod(0o755)
    return script

def test_parse_cursor_envelope_valid():
    turn = parse_cursor_envelope(
        {
            "type": "result",
            "is_error": False,
            "result": json.dumps(
                {
                    "kind": "NO_SAFE_PLAN",
                    "rationale": "x",
                    "proposal": None,
                    "inspection_requests": [],
                    "clarification_questions": [],
                    "reason": "t",
                }
            ),
        }
    )
    assert turn.kind is AgentTurnKind.NO_SAFE_PLAN

def test_cursor_provider_argv_ask_mode_no_workspace(tmp_path, monkeypatch):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append({"argv": argv, "kwargs": kwargs})
        if "--version" in argv:
            class R:
                returncode = 0
                stdout = "fake-version\n"
                stderr = b""

            return R()

        class R:
            returncode = 0
            stdout = json.dumps(
                {
                    "type": "result",
                    "is_error": False,
                    "result": json.dumps(
                        {
                            "kind": "NO_SAFE_PLAN",
                            "rationale": "h",
                            "proposal": None,
                            "inspection_requests": [],
                            "clarification_questions": [],
                            "reason": "provider_test",
                        }
                    ),
                }
            ).encode()
            stderr = b""

        return R()

    monkeypatch.setattr("music_rig.agent.cursor_provider.subprocess.run", fake_run)
    prov = CursorProvider(executable="agent")
    turn, diag = prov.handshake()
    assert turn.kind is AgentTurnKind.NO_SAFE_PLAN
    main = next(c for c in calls if "--output-format" in c["argv"])
    argv = main["argv"]
    assert "--mode=ask" in argv
    assert "--output-format" in argv
    assert "json" in argv
    assert "--workspace" not in argv
    assert main["kwargs"].get("shell") is False
    assert diag.get("workspace_flag") is False

def test_cursor_prose_no_ops_invalid(tmp_path, monkeypatch):
    def fake_run(argv, **kwargs):
        class R:
            returncode = 0
            stdout = json.dumps(
                {"type": "result", "is_error": False, "result": "I edited the YAML already."}
            ).encode()
            stderr = b""

        return R()

    monkeypatch.setattr("music_rig.agent.cursor_provider.subprocess.run", fake_run)
    prov = CursorProvider(executable="agent")
    with pytest.raises(ProviderInvalidResponseError):
        prov.handshake()

