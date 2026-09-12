"""Stage 21 UX repair — Cursor/Ollama providers + reconcile run (mocked)."""

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


def test_cli_reconcile_run_help():
    result = runner.invoke(app, ["reconcile", "--help"])
    assert result.exit_code == 0
    assert "run" in result.stdout


def test_cli_provider_use_cursor(tmp_path, monkeypatch):
    monkeypatch.setattr("music_rig.local_config.ROOT", tmp_path)
    # may fail if agent not found when resolving — use only writes config
    result = runner.invoke(app, ["agent", "provider", "use", "cursor"])
    # command writes config regardless of install
    assert result.exit_code == 0
    cfg = load_local_config(root=tmp_path)
    assert cfg.agent.provider == "cursor"
