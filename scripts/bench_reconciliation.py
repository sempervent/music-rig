#!/usr/bin/env python3
"""Manual reconciliation load / timing baseline.

Builds synthetic repos with N questions (+ proportional todos/changes) and
reports wall time for plan_question and sweep(dry), plus load_* call counts
for a single plan_question.

Usage:
    uv run python scripts/bench_reconciliation.py
"""

from __future__ import annotations

import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

from music_rig.reconciliation import service as recon
from music_rig.reconciliation.context import ReconciliationContext
from music_rig.store import load_changes, load_questions, load_todo


def _write_synthetic(root: Path, n: int) -> None:
    """Minimal YAML documents proportional to n (valid against store models)."""
    questions = []
    todos = []
    changes = []
    now = datetime(2026, 9, 11, 21, 0, 0, tzinfo=timezone.utc).isoformat()
    for i in range(1, n + 1):
        qid = f"Q-{i:03d}"
        tid = f"RIG-{i:03d}"
        cid = f"CHG-{i:03d}"
        questions.append(
            {
                "id": qid,
                "area": "Bench",
                "question": f"Bench question {i}?",
                "status": "OPEN",
                "answer": "",
                "notes": "",
                "related_todos": [tid],
                "related_changes": [cid],
                "resolved_at": None,
            }
        )
        todos.append(
            {
                "id": tid,
                "area": "Bench",
                "task": f"Bench todo {i}",
                "priority": "P2",
                "status": "READY",
                "depends_on": [],
                "definition_of_done": f"Bench DoD {i}",
                "notes": "",
            }
        )
        changes.append(
            {
                "id": cid,
                "created_at": now,
                "summary": f"Bench change {i}",
                "status": "OPEN",
                "category": "OTHER",
                "details": "",
                "affected_areas": [],
                "related_questions": [qid],
            }
        )

    def dump(name: str, payload: dict) -> None:
        (root / name).write_text(
            yaml.safe_dump(payload, sort_keys=False), encoding="utf-8"
        )

    dump("open-questions.yaml", {"questions": questions})
    dump("todo.yaml", {"tasks": todos, "next_session": []})
    dump("changes.yaml", {"items": changes})

    # Copy production-shaped stubs where possible; otherwise minimal raw maps.
    from music_rig.store import ROOT

    for src_name, dst_name in [
        ("patchbays.yaml", "patchbays.yaml"),
        ("routing.yaml", "routing.yaml"),
        ("midi.yaml", "midi.yaml"),
        ("controllers.yaml", "controllers.yaml"),
        ("ableton.yaml", "ableton.yaml"),
        ("inventory.yaml", "inventory.yaml"),
        ("channel-map.yaml", "channel-map.yaml"),
    ]:
        src = ROOT / "data" / src_name
        if src.exists():
            (root / dst_name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            dump(dst_name, {})

    for md in ("todo.md", "wishlist.md", "open-questions.md", "patchbays.md"):
        (root / md).write_text(f"# {md}\n", encoding="utf-8")


def _count_loads(ctx: ReconciliationContext, qid: str) -> dict[str, int]:
    counts = {"questions": 0, "todo": 0, "changes": 0}
    real_q = load_questions
    real_t = load_todo
    real_c = load_changes

    def wrap_q(path=None):
        counts["questions"] += 1
        return real_q(path)

    def wrap_t(path=None):
        counts["todo"] += 1
        return real_t(path)

    def wrap_c(path=None):
        counts["changes"] += 1
        return real_c(path)

    import music_rig.store as store_mod
    import music_rig.question_service as qsvc
    import music_rig.reconciliation.service as svc

    originals = {
        "store_q": store_mod.load_questions,
        "store_t": store_mod.load_todo,
        "store_c": store_mod.load_changes,
        "svc_q": svc.load_questions,
        "svc_t": svc.load_todo,
        "svc_c": svc.load_changes,
        "qs_q": qsvc.load_questions,
    }
    store_mod.load_questions = wrap_q  # type: ignore[assignment]
    store_mod.load_todo = wrap_t  # type: ignore[assignment]
    store_mod.load_changes = wrap_c  # type: ignore[assignment]
    svc.load_questions = wrap_q  # type: ignore[assignment]
    svc.load_todo = wrap_t  # type: ignore[assignment]
    svc.load_changes = wrap_c  # type: ignore[assignment]
    qsvc.load_questions = wrap_q  # type: ignore[assignment]
    try:
        recon.plan_question(qid, ctx=ctx)
    finally:
        store_mod.load_questions = originals["store_q"]  # type: ignore[assignment]
        store_mod.load_todo = originals["store_t"]  # type: ignore[assignment]
        store_mod.load_changes = originals["store_c"]  # type: ignore[assignment]
        svc.load_questions = originals["svc_q"]  # type: ignore[assignment]
        svc.load_todo = originals["svc_t"]  # type: ignore[assignment]
        svc.load_changes = originals["svc_c"]  # type: ignore[assignment]
        qsvc.load_questions = originals["qs_q"]  # type: ignore[assignment]
    return counts


def bench_size(n: int) -> dict:
    with tempfile.TemporaryDirectory(prefix=f"rig-bench-{n}-") as tmp:
        root = Path(tmp)
        _write_synthetic(root, n)
        ctx = ReconciliationContext.for_root(root)
        qid = "Q-001"
        path_kw = ctx.path_kwargs()

        t0 = time.perf_counter()
        recon.plan_question(qid, ctx=ctx)
        plan_s = time.perf_counter() - t0

        t0 = time.perf_counter()
        recon.sweep(
            dry_run=True,
            yes=False,
            questions_path=path_kw["questions_path"],
            changes_path=path_kw["changes_path"],
            todo_path=path_kw["todo_path"],
            patchbays_path=path_kw["patchbays_path"],
            routing_path=path_kw["routing_path"],
            midi_path=path_kw["midi_path"],
            controllers_path=path_kw["controllers_path"],
            ableton_path=path_kw["ableton_path"],
            docs_todo=path_kw["docs_todo"],
            docs_wishlist=path_kw["docs_wishlist"],
            docs_questions=path_kw["docs_questions"],
        )
        sweep_s = time.perf_counter() - t0

        loads = _count_loads(ctx, qid)
        return {
            "n": n,
            "plan_s": plan_s,
            "sweep_s": sweep_s,
            "loads": loads,
        }


def main() -> None:
    print("reconciliation baseline (wall time; no CI threshold)")
    print(f"{'N':>6}  {'plan_s':>10}  {'sweep_s':>10}  loads(q/t/c)")
    for n in (10, 100, 500):
        row = bench_size(n)
        loads = row["loads"]
        print(
            f"{row['n']:6d}  {row['plan_s']:10.4f}  {row['sweep_s']:10.4f}  "
            f"{loads['questions']}/{loads['todo']}/{loads['changes']}"
        )
    print(
        "\nNote: loads are for one plan_question call. "
        "If questions loads <= 2, no request-scoped cache is required."
    )


if __name__ == "__main__":
    main()
