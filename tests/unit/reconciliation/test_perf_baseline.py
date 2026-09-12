"""Structural invariants for reconciliation perf instrumentation (no time gates)."""

from __future__ import annotations

from pathlib import Path

import yaml

from music_rig.reconciliation import service as recon
from music_rig.reconciliation.context import ReconciliationContext


def _mini_repo(root: Path) -> None:
    (root / "open-questions.yaml").write_text(
        yaml.safe_dump(
            {
                "questions": [
                    {
                        "id": "Q-001",
                        "area": "Bench",
                        "question": "x?",
                        "status": "OPEN",
                        "answer": "",
                        "notes": "",
                        "related_todos": [],
                        "related_changes": [],
                        "resolved_at": None,
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (root / "todo.yaml").write_text("next_session: []\ntasks: []\n", encoding="utf-8")
    (root / "changes.yaml").write_text("items: []\n", encoding="utf-8")
    # Lightweight stubs — plan for OPEN unanswered does not need full CURRENT.
    for name, body in {
        "patchbays.yaml": {"bays": []},
        "routing.yaml": {"named_paths": {}, "routes": {}},
        "midi.yaml": {
            "endpoints": [],
            "devices": [],
            "connections": [],
            "channels": [],
            "clock": {"master": None, "status": "UNKNOWN", "destinations": []},
            "ableton_ports": [],
            "routes": [],
            "unknowns": [],
        },
        "controllers.yaml": {"controllers": []},
        "ableton.yaml": {"tracks": [], "sends": [], "actions": [], "templates": []},
        "inventory.yaml": {"items": []},
        "channel-map.yaml": {"devices": {}},
    }.items():
        (root / name).write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")


def test_plan_question_with_ctx_does_not_crash(tmp_path: Path):
    _mini_repo(tmp_path)
    ctx = ReconciliationContext.for_root(tmp_path)
    plan = recon.plan_question("Q-001", ctx=ctx)
    assert plan.artifact_id == "Q-001"
    assert "suggestions" in plan.to_dict()
    assert "suggested_commands" in plan.to_dict()


def test_context_cached_load_helper(tmp_path: Path):
    ctx = ReconciliationContext.for_root(tmp_path)
    calls = {"n": 0}

    def loader():
        calls["n"] += 1
        return {"ok": True}

    a = ctx.cached_load("questions", loader)
    b = ctx.cached_load("questions", loader)
    assert a is b
    assert calls["n"] == 1
    ctx.clear_cache()
    ctx.cached_load("questions", loader)
    assert calls["n"] == 2
