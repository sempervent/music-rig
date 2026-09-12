"""Reconciliation context + service helper edges."""

from __future__ import annotations

from datetime import UTC, datetime

from music_rig.models import OpenQuestion, QuestionStatus, ReconciliationState
from music_rig.reconciliation import service as recon_service
from music_rig.reconciliation.context import ReconciliationContext, ReconciliationPaths


def test_context_questions_path_and_cache(tmp_path):
    ctx = ReconciliationContext.for_root(tmp_path)
    assert ctx.questions_path == tmp_path / "open-questions.yaml"
    assert "questions_path" in ctx.path_kwargs()
    calls = {"n": 0}

    def loader():
        calls["n"] += 1
        return {"ok": True}

    assert ctx.cached_load("x", loader)["ok"] is True
    assert ctx.cached_load("x", loader)["ok"] is True
    assert calls["n"] == 1
    ctx.clear_cache()
    assert ctx.cached_load("x", loader)["ok"] is True
    assert calls["n"] == 2


def test_paths_default_and_overrides(monkeypatch, tmp_path):
    from music_rig import store as store_mod

    monkeypatch.setattr(store_mod, "QUESTIONS_PATH", tmp_path / "q.yaml")
    paths = ReconciliationPaths.default()
    assert paths.questions == tmp_path / "q.yaml"
    ctx = ReconciliationContext.from_overrides(
        {"questions_path": tmp_path / "other.yaml", "todo": tmp_path / "t.yaml"}
    )
    assert ctx.paths.questions == tmp_path / "other.yaml"
    assert ctx.paths.todo == tmp_path / "t.yaml"


def test_early_open_lifecycle_state():
    open_q = OpenQuestion(
        id="Q-901",
        question="?",
        area="Docs",
        status=QuestionStatus.OPEN,
        answer="",
    )
    assert recon_service.early_open_lifecycle_state(open_q) is ReconciliationState.NEEDS_ANSWER
    draft = OpenQuestion(
        id="Q-902",
        question="?",
        area="Docs",
        status=QuestionStatus.OPEN,
        answer="draft",
    )
    assert recon_service.early_open_lifecycle_state(draft) is ReconciliationState.DRAFT_ANSWER
    done = OpenQuestion(
        id="Q-903",
        question="?",
        area="Docs",
        status=QuestionStatus.RESOLVED,
        answer="done",
        resolved_at=datetime.now(UTC),
        reconciled_at=datetime.now(UTC),
    )
    assert recon_service.early_open_lifecycle_state(done) is ReconciliationState.RECONCILED
    assert (
        recon_service.early_open_lifecycle_state(
            OpenQuestion(
                id="Q-904",
                question="?",
                area="Docs",
                status=QuestionStatus.RESOLVED,
                answer="done",
                resolved_at=datetime.now(UTC),
            )
        )
        is None
    )
