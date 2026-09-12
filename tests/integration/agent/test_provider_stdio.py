"""Tests migrated to integration/agent/test_provider_stdio.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from fixtures.repo_fixtures import _provider
from music_rig.agent import (
    build_agent_packet,
)
from music_rig.agent.errors import (
    ProviderInvalidResponseError,
    ProviderTimeoutError,
)
from music_rig.agent.orchestrate import run_provider_loop
from music_rig.agent.provider import CommandProvider
from music_rig.store import ROOT


def test_provider_ready_turn(fx21, monkeypatch):
    monkeypatch.setenv("FAKE_PROVIDER_MODE", "READY")
    state = fx21["tmp"] / "prov_state"
    monkeypatch.setenv("FAKE_PROVIDER_STATE", str(state))
    prov = _provider(fx21["script"], mode="READY", state=state)
    packet = build_agent_packet("Q-200", ctx=fx21["ctx"])
    loop = run_provider_loop(packet, ctx=fx21["ctx"], provider=prov, max_rounds=3)
    assert loop["ok"] is True
    assert loop["status"] == "READY"
    assert loop["proposal"] is not None
    assert any(o.kind == "patchbay.set_model" for o in loop["proposal"].operations)


def test_provider_more_context_loop(fx21, monkeypatch):
    monkeypatch.setenv("FAKE_PROVIDER_MODE", "MORE_CONTEXT")
    state = fx21["tmp"] / "more_state"
    monkeypatch.setenv("FAKE_PROVIDER_STATE", str(state))
    prov = _provider(fx21["script"], mode="MORE_CONTEXT", state=state)
    packet = build_agent_packet("Q-200", ctx=fx21["ctx"])
    loop = run_provider_loop(packet, ctx=fx21["ctx"], provider=prov, max_rounds=5)
    assert loop["ok"] is True
    assert loop["status"] == "READY"
    assert loop["context"]
    assert loop["context"][0]["request"]["kind"] == "routing.path"


def test_provider_repeated_request_terminates(fx21, monkeypatch):
    monkeypatch.setenv("FAKE_PROVIDER_MODE", "REPEAT")
    state = fx21["tmp"] / "rep_state"
    monkeypatch.setenv("FAKE_PROVIDER_STATE", str(state))
    prov = _provider(fx21["script"], mode="REPEAT", state=state)
    packet = build_agent_packet("Q-200", ctx=fx21["ctx"])
    loop = run_provider_loop(packet, ctx=fx21["ctx"], provider=prov, max_rounds=5)
    assert loop["ok"] is False
    assert loop["reason"] == "duplicate_context_request"


def test_provider_round_limit(fx21, monkeypatch):
    monkeypatch.setenv("FAKE_PROVIDER_MODE", "MORE_CONTEXT")
    state = fx21["tmp"] / "lim_state"
    monkeypatch.setenv("FAKE_PROVIDER_STATE", str(state))
    prov = _provider(fx21["script"], mode="MORE_CONTEXT", state=state)
    packet = build_agent_packet("Q-200", ctx=fx21["ctx"])
    loop = run_provider_loop(packet, ctx=fx21["ctx"], provider=prov, max_rounds=1)
    assert loop["ok"] is False
    assert loop["reason"] == "context_round_limit"


def test_provider_malformed_json_no_write(fx21, monkeypatch):
    monkeypatch.setenv("FAKE_PROVIDER_MODE", "MALFORMED")
    before = fx21["patchbays"].read_bytes()
    prov = _provider(fx21["script"], mode="MALFORMED")
    packet = build_agent_packet("Q-200", ctx=fx21["ctx"])
    with pytest.raises(ProviderInvalidResponseError):
        run_provider_loop(packet, ctx=fx21["ctx"], provider=prov, max_rounds=2)
    assert fx21["patchbays"].read_bytes() == before


def test_provider_timeout_no_write(fx21, monkeypatch):
    monkeypatch.setenv("FAKE_PROVIDER_MODE", "TIMEOUT")
    before = fx21["patchbays"].read_bytes()
    prov = _provider(fx21["script"], mode="TIMEOUT", timeout_seconds=1)
    packet = build_agent_packet("Q-200", ctx=fx21["ctx"])
    with pytest.raises(ProviderTimeoutError):
        run_provider_loop(packet, ctx=fx21["ctx"], provider=prov, max_rounds=1)
    assert fx21["patchbays"].read_bytes() == before


def test_provider_nonzero_exit_no_write(fx21, monkeypatch):
    monkeypatch.setenv("FAKE_PROVIDER_MODE", "NONZERO")
    before = fx21["patchbays"].read_bytes()
    prov = _provider(fx21["script"], mode="NONZERO")
    packet = build_agent_packet("Q-200", ctx=fx21["ctx"])
    with pytest.raises(ProviderInvalidResponseError, match="exited"):
        run_provider_loop(packet, ctx=fx21["ctx"], provider=prov, max_rounds=1)
    assert fx21["patchbays"].read_bytes() == before


def test_provider_oversized_output_no_write(fx21, monkeypatch):
    monkeypatch.setenv("FAKE_PROVIDER_MODE", "OVERSIZE")
    before = fx21["patchbays"].read_bytes()
    prov = _provider(fx21["script"], mode="OVERSIZE", max_stdout_bytes=1000)
    packet = build_agent_packet("Q-200", ctx=fx21["ctx"])
    with pytest.raises(ProviderInvalidResponseError, match="exceeded"):
        run_provider_loop(packet, ctx=fx21["ctx"], provider=prov, max_rounds=1)
    assert fx21["patchbays"].read_bytes() == before


def test_provider_cwd_isolated(fx21, monkeypatch):
    monkeypatch.setenv("FAKE_PROVIDER_MODE", "READY")
    probe = fx21["tmp"] / "cwd_probe.txt"
    state = fx21["tmp"] / "cwd_state"
    monkeypatch.setenv("FAKE_PROVIDER_STATE", str(state))
    monkeypatch.setenv("CWD_PROBE_PATH", str(probe))
    prov = _provider(fx21["script"], mode="READY", state=state, probe=probe)
    packet = build_agent_packet("Q-200", ctx=fx21["ctx"])
    turn, diag = prov.run_turn(packet=packet, context=[])
    assert turn.kind.value == "READY"
    assert diag.get("cwd_isolated") is True
    assert probe.exists()
    cwd = Path(probe.read_text(encoding="utf-8").strip()).resolve()
    assert cwd != Path(ROOT).resolve()


def test_provider_no_shell_true(fx21, monkeypatch):
    seen: dict = {}

    def fake_run(*args, **kwargs):
        seen["shell"] = kwargs.get("shell")

        class R:
            returncode = 0
            stdout = json.dumps(
                {
                    "kind": "READY",
                    "proposal": {
                        "artifact_id": "Q-200",
                        "status": "READY",
                        "operations": [],
                        "finalize": False,
                    },
                }
            ).encode()
            stderr = b""

        return R()

    import music_rig.agent.provider as provider_mod

    monkeypatch.setattr(provider_mod.subprocess, "run", fake_run)
    prov = CommandProvider(argv=[sys.executable, "-c", "pass"], timeout_seconds=2)
    prov.run_turn(packet={"artifact": {"id": "Q-200"}}, context=[])
    assert seen.get("shell") is False
