"""Guided reconciliation of OPEN changes and questions (advisory, not auto-apply)."""

from __future__ import annotations

from pathlib import Path

from music_rig.models import (
    ChangeCategory,
    ChangeStatus,
    InboxStatus,
    QuestionStatus,
    TodoStatus,
)
from music_rig.store import (
    load_changes,
    load_inbox,
    load_questions,
    load_todo,
)

# Repository-maintenance mappings: where categories are typically documented.
# Advisory only — not physical rig facts.
CATEGORY_LIKELY_FILES: dict[ChangeCategory, list[str]] = {
    ChangeCategory.AUDIO_ROUTING: [
        "data/routing.yaml",
        "docs/current-routing.md",
        "README.md",
        "diagrams/",
    ],
    ChangeCategory.PEDAL_CHAIN: [
        "data/routing.yaml",
        "docs/pedal-chains.md",
        "docs/current-routing.md",
        "diagrams/aux-send-loop.mmd",
        "README.md",
    ],
    ChangeCategory.PATCHBAY: [
        "data/patchbays.yaml",
        "docs/patchbays.md",
        "diagrams/patchbays.mmd",
    ],
    ChangeCategory.MIDI: [
        "data/midi.yaml",
        "docs/midi-topology.md",
        "docs/midi-clock.md",
        "diagrams/midi-topology.mmd",
    ],
    ChangeCategory.ABLETON: [
        "data/ableton.yaml",
        "docs/ableton-track-map.md",
    ],
    ChangeCategory.INVENTORY: [
        "data/inventory.yaml",
        "docs/inventory.md",
    ],
    ChangeCategory.CONTROLLERS: [
        "data/controllers.yaml",
        "docs/controller-mappings.md",
    ],
    ChangeCategory.VIDEO: [
        "docs/open-questions.md",
        "docs/todo.md",
    ],
    ChangeCategory.OTHER: [
        "docs/current-routing.md",
        "docs/troubleshooting.md",
    ],
}

AREA_LIKELY_FILES: dict[str, list[str]] = {
    "routing": ["data/routing.yaml", "docs/current-routing.md", "data/channel-map.yaml"],
    "patchbay": ["data/patchbays.yaml", "docs/patchbays.md"],
    "pedals": ["docs/pedal-chains.md", "data/routing.yaml"],
    "midi": [
        "data/midi.yaml",
        "docs/midi-topology.md",
        "docs/midi-clock.md",
        "diagrams/midi-topology.mmd",
    ],
    "performance": [
        "data/performance.yaml",
        "data/control-surfaces.yaml",
        "data/ableton.yaml",
        "docs/performance.md",
        "docs/live-recovery.md",
        "docs/ableton-track-map.md",
    ],
    "controls": ["data/controllers.yaml", "docs/controller-mappings.md"],
    "video": ["docs/ableton-track-map.md", "docs/todo.md"],
}


def likely_files_for_category(category: ChangeCategory) -> list[str]:
    return list(CATEGORY_LIKELY_FILES.get(category, CATEGORY_LIKELY_FILES[ChangeCategory.OTHER]))


def likely_files_for_area(area: str) -> list[str]:
    key = area.casefold()
    for needle, files in AREA_LIKELY_FILES.items():
        if needle in key:
            return list(files)
    return ["docs/open-questions.md", "docs/current-routing.md"]


def build_reconcile_summary(
    *,
    changes_path: Path | None = None,
    questions_path: Path | None = None,
    inbox_path: Path | None = None,
) -> str:
    changes = load_changes(changes_path)
    questions = load_questions(questions_path)
    inbox = load_inbox(inbox_path)

    open_chg = [c for c in changes.items if c.status == ChangeStatus.OPEN]
    open_q = [q for q in questions.questions if q.status == QuestionStatus.OPEN]
    open_inbox = [i for i in inbox.items if i.status == InboxStatus.OPEN]

    lines = [
        "RECONCILIATION",
        "",
        f"Open Changes:   {len(open_chg)}",
        f"Open Questions: {len(open_q)}",
        f"Open Inbox:     {len(open_inbox)}",
        "",
        "Changes:",
    ]
    if open_chg:
        for c in open_chg:
            lines.append(f"  {c.id} {c.category.value:<14} {c.summary}")
    else:
        lines.append("  (none)")

    lines.append("")
    lines.append("Questions:")
    if open_q:
        for q in open_q[:12]:
            lines.append(f"  {q.id} {q.question}")
        if len(open_q) > 12:
            lines.append(f"  … and {len(open_q) - 12} more")
    else:
        lines.append("  (none)")

    advisories = reconciliation_advisories(
        changes_path=changes_path,
        questions_path=questions_path,
        todo_path=None,
    )
    if advisories:
        lines.append("")
        lines.append("Advisories:")
        for a in advisories:
            lines.append(f"  ⚠ {a}")

    lines.append("")
    lines.append("Inspect:")
    lines.append("  uv run rig reconcile change CHG-…")
    lines.append("  uv run rig reconcile question Q-…")
    return "\n".join(lines) + "\n"


def format_reconcile_change(
    chg_id: str,
    *,
    changes_path: Path | None = None,
    questions_path: Path | None = None,
    todo_path: Path | None = None,
) -> str:
    from music_rig import change_service

    item = change_service.get_change(chg_id, changes_path=changes_path)
    qdoc = load_questions(questions_path)

    related_q = list(item.related_questions)
    # also find questions pointing at this change
    for q in qdoc.questions:
        if item.id in q.related_changes and q.id not in related_q:
            related_q.append(q.id)

    related_todos: list[str] = []
    for qid in related_q:
        q = qdoc.question_map().get(qid)
        if q:
            related_todos.extend(q.related_todos)

    lines = [
        f"{item.id} — {item.category.value}",
        item.summary,
        "",
        f"Status: {item.status.value}",
        f"Created: {item.created_at.isoformat()}",
    ]
    if item.details:
        lines.append(f"Details: {item.details}")
    lines.append("")
    lines.append("CURRENT has NOT been automatically modified.")
    lines.append("")
    lines.append("Likely affected repository areas:")
    for path in likely_files_for_category(item.category):
        lines.append(f"  {path}")
    lines.append("")
    lines.append("Related:")
    lines.append("  Questions: " + (", ".join(related_q) if related_q else "—"))
    lines.append("  TODOs: " + (", ".join(dict.fromkeys(related_todos)) if related_todos else "—"))
    lines.append("")
    lines.append("Reconciliation process:")
    lines.append("  1. Verify physical state.")
    lines.append("  2. Update canonical CURRENT sources.")
    lines.append("  3. Regenerate/update projections (`uv run rig render`).")
    lines.append("  4. Run `uv run rig check`.")
    lines.append("  5. Run MkDocs validation.")
    lines.append(f"  6. Mark {item.id} APPLIED (`uv run rig changes applied {item.id}`).")
    return "\n".join(lines) + "\n"


def format_reconcile_question(
    question_id: str,
    *,
    questions_path: Path | None = None,
) -> str:
    from music_rig import question_service

    q = question_service.get_question(question_id, questions_path=questions_path)
    lines = [
        f"{q.id} — {q.status.value}",
        q.question,
        "",
        f"Area: {q.area}",
    ]
    if q.answer.strip():
        lines.append(f"Answer: {q.answer}")
    lines.append("")
    lines.append("Related TODOs:")
    if q.related_todos:
        for tid in q.related_todos:
            lines.append(f"  {tid}")
    else:
        lines.append("  —")
    lines.append("")
    lines.append("Related Changes:")
    if q.related_changes:
        for cid in q.related_changes:
            lines.append(f"  {cid}")
    else:
        lines.append("  —")
    lines.append("")
    lines.append("Likely relevant canonical areas:")
    for path in likely_files_for_area(q.area):
        lines.append(f"  {path}")
    lines.append("")
    lines.append("Suggested action:")
    if q.status == QuestionStatus.OPEN:
        target = getattr(q, "target", None)
        if target is not None and target.domain == "patchbay.mode" and target.bay:
            lines.append(f"  This question maps to CURRENT field: {target.bay} mode")
            lines.append("  Verify physically, then run:")
            if target.pair:
                lines.append(
                    f"    uv run rig current patchbay set-mode {target.bay} "
                    f"{target.pair} <mode> --question {q.id}"
                )
            else:
                lines.append(f"    uv run rig current patchbay verify {target.bay}")
                lines.append(
                    f"    # or: uv run rig current patchbay set-mode {target.bay} "
                    f"<jack> <mode> --question {q.id}"
                )
        elif target is not None and target.domain == "patchbay.model" and target.bay:
            lines.append(f"  This question maps to CURRENT field: {target.bay} model")
            lines.append(
                f"    uv run rig current patchbay set-model {target.bay} "
                f'"<model>" --question {q.id}'
            )
        elif target is not None and target.domain == "routing.verify" and target.path:
            lines.append(f"  This question maps to CURRENT path: {target.path}")
            lines.append(f"    uv run rig current path verify {target.path}")
        elif target is not None and target.domain == "inventory.patchbay_mapping":
            lines.append("  Inspect the physical patchbay units and their model labels.")
            lines.append("  Record only observed unit identity; do not invent a PB letter mapping.")
            lines.append(f"  then: uv run rig question resolve {q.id}")
        elif target is not None and target.domain == "midi.clock_master":
            lines.append("  This question maps to CURRENT MIDI clock master evidence.")
            lines.append("  Prefer verification (do not invent a master):")
            lines.append("    uv run rig current midi verify")
            lines.append(
                f"    # or after physical check: "
                f"uv run rig current midi set-clock-master <endpoint> "
                f"--question {q.id}"
            )
        elif target is not None and target.domain == "midi.verify":
            lines.append("  This question maps to CURRENT MIDI topology verification.")
            lines.append("    uv run rig current midi verify")
            lines.append(f"    # optionally pass --question {q.id} on the apply step")
        elif (
            target is not None
            and target.domain in {"controls.verify", "controls.context"}
            and target.gear
        ):
            lines.append(f"  This question maps to controller verification for {target.gear}.")
            lines.append(f"    uv run rig current controls verify {target.gear}")
            lines.append(f"    # optionally pass --question {q.id} on the apply step")
        elif target is not None and target.domain == "ableton.template" and target.path:
            lines.append(f"  This question maps to Ableton template specification: {target.path}.")
            lines.append(f"    uv run rig ableton template {target.path}")
            lines.append("  Verify the live set directly before updating INTENDED evidence.")
        else:
            lines.append("  inspect the physical rig")
            lines.append(f"  then: uv run rig question resolve {q.id}")
            if q.related_todos:
                lines.append(f"  or continue: uv run rig todo show {q.related_todos[0]}")
    elif q.status == QuestionStatus.RESOLVED:
        lines.append("  if the answer changes CURRENT docs, reconcile those files,")
        lines.append("  then mark any related OPEN changes APPLIED")
    else:
        lines.append(f"  reopen when ready: uv run rig question reopen {q.id}")
    return "\n".join(lines) + "\n"


def reconciliation_advisories(
    *,
    changes_path: Path | None = None,
    questions_path: Path | None = None,
    todo_path: Path | None = None,
) -> list[str]:
    changes = load_changes(changes_path)
    questions = load_questions(questions_path)
    todo = load_todo(todo_path)
    by_chg = changes.item_map()
    by_todo = todo.task_map()
    advisories: list[str] = []

    resolved_open_chg = 0
    for q in questions.questions:
        if q.status != QuestionStatus.RESOLVED:
            continue
        for cid in q.related_changes:
            chg = by_chg.get(cid)
            if chg and chg.status == ChangeStatus.OPEN:
                resolved_open_chg += 1
                break
    if resolved_open_chg:
        advisories.append(
            f"{resolved_open_chg} RESOLVED question(s) still linked to an OPEN change"
        )

    done_open_q = 0
    for q in questions.questions:
        if q.status != QuestionStatus.OPEN:
            continue
        for tid in q.related_todos:
            task = by_todo.get(tid)
            if task and task.status == TodoStatus.DONE:
                done_open_q += 1
                break
    if done_open_q:
        advisories.append(f"{done_open_q} DONE TODO(s) still linked to an OPEN factual question")

    return advisories
