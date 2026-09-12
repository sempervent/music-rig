"""Tests migrated to integration/agent/test_inspection.py."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from music_rig.agent.inspection import InspectionRequest, execute_inspection
from music_rig.cli import app

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
