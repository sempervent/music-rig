"""Typer CLI entrypoint: `uv run rig ...`."""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from music_rig.checks import run_checks
from music_rig import (
    change_service,
    channel_state,
    current_service,
    inbox_service,
    patchbay_state,
    question_service,
    routing_state,
    session_service,
    todo_service,
    wishlist_service,
)
from music_rig.current_projections import format_current_preview
from music_rig.doctor import build_doctor_text
from music_rig.inbox_service import default_clock
from music_rig.models import (
    ChangeStatus,
    InboxStatus,
    TodoPriority,
    TodoStatus,
    TodoTask,
    WishPriority,
    WishStatus,
    WishlistItem,
)
from music_rig.now_service import format_now, recommend_now
from music_rig.reconcile import (
    build_reconcile_summary,
    format_reconcile_change,
    format_reconcile_question,
)
from music_rig.render import check_render_sync, render_docs
from music_rig import rig_views
from music_rig.status import build_status_text
from music_rig.store import StoreError, load_inbox, load_todo, load_wishlist

console = Console(stderr=False)
err_console = Console(stderr=True)

app = typer.Typer(
    name="rig",
    help="Music-rig planning and studio-ops CLI. Canonical data lives in data/*.yaml.",
    no_args_is_help=True,
)
todo_app = typer.Typer(help="Accepted work queue (data/todo.yaml).", no_args_is_help=True)
wish_app = typer.Typer(
    help="Speculative wishlist (data/wishlist.yaml).", no_args_is_help=True
)
next_app = typer.Typer(help="Next Session queue (max 3).", no_args_is_help=True)
inbox_app = typer.Typer(help="Low-friction capture inbox.", no_args_is_help=True)
session_app = typer.Typer(help="Studio session logging.", no_args_is_help=True)
changes_app = typer.Typer(help="Structured change records.", no_args_is_help=True)
question_app = typer.Typer(
    help="Unresolved factual questions (data/open-questions.yaml).",
    no_args_is_help=True,
)
reconcile_app = typer.Typer(
    help="Guided reconciliation of OPEN changes/questions.",
    invoke_without_command=True,
    no_args_is_help=False,
)
path_app = typer.Typer(help="Read-only CURRENT named paths.", no_args_is_help=True)
current_app = typer.Typer(
    help="Modify authoritative CURRENT state (typed, previewed).",
    no_args_is_help=True,
)
current_pb_app = typer.Typer(
    help="CURRENT patchbay mutations (data/patchbays.yaml).",
    no_args_is_help=True,
)
current_ch_app = typer.Typer(
    help="CURRENT channel-map mutations (data/channel-map.yaml).",
    no_args_is_help=True,
)
current_path_app = typer.Typer(
    help="CURRENT named-path mutations (data/routing.yaml).",
    no_args_is_help=True,
)
app.add_typer(todo_app, name="todo")
app.add_typer(wish_app, name="wish")
todo_app.add_typer(next_app, name="next")
app.add_typer(inbox_app, name="inbox")
app.add_typer(session_app, name="session")
app.add_typer(changes_app, name="changes")
app.add_typer(question_app, name="question")
app.add_typer(reconcile_app, name="reconcile")
app.add_typer(path_app, name="path")
app.add_typer(current_app, name="current")
current_app.add_typer(current_pb_app, name="patchbay")
current_app.add_typer(current_ch_app, name="channels")
current_app.add_typer(current_path_app, name="path")


def _fail(message: str, code: int = 1) -> None:
    err_console.print(f"[red]Error:[/red] {message}")
    raise typer.Exit(code)


def _parse_priority(raw: str) -> TodoPriority:
    try:
        return TodoPriority(raw.strip().upper())
    except ValueError:
        _fail(f"Invalid priority {raw!r}. Use P0, P1, P2, or P3.")
        raise


def _parse_status(raw: str) -> TodoStatus:
    cleaned = " ".join(raw.strip().upper().split())
    try:
        return TodoStatus(cleaned)
    except ValueError:
        _fail(
            f"Invalid status {raw!r}. Use READY, BLOCKED, IN PROGRESS, "
            "WAITING, DONE, DEFERRED, or CANCELLED."
        )
        raise


def _parse_wish_priority(raw: str) -> WishPriority | None:
    cleaned = raw.strip().upper()
    if cleaned in {"", "—", "-", "NONE", "NULL"}:
        return None
    try:
        return WishPriority(cleaned)
    except ValueError:
        _fail(f"Invalid wishlist priority {raw!r}. Use P0–P3 or —.")
        raise


def _parse_wish_status(raw: str) -> WishStatus:
    cleaned = " ".join(raw.strip().upper().split())
    try:
        return WishStatus(cleaned)
    except ValueError:
        _fail(f"Invalid wishlist status {raw!r}.")
        raise


def _parse_deps(raw: str) -> list[str]:
    if not raw.strip():
        return []
    parts = [p.strip().upper() for p in raw.replace(";", ",").split(",")]
    return [p for p in parts if p]


def _prompt_todo_fields(
    *,
    default_task: str = "",
    default_area: str = "Studio ops",
    default_priority: str = "P2",
    default_status: str = "READY",
    default_dod: str = "",
    default_notes: str = "",
    default_deps: str = "",
) -> TodoTask:
    doc = load_todo()
    task = typer.prompt("Task", default=default_task)
    area = typer.prompt("Area", default=default_area)
    priority = typer.prompt("Priority", default=default_priority)
    status = typer.prompt("Status", default=default_status)
    depends_on = typer.prompt("Depends on (comma separated)", default=default_deps)
    definition_of_done = typer.prompt("Definition of Done", default=default_dod)
    notes = typer.prompt("Notes", default=default_notes)
    try:
        return TodoTask(
            id=doc.next_id(),
            task=task.strip(),
            area=area.strip(),
            priority=_parse_priority(priority),
            status=_parse_status(status),
            depends_on=_parse_deps(depends_on),
            definition_of_done=definition_of_done.strip() or "TBD",
            notes=(notes or "").strip(),
        )
    except Exception as exc:
        _fail(str(exc))
        raise


# --- status ---


@app.command("status")
def status_cmd() -> None:
    """Concise read-only planning dashboard."""
    try:
        console.print(build_status_text().rstrip())
    except StoreError as exc:
        _fail(str(exc))


# --- todo list/show/add ---


@todo_app.command("list")
def todo_list(
    status: Optional[str] = typer.Option(None, "--status"),
    priority: Optional[str] = typer.Option(None, "--priority"),
    all_items: bool = typer.Option(False, "--all"),
) -> None:
    try:
        doc = load_todo()
    except StoreError as exc:
        _fail(str(exc))
    status_filter = _parse_status(status) if status else None
    priority_filter = _parse_priority(priority) if priority else None
    table = Table(title="TODO")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Priority", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Area")
    table.add_column("Task")
    rows = 0
    for task in doc.tasks:
        if not all_items and task.status in {TodoStatus.DONE, TodoStatus.CANCELLED}:
            continue
        if status_filter and task.status != status_filter:
            continue
        if priority_filter and task.priority != priority_filter:
            continue
        table.add_row(
            task.id, task.priority.value, task.status.value, task.area, task.task
        )
        rows += 1
    console.print(table)
    console.print(f"[dim]{rows} task(s)[/dim]")


@todo_app.command("show")
def todo_show(todo_id: str) -> None:
    try:
        doc = load_todo()
        task = todo_service.get_task(doc, todo_id)
    except StoreError as exc:
        _fail(str(exc))
    in_next = task.id in doc.next_session
    console.print(f"[bold]{task.id}[/bold] — {task.task}")
    console.print(f"Area: {task.area}")
    console.print(f"Priority: {task.priority.value}")
    console.print(f"Status: {task.status.value}")
    deps = ", ".join(task.depends_on) if task.depends_on else "—"
    if task.depends_hint:
        deps = f"{deps} ({task.depends_hint})"
    console.print(f"Depends on: {deps}")
    console.print(f"Definition of Done: {task.definition_of_done}")
    console.print(f"Notes: {task.notes or '—'}")
    if task.waiting_on:
        console.print(f"Waiting on: {task.waiting_on}")
    console.print(f"Next Session: {'yes' if in_next else 'no'}")
    if task.next_session_why:
        console.print(f"Next Session why: {task.next_session_why}")


@todo_app.command("add")
def todo_add(no_render: bool = typer.Option(False, "--no-render")) -> None:
    """Create a TODO with the next RIG ID. Writes YAML then renders unless --no-render."""
    try:
        new_task = _prompt_todo_fields()
        todo_service.add_todo(new_task, render=not no_render)
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"Created [bold]{new_task.id}[/bold]")


def _lifecycle(
    todo_id: str,
    status: TodoStatus,
    *,
    remove_from_next: bool,
    no_render: bool,
) -> None:
    try:
        task, changed, doc = todo_service.set_todo_status(
            todo_id,
            status,
            remove_from_next=remove_from_next,
            render=not no_render,
        )
    except StoreError as exc:
        _fail(str(exc))
    if not changed:
        console.print(f"{task.id} already {task.status.value}")
    else:
        console.print(f"{task.id} -> {task.status.value}")
    if remove_from_next:
        console.print(f"Next Session now contains {len(doc.next_session)} task(s).")


@todo_app.command("start")
def todo_start(
    todo_id: str,
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    """Mark TODO IN PROGRESS (keeps Next Session membership)."""
    _lifecycle(todo_id, TodoStatus.IN_PROGRESS, remove_from_next=False, no_render=no_render)


@todo_app.command("ready")
def todo_ready(
    todo_id: str,
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    """Mark TODO READY (does not auto-add to Next Session)."""
    _lifecycle(todo_id, TodoStatus.READY, remove_from_next=False, no_render=no_render)


@todo_app.command("done")
def todo_done(
    todo_id: str,
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    """Mark TODO DONE and remove from Next Session if present."""
    _lifecycle(todo_id, TodoStatus.DONE, remove_from_next=True, no_render=no_render)


@todo_app.command("defer")
def todo_defer(
    todo_id: str,
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    """Mark TODO DEFERRED and remove from Next Session if present."""
    _lifecycle(todo_id, TodoStatus.DEFERRED, remove_from_next=True, no_render=no_render)


@todo_app.command("cancel")
def todo_cancel(
    todo_id: str,
    yes: bool = typer.Option(False, "--yes"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    """Mark TODO CANCELLED and remove from Next Session if present."""
    try:
        doc = load_todo()
        task = todo_service.get_task(doc, todo_id)
    except StoreError as exc:
        _fail(str(exc))
    if not yes:
        if not typer.confirm(f'Cancel {task.id} "{task.task}"?', default=False):
            raise typer.Abort()
    _lifecycle(todo_id, TodoStatus.CANCELLED, remove_from_next=True, no_render=no_render)


@todo_app.command("status")
def todo_status_cmd(
    todo_id: str,
    status: str,
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    """Generic status setter: rig todo status RIG-001 READY"""
    parsed = _parse_status(status)
    remove = parsed in {TodoStatus.DONE, TodoStatus.DEFERRED, TodoStatus.CANCELLED}
    _lifecycle(todo_id, parsed, remove_from_next=remove, no_render=no_render)


# --- next session ---


@next_app.command("list")
def next_list_cmd() -> None:
    try:
        tasks = todo_service.next_list()
    except StoreError as exc:
        _fail(str(exc))
    console.print("[bold]NEXT SESSION[/bold]")
    if not tasks:
        console.print("(empty)")
        return
    for i, task in enumerate(tasks, start=1):
        console.print(f"{i}. {task.id}  {task.priority.value}  {task.task}")


@next_app.command("add")
def next_add_cmd(
    todo_id: str,
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        doc = todo_service.next_add(todo_id, render=not no_render)
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"Added {todo_id.upper()} to Next Session ({len(doc.next_session)}/3)")


@next_app.command("remove")
def next_remove_cmd(
    todo_id: str,
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        doc = todo_service.next_remove(todo_id, render=not no_render)
    except StoreError as exc:
        _fail(str(exc))
    console.print(
        f"Removed {todo_id.upper()} from Next Session ({len(doc.next_session)}/3)"
    )


@next_app.command("set")
def next_set_cmd(
    ids: list[str] = typer.Argument(..., help="Up to three RIG IDs in order"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        doc = todo_service.next_set(ids, render=not no_render)
    except StoreError as exc:
        _fail(str(exc))
    console.print("Next Session set to: " + ", ".join(doc.next_session))


@next_app.command("clear")
def next_clear_cmd(no_render: bool = typer.Option(False, "--no-render")) -> None:
    try:
        todo_service.next_clear(render=not no_render)
    except StoreError as exc:
        _fail(str(exc))
    console.print("Next Session cleared.")


# --- wishlist ---


@wish_app.command("list")
def wish_list(
    status: Optional[str] = typer.Option(None, "--status"),
    priority: Optional[str] = typer.Option(None, "--priority"),
) -> None:
    try:
        doc = load_wishlist()
    except StoreError as exc:
        _fail(str(exc))
    status_filter = _parse_wish_status(status) if status else None
    priority_filter = _parse_wish_priority(priority) if priority else None
    table = Table(title="Wishlist")
    table.add_column("Item")
    table.add_column("Priority", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Category")
    table.add_column("Likely Music Impact")
    count = 0
    for item in doc.items:
        if status_filter and item.status != status_filter:
            continue
        if priority is not None and item.priority != priority_filter:
            continue
        table.add_row(
            item.item,
            item.priority.value if item.priority else "—",
            item.status.value,
            item.category,
            item.likely_music_impact or "—",
        )
        count += 1
    console.print(table)
    console.print(f"[dim]{count} item(s)[/dim]")


@wish_app.command("show")
def wish_show(name: str) -> None:
    try:
        doc = load_wishlist()
        item = wishlist_service.get_item(doc, name)
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"[bold]{item.item}[/bold]")
    console.print(f"Category: {item.category}")
    console.print(f"Problem / Capability: {item.problem_capability}")
    console.print(f"Priority: {item.priority.value if item.priority else '—'}")
    console.print(f"Status: {item.status.value}")
    console.print(f"Duplication: {item.duplication or '—'}")
    console.print(f"Cost: {item.cost or '—'}")
    console.print(f"Friction: {item.friction or '—'}")
    console.print(f"Likely Music Impact: {item.likely_music_impact or '—'}")
    console.print(f"Notes: {item.notes or '—'}")
    if item.todo_refs:
        console.print("Related TODOs: " + ", ".join(item.todo_refs))
    if item.details.strip():
        console.print("\n[bold]Details[/bold]")
        console.print(item.details)


@wish_app.command("add")
def wish_add(no_render: bool = typer.Option(False, "--no-render")) -> None:
    item_name = typer.prompt("Item")
    category = typer.prompt("Category")
    problem = typer.prompt("Problem / Capability")
    priority = typer.prompt("Priority", default="P2")
    status = typer.prompt("Status", default="IDEA")
    duplication = typer.prompt("Duplication", default="")
    cost = typer.prompt("Cost", default="UNKNOWN")
    friction = typer.prompt("Friction", default="")
    impact = typer.prompt("Likely Music Impact", default="")
    notes = typer.prompt("Notes", default="")
    try:
        new_item = WishlistItem(
            item=item_name.strip(),
            category=category.strip(),
            problem_capability=problem.strip(),
            priority=_parse_wish_priority(priority),
            status=_parse_wish_status(status),
            duplication=duplication.strip(),
            cost=cost.strip(),
            friction=friction.strip(),
            likely_music_impact=impact.strip(),
            notes=notes.strip(),
        )
        wishlist_service.add_wish(new_item, render=not no_render)
    except (StoreError, Exception) as exc:
        _fail(str(exc))
    console.print(f'Created wishlist item [bold]{new_item.item}[/bold]')


def _wish_status(
    name: str, status: WishStatus, *, no_render: bool, confirm: bool = False, yes: bool = False
) -> None:
    if confirm and not yes:
        if not typer.confirm(f'Set "{name}" to {status.value}?', default=False):
            raise typer.Abort()
    try:
        item, changed = wishlist_service.set_wish_status(
            name, status, render=not no_render
        )
    except StoreError as exc:
        _fail(str(exc))
    if not changed:
        console.print(f"{item.item} already {item.status.value}")
    else:
        console.print(f"{item.item} -> {item.status.value}")


@wish_app.command("research")
def wish_research(name: str, no_render: bool = typer.Option(False, "--no-render")) -> None:
    _wish_status(name, WishStatus.RESEARCH, no_render=no_render)


@wish_app.command("defer")
def wish_defer(name: str, no_render: bool = typer.Option(False, "--no-render")) -> None:
    _wish_status(name, WishStatus.DEFERRED, no_render=no_render)


@wish_app.command("reject")
def wish_reject(
    name: str,
    yes: bool = typer.Option(False, "--yes"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    _wish_status(name, WishStatus.REJECTED, no_render=no_render, confirm=True, yes=yes)


@wish_app.command("status")
def wish_status_cmd(
    name: str,
    status: str,
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    parsed = _parse_wish_status(status)
    confirm = parsed == WishStatus.REJECTED
    _wish_status(name, parsed, no_render=no_render, confirm=confirm, yes=False)


@wish_app.command("promote")
def wish_promote(
    name: str,
    wish_status: Optional[str] = typer.Option(
        None, "--wish-status", help="Optional new wishlist status after promotion"
    ),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    """Create a TODO from a wishlist item (accepted work, not purchase approval)."""
    try:
        doc = load_wishlist()
        item = wishlist_service.get_item(doc, name)
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"[bold]{item.item}[/bold]")
    console.print(f"Priority: {item.priority.value if item.priority else '—'}")
    console.print(f"Status: {item.status.value}")
    console.print(f"Problem: {item.problem_capability}")
    console.print("")
    default_pri = item.priority.value if item.priority else "P2"
    new_task = _prompt_todo_fields(
        default_task=item.item,
        default_area=item.category,
        default_priority=default_pri,
        default_status="READY",
        default_dod="",
        default_notes=f"Promoted from wishlist: {item.item}",
    )
    keep = True
    new_status = None
    if wish_status:
        new_status = _parse_wish_status(wish_status)
        keep = False
    else:
        keep = typer.confirm(
            f"Keep wishlist status as {item.status.value}?", default=True
        )
        if not keep:
            new_status = _parse_wish_status(
                typer.prompt("New wishlist status", default=item.status.value)
            )
    try:
        updated, created = wishlist_service.promote_wish(
            name,
            new_task,
            keep_wish_status=keep,
            new_wish_status=new_status,
            render=not no_render,
        )
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"Created [bold]{created.id}[/bold] from wishlist '{updated.item}'")
    if updated.todo_refs:
        console.print("Related TODOs: " + ", ".join(updated.todo_refs))


# --- capture / inbox ---


@app.command("capture")
def capture_cmd(
    text: Optional[str] = typer.Argument(None, help="Observation text"),
    as_type: str = typer.Option(
        "inbox", "--as", help="inbox (default), todo, or wish"
    ),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    """Zero-friction capture. Default writes an OPEN inbox item."""
    body = text if text is not None else typer.prompt("Capture")
    kind = as_type.strip().lower()
    if kind == "inbox":
        try:
            item = inbox_service.capture_text(body)
        except StoreError as exc:
            _fail(str(exc))
        console.print(f"Captured [bold]{item.id}[/bold]")
        return
    if kind == "todo":
        new_task = _prompt_todo_fields(default_task=body.strip())
        try:
            todo_service.add_todo(new_task, render=not no_render)
        except StoreError as exc:
            _fail(str(exc))
        console.print(f"Created [bold]{new_task.id}[/bold]")
        return
    if kind == "wish":
        try:
            new_item = WishlistItem(
                item=typer.prompt("Item", default=body.strip()[:60]),
                category=typer.prompt("Category", default="Uncategorized"),
                problem_capability=typer.prompt("Problem / Capability", default=body.strip()),
                priority=_parse_wish_priority(typer.prompt("Priority", default="P2")),
                status=_parse_wish_status(typer.prompt("Status", default="IDEA")),
            )
            wishlist_service.add_wish(new_item, render=not no_render)
        except (StoreError, Exception) as exc:
            _fail(str(exc))
        console.print(f'Created wishlist item [bold]{new_item.item}[/bold]')
        return
    _fail("--as must be inbox, todo, or wish")


@inbox_app.command("list")
def inbox_list(all_items: bool = typer.Option(False, "--all")) -> None:
    try:
        doc = load_inbox()
    except StoreError as exc:
        _fail(str(exc))
    console.print("[bold]INBOX[/bold]")
    shown = 0
    for item in doc.items:
        if not all_items and item.status != InboxStatus.OPEN:
            continue
        day = item.created_at.date().isoformat()
        console.print(f"{item.id}  {day}  {item.text}")
        shown += 1
    if shown == 0:
        console.print("(empty)")


@inbox_app.command("show")
def inbox_show(cap_id: str) -> None:
    try:
        item = inbox_service.get_capture(cap_id)
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"[bold]{item.id}[/bold]  {item.status.value}")
    console.print(f"Created: {item.created_at.isoformat()}")
    console.print(item.text)
    if item.notes:
        console.print(f"Notes: {item.notes}")


@inbox_app.command("dismiss")
def inbox_dismiss(
    cap_id: str,
    yes: bool = typer.Option(False, "--yes"),
) -> None:
    try:
        item = inbox_service.get_capture(cap_id)
    except StoreError as exc:
        _fail(str(exc))
    if not yes:
        if not typer.confirm(f"Dismiss {item.id}?", default=False):
            raise typer.Abort()
    try:
        updated, changed = inbox_service.dismiss_capture(cap_id)
    except StoreError as exc:
        _fail(str(exc))
    if not changed:
        console.print(f"{updated.id} already DISMISSED")
    else:
        console.print(f"{updated.id} -> DISMISSED")


@inbox_app.command("triage")
def inbox_triage(
    cap_id: str,
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        item = inbox_service.get_capture(cap_id)
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"[bold]{item.id}[/bold]")
    console.print(f'"{item.text}"')
    console.print("Convert to:")
    console.print("  1. TODO")
    console.print("  2. Wishlist")
    console.print("  3. Dismiss")
    console.print("  4. Leave open")
    choice = typer.prompt("Choice", default="4")
    if choice.strip() == "4":
        console.print("Left open.")
        return
    if choice.strip() == "3":
        inbox_service.dismiss_capture(cap_id)
        console.print(f"{item.id} -> DISMISSED")
        return
    if choice.strip() == "1":
        new_task = _prompt_todo_fields(default_task=item.text)
        try:
            cap, created = inbox_service.triage_to_todo(
                cap_id, new_task, render=not no_render
            )
        except StoreError as exc:
            _fail(str(exc))
        console.print(f"{cap.id} TRIAGED -> created {created.id}")
        return
    if choice.strip() == "2":
        try:
            new_item = WishlistItem(
                item=typer.prompt("Item", default=item.text[:60]),
                category=typer.prompt("Category", default="Uncategorized"),
                problem_capability=typer.prompt(
                    "Problem / Capability", default=item.text
                ),
                priority=_parse_wish_priority(typer.prompt("Priority", default="P2")),
                status=_parse_wish_status(typer.prompt("Status", default="IDEA")),
            )
            cap, created = inbox_service.triage_to_wish(
                cap_id, new_item, render=not no_render
            )
        except (StoreError, Exception) as exc:
            _fail(str(exc))
        console.print(f"{cap.id} TRIAGED -> wishlist '{created.item}'")
        return
    _fail("Invalid choice.")


# --- render / check / doctor / studio views ---


@app.command("channels")
def channels_cmd(
    device: Optional[str] = typer.Option(None, "--device", help="tascam|alesis"),
) -> None:
    try:
        console.print(rig_views.format_channels(device=device).rstrip())
    except StoreError as exc:
        _fail(str(exc))


@app.command("patchbay")
def patchbay_cmd(
    target: Optional[str] = typer.Argument(
        None, help="Patchbay id (e.g. PB-B), or 'list'"
    ),
    unknown: bool = typer.Option(False, "--unknown"),
    all_jacks: bool = typer.Option(False, "--all"),
) -> None:
    """Read-only patchbay views from data/patchbays.yaml."""
    if target is None or target.strip().lower() == "list":
        console.print(rig_views.format_patchbay_list().rstrip())
        return
    try:
        console.print(
            rig_views.format_patchbay(
                target, unknown_only=unknown, show_all_jacks=all_jacks
            ).rstrip()
        )
    except StoreError as exc:
        _fail(str(exc))


@path_app.command("list")
def path_list_cmd() -> None:
    try:
        console.print(rig_views.format_path_list().rstrip())
    except StoreError as exc:
        _fail(str(exc))


@path_app.command("show")
def path_show_cmd(name: str) -> None:
    try:
        header, tree = rig_views.path_tree_for(name)
    except StoreError as exc:
        _fail(str(exc))
    console.print(header)
    console.print(tree)


@app.command("change")
def change_cmd(
    summary: Optional[str] = typer.Argument(None),
    category: Optional[str] = typer.Option(None, "--category", "-c"),
    details: Optional[str] = typer.Option(None, "--details", "-d"),
    area: Optional[list[str]] = typer.Option(None, "--area", "-a"),
) -> None:
    """Record that physical/logical reality may have changed (does not edit CURRENT)."""
    try:
        if summary is None:
            summary = typer.prompt("What changed?")
            category = category or typer.prompt("Category", default="OTHER")
            areas_raw = typer.prompt("Affected area(s)", default="")
            details = details if details is not None else typer.prompt("Details", default="")
            areas = [a.strip() for a in areas_raw.split(",") if a.strip()]
        else:
            areas = list(area or [])
            details = details or ""
            category = category or "OTHER"
        cat = change_service.parse_category(category)
        record = change_service.create_change(
            summary,
            category=cat,
            details=details or "",
            affected_areas=areas,
        )
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"Recorded [bold]{record.id}[/bold]")
    if record.session_id:
        console.print(f"Active session detected: {record.session_id}")
        console.print(f"Change {record.id} linked to session.")
    console.print("CURRENT documentation has not been modified.")


@changes_app.command("list")
def changes_list_cmd(all_items: bool = typer.Option(False, "--all")) -> None:
    try:
        items = change_service.list_changes(all_items=all_items)
    except StoreError as exc:
        _fail(str(exc))
    console.print(
        "[bold]RIG CHANGES[/bold]" if all_items else "[bold]OPEN RIG CHANGES[/bold]"
    )
    if not items:
        console.print("(none)")
        return
    for item in items:
        if all_items:
            console.print(
                f"{item.id}  {item.status.value:<10} {item.category.value:<14} {item.summary}"
            )
        else:
            console.print(f"{item.id}  {item.category.value:<14} {item.summary}")


@changes_app.command("show")
def changes_show_cmd(chg_id: str) -> None:
    try:
        item = change_service.get_change(chg_id)
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"[bold]{item.id}[/bold]  {item.status.value}")
    console.print(f"Created: {item.created_at.isoformat()}")
    console.print(f"Category: {item.category.value}")
    console.print(f"Summary: {item.summary}")
    if item.details:
        console.print(f"Details: {item.details}")
    console.print(f"Session: {item.session_id or '—'}")
    areas = ", ".join(item.affected_areas) if item.affected_areas else "—"
    console.print(f"Affected: {areas}")


@changes_app.command("applied")
def changes_applied_cmd(
    chg_id: str,
    yes: bool = typer.Option(False, "--yes"),
) -> None:
    try:
        item = change_service.get_change(chg_id)
    except StoreError as exc:
        _fail(str(exc))
    if not yes:
        console.print(
            f"Mark {item.id} APPLIED only after CURRENT docs/data reflect the physical rig."
        )
        if not typer.confirm("Continue?", default=False):
            raise typer.Abort()
    try:
        updated, changed = change_service.set_change_status(
            chg_id, ChangeStatus.APPLIED
        )
    except StoreError as exc:
        _fail(str(exc))
    if not changed:
        console.print(f"{updated.id} already APPLIED")
    else:
        console.print(f"{updated.id} -> APPLIED")


@changes_app.command("dismiss")
def changes_dismiss_cmd(
    chg_id: str,
    yes: bool = typer.Option(False, "--yes"),
) -> None:
    try:
        item = change_service.get_change(chg_id)
    except StoreError as exc:
        _fail(str(exc))
    if not yes:
        if not typer.confirm(f"Dismiss {item.id}?", default=False):
            raise typer.Abort()
    try:
        updated, changed = change_service.set_change_status(
            chg_id, ChangeStatus.DISMISSED
        )
    except StoreError as exc:
        _fail(str(exc))
    if not changed:
        console.print(f"{updated.id} already DISMISSED")
    else:
        console.print(f"{updated.id} -> DISMISSED")


@session_app.command("start")
def session_start_cmd(
    focus: Optional[str] = typer.Option(None, "--focus"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    chosen = focus
    try:
        if chosen is None:
            console.print("[bold]NEXT SESSION[/bold]")
            console.print("")
            tasks = todo_service.next_list()
            options: list[str] = []
            for i, task in enumerate(tasks, start=1):
                console.print(f"{i}. {task.id}  {task.task}")
                options.append(task.id)
            free_n = len(options) + 1
            console.print(f"{free_n}. No task — just play / freeform")
            default = str(free_n)
            choice = typer.prompt("Focus", default=default)
            if choice.strip().isdigit():
                idx = int(choice.strip())
                if 1 <= idx <= len(options):
                    chosen = options[idx - 1]
                elif idx == free_n:
                    chosen = typer.prompt("Focus text", default="Just play")
                else:
                    _fail("Invalid focus choice.")
            else:
                chosen = choice
        session = session_service.start_session(chosen or "")
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"Started [bold]{session.id}[/bold]")
    console.print(f"Focus: {session_service.focus_label(session.focus)}")
    if session.focus.upper().startswith("RIG-"):
        if typer.confirm(
            f"Mark {session.focus.strip().upper()} IN PROGRESS?", default=False
        ):
            try:
                session_service.start_task(
                    session.focus, render=not no_render
                )
                console.print(f"{session.focus.strip().upper()} -> IN PROGRESS")
            except StoreError as exc:
                _fail(str(exc))


@session_app.command("status")
def session_status_cmd() -> None:
    try:
        session = session_service.require_active()
    except StoreError as exc:
        _fail(str(exc))
    now = default_clock()
    duration = session_service.format_duration(
        session.started_at, session.ended_at, now=now
    )
    started_local = session.started_at.strftime("%I:%M %p").lstrip("0")
    console.print("[bold]ACTIVE SESSION[/bold]")
    console.print(session.id)
    console.print("")
    console.print(f"Started: {started_local}")
    console.print(f"Duration: {duration}")
    console.print(f"Focus: {session_service.focus_label(session.focus)}")
    console.print("")
    console.print("Events:")
    if not session.events:
        console.print("  (none)")
    else:
        for event in session.events:
            stamp = event.timestamp.strftime("%H:%M")
            console.print(f"  {stamp} {event.type.value:<12} {event.text}")


@session_app.command("note")
def session_note_cmd(text: str) -> None:
    try:
        session = session_service.add_note(text)
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"NOTE added to {session.id}")


@session_app.command("discovery")
def session_discovery_cmd(text: str) -> None:
    try:
        session = session_service.add_discovery(text)
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"DISCOVERY added to {session.id}")


@session_app.command("start-task")
def session_start_task_cmd(
    todo_id: str,
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        session, task = session_service.start_task(todo_id, render=not no_render)
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"{task.id} -> IN PROGRESS")
    console.print(f"TODO_STARTED on {session.id}")


@session_app.command("complete-task")
def session_complete_task_cmd(
    todo_id: str,
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        session, task = session_service.complete_task(todo_id, render=not no_render)
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"{task.id} -> DONE")
    console.print(f"TODO_COMPLETED on {session.id}")


@session_app.command("capture")
def session_capture_cmd(text: str) -> None:
    try:
        session, item = session_service.session_capture(text)
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"Captured {item.id}")
    console.print(f"Added to active session {session.id}")


@session_app.command("end")
def session_end_cmd() -> None:
    try:
        session = session_service.require_active()
    except StoreError as exc:
        _fail(str(exc))
    now = default_clock()
    summary = session_service.summarize(session)
    console.print("[bold]SESSION SUMMARY[/bold]")
    console.print("")
    console.print(
        f"Duration: {session_service.format_duration(session.started_at, None, now=now)}"
    )
    console.print(f"Focus: {session.focus or '(none)'}")
    console.print("")
    console.print(f"Notes:        {summary['notes']}")
    console.print(f"Discoveries:  {summary['discoveries']}")
    console.print(f"TODOs done:   {summary['todos_done']}")
    console.print(f"Captures:     {summary['captures']}")
    console.print(f"Changes:      {summary['changes']}")
    console.print("")
    console.print("Open inbox from this session:")
    caps = summary["capture_ids"]
    if caps:
        for cap in caps:
            console.print(f"  {cap}")
    else:
        console.print("  (none)")
    console.print("")
    console.print("Unreconciled rig changes:")
    chgs = summary["change_ids"]
    if chgs:
        for chg in chgs:
            console.print(f"  {chg}")
    else:
        console.print("  (none)")
    console.print("")
    if not typer.confirm("Complete session?", default=True):
        raise typer.Abort()
    try:
        ended = session_service.end_session()
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"{ended.id} -> COMPLETED")


@session_app.command("abort")
def session_abort_cmd(
    yes: bool = typer.Option(False, "--yes"),
) -> None:
    try:
        session = session_service.require_active()
    except StoreError as exc:
        _fail(str(exc))
    if not yes:
        if not typer.confirm(f"Abort {session.id}? Events are preserved.", default=False):
            raise typer.Abort()
    try:
        aborted = session_service.abort_session()
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"{aborted.id} -> ABORTED")


@session_app.command("list")
def session_list_cmd(limit: int = typer.Option(10, "--limit")) -> None:
    try:
        sessions = session_service.list_sessions(limit=limit)
    except StoreError as exc:
        _fail(str(exc))
    table = Table(title="Sessions")
    table.add_column("ID")
    table.add_column("Date")
    table.add_column("Status")
    table.add_column("Duration")
    table.add_column("Focus")
    table.add_column("Events")
    now = default_clock()
    for session in sessions:
        duration = session_service.format_duration(
            session.started_at, session.ended_at, now=now
        )
        table.add_row(
            session.id,
            session.started_at.date().isoformat(),
            session.status.value,
            duration,
            (session.focus or "—")[:40],
            str(len(session.events)),
        )
    console.print(table)


@app.command("doctor")
def doctor_cmd() -> None:
    """Advisory maintenance overview (not a CI gate)."""
    console.print(build_doctor_text().rstrip())


def _confirm_current(preview, *, yes: bool, dry_run: bool) -> bool:
    console.print(format_current_preview(preview).rstrip())
    if dry_run:
        console.print("[dim]Dry-run: nothing written.[/dim]")
        return False
    if not preview.changed:
        console.print(preview.message)
        return False
    if yes:
        return True
    return typer.confirm("Apply?", default=False)


def _maybe_resolve_evidence(
    *,
    question_id: Optional[str],
    change_id: Optional[str],
    answer_hint: str,
    yes: bool,
) -> tuple[bool, bool, str]:
    resolve_q = False
    apply_chg = False
    answer = answer_hint
    if question_id:
        try:
            q = question_service.get_question(question_id)
            console.print("")
            console.print(f"Related Question: {q.id} — {q.question}")
            console.print(f"Current status: {q.status.value}")
        except StoreError as exc:
            _fail(str(exc))
        if yes:
            resolve_q = False
        else:
            resolve_q = typer.confirm(
                f'Resolve {question_id.strip().upper()} with answer "{answer_hint}"?',
                default=False,
            )
            if resolve_q and not answer_hint:
                answer = typer.prompt("Answer")
    if change_id:
        try:
            chg = change_service.get_change(change_id)
            console.print("")
            console.print(f"Related Change: {chg.id} — {chg.summary}")
            console.print(f"Current status: {chg.status.value}")
        except StoreError as exc:
            _fail(str(exc))
        # Prefer default No: freeform CHG text cannot be auto-trusted
        if yes:
            apply_chg = False
        else:
            apply_chg = typer.confirm(
                f"Mark {change_id.strip().upper()} APPLIED?", default=False
            )
    return resolve_q, apply_chg, answer


def _commit_routing_preview(
    preview,
    data: dict,
    *,
    yes: bool,
    dry_run: bool,
    question: Optional[str],
    change: Optional[str],
    answer_hint: str,
    no_render: bool,
) -> None:
    if not _confirm_current(preview, yes=yes, dry_run=dry_run):
        if dry_run:
            try:
                current_service.commit_routing(
                    data,
                    preview,
                    dry_run=True,
                    render=False,
                    question_id=question,
                    change_id=change,
                )
            except StoreError as exc:
                _fail(str(exc))
            raise typer.Exit(0)
        if not preview.changed:
            raise typer.Exit(0)
        raise typer.Abort()
    resolve_q, apply_chg, answer = _maybe_resolve_evidence(
        question_id=question,
        change_id=change,
        answer_hint=answer_hint,
        yes=yes,
    )
    try:
        result = current_service.commit_routing(
            data,
            preview,
            render=not no_render,
            question_id=question,
            change_id=change,
            resolve_q=resolve_q,
            apply_chg=apply_chg,
            answer=answer,
        )
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"[green]Applied:[/green] {result.message}")


@current_path_app.command("branches")
def current_path_branches(path: str) -> None:
    """List editable branches for a CURRENT named path."""
    try:
        data = routing_state.load_raw()
        path_id, named = routing_state.get_named_path(data, path)
    except StoreError as exc:
        _fail(str(exc))
    console.print(routing_state.format_branch_list(path_id, named).rstrip())


@current_path_app.command("move")
def current_path_move(
    path: str,
    node: str,
    branch: Optional[str] = typer.Option(None, "--branch"),
    before: Optional[str] = typer.Option(None, "--before"),
    after: Optional[str] = typer.Option(None, "--after"),
    first: bool = typer.Option(False, "--first"),
    last: bool = typer.Option(False, "--last"),
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    question: Optional[str] = typer.Option(None, "--question"),
    change: Optional[str] = typer.Option(None, "--change"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        preview, data = routing_state.propose_move(
            path,
            node,
            branch=branch,
            before=before,
            after=after,
            first=first,
            last=last,
        )
    except StoreError as exc:
        _fail(str(exc))
    _commit_routing_preview(
        preview,
        data,
        yes=yes,
        dry_run=dry_run,
        question=question,
        change=change,
        answer_hint=preview.after.get("chain", ""),
        no_render=no_render,
    )


@current_path_app.command("insert")
def current_path_insert(
    path: str,
    node_id: str,
    label: Optional[str] = typer.Option(None, "--label"),
    branch: Optional[str] = typer.Option(None, "--branch"),
    before: Optional[str] = typer.Option(None, "--before"),
    after: Optional[str] = typer.Option(None, "--after"),
    first: bool = typer.Option(False, "--first"),
    last: bool = typer.Option(False, "--last"),
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    question: Optional[str] = typer.Option(None, "--question"),
    change: Optional[str] = typer.Option(None, "--change"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        preview, data = routing_state.propose_insert(
            path,
            node_id,
            label=label,
            branch=branch,
            before=before,
            after=after,
            first=first,
            last=last,
        )
    except StoreError as exc:
        _fail(str(exc))
    _commit_routing_preview(
        preview,
        data,
        yes=yes,
        dry_run=dry_run,
        question=question,
        change=change,
        answer_hint=f"{node_id} inserted in {path}",
        no_render=no_render,
    )


@current_path_app.command("remove")
def current_path_remove(
    path: str,
    node: str,
    branch: Optional[str] = typer.Option(None, "--branch"),
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    question: Optional[str] = typer.Option(None, "--question"),
    change: Optional[str] = typer.Option(None, "--change"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        preview, data = routing_state.propose_remove(path, node, branch=branch)
    except StoreError as exc:
        _fail(str(exc))
    _commit_routing_preview(
        preview,
        data,
        yes=yes,
        dry_run=dry_run,
        question=question,
        change=change,
        answer_hint=f"{node} removed from {path}",
        no_render=no_render,
    )


@current_path_app.command("set-mode")
def current_path_set_mode(
    path: str,
    node: str,
    mode: str,
    branch: Optional[str] = typer.Option(None, "--branch"),
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    question: Optional[str] = typer.Option(None, "--question"),
    change: Optional[str] = typer.Option(None, "--change"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        preview, data = routing_state.propose_set_mode(
            path, node, mode, branch=branch
        )
    except StoreError as exc:
        _fail(str(exc))
    _commit_routing_preview(
        preview,
        data,
        yes=yes,
        dry_run=dry_run,
        question=question,
        change=change,
        answer_hint=mode.strip(),
        no_render=no_render,
    )


def _numbered_branch(branch) -> None:
    if not branch.nodes:
        console.print("  (empty)")
        return
    for index, node in enumerate(branch.nodes, start=1):
        console.print(f"  {index}. {routing_state.node_display(node)} [{node.id}]")


def _wizard_node(branch, prompt: str) -> str:
    raw = typer.prompt(prompt).strip()
    if raw.isdigit() and 1 <= int(raw) <= len(branch.nodes):
        return branch.nodes[int(raw) - 1].id
    return raw


def _wizard_placement(branch) -> dict:
    console.print("Placement: [1] before  [2] after  [3] first  [4] last")
    choice = typer.prompt("Placement", default="4").strip().lower()
    if choice in {"1", "before"}:
        return {"before": _wizard_node(branch, "Before node")}
    if choice in {"2", "after"}:
        return {"after": _wizard_node(branch, "After node")}
    if choice in {"3", "first"}:
        return {"first": True}
    if choice in {"4", "last"}:
        return {"last": True}
    raise StoreError(f"Invalid placement {choice!r}")


@current_path_app.command("verify")
def current_path_verify(
    path: str,
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    """Verify every branch and apply all selected edits as one transaction."""
    try:
        original = routing_state.load_raw()
        path_id, initial = routing_state.get_named_path(original, path)
    except StoreError as exc:
        _fail(str(exc))
    branch_ids = ["main", *[bid for bid in initial.branches if bid != "main"]]
    mutations: list[dict] = []
    pending_changes: list[str] = []

    for branch_id in branch_ids:
        while True:
            try:
                _preview, staged = routing_state.propose_batch(
                    path_id, mutations, data=original
                )
                _pid, named = routing_state.get_named_path(staged, path_id)
                branch = named.branches[branch_id]
            except StoreError as exc:
                _fail(str(exc))
            console.print("")
            console.print(f"[bold]{path_id} / {branch_id} — {branch.label}[/bold]")
            _numbered_branch(branch)
            if typer.confirm("Does this match?", default=True):
                break
            console.print("  [1] reorder")
            console.print("  [2] remove")
            console.print("  [3] add")
            console.print("  [4] record change only")
            console.print("  [q] quit")
            choice = typer.prompt("Choice").strip().lower()
            try:
                if choice in {"1", "reorder"}:
                    node = _wizard_node(branch, "Node")
                    mutations.append(
                        {
                            "op": "move",
                            "branch": branch_id,
                            "node": node,
                            **_wizard_placement(branch),
                        }
                    )
                elif choice in {"2", "remove"}:
                    mutations.append(
                        {
                            "op": "remove",
                            "branch": branch_id,
                            "node": _wizard_node(branch, "Node"),
                        }
                    )
                elif choice in {"3", "add"}:
                    node_id = typer.prompt("Node id").strip()
                    label = typer.prompt("Label", default=node_id).strip()
                    mutations.append(
                        {
                            "op": "insert",
                            "branch": branch_id,
                            "node": node_id,
                            "label": label,
                            **_wizard_placement(branch),
                        }
                    )
                elif choice in {"4", "record", "record change only"}:
                    pending_changes.append(
                        typer.prompt(
                            "What differs physically?",
                            default=f"{path_id}/{branch_id} differs from CURRENT",
                        ).strip()
                    )
                    break
                elif choice in {"q", "quit"}:
                    console.print("Quit: nothing written.")
                    raise typer.Exit(0)
                else:
                    raise StoreError(f"Invalid choice {choice!r}")
            except StoreError as exc:
                _fail(str(exc))

    try:
        preview, data = routing_state.propose_batch(
            path_id, mutations, data=original
        )
    except StoreError as exc:
        _fail(str(exc))
    console.print("")
    console.print(format_current_preview(preview).rstrip())
    if pending_changes:
        console.print("")
        console.print("Change records to create:")
        for summary in pending_changes:
            console.print(f"  - {summary}")
    if dry_run:
        try:
            current_service.commit_routing(
                data, preview, dry_run=True, render=False
            )
        except StoreError as exc:
            _fail(str(exc))
        console.print("[dim]Dry-run: nothing written.[/dim]")
        raise typer.Exit(0)
    if not preview.changed and not pending_changes:
        console.print("No routing changes selected.")
        raise typer.Exit(0)
    if not yes and not typer.confirm(
        f"Apply {len(mutations)} routing mutation(s) and "
        f"create {len(pending_changes)} change record(s)?",
        default=False,
    ):
        raise typer.Abort()
    try:
        if preview.changed:
            current_service.commit_routing(
                data, preview, render=not no_render
            )
        for summary in pending_changes:
            change_service.create_change(
                summary,
                category=ChangeCategory.PEDAL_CHAIN,
                affected_areas=[f"Routing: {path_id}"],
            )
    except StoreError as exc:
        _fail(str(exc))
    console.print(
        f"[green]Applied:[/green] {len(mutations)} routing mutation(s); "
        f"{len(pending_changes)} change record(s) created."
    )


@current_pb_app.command("show")
def current_pb_show(
    bay_id: str,
    unknown: bool = typer.Option(False, "--unknown"),
) -> None:
    """Alias for read-only `rig patchbay` (reuses the same view)."""
    try:
        console.print(
            rig_views.format_patchbay(bay_id, unknown_only=unknown).rstrip()
        )
    except StoreError as exc:
        _fail(str(exc))


@current_pb_app.command("set-mode")
def current_pb_set_mode(
    bay_id: str,
    jack: str = typer.Argument(..., help="Upper jack N or pair N/M (e.g. 1 or 1/25)"),
    mode: str = typer.Argument(..., help="normal|half-normal|thru|unknown"),
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    question: Optional[str] = typer.Option(None, "--question"),
    change: Optional[str] = typer.Option(None, "--change"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        preview, data = patchbay_state.propose_set_mode(bay_id, jack, mode)
    except StoreError as exc:
        _fail(str(exc))
    console.print(format_current_preview(preview).rstrip())
    if dry_run:
        try:
            current_service.commit_patchbay(
                data,
                preview,
                dry_run=True,
                render=False,
                question_id=question,
                change_id=change,
            )
        except StoreError as exc:
            _fail(str(exc))
        console.print("[dim]Dry-run: nothing written.[/dim]")
        console.print(preview.message)
        raise typer.Exit(0)
    if not preview.changed:
        console.print(preview.message)
        raise typer.Exit(0)
    if not yes and not typer.confirm("Apply?", default=False):
        raise typer.Abort()
    resolve_q, apply_chg, answer = _maybe_resolve_evidence(
        question_id=question,
        change_id=change,
        answer_hint=mode.strip().lower().replace("_", "-"),
        yes=yes,
    )
    try:
        result = current_service.commit_patchbay(
            data,
            preview,
            dry_run=False,
            render=not no_render,
            question_id=question,
            change_id=change,
            resolve_q=resolve_q,
            apply_chg=apply_chg,
            answer=answer,
        )
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"[green]Applied:[/green] {result.message}")


@current_pb_app.command("set-model")
def current_pb_set_model(
    bay_id: str,
    model: str,
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    question: Optional[str] = typer.Option(None, "--question"),
    change: Optional[str] = typer.Option(None, "--change"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        preview, data = patchbay_state.propose_set_model(bay_id, model)
    except StoreError as exc:
        _fail(str(exc))
    if not _confirm_current(preview, yes=yes, dry_run=dry_run):
        if dry_run or not preview.changed:
            if dry_run:
                console.print(preview.message)
            raise typer.Exit(0)
        raise typer.Abort()
    resolve_q, apply_chg, answer = _maybe_resolve_evidence(
        question_id=question,
        change_id=change,
        answer_hint=model.strip(),
        yes=yes,
    )
    try:
        result = current_service.commit_patchbay(
            data,
            preview,
            render=not no_render,
            question_id=question,
            change_id=change,
            resolve_q=resolve_q,
            apply_chg=apply_chg,
            answer=answer,
        )
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"[green]Applied:[/green] {result.message}")


@current_pb_app.command("verify")
def current_pb_verify(
    bay_id: str,
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    """Interactively verify modes for represented pairs; apply as one transaction."""
    try:
        pairs = patchbay_state.list_pairs(bay_id)
    except StoreError as exc:
        _fail(str(exc))
    if not pairs:
        console.print(f"{bay_id.upper()}: no represented pairs.")
        raise typer.Exit(0)
    updates: list[tuple[str, str]] = []
    mode_choices = {
        "1": "normal",
        "2": "half-normal",
        "3": "thru",
        "4": "unknown",
    }
    for pair in pairs:
        lower = pair["lower_n"] if pair["lower_n"] is not None else "?"
        console.print("")
        console.print(f"{bay_id.upper()} pair {pair['upper_n']}/{lower}")
        console.print(
            f"{pair['upper_conn'] or '—'} -> {pair['lower_conn'] or '—'}"
        )
        console.print(f"Current mode: {str(pair['mode']).upper()}")
        console.print("Mode:")
        console.print("  [1] normal")
        console.print("  [2] half-normal")
        console.print("  [3] thru")
        console.print("  [4] unknown")
        console.print("  [s] skip")
        choice = typer.prompt("Choice", default="s").strip().lower()
        if choice in {"s", "skip", ""}:
            continue
        if choice not in mode_choices:
            _fail(f"Invalid choice {choice!r}")
        updates.append((str(pair["upper_n"]), mode_choices[choice]))

    if not updates:
        console.print("No mode changes selected.")
        raise typer.Exit(0)
    try:
        preview, data = patchbay_state.propose_set_modes_batch(bay_id, updates)
    except StoreError as exc:
        _fail(str(exc))
    console.print("")
    console.print("[bold]PATCHBAY VERIFICATION SUMMARY[/bold]")
    console.print("")
    # Show batch before/after compactly
    before_modes = preview.before.get("modes") or {}
    after_modes = preview.after.get("modes") or {}
    changed_n = 0
    for key in after_modes:
        b = before_modes.get(key)
        a = after_modes.get(key)
        if b != a:
            changed_n += 1
            console.print(f"{key}  {str(b).upper()} -> {str(a).upper()}")
        else:
            console.print(f"{key}  unchanged")
    console.print("")
    console.print("This modifies authoritative CURRENT state.")
    if dry_run:
        console.print("[dim]Dry-run: nothing written.[/dim]")
        raise typer.Exit(0)
    if not yes and not typer.confirm(
        f"Apply {changed_n} CURRENT updates?", default=False
    ):
        raise typer.Abort()
    try:
        result = current_service.commit_patchbay(
            data, preview, render=not no_render
        )
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"[green]Applied:[/green] {result.message}")


@current_ch_app.command("show")
def current_ch_show(
    device: Optional[str] = typer.Option(None, "--device", help="tascam|alesis"),
) -> None:
    """Alias for read-only `rig channels`."""
    try:
        console.print(rig_views.format_channels(device=device).rstrip())
    except StoreError as exc:
        _fail(str(exc))


@current_ch_app.command("set-source")
def current_ch_set_source(
    device: str,
    channel: str,
    source: str,
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    question: Optional[str] = typer.Option(None, "--question"),
    change: Optional[str] = typer.Option(None, "--change"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        preview, data = channel_state.propose_set_source(device, channel, source)
    except StoreError as exc:
        _fail(str(exc))
    if not _confirm_current(preview, yes=yes, dry_run=dry_run):
        if dry_run or not preview.changed:
            if dry_run:
                console.print(preview.message)
            raise typer.Exit(0)
        raise typer.Abort()
    resolve_q, apply_chg, answer = _maybe_resolve_evidence(
        question_id=question,
        change_id=change,
        answer_hint=source.strip(),
        yes=yes,
    )
    try:
        result = current_service.commit_channel(
            data,
            preview,
            render=not no_render,
            question_id=question,
            change_id=change,
            resolve_q=resolve_q,
            apply_chg=apply_chg,
            answer=answer,
        )
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"[green]Applied:[/green] {result.message}")


@current_ch_app.command("clear-source")
def current_ch_clear_source(
    device: str,
    channel: str,
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    question: Optional[str] = typer.Option(None, "--question"),
    change: Optional[str] = typer.Option(None, "--change"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        preview, data = channel_state.clear_source(device, channel)
    except StoreError as exc:
        _fail(str(exc))
    if not _confirm_current(preview, yes=yes, dry_run=dry_run):
        if dry_run or not preview.changed:
            if dry_run:
                console.print(preview.message)
            raise typer.Exit(0)
        raise typer.Abort()
    resolve_q, apply_chg, answer = _maybe_resolve_evidence(
        question_id=question,
        change_id=change,
        answer_hint="UNASSIGNED",
        yes=yes,
    )
    try:
        result = current_service.commit_channel(
            data,
            preview,
            render=not no_render,
            question_id=question,
            change_id=change,
            resolve_q=resolve_q,
            apply_chg=apply_chg,
            answer=answer,
        )
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"[green]Applied:[/green] {result.message}")


@app.command("now")
def now_cmd(
    play: bool = typer.Option(False, "--play", help="Recommend freeform play session"),
    why: bool = typer.Option(False, "--why", help="Show skipped-task context"),
) -> None:
    """Deterministic next-action recommendation from repository state."""
    try:
        rec = recommend_now(play=play)
    except StoreError as exc:
        _fail(str(exc))
    console.print(format_now(rec, extra_why=why).rstrip())


@reconcile_app.callback(invoke_without_command=True)
def reconcile_main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is not None:
        return
    try:
        console.print(build_reconcile_summary().rstrip())
    except StoreError as exc:
        _fail(str(exc))


@reconcile_app.command("change")
def reconcile_change_cmd(chg_id: str) -> None:
    try:
        console.print(format_reconcile_change(chg_id).rstrip())
    except StoreError as exc:
        _fail(str(exc))


@reconcile_app.command("question")
def reconcile_question_cmd(question_id: str) -> None:
    try:
        console.print(format_reconcile_question(question_id).rstrip())
    except StoreError as exc:
        _fail(str(exc))


@question_app.command("list")
def question_list_cmd(
    all_items: bool = typer.Option(False, "--all"),
    area: Optional[str] = typer.Option(None, "--area"),
) -> None:
    try:
        items = question_service.list_questions(all_items=all_items, area=area)
    except StoreError as exc:
        _fail(str(exc))
    title = "QUESTIONS" if all_items else "OPEN QUESTIONS"
    console.print(f"[bold]{title}[/bold]")
    if not items:
        console.print("(none)")
        return
    for q in items:
        status = f"{q.status.value}  " if all_items else ""
        console.print(f"{q.id}  {status}{q.area:<18} {q.question}")


@question_app.command("show")
def question_show_cmd(question_id: str) -> None:
    try:
        q = question_service.get_question(question_id)
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"[bold]{q.id}[/bold]")
    console.print("")
    console.print("Question:")
    console.print(q.question)
    console.print("")
    console.print(f"Area: {q.area}")
    console.print(f"Status: {q.status.value}")
    console.print("")
    console.print("Related TODOs:")
    if q.related_todos:
        for tid in q.related_todos:
            console.print(f"  {tid}")
    else:
        console.print("  —")
    console.print("")
    console.print("Related Changes:")
    if q.related_changes:
        for cid in q.related_changes:
            console.print(f"  {cid}")
    else:
        console.print("  —")
    console.print("")
    console.print("Answer:")
    console.print(f"  {q.answer.strip() or '—'}")
    console.print("")
    console.print("Notes:")
    console.print(f"  {q.notes.strip() or '—'}")
    if q.resolved_at is not None:
        console.print("")
        console.print(f"Resolved at: {q.resolved_at.isoformat()}")


@question_app.command("add")
def question_add_cmd(
    question: Optional[str] = typer.Option(None, "--question", "-q"),
    area: Optional[str] = typer.Option(None, "--area", "-a"),
    todo: Optional[list[str]] = typer.Option(None, "--todo", "-t"),
    notes: Optional[str] = typer.Option(None, "--notes", "-n"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        if question is None:
            question = typer.prompt("Question")
            area = area or typer.prompt("Area", default="Routing")
            todos_raw = typer.prompt("Related TODOs (comma separated)", default="")
            notes = notes if notes is not None else typer.prompt("Notes", default="")
            todos = [p.strip() for p in todos_raw.replace(";", ",").split(",") if p.strip()]
        else:
            area = area or "Uncategorized"
            notes = notes or ""
            todos = list(todo or [])
        item = question_service.add_question(
            question,
            area=area,
            related_todos=todos,
            notes=notes or "",
            render=not no_render,
        )
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"Created [bold]{item.id}[/bold]")


@question_app.command("resolve")
def question_resolve_cmd(
    question_id: str,
    answer: Optional[str] = typer.Option(None, "--answer"),
    change: Optional[str] = typer.Option(None, "--change", help="Related CHG id"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        if answer is None:
            answer = typer.prompt("Answer")
        if change is None and typer.confirm("Link a related CHG record?", default=False):
            change = typer.prompt("Related CHG record")
        updated = question_service.resolve_question(
            question_id,
            answer,
            related_change=change,
            render=not no_render,
        )
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"{updated.id} resolved.")
    console.print("")
    console.print(
        "If this answer changes documented CURRENT state,\n"
        "reconcile the affected rig data before considering the work complete."
    )


@question_app.command("defer")
def question_defer_cmd(
    question_id: str,
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        updated = question_service.defer_question(question_id, render=not no_render)
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"{updated.id} -> DEFERRED")


@question_app.command("reopen")
def question_reopen_cmd(
    question_id: str,
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        updated = question_service.reopen_question(question_id, render=not no_render)
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"{updated.id} -> OPEN")


@question_app.command("todo")
def question_todo_cmd(
    question_id: str,
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        q = question_service.get_question(question_id)
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"[bold]{q.id}[/bold]")
    console.print(q.question)
    console.print("")
    new_task = _prompt_todo_fields(
        default_task=q.question[:80],
        default_area=q.area,
        default_priority="P1",
        default_dod=f"Answer {q.id} and update CURRENT docs if needed",
        default_notes=f"Created from {q.id}",
    )
    try:
        updated, task = question_service.create_todo_for_question(
            question_id, new_task, render=not no_render
        )
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"Created {task.id}; linked on {updated.id}")
    console.print(f"{updated.id} status unchanged ({updated.status.value})")


@question_app.command("link-todo")
def question_link_todo_cmd(
    question_id: str,
    todo_id: str,
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        updated = question_service.link_todo(
            question_id, todo_id, render=not no_render
        )
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"Linked {todo_id.strip().upper()} -> {updated.id}")


@question_app.command("link-change")
def question_link_change_cmd(
    question_id: str,
    change_id: str,
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        updated = question_service.link_change(
            question_id, change_id, render=not no_render
        )
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"Linked {change_id.strip().upper()} <-> {updated.id}")


@app.command("render")
def render_cmd(check: bool = typer.Option(False, "--check")) -> None:
    if check:
        try:
            stale = check_render_sync()
        except StoreError as exc:
            _fail(str(exc))
        if stale:
            for path in stale:
                err_console.print(
                    f"[red]{path} is out of date with canonical YAML[/red]"
                )
            err_console.print("Run: uv run rig render")
            raise typer.Exit(1)
        console.print("[green]Generated Markdown is synchronized.[/green]")
        return
    try:
        changed, names = render_docs(write=True)
    except StoreError as exc:
        _fail(str(exc))
    if changed:
        console.print("Updated: " + ", ".join(names))
    else:
        console.print("[dim]No changes.[/dim]")


@app.command("check")
def check_cmd() -> None:
    result = run_checks()
    for warning in result.warnings:
        err_console.print(f"[yellow]Warning:[/yellow] {warning}")
    if not result.ok:
        for error in result.errors:
            err_console.print(f"[red]Error:[/red] {error}")
        raise typer.Exit(1)
    console.print("[green]All checks passed.[/green]")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
