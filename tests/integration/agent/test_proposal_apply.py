"""Tests migrated to integration/agent/test_proposal_apply.py."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from music_rig import patchbay_state
from music_rig.agent import (
    AgentReconciliationProposal,
    ProposalStatus,
    apply_proposal,
)
from music_rig.cli import app
from music_rig.models import QuestionStatus
from music_rig.reconciliation.checks import (
    FindingStatus,
    QuestionConvergenceCheck,
    run_checks,
)
from music_rig.reconciliation.operations import RigOperation
from music_rig.store import load_questions

runner = CliRunner()


def test_sweep_isolates_malformed_artifact(fx20, monkeypatch):
    """One inspect error must not silence other findings."""

    class Boom(QuestionConvergenceCheck):
        def _inspect_one(self, q, paths):
            if q.id == "Q-201":
                raise RuntimeError("simulated malformed target")
            return super()._inspect_one(q, paths)

    ctx = fx20["ctx"]
    findings = run_checks(ctx, checks=[Boom()])
    by_id = {f.artifact_id: f for f in findings}
    assert by_id["Q-201"].status is FindingStatus.ERROR
    assert by_id["Q-200"].status in {FindingStatus.BLOCKED, FindingStatus.READY}
    assert "simulated" in by_id["Q-201"].summary


def test_model_mapping_apply_dry_run_and_write(fx20):
    ops = [
        RigOperation(
            namespace="patchbay",
            action="set_model",
            args={"bay_id": "PB-A", "model": "ART P48", "question_id": "Q-200"},
        ),
        RigOperation(
            namespace="patchbay",
            action="set_model",
            args={"bay_id": "PB-B", "model": "ART P48", "question_id": "Q-200"},
        ),
        RigOperation(
            namespace="patchbay",
            action="set_model",
            args={"bay_id": "PB-C", "model": "Behringer PX3000", "question_id": "Q-200"},
        ),
        RigOperation(
            namespace="patchbay",
            action="set_model",
            args={"bay_id": "PB-D", "model": "Behringer PX3000", "question_id": "Q-200"},
        ),
    ]
    proposal = AgentReconciliationProposal(
        artifact_id="Q-200",
        status=ProposalStatus.READY,
        rationale="Human answer maps models by bay letter.",
        operations=ops,
        finalize=False,
    )
    dry = apply_proposal(proposal, ctx=fx20["ctx"], dry_run=True)
    assert dry["ok"] is True
    data = patchbay_state.load_raw(fx20["patchbays"])
    assert data["patchbays"]["PB-A"]["hardware_model"] == "unknown"

    written = apply_proposal(proposal, ctx=fx20["ctx"], dry_run=False, yes=True)
    assert written["ok"] is True
    data = patchbay_state.load_raw(fx20["patchbays"])
    assert data["patchbays"]["PB-A"]["hardware_model"] == "ART P48"
    assert data["patchbays"]["PB-C"]["hardware_model"] == "Behringer PX3000"
    q = load_questions(fx20["questions"]).question_map()["Q-200"]
    assert q.status == QuestionStatus.RESOLVED
    assert q.reconciled_at is None  # finalize not in this proposal


def test_cli_agent_packet_and_validate(fx20, tmp_path):
    r = runner.invoke(app, ["agent", "packet", "Q-200", "--json"])
    assert r.exit_code == 0, r.output
    payload = json.loads(r.output)
    assert payload["ok"] is True
    assert payload["result"]["artifact"]["id"] == "Q-200"

    proposal = {
        "artifact_id": "Q-200",
        "status": "READY",
        "rationale": "set models",
        "operations": [
            {
                "namespace": "patchbay",
                "action": "set_model",
                "args": {"bay_id": "PB-A", "model": "ART P48", "question_id": "Q-200"},
            }
        ],
        "finalize": False,
    }
    prop_path = tmp_path / "proposal.json"
    prop_path.write_text(json.dumps(proposal), encoding="utf-8")
    r2 = runner.invoke(app, ["agent", "validate", str(prop_path), "--json"])
    assert r2.exit_code == 0, r2.output
    r3 = runner.invoke(app, ["agent", "apply", str(prop_path), "--dry-run", "--json"])
    assert r3.exit_code == 0, r3.output
