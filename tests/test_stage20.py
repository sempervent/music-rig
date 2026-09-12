"""Stage 20 — agent-assisted reconciliation engine (fixture-only mutations)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from music_rig import agent as agent_mod
from music_rig import patchbay_state, question_service
from music_rig.agent import (
    AgentReconciliationProposal,
    ProposalStatus,
    apply_proposal,
    build_agent_packet,
    validate_proposal,
)
from music_rig.cli import app
from music_rig.models import QuestionStatus
from music_rig.reconciliation.checks import (
    FindingStatus,
    QuestionConvergenceCheck,
    run_checks,
)
from music_rig.reconciliation.context import ReconciliationContext, ReconciliationPaths
from music_rig.reconciliation.operation_registry import (
    allowlisted_kinds,
    get_spec,
    validate_operation_shape,
)
from music_rig.reconciliation.operation_renderer import render_cli
from music_rig.reconciliation.operations import RigOperation
from music_rig.store import StoreError, load_questions
from music_rig import store as store_mod


runner = CliRunner()


def _write_docs(tmp: Path) -> None:
    for name, start, end in [
        ("todo.md", "<!-- rig:todo:start -->", "<!-- rig:todo:end -->"),
        ("wishlist.md", "<!-- rig:wishlist:start -->", "<!-- rig:wishlist:end -->"),
        ("open-questions.md", "<!-- rig:questions:start -->", "<!-- rig:questions:end -->"),
        ("patchbays.md", "<!-- rig:patchbays:start -->", "<!-- rig:patchbays:end -->"),
    ]:
        (tmp / name).write_text(f"x\n{start}\n{end}\n", encoding="utf-8")


@pytest.fixture
def fx20(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    questions = tmp_path / "open-questions.yaml"
    todo = tmp_path / "todo.yaml"
    wish = tmp_path / "wishlist.yaml"
    inbox = tmp_path / "inbox.yaml"
    changes = tmp_path / "changes.yaml"
    patchbays = tmp_path / "patchbays.yaml"
    inventory = tmp_path / "inventory.yaml"
    channels = tmp_path / "channel-map.yaml"
    routing = tmp_path / "routing.yaml"
    midi = tmp_path / "midi.yaml"
    controllers = tmp_path / "controllers.yaml"
    ableton = tmp_path / "ableton.yaml"
    _write_docs(tmp_path)

    todo.write_text(
        yaml.safe_dump(
            {
                "next_session": ["RIG-200"],
                "tasks": [
                    {
                        "id": "RIG-200",
                        "task": "Map patchbay models",
                        "area": "Patchbay",
                        "priority": "P1",
                        "status": "READY",
                        "depends_on": [],
                        "definition_of_done": "models recorded",
                        "notes": "",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    wish.write_text("items: []\n", encoding="utf-8")
    inbox.write_text("items: []\n", encoding="utf-8")
    changes.write_text("items: []\n", encoding="utf-8")
    inventory.write_text(
        yaml.safe_dump(
            {
                "items": [
                    {
                        "id": "art-p48-1",
                        "name": "ART P48 #1",
                        "category": "patchbay",
                        "ownership_status": "OWNED",
                        "condition": "WORKING",
                    },
                    {
                        "id": "behringer-px3000-1",
                        "name": "Behringer PX3000 #1",
                        "category": "patchbay",
                        "ownership_status": "OWNED",
                        "condition": "WORKING",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    questions.write_text(
        yaml.safe_dump(
            {
                "questions": [
                    {
                        "id": "Q-200",
                        "question": "PB models?",
                        "area": "Patchbay",
                        "status": "RESOLVED",
                        "related_todos": ["RIG-200"],
                        "related_changes": [],
                        "answer": "PB-A & PB-B are ART P48, PB-C & PB-D are Behringer PX3000",
                        "notes": "",
                        "resolved_at": "2026-09-12T12:00:00+00:00",
                        "reconciled_at": None,
                        "target": {"domain": "inventory.patchbay_mapping"},
                        "verification": {
                            "kind": "PATCHBAY_UNIT",
                            "prompt": "read faceplates",
                            "answer_type": "TEXT",
                            "choices": [],
                        },
                    },
                    {
                        "id": "Q-201",
                        "question": "Broken target?",
                        "area": "Patchbay",
                        "status": "RESOLVED",
                        "related_todos": [],
                        "related_changes": [],
                        "answer": "normal",
                        "notes": "",
                        "resolved_at": "2026-09-12T12:00:00+00:00",
                        "reconciled_at": None,
                        "target": {
                            "domain": "patchbay.mode",
                            "bay": "PB-B",
                            "pair": None,
                        },
                        "verification": {
                            "kind": "PATCHBAY_MODE",
                            "prompt": "mode",
                            "answer_type": "ENUM",
                            "choices": ["normal", "thru"],
                        },
                    },
                    {
                        "id": "Q-202",
                        "question": "Ambiguous destinations",
                        "area": "Routing",
                        "status": "RESOLVED",
                        "related_todos": [],
                        "related_changes": [],
                        "answer": "maybe Alesis 2 or maybe Alesis 3 for acoustic",
                        "notes": "",
                        "resolved_at": "2026-09-12T12:00:00+00:00",
                        "reconciled_at": None,
                        "target": {"domain": "routing.verify"},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    patchbays.write_text(
        "# test\n"
        + yaml.safe_dump(
            {
                "schema_notes": {},
                "patchbays": {
                    "PB-A": {"hardware_model": "unknown", "status": "undocumented", "jacks": {}},
                    "PB-B": {"hardware_model": "unknown", "status": "undocumented", "jacks": {}},
                    "PB-C": {"hardware_model": "unknown", "status": "undocumented", "jacks": {}},
                    "PB-D": {"hardware_model": "unknown", "status": "undocumented", "jacks": {}},
                },
            }
        ),
        encoding="utf-8",
    )
    channels.write_text("devices: {}\n", encoding="utf-8")
    routing.write_text("paths: []\n", encoding="utf-8")
    midi.write_text("{}\n", encoding="utf-8")
    controllers.write_text("{}\n", encoding="utf-8")
    ableton.write_text("{}\n", encoding="utf-8")

    monkeypatch.setattr(store_mod, "QUESTIONS_PATH", questions)
    monkeypatch.setattr(store_mod, "TODO_PATH", todo)
    monkeypatch.setattr(store_mod, "WISHLIST_PATH", wish)
    monkeypatch.setattr(store_mod, "INBOX_PATH", inbox)
    monkeypatch.setattr(store_mod, "CHANGES_PATH", changes)
    monkeypatch.setattr(store_mod, "PATCHBAYS_PATH", patchbays)
    monkeypatch.setattr(store_mod, "INVENTORY_PATH", inventory)
    monkeypatch.setattr(store_mod, "CHANNEL_MAP_PATH", channels)
    monkeypatch.setattr(store_mod, "ROUTING_PATH", routing)
    monkeypatch.setattr(store_mod, "MIDI_PATH", midi)
    monkeypatch.setattr(store_mod, "CONTROLLERS_PATH", controllers)
    monkeypatch.setattr(store_mod, "ABLETON_PATH", ableton)
    monkeypatch.setattr(store_mod, "DOCS_TODO_PATH", tmp_path / "todo.md")
    monkeypatch.setattr(store_mod, "DOCS_WISHLIST_PATH", tmp_path / "wishlist.md")
    monkeypatch.setattr(store_mod, "DOCS_QUESTIONS_PATH", tmp_path / "open-questions.md")
    monkeypatch.setattr(store_mod, "DOCS_PATCHBAYS_PATH", tmp_path / "patchbays.md")
    monkeypatch.setattr(patchbay_state, "PATCHBAYS_PATH", patchbays)

    ctx = ReconciliationContext.for_root(tmp_path)
    return {"tmp": tmp_path, "ctx": ctx, "questions": questions, "patchbays": patchbays}


def test_paths_default_matches_store():
    paths = ReconciliationPaths.default()
    assert paths.questions == store_mod.QUESTIONS_PATH
    assert paths.patchbays == store_mod.PATCHBAYS_PATH


def test_operation_renderer_quotes():
    op = RigOperation(
        namespace="patchbay",
        action="set_model",
        args={"bay_id": "PB-A", "model": "ART P48"},
    )
    cli = render_cli(op)
    assert "set-model" in cli
    assert "ART" in cli
    assert "uv run rig" in cli


def test_unregistered_operation_rejected():
    op = RigOperation(namespace="shell", action="rm", args={"path": "/"})
    with pytest.raises(StoreError, match="unregistered"):
        validate_operation_shape(op)


def test_evidence_verified_arg_rejected():
    op = RigOperation(
        namespace="patchbay",
        action="set_model",
        args={"bay_id": "PB-A", "model": "x", "evidence": "VERIFIED"},
    )
    with pytest.raises(StoreError, match="forbidden|VERIFIED"):
        validate_operation_shape(op)


def test_question_resolve_not_agent_allowed():
    op = RigOperation(
        namespace="question", action="resolve", args={"question_id": "Q-200"}
    )
    with pytest.raises(StoreError, match="not agent-allowed"):
        validate_operation_shape(op, agent=True)


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


def test_agent_packet_q007_shaped(fx20):
    packet = build_agent_packet("Q-200", ctx=fx20["ctx"])
    assert packet["final_human_answer"].startswith("PB-A")
    assert "ART P48" in packet["final_human_answer"]
    assert "unit_identity_note" in packet["relevant_current_context"]
    assert "wishlist" not in json.dumps(packet).casefold()
    assert "midi" not in packet["relevant_current_context"]
    # Determinism
    p2 = build_agent_packet("Q-200", ctx=fx20["ctx"])
    assert packet["packet_hash"] == p2["packet_hash"]


def test_agent_packet_rejects_unit_id_invention(fx20):
    proposal = AgentReconciliationProposal(
        artifact_id="Q-200",
        status=ProposalStatus.READY,
        rationale="guess unit ids",
        operations=[
            RigOperation(
                namespace="patchbay",
                action="set_model",
                args={"bay_id": "PB-A", "model": "art-p48-1", "question_id": "Q-200"},
            )
        ],
    )
    result = validate_proposal(proposal, ctx=fx20["ctx"])
    assert result["ok"] is False
    assert any("unit-id" in e for e in result["errors"])


def test_ambiguous_proposal_no_writes(fx20):
    proposal = AgentReconciliationProposal(
        artifact_id="Q-202",
        status=ProposalStatus.NEEDS_HUMAN_CLARIFICATION,
        clarification_questions=[
            "Which Alesis return is Acoustic — 2 or 3?"
        ],
        operations=[],
    )
    result = apply_proposal(proposal, ctx=fx20["ctx"], dry_run=False, yes=True)
    assert result["ok"] is True
    assert result["applied"] == []
    q = load_questions(fx20["questions"]).question_map()["Q-202"]
    assert q.reconciled_at is None


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
    r3 = runner.invoke(
        app, ["agent", "apply", str(prop_path), "--dry-run", "--json"]
    )
    assert r3.exit_code == 0, r3.output


def test_production_q007_packet_readonly():
    """Read-only production packet — no mutation."""
    before = question_service.get_question("Q-007")
    packet = build_agent_packet("Q-007")
    assert "ART P48" in packet["final_human_answer"]
    assert "Behringer PX3000" in packet["final_human_answer"]
    assert packet["relevant_current_context"].get("unit_identity_note")
    after = question_service.get_question("Q-007")
    assert after.answer == before.answer
    assert after.reconciled_at == before.reconciled_at


def test_allowlisted_kinds_exclude_shell():
    kinds = allowlisted_kinds(agent_only=True)
    assert "patchbay.set_model" in kinds
    assert all("shell" not in k for k in kinds)
    assert "question.resolve" not in kinds


def test_agent_capabilities_cli(tmp_path, monkeypatch):
    monkeypatch.setattr("music_rig.store.ROOT", tmp_path)
    monkeypatch.setattr("music_rig.local_config.ROOT", tmp_path)
    r = runner.invoke(app, ["agent", "capabilities", "--json"])
    assert r.exit_code == 0, r.output
    payload = json.loads(r.output)
    assert payload["result"]["provider_configured"] is False
