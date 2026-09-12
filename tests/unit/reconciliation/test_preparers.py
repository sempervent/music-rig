"""Unit coverage for preparers and materialize_working_docs."""

from __future__ import annotations

import pytest
import yaml

from music_rig.models import MidiEvidenceStatus
from music_rig.reconciliation.operation_registry import prepare_operation
from music_rig.reconciliation.operations import RigOperation
from music_rig.reconciliation.preparers import materialize_working_docs
from music_rig.store import StoreError


def _jacks_pair() -> dict:
    return {
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
    }


def test_prepare_patchbay_mode_and_connection(fx21):
    from music_rig import patchbay_state

    raw = patchbay_state.load_raw(fx21["patchbays"])
    raw["patchbays"]["PB-A"]["jacks"] = _jacks_pair()
    patchbay_state.save_raw(raw, fx21["patchbays"])
    ctx = fx21["ctx"]
    working: dict = {}

    mode_op = RigOperation(
        namespace="patchbay",
        action="set_mode",
        args={"bay_id": "PB-A", "jack_spec": "1/25", "mode": "normal"},
    )
    prep = prepare_operation(mode_op, ctx, working)
    assert "patchbays" in prep.touched_documents
    assert prep.after.get("mode") == "normal"

    conn_op = RigOperation(
        namespace="patchbay",
        action="set_connection",
        args={
            "bay_id": "PB-A",
            "jack_spec": "1/25",
            "upper_connection": "X",
            "lower_connection": "Y",
        },
    )
    prep2 = prepare_operation(conn_op, ctx, working)
    assert prep2.after.get("upper_connection") == "X"
    payloads, _ = materialize_working_docs(working, ctx, [prep, prep2])
    assert any(p[0] == ctx.paths.patchbays for p in payloads)


def test_prepare_channels_clear_source(fx21):
    ctx = fx21["ctx"]
    working: dict = {}
    set_op = RigOperation(
        namespace="channels",
        action="set_source",
        args={"device": "alesis", "channel": "2", "source": "Acoustic"},
    )
    prepare_operation(set_op, ctx, working)
    clear_op = RigOperation(
        namespace="channels",
        action="clear_source",
        args={"device": "alesis", "channel": "2"},
    )
    prep = prepare_operation(clear_op, ctx, working)
    assert prep.after.get("source") is None
    payloads, _ = materialize_working_docs(working, ctx, [prep])
    assert any(p[0] == ctx.paths.channels for p in payloads)


def test_prepare_path_mutations(fx21):
    ctx = fx21["ctx"]
    working: dict = {}

    move = RigOperation(
        namespace="path",
        action="move",
        args={"path_id": "dirty", "node": "c", "first": True},
    )
    prep_move = prepare_operation(move, ctx, working)
    assert "routing" in prep_move.touched_documents

    insert = RigOperation(
        namespace="path",
        action="insert",
        args={"path_id": "dirty", "node_id": "z", "label": "Z", "last": True},
    )
    prep_ins = prepare_operation(insert, ctx, working)
    assert "routing:dirty:node:z" in prep_ins.conflict_claims

    remove = RigOperation(
        namespace="path",
        action="remove",
        args={"path_id": "dirty", "node": "z"},
    )
    prep_rm = prepare_operation(remove, ctx, working)
    assert prep_rm.conflict_claims.get("routing:dirty:node:z") == "absent"

    mode = RigOperation(
        namespace="path",
        action="set_mode",
        args={"path_id": "dirty", "node": "a", "mode": "bypass"},
    )
    prep_mode = prepare_operation(mode, ctx, working)
    assert prep_mode.after.get("mode") == "bypass"

    ev = RigOperation(
        namespace="path",
        action="set_evidence",
        args={"path_id": "dirty", "evidence": MidiEvidenceStatus.INTENDED.value},
    )
    prep_ev = prepare_operation(ev, ctx, working)
    assert prep_ev.after.get("evidence") == "INTENDED"

    payloads, _ = materialize_working_docs(
        working, ctx, [prep_move, prep_ins, prep_rm, prep_mode, prep_ev]
    )
    assert any(p[0] == ctx.paths.routing for p in payloads)


def test_prepare_path_set_evidence_verified_guards(fx21):
    ctx = fx21["ctx"]
    working: dict = {}
    op = RigOperation(
        namespace="path",
        action="set_evidence",
        args={"path_id": "dirty", "evidence": "VERIFIED"},
    )
    with pytest.raises(StoreError, match="question_id"):
        prepare_operation(op, ctx, working)

    op2 = RigOperation(
        namespace="path",
        action="set_evidence",
        args={
            "path_id": "dirty",
            "evidence": "VERIFIED",
            "question_id": "Q-200",
        },
    )
    with pytest.raises(StoreError, match="verification_result"):
        prepare_operation(op2, ctx, working)


def test_prepare_gear_set_location(fx21):
    ctx = fx21["ctx"]
    working: dict = {}
    op = RigOperation(
        namespace="gear",
        action="set_location",
        args={"gear_id": "art-p48-1", "location": "rack-A"},
    )
    prep = prepare_operation(op, ctx, working)
    assert "inventory" in prep.touched_documents
    payloads, _ = materialize_working_docs(working, ctx, [prep])
    assert any(p[0] == ctx.paths.inventory for p in payloads)


def test_prepare_finalize_manual_and_clarification(fx21):
    ctx = fx21["ctx"]
    working: dict = {}

    fin = RigOperation(
        namespace="question",
        action="finalize_manual",
        args={
            "question_id": "Q-200",
            "note": "faceplates match",
            "complete_linked_todos": True,
            "confirm_dod": True,
            "apply_linked_changes": True,
        },
    )
    prep = prepare_operation(fin, ctx, working)
    assert prep.after.get("reconciled_at") == "set"
    assert "RIG-200" in (prep.after.get("completed_todos") or [])

    clar = RigOperation(
        namespace="question",
        action="open_clarification",
        args={
            "parent_question_id": "Q-200",
            "clarification": "Which ART unit is PB-A specifically?",
        },
    )
    prep_c = prepare_operation(clar, ctx, working)
    assert prep_c.after.get("clarifies_question") == "Q-200"
    new_id = prep_c.after["question_id"]

    payloads, plan = materialize_working_docs(working, ctx, [prep, prep_c])
    assert plan is not None and plan.get("requested") is True
    assert any(p[0] == ctx.paths.questions for p in payloads)
    assert any(p[0] == ctx.paths.todo for p in payloads)
    # staged questions include new clarification
    qdoc = working["questions"]
    assert new_id in qdoc.question_map()


def test_prepare_finalize_error_paths(fx21):
    ctx = fx21["ctx"]
    working: dict = {}

    with pytest.raises(StoreError, match="non-empty note"):
        prepare_operation(
            RigOperation(
                namespace="question",
                action="finalize_manual",
                args={"question_id": "Q-200", "note": "   "},
            ),
            ctx,
            working,
        )

    with pytest.raises(StoreError, match="unknown question"):
        prepare_operation(
            RigOperation(
                namespace="question",
                action="finalize_manual",
                args={"question_id": "Q-999", "note": "x"},
            ),
            ctx,
            {},
        )

    # OPEN question cannot finalize
    qpath = fx21["questions"]
    data = yaml.safe_load(qpath.read_text(encoding="utf-8"))
    data["questions"].append(
        {
            "id": "Q-299",
            "question": "open?",
            "area": "Routing",
            "status": "OPEN",
            "related_todos": [],
            "related_changes": [],
            "answer": "",
            "notes": "",
        }
    )
    qpath.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(StoreError, match="RESOLVED"):
        prepare_operation(
            RigOperation(
                namespace="question",
                action="finalize_manual",
                args={"question_id": "Q-299", "note": "nope"},
            ),
            ctx,
            {},
        )


def test_prepare_clarification_errors(fx21):
    ctx = fx21["ctx"]
    with pytest.raises(StoreError, match="clarification text"):
        prepare_operation(
            RigOperation(
                namespace="question",
                action="open_clarification",
                args={"parent_question_id": "Q-200", "clarification": "  "},
            ),
            ctx,
            {},
        )
    with pytest.raises(StoreError, match="unknown parent"):
        prepare_operation(
            RigOperation(
                namespace="question",
                action="open_clarification",
                args={"parent_question_id": "Q-999", "clarification": "why?"},
            ),
            ctx,
            {},
        )


def test_materialize_validation_failures(fx21):
    ctx = fx21["ctx"]
    working = {
        "channels": {
            "alesis": {"2": {"source": "x", "status": "UNASSIGNED"}},
        }
    }
    with pytest.raises(StoreError, match="Channel map validation"):
        materialize_working_docs(working, ctx, [])

    working2 = {"patchbays": {"schema_notes": {}, "patchbays": "bad"}}
    with pytest.raises(StoreError, match="Patchbay validation"):
        materialize_working_docs(working2, ctx, [])

    working3 = {"routing": {"named_paths": "nope"}}
    with pytest.raises(StoreError, match="Routing validation"):
        materialize_working_docs(working3, ctx, [])

    working4 = {"inventory": {"items": "nope"}}
    with pytest.raises(StoreError, match="Inventory validation"):
        materialize_working_docs(working4, ctx, [])
