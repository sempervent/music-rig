"""Typer CLI entrypoint: `uv run rig ...`."""

from __future__ import annotations

import sys
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from music_rig.checks import run_checks
from music_rig.models import (
    TodoDocument,
    TodoPriority,
    TodoStatus,
    TodoTask,
    WishPriority,
    WishStatus,
    WishlistDocument,
    WishlistItem,
)
from music_rig.render import check_render_sync, render_docs
from music_rig.store import StoreError, load_todo, load_wishlist, save_todo, save_wishlist

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
app.add_typer(todo_app, name="todo")
app.add_typer(wish_app, name="wish")


def _fail(message: str, code: int = 1) -> None:
    err_console.print(f"[red]Error:[/red] {message}")
    raise typer.Exit(code)


def _parse_priority(raw: str) -> TodoPriority:
    try:
        return TodoPriority(raw.strip().upper())
    except ValueError:
        _fail(f"Invalid priority {raw!r}. Use P0, P1, P2, or P3.")


def _parse_status(raw: str) -> TodoStatus:
    cleaned = " ".join(raw.strip().upper().split())
    try:
        return TodoStatus(cleaned)
    except ValueError:
        _fail(
            f"Invalid status {raw!r}. Use NEXT, READY, BLOCKED, IN PROGRESS, "
            "WAITING, DONE, DEFERRED, or CANCELLED."
        )


def _parse_wish_priority(raw: str) -> WishPriority | None:
    cleaned = raw.strip().upper()
    if cleaned in {"", "—", "-", "NONE", "NULL"}:
        return None
    try:
        return WishPriority(cleaned)
    except ValueError:
        _fail(f"Invalid wishlist priority {raw!r}. Use P0–P3 or —.")


def _parse_wish_status(raw: str) -> WishStatus:
    cleaned = " ".join(raw.strip().upper().split())
    try:
        return WishStatus(cleaned)
    except ValueError:
        _fail(f"Invalid wishlist status {raw!r}.")


def _parse_deps(raw: str) -> list[str]:
    if not raw.strip():
        return []
    parts = [p.strip().upper() for p in raw.replace(";", ",").split(",")]
    return [p for p in parts if p]


@todo_app.command("list")
def todo_list(
    status: Optional[str] = typer.Option(
        None, "--status", help="Filter by status (e.g. READY)."
    ),
    priority: Optional[str] = typer.Option(
        None, "--priority", help="Filter by priority (e.g. P0)."
    ),
    all_items: bool = typer.Option(
        False, "--all", help="Include DONE and CANCELLED tasks."
    ),
) -> None:
    """List TODO tasks in a terminal table."""
    try:
        doc = load_todo()
    except StoreError as exc:
        _fail(str(exc))

    status_filter = _parse_status(status) if status else None
    priority_filter = _parse_priority(priority) if priority else None

    rows = []
    for task in doc.tasks:
        if not all_items and task.status in {TodoStatus.DONE, TodoStatus.CANCELLED}:
            continue
        if status_filter and task.status != status_filter:
            continue
        if priority_filter and task.priority != priority_filter:
            continue
        rows.append(task)

    table = Table(title="TODO")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Priority", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Area")
    table.add_column("Task")
    for task in rows:
        table.add_row(
            task.id,
            task.priority.value,
            task.status.value,
            task.area,
            task.task,
        )
    console.print(table)
    console.print(f"[dim]{len(rows)} task(s)[/dim]")


@todo_app.command("show")
def todo_show(todo_id: str = typer.Argument(..., help="TODO id, e.g. RIG-038")) -> None:
    """Show one TODO record."""
    try:
        doc = load_todo()
    except StoreError as exc:
        _fail(str(exc))
    key = todo_id.strip().upper()
    task = doc.task_map().get(key)
    if task is None:
        _fail(f"TODO {key} does not exist.")

    in_next = key in doc.next_session
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
def todo_add(
    task: Optional[str] = typer.Option(None, help="Task title"),
    area: Optional[str] = typer.Option(None, help="Area"),
    priority: Optional[str] = typer.Option(None, help="P0–P3"),
    status: Optional[str] = typer.Option(None, help="Status"),
    depends_on: Optional[str] = typer.Option(
        None, "--depends-on", help="Comma-separated RIG IDs"
    ),
    definition_of_done: Optional[str] = typer.Option(
        None, "--dod", help="Definition of Done"
    ),
    notes: Optional[str] = typer.Option(None, help="Notes"),
    no_render: bool = typer.Option(
        False, "--no-render", help="Write YAML only; skip Markdown render"
    ),
) -> None:
    """Create a TODO with the next RIG ID. Writes YAML then renders docs unless --no-render."""
    try:
        doc = load_todo()
    except StoreError as exc:
        _fail(str(exc))

    task = task or typer.prompt("Task")
    area = area or typer.prompt("Area")
    priority = priority or typer.prompt("Priority", default="P2")
    status = status or typer.prompt("Status", default="READY")
    if depends_on is None:
        depends_on = typer.prompt("Depends on (comma separated)", default="")
    definition_of_done = definition_of_done or typer.prompt("Definition of Done")
    if notes is None:
        notes = typer.prompt("Notes", default="")

    new_id = doc.next_id()
    try:
        new_task = TodoTask(
            id=new_id,
            task=task.strip(),
            area=area.strip(),
            priority=_parse_priority(priority),
            status=_parse_status(status),
            depends_on=_parse_deps(depends_on),
            definition_of_done=definition_of_done.strip(),
            notes=(notes or "").strip(),
        )
    except Exception as exc:
        _fail(str(exc))

    # Validate as a whole document before writing
    updated = _todo_with(doc, new_task)
    try:
        save_todo(updated)
    except StoreError as exc:
        _fail(str(exc))

    if not no_render:
        try:
            render_docs(write=True)
        except StoreError as exc:
            _fail(str(exc))

    console.print(f"Created [bold]{new_id}[/bold]")
    if not no_render:
        console.print("[dim]Updated data/todo.yaml and rendered docs/todo.md[/dim]")
    else:
        console.print("[dim]Updated data/todo.yaml (render skipped)[/dim]")


def _todo_with(doc: TodoDocument, new_task: TodoTask) -> TodoDocument:
    return TodoDocument(
        next_session=list(doc.next_session),
        tasks=[*doc.tasks, new_task],
    )


@wish_app.command("list")
def wish_list(
    status: Optional[str] = typer.Option(None, "--status"),
    priority: Optional[str] = typer.Option(None, "--priority"),
) -> None:
    """List wishlist items."""
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
def wish_show(name: str = typer.Argument(..., help="Exact item name (case-insensitive)")) -> None:
    """Show one wishlist item."""
    try:
        doc = load_wishlist()
    except StoreError as exc:
        _fail(str(exc))
    item = doc.find(name)
    if item is None:
        _fail(f'Wishlist item "{name}" does not exist.')

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
    if item.details.strip():
        console.print("\n[bold]Details[/bold]")
        console.print(item.details)


@wish_app.command("add")
def wish_add(
    item: Optional[str] = typer.Option(None),
    category: Optional[str] = typer.Option(None),
    problem_capability: Optional[str] = typer.Option(None, "--problem"),
    priority: Optional[str] = typer.Option(None),
    status: Optional[str] = typer.Option(None),
    duplication: Optional[str] = typer.Option(None),
    cost: Optional[str] = typer.Option(None),
    friction: Optional[str] = typer.Option(None),
    likely_music_impact: Optional[str] = typer.Option(None, "--impact"),
    notes: Optional[str] = typer.Option(None),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    """Add a wishlist item. Defaults to status IDEA. Writes YAML then renders unless --no-render."""
    try:
        doc = load_wishlist()
    except StoreError as exc:
        _fail(str(exc))

    item = item or typer.prompt("Item")
    category = category or typer.prompt("Category")
    problem_capability = problem_capability or typer.prompt("Problem / Capability")
    priority = priority or typer.prompt("Priority", default="P2")
    status = status or typer.prompt("Status", default="IDEA")
    duplication = duplication if duplication is not None else typer.prompt("Duplication", default="")
    cost = cost if cost is not None else typer.prompt("Cost", default="UNKNOWN")
    friction = friction if friction is not None else typer.prompt("Friction", default="")
    likely_music_impact = (
        likely_music_impact
        if likely_music_impact is not None
        else typer.prompt("Likely Music Impact", default="")
    )
    notes = notes if notes is not None else typer.prompt("Notes", default="")

    try:
        new_item = WishlistItem(
            item=item.strip(),
            category=category.strip(),
            problem_capability=problem_capability.strip(),
            priority=_parse_wish_priority(priority),
            status=_parse_wish_status(status),
            duplication=(duplication or "").strip(),
            cost=(cost or "").strip(),
            friction=(friction or "").strip(),
            likely_music_impact=(likely_music_impact or "").strip(),
            notes=(notes or "").strip(),
        )
    except Exception as exc:
        _fail(str(exc))

    updated = WishlistDocument(items=[*doc.items, new_item])
    try:
        save_wishlist(updated)
    except StoreError as exc:
        _fail(str(exc))

    if not no_render:
        try:
            render_docs(write=True)
        except StoreError as exc:
            _fail(str(exc))

    console.print(f'Created wishlist item [bold]{new_item.item}[/bold]')


@app.command("render")
def render_cmd(
    check: bool = typer.Option(
        False, "--check", help="Exit nonzero if generated Markdown is stale"
    ),
) -> None:
    """Render docs/todo.md and docs/wishlist.md generated sections from YAML."""
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
    """Validate planning YAML, generated docs sync, and existing data/*.yaml parse."""
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
