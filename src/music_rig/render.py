"""Render human-facing Markdown sections from canonical YAML."""

from __future__ import annotations

from pathlib import Path

from music_rig.models import TodoDocument, TodoStatus, WishlistDocument
from music_rig.store import (
    DOCS_TODO_PATH,
    DOCS_WISHLIST_PATH,
    StoreError,
    load_todo,
    load_wishlist,
)

TODO_START = "<!-- rig:todo:start -->"
TODO_END = "<!-- rig:todo:end -->"
WISH_START = "<!-- rig:wishlist:start -->"
WISH_END = "<!-- rig:wishlist:end -->"

TODO_BANNER = (
    "<!-- GENERATED FROM data/todo.yaml BY `uv run rig render`. "
    "DO NOT EDIT THIS SECTION DIRECTLY. -->"
)
WISH_BANNER = (
    "<!-- GENERATED FROM data/wishlist.yaml BY `uv run rig render`. "
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

    detailed = [i for i in doc.items if i.details.strip()]
    if detailed:
        lines.append("## Detail notes")
        lines.append("")
        for item in detailed:
            lines.append(f"### {item.item}")
            lines.append("")
            lines.append(item.details.rstrip())
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


def render_docs(
    *,
    todo_path: Path | None = None,
    wishlist_path: Path | None = None,
    docs_todo: Path | None = None,
    docs_wishlist: Path | None = None,
    write: bool = True,
) -> tuple[bool, list[str]]:
    """Render generated sections. Returns (changed, messages)."""
    todo = load_todo(todo_path)
    wishlist = load_wishlist(wishlist_path)
    todo_md_path = docs_todo or DOCS_TODO_PATH
    wish_md_path = docs_wishlist or DOCS_WISHLIST_PATH

    todo_src = todo_md_path.read_text(encoding="utf-8")
    wish_src = wish_md_path.read_text(encoding="utf-8")
    todo_new = apply_todo_render(todo_src, todo)
    wish_new = apply_wishlist_render(wish_src, wishlist)

    messages: list[str] = []
    changed = False
    if todo_new != todo_src:
        changed = True
        messages.append("docs/todo.md")
        if write:
            todo_md_path.write_text(todo_new, encoding="utf-8")
    if wish_new != wish_src:
        changed = True
        messages.append("docs/wishlist.md")
        if write:
            wish_md_path.write_text(wish_new, encoding="utf-8")
    return changed, messages


def check_render_sync(
    *,
    todo_path: Path | None = None,
    wishlist_path: Path | None = None,
    docs_todo: Path | None = None,
    docs_wishlist: Path | None = None,
) -> list[str]:
    """Return list of stale doc paths (as display names). Empty if synchronized."""
    todo = load_todo(todo_path)
    wishlist = load_wishlist(wishlist_path)
    todo_md_path = docs_todo or DOCS_TODO_PATH
    wish_md_path = docs_wishlist or DOCS_WISHLIST_PATH

    stale: list[str] = []
    todo_src = todo_md_path.read_text(encoding="utf-8")
    if apply_todo_render(todo_src, todo) != todo_src:
        stale.append("docs/todo.md")
    wish_src = wish_md_path.read_text(encoding="utf-8")
    if apply_wishlist_render(wish_src, wishlist) != wish_src:
        stale.append("docs/wishlist.md")
    return stale
