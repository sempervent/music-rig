"""Render human-facing Markdown sections from canonical YAML."""

from __future__ import annotations

from pathlib import Path

from music_rig.models import (
    OpenQuestionsDocument,
    QuestionStatus,
    TodoDocument,
    TodoStatus,
    WishlistDocument,
)
from music_rig.current_projections import (
    render_alesis_section,
    render_patchbays_mermaid,
    render_patchbays_section,
    render_tascam_mermaid,
    render_tascam_section,
)
from music_rig import channel_state, patchbay_state
from music_rig.store import (
    CHANNEL_MAP_PATH,
    DIAGRAM_PATCHBAYS_PATH,
    DIAGRAM_TASCAM_PATH,
    DOCS_ALESIS_PATH,
    DOCS_PATCHBAYS_PATH,
    DOCS_QUESTIONS_PATH,
    DOCS_TASCAM_PATH,
    DOCS_TODO_PATH,
    DOCS_WISHLIST_PATH,
    PATCHBAYS_PATH,
    QUESTIONS_PATH,
    TODO_PATH,
    WISHLIST_PATH,
    StoreError,
    load_questions,
    load_todo,
    load_wishlist,
)

TODO_START = "<!-- rig:todo:start -->"
TODO_END = "<!-- rig:todo:end -->"
WISH_START = "<!-- rig:wishlist:start -->"
WISH_END = "<!-- rig:wishlist:end -->"
QUESTIONS_START = "<!-- rig:questions:start -->"
QUESTIONS_END = "<!-- rig:questions:end -->"
PATCHBAYS_START = "<!-- rig:patchbays:start -->"
PATCHBAYS_END = "<!-- rig:patchbays:end -->"
TASCAM_START = "<!-- rig:tascam:start -->"
TASCAM_END = "<!-- rig:tascam:end -->"
ALESIS_START = "<!-- rig:alesis:start -->"
ALESIS_END = "<!-- rig:alesis:end -->"

TODO_BANNER = (
    "<!-- GENERATED FROM data/todo.yaml BY `uv run rig render`. "
    "DO NOT EDIT THIS SECTION DIRECTLY. -->"
)
WISH_BANNER = (
    "<!-- GENERATED FROM data/wishlist.yaml BY `uv run rig render`. "
    "DO NOT EDIT THIS SECTION DIRECTLY. -->"
)
QUESTIONS_BANNER = (
    "<!-- GENERATED FROM data/open-questions.yaml BY `uv run rig render`. "
    "DO NOT EDIT THIS SECTION DIRECTLY. -->"
)


def _cell(value: str | None) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ").strip() or "—"


def _depends_cell(task) -> str:
    if not task.depends_on:
        return "—"
    parts = []
    for dep in task.depends_on:
        if task.depends_hint:
            parts.append(f"{dep} {task.depends_hint}")
        else:
            parts.append(dep)
    # If multiple deps with a single hint, join IDs then hint once when hint is "helpful"
    if task.depends_hint and len(task.depends_on) > 1:
        return ", ".join(task.depends_on) + f" {task.depends_hint}"
    if task.depends_hint and len(task.depends_on) == 1:
        return f"{task.depends_on[0]} {task.depends_hint}"
    return ", ".join(task.depends_on)


def render_todo_section(doc: TodoDocument) -> str:
    by_id = doc.task_map()
    lines: list[str] = [TODO_BANNER, ""]

    lines.append("## Next Session")
    lines.append("")
    lines.append(
        "At most three tasks. Prefer resolving physical uncertainty, "
        "reproducibility, and documentation drift — not purchases."
    )
    lines.append("")
    lines.append("| ID | Task | Why this session |")
    lines.append("|---|---|---|")
    for tid in doc.next_session:
        task = by_id[tid]
        why = task.next_session_why or ""
        lines.append(f"| {tid} | {_cell(task.task)} | {_cell(why)} |")
    lines.append("")

    waiting = [t for t in doc.tasks if t.status == TodoStatus.WAITING]
    lines.append("## Waiting / External")
    lines.append("")
    lines.append("| ID | Task | Waiting on |")
    lines.append("|---|---|---|")
    if waiting:
        for task in waiting:
            lines.append(
                f"| {task.id} | {_cell(task.task)} | {_cell(task.waiting_on)} |"
            )
    else:
        lines.append("| — | — | — |")
    lines.append("")

    active = [
        t
        for t in doc.tasks
        if t.status
        not in {TodoStatus.WAITING, TodoStatus.DONE, TodoStatus.CANCELLED}
    ]
    lines.append("## Active queue")
    lines.append("")
    lines.append(
        "| ID | Task | Area | Priority | Status | Depends On | "
        "Definition of Done | Notes |"
    )
    lines.append("|---|---|---|---|---|---|---|---|")
    for task in active:
        lines.append(
            "| {id} | {task} | {area} | {priority} | {status} | {deps} | {dod} | {notes} |".format(
                id=task.id,
                task=_cell(task.task),
                area=_cell(task.area),
                priority=task.priority.value,
                status=task.status.value,
                deps=_cell(_depends_cell(task)),
                dod=_cell(task.definition_of_done),
                notes=_cell(task.notes),
            )
        )
    lines.append("")

    done = [t for t in doc.tasks if t.status == TodoStatus.DONE]
    lines.append("## Done")
    lines.append("")
    lines.append("| ID | Task | Completed | Notes |")
    lines.append("|---|---|---|---|")
    if done:
        for task in done:
            lines.append(
                f"| {task.id} | {_cell(task.task)} | — | {_cell(task.notes)} |"
            )
    else:
        lines.append("| — | — | — | No TODO items marked done yet |")
    lines.append("")

    lines.append("## ID allocation")
    lines.append("")
    lines.append(f"Next free ID: **{doc.next_id()}**.")
    lines.append("")
    return "\n".join(lines)


def render_wishlist_section(doc: WishlistDocument) -> str:
    lines: list[str] = [WISH_BANNER, ""]
    lines.append("## Master table")
    lines.append("")
    lines.append(
        "| Item | Category | Problem / Capability | Priority | Status | "
        "Duplication | Cost | Friction | Likely Music Impact | Notes |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for item in doc.items:
        priority = item.priority.value if item.priority else "—"
        lines.append(
            "| {item} | {cat} | {prob} | {pri} | {status} | {dup} | {cost} | "
            "{friction} | {impact} | {notes} |".format(
                item=_cell(item.item),
                cat=_cell(item.category),
                prob=_cell(item.problem_capability),
                pri=priority,
                status=item.status.value,
                dup=_cell(item.duplication),
                cost=_cell(item.cost),
                friction=_cell(item.friction),
                impact=_cell(item.likely_music_impact),
                notes=_cell(item.notes),
            )
        )
    lines.append("")

    detailed = [i for i in doc.items if i.details.strip() or i.todo_refs]
    if detailed:
        lines.append("## Detail notes")
        lines.append("")
        for item in detailed:
            lines.append(f"### {item.item}")
            lines.append("")
            if item.todo_refs:
                lines.append("Related TODOs: " + ", ".join(item.todo_refs))
                lines.append("")
            if item.details.strip():
                lines.append(item.details.rstrip())
                lines.append("")
    return "\n".join(lines)


def render_questions_section(doc: OpenQuestionsDocument) -> str:
    lines: list[str] = [QUESTIONS_BANNER, ""]
    open_items = [q for q in doc.questions if q.status == QuestionStatus.OPEN]
    deferred = [q for q in doc.questions if q.status == QuestionStatus.DEFERRED]
    resolved = [q for q in doc.questions if q.status == QuestionStatus.RESOLVED]

    def _table(items: list, title: str) -> None:
        lines.append(f"## {title}")
        lines.append("")
        lines.append("| ID | Area | Question | Related TODOs | Related Changes |")
        lines.append("|---|---|---|---|---|")
        if not items:
            lines.append("| — | — | — | — | — |")
        else:
            for q in items:
                lines.append(
                    "| {id} | {area} | {question} | {todos} | {chgs} |".format(
                        id=q.id,
                        area=_cell(q.area),
                        question=_cell(q.question),
                        todos=_cell(", ".join(q.related_todos)),
                        chgs=_cell(", ".join(q.related_changes)),
                    )
                )
        lines.append("")

    _table(open_items, "Open")
    _table(deferred, "Deferred")
    _table(resolved, "Resolved")

    answered = [
        q
        for q in doc.questions
        if q.answer.strip() or q.notes.strip()
    ]
    if answered:
        lines.append("## Answers and notes")
        lines.append("")
        for q in answered:
            lines.append(f"### {q.id} — {q.status.value}")
            lines.append("")
            lines.append(q.question)
            lines.append("")
            if q.answer.strip():
                lines.append(f"**Answer:** {q.answer.strip()}")
                lines.append("")
            if q.notes.strip():
                lines.append(f"**Notes:** {q.notes.strip()}")
                lines.append("")
            if q.resolved_at is not None:
                lines.append(f"**Resolved at:** {q.resolved_at.isoformat()}")
                lines.append("")

    lines.append("## ID allocation")
    lines.append("")
    lines.append(f"Next free ID: **{doc.next_id()}**.")
    lines.append("")
    return "\n".join(lines)


def _replace_region(text: str, start: str, end: str, body: str) -> str:
    if start not in text or end not in text:
        raise StoreError(
            f"Missing generation markers {start!r} / {end!r} in Markdown file"
        )
    before, rest = text.split(start, 1)
    _, after = rest.split(end, 1)
    # Ensure body ends with single newline before end marker
    body = body.rstrip() + "\n"
    return f"{before}{start}\n{body}{end}{after}"


def apply_todo_render(markdown: str, doc: TodoDocument) -> str:
    return _replace_region(markdown, TODO_START, TODO_END, render_todo_section(doc))


def apply_wishlist_render(markdown: str, doc: WishlistDocument) -> str:
    return _replace_region(
        markdown, WISH_START, WISH_END, render_wishlist_section(doc)
    )


def apply_questions_render(markdown: str, doc: OpenQuestionsDocument) -> str:
    return _replace_region(
        markdown, QUESTIONS_START, QUESTIONS_END, render_questions_section(doc)
    )


def apply_patchbays_render(markdown: str, data: dict) -> str:
    return _replace_region(
        markdown, PATCHBAYS_START, PATCHBAYS_END, render_patchbays_section(data)
    )


def apply_tascam_render(markdown: str, data: dict) -> str:
    return _replace_region(
        markdown, TASCAM_START, TASCAM_END, render_tascam_section(data)
    )


def apply_alesis_render(markdown: str, data: dict) -> str:
    return _replace_region(
        markdown, ALESIS_START, ALESIS_END, render_alesis_section(data)
    )


def _write_if_changed(
    path: Path,
    new_text: str,
    *,
    display_name: str,
    write: bool,
    messages: list[str],
) -> bool:
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    if new_text == old:
        return False
    messages.append(display_name)
    if write:
        path.write_text(new_text, encoding="utf-8")
    return True


def render_docs(
    *,
    todo_path: Path | None = None,
    wishlist_path: Path | None = None,
    questions_path: Path | None = None,
    patchbays_path: Path | None = None,
    channel_map_path: Path | None = None,
    docs_todo: Path | None = None,
    docs_wishlist: Path | None = None,
    docs_questions: Path | None = None,
    docs_patchbays: Path | None = None,
    docs_tascam: Path | None = None,
    docs_alesis: Path | None = None,
    diagram_patchbays: Path | None = None,
    diagram_tascam: Path | None = None,
    write: bool = True,
) -> tuple[bool, list[str]]:
    """Render generated sections. Returns (changed, messages)."""
    using_custom_todo = todo_path is not None and todo_path != TODO_PATH
    using_custom_wish = wishlist_path is not None and wishlist_path != WISHLIST_PATH
    using_custom_q = questions_path is not None and questions_path != QUESTIONS_PATH
    using_custom_pb = patchbays_path is not None and patchbays_path != PATCHBAYS_PATH
    using_custom_ch = (
        channel_map_path is not None and channel_map_path != CHANNEL_MAP_PATH
    )
    if using_custom_todo and docs_todo is None:
        raise StoreError(
            "docs_todo path is required when rendering with a custom todo_path"
        )
    if using_custom_wish and docs_wishlist is None:
        raise StoreError(
            "docs_wishlist path is required when rendering with a custom wishlist_path"
        )
    if using_custom_q and docs_questions is None:
        raise StoreError(
            "docs_questions path is required when rendering with a custom questions_path"
        )
    if using_custom_pb and docs_patchbays is None:
        raise StoreError(
            "docs_patchbays path is required when rendering with a custom patchbays_path"
        )
    if using_custom_ch and (docs_tascam is None or docs_alesis is None):
        raise StoreError(
            "docs_tascam and docs_alesis are required when rendering with a custom channel_map_path"
        )

    todo = load_todo(todo_path)
    wishlist = load_wishlist(wishlist_path)
    questions = load_questions(questions_path)

    todo_md_path = docs_todo or DOCS_TODO_PATH
    wish_md_path = docs_wishlist or DOCS_WISHLIST_PATH
    q_md_path = docs_questions or DOCS_QUESTIONS_PATH

    messages: list[str] = []
    changed = False

    pairs = [
        (todo_md_path, apply_todo_render(todo_md_path.read_text(encoding="utf-8"), todo), "docs/todo.md"),
        (
            wish_md_path,
            apply_wishlist_render(wish_md_path.read_text(encoding="utf-8"), wishlist),
            "docs/wishlist.md",
        ),
        (
            q_md_path,
            apply_questions_render(q_md_path.read_text(encoding="utf-8"), questions),
            "docs/open-questions.md",
        ),
    ]
    for path, new_text, display in pairs:
        if _write_if_changed(
            path, new_text, display_name=display, write=write, messages=messages
        ):
            changed = True

    # Skip CURRENT projections when only planning fixtures are in play.
    planning_fixture_only = (
        (using_custom_todo or using_custom_wish or using_custom_q)
        and not using_custom_pb
        and not using_custom_ch
    )
    if planning_fixture_only:
        return changed, messages

    patchbays = patchbay_state.load_raw(patchbays_path)
    channels = channel_state.load_raw(channel_map_path)
    pb_md_path = docs_patchbays or DOCS_PATCHBAYS_PATH
    tascam_md_path = docs_tascam or DOCS_TASCAM_PATH
    alesis_md_path = docs_alesis or DOCS_ALESIS_PATH
    pb_mmd_path = diagram_patchbays or DIAGRAM_PATCHBAYS_PATH
    tascam_mmd_path = diagram_tascam or DIAGRAM_TASCAM_PATH

    current_pairs = [
        (
            pb_md_path,
            apply_patchbays_render(pb_md_path.read_text(encoding="utf-8"), patchbays),
            "docs/patchbays.md",
        ),
        (
            tascam_md_path,
            apply_tascam_render(tascam_md_path.read_text(encoding="utf-8"), channels),
            "docs/tascam-channel-map.md",
        ),
        (
            alesis_md_path,
            apply_alesis_render(alesis_md_path.read_text(encoding="utf-8"), channels),
            "docs/alesis-mixer-map.md",
        ),
    ]
    for path, new_text, display in current_pairs:
        if _write_if_changed(
            path, new_text, display_name=display, write=write, messages=messages
        ):
            changed = True

    if not using_custom_pb or diagram_patchbays is not None:
        pb_mmd = render_patchbays_mermaid(patchbays)
        if _write_if_changed(
            pb_mmd_path,
            pb_mmd,
            display_name="diagrams/patchbays.mmd",
            write=write,
            messages=messages,
        ):
            changed = True
    if not using_custom_ch or diagram_tascam is not None:
        t_mmd = render_tascam_mermaid(channels)
        if _write_if_changed(
            tascam_mmd_path,
            t_mmd,
            display_name="diagrams/tascam-channel-map.mmd",
            write=write,
            messages=messages,
        ):
            changed = True

    return changed, messages


def check_render_sync(
    *,
    todo_path: Path | None = None,
    wishlist_path: Path | None = None,
    questions_path: Path | None = None,
    patchbays_path: Path | None = None,
    channel_map_path: Path | None = None,
    docs_todo: Path | None = None,
    docs_wishlist: Path | None = None,
    docs_questions: Path | None = None,
    docs_patchbays: Path | None = None,
    docs_tascam: Path | None = None,
    docs_alesis: Path | None = None,
    diagram_patchbays: Path | None = None,
    diagram_tascam: Path | None = None,
) -> list[str]:
    """Return list of stale doc paths. Empty if synchronized."""
    _, messages = render_docs(
        todo_path=todo_path,
        wishlist_path=wishlist_path,
        questions_path=questions_path,
        patchbays_path=patchbays_path,
        channel_map_path=channel_map_path,
        docs_todo=docs_todo,
        docs_wishlist=docs_wishlist,
        docs_questions=docs_questions,
        docs_patchbays=docs_patchbays,
        docs_tascam=docs_tascam,
        docs_alesis=docs_alesis,
        diagram_patchbays=diagram_patchbays,
        diagram_tascam=diagram_tascam,
        write=False,
    )
    return messages
