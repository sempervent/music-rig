"""Stage 21 — autonomous reconciliation (fixture-only mutations)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from music_rig import channel_state, patchbay_state, question_service
from music_rig import store as store_mod
from music_rig.agent import (
    AgentReconciliationProposal,
    ProposalStatus,
    apply_proposal,
    build_agent_packet,
    capabilities,
    validate_proposal,
)
from music_rig.agent import transaction as transaction_mod
from music_rig.agent.errors import (
    ConcurrentModificationError,
    PlanConflictError,
    ProviderInvalidResponseError,
    ProviderTimeoutError,
)
from music_rig.agent.inspection import InspectionRequest, execute_inspection
from music_rig.agent.orchestrate import AutonomyLevel, autonomous_reconcile, run_provider_loop
from music_rig.agent.provider import CommandProvider
from music_rig.agent.transaction import (
    commit_transaction,
    evaluate_postconditions,
    prepare_transaction,
)
from music_rig.cli import app
from music_rig.reconciliation.context import ReconciliationContext
from music_rig.reconciliation.operation_registry import allowlisted_kinds, get_spec
from music_rig.reconciliation.operations import RigOperation
from music_rig.store import StoreError, ROOT, load_questions


runner = CliRunner()
FIXTURE_PROVIDER = Path(__file__).resolve().parent / "fixtures" / "fake_agent_provider.py"


def _write_docs(tmp: Path) -> None:
    for name, start, end in [
        ("todo.md", "<!-- rig:todo:start -->", "<!-- rig:todo:end -->"),
        ("wishlist.md", "<!-- rig:wishlist:start -->", "<!-- rig:wishlist:end -->"),
        ("open-questions.md", "<!-- rig:questions:start -->", "<!-- rig:questions:end -->"),
        ("patchbays.md", "<!-- rig:patchbays:start -->", "<!-- rig:patchbays:end -->"),
    ]:
        (tmp / name).write_text(f"x\n{start}\n{end}\n", encoding="utf-8")


def _minimal_routing() -> dict:
    return {
        "routes": {},
        "named_paths": {
            "dirty": {
                "label": "DIRTY",
                "status": "CURRENT",
                "evidence": "UNKNOWN",
                "branches": {
                    "main": {
                        "label": "Main",
                        "nodes": [
                            {"id": "a", "label": "A"},
                            {"id": "b", "label": "B"},
                            {"id": "c", "label": "C"},
                        ],
                    }
                },
            }
        },
    }


def _install_fake_provider(tmp: Path) -> Path:
    dest = tmp / "fake_agent_provider.py"
    shutil.copy(FIXTURE_PROVIDER, dest)
    dest.chmod(0o755)
    return dest


def _provider(
    script: Path,
    *,
    mode: str,
    state: Path | None = None,
    probe: Path | None = None,
    timeout_seconds: int = 2,
    max_stdout_bytes: int = 1_000_000,
) -> CommandProvider:
    forward = ["FAKE_PROVIDER_MODE"]
    if state is not None:
        forward.append("FAKE_PROVIDER_STATE")
    if probe is not None:
        forward.append("CWD_PROBE_PATH")
    return CommandProvider(
        argv=[sys.executable, str(script)],
        timeout_seconds=timeout_seconds,
        env_forward=forward,
        max_stdout_bytes=max_stdout_bytes,
    )


@pytest.fixture
def fx21(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
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
                    },
                    {
                        "id": "RIG-001",
                        "task": "Map Alesis returns",
                        "area": "Routing",
                        "priority": "P1",
                        "status": "READY",
                        "depends_on": [],
                        "definition_of_done": "channels recorded",
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
                        "answer": (
                            "PB-A & PB-B are ART P48, PB-C & PB-D are Behringer PX3000"
                        ),
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
                        "id": "Q-001",
                        "question": "Where do A/B/Y non-clean legs go?",
                        "area": "Routing",
                        "status": "RESOLVED",
                        "related_todos": ["RIG-001"],
                        "related_changes": [],
                        "answer": "Acoustic: Alesis 2, bass: Alesis 1, electric: Alesis 3",
                        "notes": "",
                        "resolved_at": "2026-09-12T12:00:00+00:00",
                        "reconciled_at": None,
                        "target": {"domain": "routing.verify"},
                        "verification": {
                            "kind": "ROUTING_VISUAL",
                            "prompt": "trace cables",
                            "answer_type": "TEXT",
                            "choices": [],
                        },
                    },
                    {
                        "id": "Q-007",
                        "question": "Which unit is each bay?",
                        "area": "Patchbay",
                        "status": "RESOLVED",
                        "related_todos": ["RIG-200"],
                        "related_changes": [],
                        "answer": (
                            "PB-A & PB-B are ART P48, PB-C & PB-D are Behringer PX3000"
                        ),
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
                        "id": "Q-210",
                        "question": "Multi-domain fixture",
                        "area": "Routing",
                        "status": "RESOLVED",
                        "related_todos": ["RIG-200"],
                        "related_changes": [],
                        "answer": (
                            "Alesis 2=Acoustic; PB-A is ART P48 for the return path"
                        ),
                        "notes": "",
                        "resolved_at": "2026-09-12T12:00:00+00:00",
                        "reconciled_at": None,
                        "target": {"domain": "inventory.patchbay_mapping"},
                        "verification": {
                            "kind": "ROUTING_VISUAL",
                            "prompt": "observe",
                            "answer_type": "TEXT",
                            "choices": [],
                        },
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
                    "PB-A": {
                        "hardware_model": "unknown",
                        "status": "undocumented",
                        "jacks": {},
                    },
                    "PB-B": {
                        "hardware_model": "unknown",
                        "status": "undocumented",
                        "jacks": {},
                    },
                    "PB-C": {
                        "hardware_model": "unknown",
                        "status": "undocumented",
                        "jacks": {},
                    },
                    "PB-D": {
                        "hardware_model": "unknown",
                        "status": "undocumented",
                        "jacks": {},
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    channels.write_text(
        yaml.safe_dump(
            {
                "alesis": {
                    "1": {"source": None, "status": "UNASSIGNED"},
                    "2": {"source": None, "status": "UNASSIGNED"},
                    "3": {"source": None, "status": "UNASSIGNED"},
                }
            }
        ),
        encoding="utf-8",
    )
    routing.write_text(yaml.safe_dump(_minimal_routing()), encoding="utf-8")
    midi.write_text(
        yaml.safe_dump({"clock": {"transport": {"status": "UNKNOWN"}}}),
        encoding="utf-8",
    )
    controllers.write_text("controllers: []\n", encoding="utf-8")
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

    script = _install_fake_provider(tmp_path)
    ctx = ReconciliationContext.for_root(tmp_path)
    return {
        "tmp": tmp_path,
        "ctx": ctx,
        "questions": questions,
        "patchbays": patchbays,
        "channels": channels,
        "routing": routing,
        "script": script,
    }


def test_atomic_multi_domain_success(fx21):
    """channels + patchbay + finalize commit in one atomic write."""
    ctx = fx21["ctx"]
    ops = [
        RigOperation(
            namespace="channels",
            action="set_source",
            args={
                "device": "alesis",
                "channel": "2",
                "source": "Acoustic",
                "question_id": "Q-210",
            },
        ),
        RigOperation(
            namespace="patchbay",
            action="set_model",
            args={"bay_id": "PB-A", "model": "ART P48", "question_id": "Q-210"},
        ),
    ]
    proposal = AgentReconciliationProposal(
        artifact_id="Q-210",
        status=ProposalStatus.READY,
        rationale="multi-domain fixture apply",
        operations=ops,
        finalize=True,
    )
    before_ch = fx21["channels"].read_bytes()
    before_pb = fx21["patchbays"].read_bytes()
    before_q = fx21["questions"].read_bytes()

    result = apply_proposal(proposal, ctx=ctx, dry_run=False, yes=True)
    assert result["ok"] is True, result
    assert result.get("atomic") is True

    ch = channel_state.load_raw(fx21["channels"])
    assert ch["alesis"]["2"]["source"] == "Acoustic"
    pb = patchbay_state.load_raw(fx21["patchbays"])
    assert pb["patchbays"]["PB-A"]["hardware_model"] == "ART P48"
    q = load_questions(fx21["questions"]).question_map()["Q-210"]
    assert q.reconciled_at is not None

    assert fx21["channels"].read_bytes() != before_ch
    assert fx21["patchbays"].read_bytes() != before_pb
    assert fx21["questions"].read_bytes() != before_q


def test_prepare_invalid_op_zero_writes(fx21):
    ctx = fx21["ctx"]
    before = {
        "channels": fx21["channels"].read_bytes(),
        "patchbays": fx21["patchbays"].read_bytes(),
        "questions": fx21["questions"].read_bytes(),
    }
    bad = RigOperation(namespace="shell", action="rm", args={"path": "/"})
    with pytest.raises(StoreError):
        prepare_transaction([bad], ctx=ctx)
    assert fx21["channels"].read_bytes() == before["channels"]
    assert fx21["patchbays"].read_bytes() == before["patchbays"]
    assert fx21["questions"].read_bytes() == before["questions"]


def test_commit_failure_rollback(fx21, monkeypatch):
    ctx = fx21["ctx"]
    ops = [
        RigOperation(
            namespace="patchbay",
            action="set_model",
            args={"bay_id": "PB-A", "model": "ART P48", "question_id": "Q-200"},
        )
    ]
    prepared = prepare_transaction(ops, ctx=ctx)
    originals = dict(prepared.originals)

    calls = {"n": 0}
    real = transaction_mod.write_text_files

    def boom(payloads):
        calls["n"] += 1
        if calls["n"] == 1:
            for path, _text in payloads:
                path.write_text("CORRUPTED\n", encoding="utf-8")
            raise OSError("simulated commit failure")
        return real(payloads)

    monkeypatch.setattr(transaction_mod, "write_text_files", boom)
    with pytest.raises(Exception):
        commit_transaction(prepared, ctx=ctx, artifact_id="Q-200")

    for path_str, data in originals.items():
        assert Path(path_str).read_bytes() == data


def test_concurrency_refuses(fx21):
    ctx = fx21["ctx"]
    ops = [
        RigOperation(
            namespace="patchbay",
            action="set_model",
            args={"bay_id": "PB-A", "model": "ART P48", "question_id": "Q-200"},
        )
    ]
    prepared = prepare_transaction(ops, ctx=ctx)
    text = fx21["patchbays"].read_text(encoding="utf-8")
    fx21["patchbays"].write_text(text + "\n# concurrent edit\n", encoding="utf-8")
    with pytest.raises(ConcurrentModificationError):
        commit_transaction(prepared, ctx=ctx, artifact_id="Q-200")


def test_plan_conflict(fx21):
    ctx = fx21["ctx"]
    ops = [
        RigOperation(
            namespace="channels",
            action="set_source",
            args={"device": "alesis", "channel": "1", "source": "Bass"},
        ),
        RigOperation(
            namespace="channels",
            action="set_source",
            args={"device": "alesis", "channel": "1", "source": "Acoustic"},
        ),
    ]
    with pytest.raises(PlanConflictError) as excinfo:
        prepare_transaction(ops, ctx=ctx)
    assert excinfo.value.conflict_key


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


def test_q001_style_channel_ops_apply(fx21):
    ops = [
        RigOperation(
            namespace="channels",
            action="set_source",
            args={
                "device": "alesis",
                "channel": "1",
                "source": "Bass",
                "question_id": "Q-001",
            },
        ),
        RigOperation(
            namespace="channels",
            action="set_source",
            args={
                "device": "alesis",
                "channel": "2",
                "source": "Acoustic",
                "question_id": "Q-001",
            },
        ),
        RigOperation(
            namespace="channels",
            action="set_source",
            args={
                "device": "alesis",
                "channel": "3",
                "source": "Electric",
                "question_id": "Q-001",
            },
        ),
    ]
    proposal = AgentReconciliationProposal(
        artifact_id="Q-001",
        status=ProposalStatus.READY,
        rationale="Q-001 channel mapping",
        operations=ops,
        finalize=False,
    )
    result = apply_proposal(proposal, ctx=fx21["ctx"], dry_run=False, yes=True)
    assert result["ok"] is True, result
    ch = channel_state.load_raw(fx21["channels"])
    assert ch["alesis"]["1"]["source"] == "Bass"
    assert ch["alesis"]["2"]["source"] == "Acoustic"
    assert ch["alesis"]["3"]["source"] == "Electric"


def test_q007_model_mapping_no_unit_invention(fx21):
    proposal = AgentReconciliationProposal(
        artifact_id="Q-007",
        status=ProposalStatus.READY,
        rationale="invent unit id",
        operations=[
            RigOperation(
                namespace="patchbay",
                action="set_model",
                args={
                    "bay_id": "PB-A",
                    "model": "art-p48-1",
                    "question_id": "Q-007",
                },
            )
        ],
    )
    result = validate_proposal(proposal, ctx=fx21["ctx"])
    assert result["ok"] is False
    assert any("unit-id" in e for e in result["errors"])


def test_evidence_verified_rejected(fx21):
    proposal = AgentReconciliationProposal(
        artifact_id="Q-001",
        status=ProposalStatus.READY,
        rationale="verify without observation",
        operations=[
            RigOperation(
                namespace="path",
                action="set_evidence",
                args={
                    "path_id": "dirty",
                    "evidence": "VERIFIED",
                    "question_id": "Q-001",
                },
            )
        ],
    )
    result = validate_proposal(proposal, ctx=fx21["ctx"])
    if result["ok"]:
        with pytest.raises(StoreError, match="VERIFIED|verification_result"):
            prepare_transaction(proposal.operations, ctx=fx21["ctx"])
    else:
        assert any(
            "verified" in e.casefold() or "evidence" in e.casefold()
            for e in result["errors"]
        )


def test_irrelevant_domain_rejected(fx21):
    proposal = AgentReconciliationProposal(
        artifact_id="Q-001",
        status=ProposalStatus.READY,
        rationale="gear location on routing question",
        operations=[
            RigOperation(
                namespace="gear",
                action="set_location",
                args={"gear_id": "art-p48-1", "location": "rack"},
            )
        ],
    )
    result = validate_proposal(proposal, ctx=fx21["ctx"])
    assert result["ok"] is False
    assert any("not relevant" in e or "unregistered" in e for e in result["errors"])


def test_unknown_operation_rejected(fx21):
    proposal = AgentReconciliationProposal(
        artifact_id="Q-200",
        status=ProposalStatus.READY,
        rationale="wishlist invent",
        operations=[
            RigOperation(
                namespace="wishlist",
                action="add",
                args={"item": "noise"},
            )
        ],
    )
    result = validate_proposal(proposal, ctx=fx21["ctx"])
    assert result["ok"] is False
    assert any("unregistered" in e for e in result["errors"])


def test_postcondition_failure_rolls_back(fx21, monkeypatch):
    ctx = fx21["ctx"]
    ops = [
        RigOperation(
            namespace="patchbay",
            action="set_model",
            args={"bay_id": "PB-A", "model": "ART P48", "question_id": "Q-200"},
        )
    ]
    prepared = prepare_transaction(ops, ctx=ctx)
    original_pb = fx21["patchbays"].read_bytes()

    monkeypatch.setattr(
        transaction_mod,
        "evaluate_postconditions",
        lambda **kwargs: {
            "ok": False,
            "errors": ["forced postcondition failure"],
            "question_status": "RESOLVED",
            "reconciled_at": None,
        },
    )
    result = commit_transaction(prepared, ctx=ctx, artifact_id="Q-200")
    assert result["ok"] is False
    assert result.get("rolled_back") is True
    assert fx21["patchbays"].read_bytes() == original_pb

    post = evaluate_postconditions(
        artifact_id="Q-200",
        ctx=ctx,
        require_finalize=True,
        finalize_plan={"requested": True},
    )
    assert post["ok"] is False
    assert any("reconciled_at" in e for e in post["errors"])


def test_clarification_stops_writes(fx21, monkeypatch):
    monkeypatch.setenv("FAKE_PROVIDER_MODE", "CLARIFY")
    before = fx21["patchbays"].read_bytes()
    prov = _provider(fx21["script"], mode="CLARIFY")
    result = autonomous_reconcile(
        "Q-200",
        ctx=fx21["ctx"],
        provider=prov,
        apply=True,
        yes=True,
        dry_run=False,
        autonomy=AutonomyLevel.APPLY_AND_FINALIZE,
        root=fx21["tmp"],
    )
    assert result.get("writes") is False or result.get("applied") is not True
    assert result.get("status") == "NEEDS_HUMAN_CLARIFICATION"
    assert fx21["patchbays"].read_bytes() == before


def test_capabilities_includes_new_ops():
    caps = capabilities()
    kinds = caps["allowlisted_operations"]
    assert "channels.set_source" in kinds
    assert "channels.clear_source" in kinds
    assert "path.move" in kinds
    assert "path.set_evidence" in kinds
    assert "PLAN_ONLY" in caps["autonomy_levels"]


def test_allowlisted_includes_path_and_channels_clear():
    kinds = allowlisted_kinds(agent_only=True)
    assert "path.insert" in kinds
    assert "path.remove" in kinds
    assert "path.set_mode" in kinds
    assert "channels.clear_source" in kinds
    assert get_spec("channels.clear_source").agent_allowed is True


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


def test_production_readonly_packet_q007():
    """Read-only production packet — no mutation."""
    before = question_service.get_question("Q-007")
    packet = build_agent_packet("Q-007")
    assert "ART P48" in packet["final_human_answer"]
    assert "Behringer PX3000" in packet["final_human_answer"]
    assert packet["relevant_current_context"].get("unit_identity_note")
    after = question_service.get_question("Q-007")
    assert after.answer == before.answer
    assert after.reconciled_at == before.reconciled_at
