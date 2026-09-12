"""Unit coverage for operation CLI rendering edges."""

from __future__ import annotations

from music_rig.actor import ActorKind
from music_rig.reconciliation.operation_renderer import (
    operation_json_view,
    render_argv,
    render_cli,
    render_human,
    render_suggestion,
)
from music_rig.reconciliation.operations import RigOperation
from music_rig.reconciliation.suggestions import (
    suggest_finalize,
)


def test_render_set_model_with_flags():
    op = RigOperation(
        namespace="patchbay",
        action="set_model",
        args={"bay_id": "PB-A", "model": "ART P48", "question_id": "Q-1", "yes": True},
    )
    argv = render_argv(op)
    assert "--question" in argv and "Q-1" in argv and "--yes" in argv
    assert "set-model" in render_cli(op)


def test_render_channels_set_source_with_flags():
    op = RigOperation(
        namespace="channels",
        action="set_source",
        args={
            "device": "alesis",
            "channel": "2",
            "source": "Acoustic",
            "question_id": "Q-1",
            "yes": True,
        },
    )
    cli = render_cli(op)
    assert "set-source" in cli and "Acoustic" in cli and "--yes" in cli


def test_render_finalize_and_resolve_and_inspect():
    fin = RigOperation(
        namespace="question",
        action="finalize_manual",
        args={"question_id": "Q-200", "note": "done"},
    )
    assert "finalize" in render_cli(fin) and "--confirm-current-reconciled" in render_cli(fin)

    res = RigOperation(namespace="question", action="resolve", args={"question_id": "Q-1"})
    assert render_argv(res)[-2:] == ["resolve", "Q-1"]

    iq = RigOperation(namespace="inspect", action="question", args={"question_id": "Q-1"})
    assert "--json" in render_argv(iq)

    ip = RigOperation(namespace="inspect", action="patchbay", args={"bay_id": "PB-A"})
    assert "patchbay" in render_argv(ip) and "PB-A" in render_argv(ip)


def test_render_generic_bool_and_value_args():
    op = RigOperation(
        namespace="path",
        action="move",
        args={"path_id": "dirty", "node": "a", "first": True, "branch": "main"},
    )
    argv = render_argv(op)
    assert "--first" in argv
    assert "--branch" in argv and "main" in argv
    assert render_human(op).startswith("path.move")


def test_operation_json_view_and_suggestion_delegate():
    op = RigOperation(
        namespace="patchbay",
        action="set_model",
        args={"bay_id": "PB-A", "model": "x"},
    )
    view = operation_json_view(op)
    assert "rendered_cli" in view and view["operation"]["kind"] == "patchbay.set_model"

    sug = suggest_finalize("Q-200", confirm_current_reconciled=True, note="n")
    text = render_suggestion(sug, actor=ActorKind.BOT)
    assert "--am-bot" in text or "finalize" in text
