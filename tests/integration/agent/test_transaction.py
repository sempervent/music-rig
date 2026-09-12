"""Tests migrated to integration/agent/test_transaction.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from fixtures.repo_fixtures import _provider
from music_rig import channel_state, patchbay_state
from music_rig.agent import (
    AgentReconciliationProposal,
    ProposalStatus,
    apply_proposal,
    validate_proposal,
)
from music_rig.agent import transaction as transaction_mod
from music_rig.agent.errors import (
    ConcurrentModificationError,
    PlanConflictError,
)
from music_rig.agent.orchestrate import AutonomyLevel, autonomous_reconcile
from music_rig.agent.transaction import (
    commit_transaction,
    evaluate_postconditions,
    prepare_transaction,
)
from music_rig.reconciliation.operations import RigOperation
from music_rig.store import StoreError, load_questions


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
            "verified" in e.casefold() or "evidence" in e.casefold() for e in result["errors"]
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
