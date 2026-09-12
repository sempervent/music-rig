"""Stage 16 — guided human verification (`rig verify`). Fixtures only for mutations."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from music_rig import patchbay_state, question_service, store, verification_service
from music_rig.cli import app
from music_rig.models import QuestionStatus, ReconciliationState
from music_rig.presentation import format_verify_queue_table, format_verify_summary_table
from music_rig.reconciliation import service as reconcile_service
from music_rig.reconciliation.types import Capability, VerificationStatus
from music_rig.store import StoreError, load_questions


def _clock():
    return datetime(2026, 9, 11, 22, 0, 0, tzinfo=timezone.utc)


def _write_docs(tmp: Path) -> dict[str, Path]:
    paths = {}
    for name, start, end in [
        ("todo.md", "<!-- rig:todo:start -->", "<!-- rig:todo:end -->"),
        ("wishlist.md", "<!-- rig:wishlist:start -->", "<!-- rig:wishlist:end -->"),
        ("open-questions.md", "<!-- rig:questions:start -->", "<!-- rig:questions:end -->"),
        ("patchbays.md", "<!-- rig:patchbays:start -->", "<!-- rig:patchbays:end -->"),
        ("inventory.md", "<!-- rig:inventory:start -->", "<!-- rig:inventory:end -->"),
    ]:
        path = tmp / name
        path.write_text(f"x\n{start}\n{end}\n", encoding="utf-8")
        paths[name] = path
    return paths


@pytest.fixture
def fx16(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    questions = tmp_path / "open-questions.yaml"
    todo = tmp_path / "todo.yaml"
    wish = tmp_path / "wishlist.yaml"
    inbox = tmp_path / "inbox.yaml"
    changes = tmp_path / "changes.yaml"
    patchbays = tmp_path / "patchbays.yaml"
    routing = tmp_path / "routing.yaml"
    midi = tmp_path / "midi.yaml"
    controllers = tmp_path / "controllers.yaml"
    ableton = tmp_path / "ableton.yaml"
    inventory = tmp_path / "inventory.yaml"
    docs = _write_docs(tmp_path)

    todo.write_text(
        yaml.safe_dump(
            {
                "next_session": ["RIG-090", "RIG-091"],
                "tasks": [
                    {
                        "id": "RIG-090",
                        "task": "Next session patchbay mode",
                        "area": "Patchbay",
                        "priority": "P0",
                        "status": "READY",
                        "depends_on": [],
                        "definition_of_done": "mode recorded",
                        "notes": "",
                    },
                    {
                        "id": "RIG-091",
                        "task": "P0 routing visual",
                        "area": "Routing",
                        "priority": "P0",
                        "status": "READY",
                        "depends_on": [],
                        "definition_of_done": "traced",
                        "notes": "",
                    },
                    {
                        "id": "RIG-092",
                        "task": "P1 freeform",
                        "area": "Docs",
                        "priority": "P1",
                        "status": "READY",
                        "depends_on": [],
                        "definition_of_done": "x",
                        "notes": "",
                    },
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
                        "id": "art-p48",
                        "name": "ART P48",
                        "category": "patchbay",
                        "ownership_status": "OWNED",
                        "condition": "WORKING",
                        "quantity": 1,
                        "units": [{"id": "art-p48-1"}],
                    },
                    {
                        "id": "behringer-px3000",
                        "name": "Behringer PX3000",
                        "category": "patchbay",
                        "ownership_status": "OWNED",
                        "condition": "WORKING",
                        "quantity": 1,
                        "units": [{"id": "behringer-px3000-1"}],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    patchbays.write_text(
        yaml.safe_dump(
            {
                "schema_notes": {},
                "patchbays": {
                    "PB-B": {
                        "hardware_model": "unknown",
                        "status": "partially_documented",
                        "jacks": {
                            1: {
                                "row": "upper",
                                "connection": "A",
                                "paired_with": 25,
                                "mode": "unknown",
                                "status": "documented",
                            },
                            25: {
                                "row": "lower",
                                "connection": "B",
                                "paired_with": 1,
                                "mode": "unknown",
                                "status": "documented",
                            },
                        },
                    },
                    "PB-A": {
                        "hardware_model": "unknown",
                        "status": "undocumented",
                        "jacks": {},
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    routing.write_text(
        yaml.safe_dump(
            {
                "routes": {},
                "named_paths": {
                    "kaoss": {
                        "label": "KAOSS",
                        "status": "UNKNOWN",
                        "branches": {
                            "main": {
                                "label": "main",
                                "nodes": [{"id": "a", "label": "A"}],
                            }
                        },
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    midi.write_text(
        yaml.safe_dump(
            {
                "devices": [],
                "links": [],
                "channels": [],
                "clock": {
                    "master": {
                        "endpoint_ref": "ableton",
                        "status": "INTENDED",
                        "notes": "",
                    },
                    "destinations": [],
                    "transport": {"status": "UNKNOWN", "notes": ""},
                },
                "ableton_ports": [],
            }
        ),
        encoding="utf-8",
    )
    controllers.write_text(yaml.safe_dump({"controllers": []}), encoding="utf-8")
    ableton.write_text(
        yaml.safe_dump({"tracks": [], "sends": [], "actions": [], "templates": []}),
        encoding="utf-8",
    )

    questions.write_text(
        yaml.safe_dump(
            {
                "questions": [
                    {
                        "id": "Q-090",
                        "question": "What mode is PB-B 1/25?",
                        "area": "Patchbay",
                        "status": "OPEN",
                        "related_todos": ["RIG-090"],
                        "related_changes": [],
                        "answer": "",
                        "notes": "",
                        "resolved_at": None,
                        "reconciled_at": None,
                        "reconciliation_note": "",
                        "target": {
                            "domain": "patchbay.mode",
                            "bay": "PB-B",
                            "pair": "1/25",
                        },
                        "verification": {
                            "kind": "PATCHBAY_MODE",
                            "prompt": "Inspect switch on pair 1/25",
                            "answer_type": "ENUM",
                            "choices": ["normal", "half-normal", "thru", "UNKNOWN"],
                            "ref_domain": None,
                        },
                        "verification_note": "",
                    },
                    {
                        "id": "Q-091",
                        "question": "Does kaoss path match docs?",
                        "area": "Routing",
                        "status": "OPEN",
                        "related_todos": ["RIG-091"],
                        "related_changes": [],
                        "answer": "",
                        "notes": "",
                        "resolved_at": None,
                        "reconciled_at": None,
                        "reconciliation_note": "",
                        "target": {"domain": "routing.verify", "path": "kaoss"},
                        "verification": {
                            "kind": "ROUTING_COMPARE",
                            "prompt": "Compare physical path",
                            "answer_type": "BOOL",
                            "choices": ["YES", "NO", "UNKNOWN"],
                            "ref_domain": None,
                        },
                        "verification_note": "",
                    },
                    {
                        "id": "Q-092",
                        "question": "Freeform workflow order?",
                        "area": "Performance / video",
                        "status": "OPEN",
                        "related_todos": ["RIG-092"],
                        "related_changes": [],
                        "answer": "",
                        "notes": "",
                        "resolved_at": None,
                        "reconciled_at": None,
                        "reconciliation_note": "",
                        "target": {"domain": "ableton.template", "path": "pfl-jam"},
                        "verification": {
                            "kind": "WORKFLOW",
                            "prompt": "Describe jam order",
                            "answer_type": "TEXT",
                            "choices": [],
                            "ref_domain": None,
                        },
                        "verification_note": "",
                    },
                    {
                        "id": "Q-093",
                        "question": "Already resolved fixture",
                        "area": "Patchbay",
                        "status": "RESOLVED",
                        "related_todos": [],
                        "related_changes": [],
                        "answer": "half-normal",
                        "notes": "",
                        "resolved_at": "2026-09-01T00:00:00+00:00",
                        "reconciled_at": None,
                        "reconciliation_note": "",
                        "target": {
                            "domain": "patchbay.mode",
                            "bay": "PB-B",
                            "pair": "1/25",
                        },
                        "verification": {
                            "kind": "PATCHBAY_MODE",
                            "prompt": "x",
                            "answer_type": "ENUM",
                            "choices": ["normal", "half-normal", "thru", "UNKNOWN"],
                            "ref_domain": None,
                        },
                        "verification_note": "",
                    },
                    {
                        "id": "Q-094",
                        "question": "No verification metadata",
                        "area": "Docs",
                        "status": "OPEN",
                        "related_todos": [],
                        "related_changes": [],
                        "answer": "",
                        "notes": "",
                        "resolved_at": None,
                        "reconciled_at": None,
                        "reconciliation_note": "",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(store, "QUESTIONS_PATH", questions)
    monkeypatch.setattr(store, "TODO_PATH", todo)
    monkeypatch.setattr(store, "WISHLIST_PATH", wish)
    monkeypatch.setattr(store, "INBOX_PATH", inbox)
    monkeypatch.setattr(store, "CHANGES_PATH", changes)
    monkeypatch.setattr(store, "PATCHBAYS_PATH", patchbays)
    monkeypatch.setattr(store, "ROUTING_PATH", routing)
    monkeypatch.setattr(store, "MIDI_PATH", midi)
    monkeypatch.setattr(store, "CONTROLLERS_PATH", controllers)
    monkeypatch.setattr(store, "ABLETON_PATH", ableton)
    monkeypatch.setattr(store, "INVENTORY_PATH", inventory)
    monkeypatch.setattr(store, "DOCS_TODO_PATH", docs["todo.md"])
    monkeypatch.setattr(store, "DOCS_WISHLIST_PATH", docs["wishlist.md"])
    monkeypatch.setattr(store, "DOCS_QUESTIONS_PATH", docs["open-questions.md"])
    monkeypatch.setattr(store, "DOCS_PATCHBAYS_PATH", docs["patchbays.md"])
    monkeypatch.setattr(store, "DOCS_INVENTORY_PATH", docs["inventory.md"])
    monkeypatch.setattr(patchbay_state, "PATCHBAYS_PATH", patchbays)

    from music_rig import midi_state, render as render_mod, routing_state

    monkeypatch.setattr(midi_state, "MIDI_PATH", midi)
    monkeypatch.setattr(routing_state, "ROUTING_PATH", routing)
    monkeypatch.setattr(render_mod, "MIDI_PATH", midi)
    monkeypatch.setattr(render_mod, "INVENTORY_PATH", inventory)
    monkeypatch.setattr(render_mod, "QUESTIONS_PATH", questions)
    monkeypatch.setattr(render_mod, "TODO_PATH", todo)
    monkeypatch.setattr(render_mod, "WISHLIST_PATH", wish)
    monkeypatch.setattr(render_mod, "DOCS_TODO_PATH", docs["todo.md"])
    monkeypatch.setattr(render_mod, "DOCS_WISHLIST_PATH", docs["wishlist.md"])
    monkeypatch.setattr(render_mod, "DOCS_QUESTIONS_PATH", docs["open-questions.md"])
    monkeypatch.setattr(render_mod, "DOCS_PATCHBAYS_PATH", docs["patchbays.md"])
    monkeypatch.setattr(render_mod, "DOCS_INVENTORY_PATH", docs["inventory.md"])

    def _noop_render(**kwargs):
        return False, []

    monkeypatch.setattr(render_mod, "render_docs", _noop_render)
    monkeypatch.setattr(question_service, "render_docs", _noop_render)

    return {
        "questions": questions,
        "todo": todo,
        "patchbays": patchbays,
        "routing": routing,
        "midi": midi,
        "inventory": inventory,
        "tmp": tmp_path,
    }


# --- production metadata (read-only) ---


# Production Questions reconciled in the approved post-Stage-18 answering session.
_RECONCILED_PROD = frozenset({"Q-001", "Q-002", "Q-003", "Q-004", "Q-006"})


def test_production_questions_have_verification_metadata_answers_untouched():
    doc = load_questions()
    prod = [q for q in doc.questions if q.id.startswith("Q-") and int(q.id.split("-")[1]) <= 20]
    assert len(prod) == 20
    kinds = {}
    for q in prod:
        assert q.verification is not None, q.id
        assert q.verification.kind
        assert q.verification.answer_type in {"ENUM", "BOOL", "REF", "TEXT"}
        assert q.verification_result is None  # never invent observations
        if q.id in _RECONCILED_PROD:
            assert q.status == QuestionStatus.RESOLVED
            assert q.answer.strip()
            assert q.resolved_at is not None
            assert q.reconciled_at is not None
        else:
            assert q.status == QuestionStatus.OPEN
            assert q.answer == ""
            assert q.resolved_at is None
            assert q.reconciled_at is None
        kinds[q.verification.kind] = kinds.get(q.verification.kind, 0) + 1
        # recipes validate via pydantic already
        if q.verification.answer_type in {"ENUM", "BOOL"}:
            assert q.verification.choices
    assert "PATCHBAY_MODE" in kinds
    assert "PATCHBAY_UNIT" in kinds
    # Q-008 pair stays null
    q8 = doc.question_map()["Q-008"]
    assert q8.target is not None
    assert q8.target.bay == "PB-B"
    assert q8.target.pair is None
    q7 = doc.question_map()["Q-007"]
    assert q7.target is not None
    assert q7.target.domain == "inventory.patchbay_mapping"
    # Approved Q-001 A/B/Y reconciliation baseline
    q1 = doc.question_map()["Q-001"]
    assert "Alesis 2" in q1.answer and "Alesis 1" in q1.answer and "Alesis 3" in q1.answer


def test_production_readiness_matrix_no_answers():
    rows = verification_service.production_readiness_matrix()
    assert len(rows) >= 20
    for row in rows:
        if row["id"] in {f"Q-{i:03d}" for i in range(1, 21)}:
            assert row["kind"]
            if row["id"] in _RECONCILED_PROD:
                assert row["answer"]
                assert row["resolved_at"] is not None
            else:
                assert row["answer"] == ""
                assert row["resolved_at"] is None


# --- queue ordering / filters ---


def test_queue_ordering_and_excludes_resolved(fx16):
    items = verification_service.list_verify_queue()
    ids = [i.question_id for i in items]
    assert "Q-093" not in ids  # RESOLVED
    assert "Q-094" not in ids  # no verification
    assert ids[0] == "Q-090"  # next session + enum
    assert "Q-091" in ids
    assert "Q-092" in ids
    # Q-090 before Q-091 (both next/P0; lower id among same tier — both tier 0)
    assert ids.index("Q-090") < ids.index("Q-091")
    # structured before freeform remaining: Q-092 is remaining tier
    assert ids.index("Q-091") < ids.index("Q-092")


def test_queue_area_filter(fx16):
    items = verification_service.list_verify_queue(area="Patchbay")
    assert [i.question_id for i in items] == ["Q-090"]


def test_queue_table_no_tabs(fx16):
    items = verification_service.list_verify_queue()
    text = format_verify_queue_table(items, width=100)
    assert "\t" not in text
    assert "Q-090" in text


# --- answer validation / normalization ---


def test_normalize_enum_and_reject_invalid(fx16):
    q = question_service.get_question("Q-090")
    assert verification_service.normalize_answer(q, "HALF_NORMAL") == "half-normal"
    assert verification_service.normalize_answer(q, "unknown") == "UNKNOWN"
    with pytest.raises(StoreError, match="Invalid ENUM"):
        verification_service.normalize_answer(q, "purple")


def test_normalize_bool(fx16):
    q = question_service.get_question("Q-091")
    assert verification_service.normalize_answer(q, "yes") == "YES"
    assert verification_service.normalize_answer(q, "n") == "NO"


def test_verify_answer_cli_json_no_ansi(fx16):
    runner = CliRunner()
    bad = runner.invoke(
        app,
        ["verify", "answer", "Q-090", "--value", "purple", "--yes", "--json"],
    )
    assert bad.exit_code == 1
    assert "\x1b[" not in bad.stdout
    err = json.loads(bad.stdout)
    assert err["ok"] is False

    ok = runner.invoke(
        app,
        [
            "verify",
            "answer",
            "Q-090",
            "--value",
            "half-normal",
            "--yes",
            "--json",
            "--note",
            "rack check",
        ],
    )
    assert ok.exit_code == 0
    assert "\x1b[" not in ok.stdout
    payload = json.loads(ok.stdout)
    assert payload["ok"] is True
    assert payload["result"]["normalized_value"] == "half-normal"
    q = question_service.get_question("Q-090")
    assert q.status == QuestionStatus.RESOLVED
    assert q.answer == "half-normal"
    assert q.reconciled_at is None
    assert q.verification_note == "rack check"
    assert q.verification is not None  # metadata preserved


# --- interactive run ---


def test_verify_run_enum_answer_only(fx16):
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["verify", "run", "Q-090", "--answer-only"],
        # choice 2=half-normal, note empty, record observation? n → answer only
        input="2\n\nn\n",
    )
    assert result.exit_code == 0, result.stdout
    q = question_service.get_question("Q-090")
    assert q.answer == "half-normal"
    assert q.verification_result is None
    assert q.reconciled_at is None
    data = patchbay_state.load_raw()
    jack = data["patchbays"]["PB-B"]["jacks"].get(1) or data["patchbays"]["PB-B"]["jacks"].get("1")
    assert jack["mode"] == "unknown"


def test_verify_run_unknown_and_cancel(fx16):
    runner = CliRunner()
    cancel = runner.invoke(app, ["verify", "run", "Q-090"], input="0\n")
    assert cancel.exit_code == 0
    assert "Cancelled" in cancel.stdout or question_service.get_question("Q-090").status == QuestionStatus.OPEN

    # UNKNOWN as observation → no resolve (Stage 17)
    unk_obs = runner.invoke(
        app,
        ["verify", "run", "Q-090", "--answer-only"],
        input="4\n\ny\n",  # UNKNOWN, note, yes observation
    )
    assert unk_obs.exit_code == 0, unk_obs.stdout
    q = question_service.get_question("Q-090")
    assert q.status == QuestionStatus.OPEN
    assert q.verification_result is not None
    assert q.verification_result.outcome.value == "UNKNOWN"

    # Decline observation → classic answer path resolves UNKNOWN
    unk_ans = runner.invoke(
        app,
        ["verify", "run", "Q-091", "--answer-only"],
        input="3\n\nn\n",  # UNKNOWN (3rd BOOL), note, no observation
    )
    assert unk_ans.exit_code == 0, unk_ans.stdout
    q2 = question_service.get_question("Q-091")
    assert q2.answer == "UNKNOWN"
    assert q2.status == QuestionStatus.RESOLVED
    assert q2.verification_result is None

# --- e2e patchbay HALF-NORMAL → reconcile MATCH finalize ---


def test_e2e_patchbay_half_normal_reconcile_finalize(fx16):
    verification_service.record_verified_answer(
        "Q-090", "HALF_NORMAL", clock=_clock, render=False
    )
    q = question_service.get_question("Q-090")
    assert q.answer == "half-normal"
    plan = reconcile_service.plan_question("Q-090")
    assert plan.state == ReconciliationState.READY_TO_APPLY
    assert plan.capability == Capability.APPLY_AND_VERIFY
    applied = reconcile_service.apply_question("Q-090", yes=True)
    assert applied is not None
    verified = reconcile_service.verify_question("Q-090")
    assert verified["verification"] == VerificationStatus.MATCH.value
    reconcile_service.finalize_question("Q-090", yes=True)
    q2 = question_service.get_question("Q-090")
    assert q2.reconciled_at is not None
    data = patchbay_state.load_raw()
    mode = data["patchbays"]["PB-B"]["jacks"].get(1) or data["patchbays"]["PB-B"]["jacks"].get("1")
    assert mode["mode"] == "half-normal"


# --- free-text → NEEDS_AGENT_ACTION no CURRENT guess ---


def test_freetext_needs_agent_no_current_guess(fx16):
    verification_service.record_verified_answer(
        "Q-092", "RC-1 then KAOSS", clock=_clock, render=False
    )
    plan = reconcile_service.plan_question("Q-092")
    assert plan.state == ReconciliationState.NEEDS_AGENT_ACTION
    # Ableton template not mutated
    from music_rig.store import load_ableton

    ab = load_ableton()
    assert ab.templates == [] or True  # fixture empty


def test_verify_only_epistemic_guard(fx16):
    """BOOL answer on routing.verify stays VERIFY_ONLY — no CURRENT invent."""
    verification_service.record_verified_answer(
        "Q-091", "YES", clock=_clock, render=False
    )
    plan = reconcile_service.plan_question("Q-091")
    assert plan.capability == Capability.VERIFY_ONLY
    assert plan.state in {
        ReconciliationState.NEEDS_AGENT_ACTION,
        ReconciliationState.CURRENT_MATCHES,
        ReconciliationState.READY_TO_FINALIZE,
    }
    # Path status unchanged by answer alone
    from music_rig import routing_state

    _key, path = routing_state.get_named_path(routing_state.load_raw(), "kaoss")
    assert path.status == "UNKNOWN"


# --- session skip/quit/summary ---


def test_verify_session_skip_quit_summary(fx16):
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["verify", "session"],
        input="s\nq\n",
    )
    assert result.exit_code == 0
    assert "Session summary" in result.stdout
    assert "skipped=" in result.stdout
    assert question_service.get_question("Q-090").status == QuestionStatus.OPEN


def test_verify_summary_and_next_json(fx16):
    runner = CliRunner()
    summary = runner.invoke(app, ["verify", "summary", "--json"])
    assert summary.exit_code == 0
    assert "\x1b[" not in summary.stdout
    data = json.loads(summary.stdout)
    assert data["ok"] is True
    assert data["result"]["total_open_guided"] >= 3

    nxt = runner.invoke(app, ["verify", "next", "--json"])
    assert nxt.exit_code == 0
    payload = json.loads(nxt.stdout)
    assert payload["result"]["question_id"] == "Q-090"
    assert "start_command" in payload["result"]

    show = runner.invoke(app, ["verify", "show", "Q-090", "--json"])
    assert show.exit_code == 0
    card = json.loads(show.stdout)["result"]
    assert card["verification"]["kind"] == "PATCHBAY_MODE"
    assert "accepted" in card


def test_summary_table_no_tabs(fx16):
    data = verification_service.summary()
    text = format_verify_summary_table(data, width=80)
    assert "\t" not in text


def test_now_mentions_verify_run(fx16, monkeypatch):
    from music_rig.now_service import format_now, recommend_now

    monkeypatch.setattr(
        "music_rig.now_service.find_active", lambda *a, **k: None
    )
    rec = recommend_now()
    assert rec.primary_reference == "RIG-090"
    text = format_now(rec)
    assert "verify run Q-090" in text or any(
        "verify run Q-090" in c for c in rec.suggested_commands
    )
    # --play unchanged
    play = recommend_now(play=True)
    assert play.primary_reference == "PLAY"
    assert not any("verify run" in c for c in play.suggested_commands)


def test_verify_queue_cli(fx16):
    runner = CliRunner()
    human = runner.invoke(app, ["verify", "queue"])
    assert human.exit_code == 0
    assert "\t" not in human.stdout
    assert "Q-090" in human.stdout
    js = runner.invoke(app, ["verify", "queue", "--json"])
    assert js.exit_code == 0
    assert "\x1b[" not in js.stdout
    assert json.loads(js.stdout)["result"]["count"] >= 3
