"""Typer CLI entrypoint: `uv run rig ...`."""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from music_rig.checks import run_checks
from music_rig import inbox_service, todo_service, wishlist_service
from music_rig.models import (
    InboxStatus,
    TodoPriority,
    TodoStatus,
    TodoTask,
    WishPriority,
    WishStatus,
    WishlistItem,
)
from music_rig.render import check_render_sync, render_docs
from music_rig.status import build_status_text
from music_rig.store import StoreError, load_inbox, load_todo, load_wishlist

console = Console(stderr=False)
err_console = Console(stderr=True)

app = typer.Typer(
    name="rig",
    help="Music-rig planning CLI. Canonical data lives in data/*.yaml.",
    no_args_is_help=True,
)
todo_app = typer.Typer(help="Accepted work queue (data/todo.yaml).", no_args_is_help=True)
wish_app = typer.Typer(
    help="Speculative wishlist (data/wishlist.yaml).", no_args_is_help=True
)
next_app = typer.Typer(help="Next Session queue (max 3).", no_args_is_help=True)
inbox_app = typer.Typer(help="Low-friction capture inbox.", no_args_is_help=True)
app.add_typer(todo_app, name="todo")
app.add_typer(wish_app, name="wish")
todo_app.add_typer(next_app, name="next")
app.add_typer(inbox_app, name="inbox")


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


# --- render / check ---


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
