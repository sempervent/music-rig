"""Typer CLI entrypoint: `uv run rig ...`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from music_rig.checks import run_checks
from music_rig import (
    change_service,
    channel_state,
    current_service,
    control_state,
    control_surface_state,
    ableton_state,
    automation,
    backup_state,
    inbox_service,
    inventory_state,
    midi_state,
    gear_usage,
    patchbay_state,
    performance_state,
    question_service,
    routing_state,
    session_service,
    snapshot_service,
    todo_service,
    wishlist_service,
)
from music_rig.current_projections import format_current_preview
from music_rig.doctor import build_doctor_text
from music_rig.inbox_service import default_clock
from music_rig.local_config import load_local_config
from music_rig.models import (
    ChangeStatus,
    GearCondition,
    InboxStatus,
    OwnershipStatus,
    MidiEvidenceStatus,
    MidiTransport,
    MidiTriState,
    ControlAvailability,
    ControlTarget,
    MidiMessage,
    MidiMessageType,
    PhysicalControlType,
    TargetKind,
    TargetState,
    PerformanceCriticality,
    ValueBehavior,
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
from music_rig.reconciliation import service as reconcile_service
from music_rig.reconciliation.types import err_payload, ok_payload
from music_rig.render import check_render_sync, render_docs
from music_rig import rig_views
from music_rig.status import build_status_text
from music_rig.store import (
    StoreError,
    load_inbox,
    load_inventory,
    load_midi,
    load_controllers,
    load_ableton,
    load_todo,
    load_wishlist,
)

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
    help="Reconcile questions/changes into CURRENT via adapters (CLI-first).",
    invoke_without_command=True,
    no_args_is_help=False,
)
path_app = typer.Typer(help="Read-only CURRENT named paths.", no_args_is_help=True)
gear_app = typer.Typer(help="Owned equipment inventory.", no_args_is_help=True)
midi_app = typer.Typer(help="Read-only CURRENT MIDI state.", no_args_is_help=True)
controls_app = typer.Typer(help="Controller mapping evidence and gaps.", no_args_is_help=True)
ableton_app = typer.Typer(help="Durable Ableton mapping targets.", no_args_is_help=True)
performance_app = typer.Typer(
    help="PFL performance orchestration and readiness.", no_args_is_help=True
)
snapshot_app = typer.Typer(
    help="Canonical YAML repository snapshots.", no_args_is_help=True
)
backup_app = typer.Typer(
    help="Backup plan and archive packages.", no_args_is_help=True
)
automation_app = typer.Typer(
    help="Automation capability registry.", no_args_is_help=True
)
inspect_app = typer.Typer(
    help="Structured inspection for agents and humans.",
    no_args_is_help=True,
)
rename_app = typer.Typer(
    help="Safe stable-ID rename (preview + apply).",
    no_args_is_help=True,
)
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
current_gear_app = typer.Typer(
    help="CURRENT owned-equipment mutations (data/inventory.yaml).",
    no_args_is_help=True,
)
current_midi_app = typer.Typer(
    help="CURRENT MIDI mutations (data/midi.yaml).",
    no_args_is_help=True,
)
current_controls_app = typer.Typer(
    help="CURRENT controller mapping mutations (data/controllers.yaml).",
    no_args_is_help=True,
)
current_performance_app = typer.Typer(
    help="PFL performance binding/evidence mutations.", no_args_is_help=True
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
app.add_typer(gear_app, name="gear")
app.add_typer(midi_app, name="midi")
app.add_typer(controls_app, name="controls")
app.add_typer(ableton_app, name="ableton")
app.add_typer(performance_app, name="performance")
app.add_typer(snapshot_app, name="snapshot")
app.add_typer(backup_app, name="backup")
app.add_typer(automation_app, name="automation")
app.add_typer(inspect_app, name="inspect")
app.add_typer(rename_app, name="rename")
app.add_typer(current_app, name="current")
current_app.add_typer(current_pb_app, name="patchbay")
current_app.add_typer(current_ch_app, name="channels")
current_app.add_typer(current_path_app, name="path")
current_app.add_typer(current_gear_app, name="gear")
current_app.add_typer(current_midi_app, name="midi")
current_app.add_typer(current_controls_app, name="controls")
current_app.add_typer(current_performance_app, name="performance")


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


def _parse_ownership(raw: str) -> OwnershipStatus:
    try:
        return OwnershipStatus(raw.strip().upper().replace("-", "_"))
    except ValueError:
        _fail(
            "Invalid ownership status. Use OWNED, RETIRED, SOLD, "
            "LOANED_OUT, or UNKNOWN."
        )
        raise


def _parse_condition(raw: str) -> GearCondition:
    try:
        return GearCondition(raw.strip().upper())
    except ValueError:
        _fail("Invalid condition. Use WORKING, ISSUE, BROKEN, or UNKNOWN.")
        raise


@gear_app.command("list")
def gear_list_cmd(
    category: Optional[str] = typer.Option(None, "--category"),
    status: Optional[str] = typer.Option(None, "--status"),
) -> None:
    """List canonical owned-equipment records."""
    try:
        doc = load_inventory()
        wanted_status = _parse_ownership(status) if status else None
    except StoreError as exc:
        _fail(str(exc))
    items = [
        item
        for item in doc.items
        if (category is None or item.category.casefold() == category.casefold())
        and (wanted_status is None or item.ownership_status == wanted_status)
    ]
    table = Table(title="GEAR")
    for column in ("ID", "Name", "Category", "Qty", "Status", "Condition"):
        table.add_column(column)
    for item in items:
        table.add_row(
            item.id,
            item.name,
            item.category,
            str(item.quantity),
            item.ownership_status.value,
            item.condition.value,
        )
    console.print(table)


@gear_app.command("show")
def gear_show_cmd(gear_id: str) -> None:
    try:
        item = load_inventory().resolve(gear_id)
        if item is None:
            raise StoreError(f"Unknown gear ID {gear_id!r}.")
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"[bold]{item.id}[/bold] — {item.name}")
    console.print(f"Manufacturer: {item.manufacturer or '—'}")
    console.print(f"Model: {item.model or '—'}")
    console.print(f"Category: {item.category}")
    console.print(f"Quantity: {item.quantity}")
    console.print(f"Status: {item.ownership_status.value}")
    console.print(f"Condition: {item.condition.value}")
    console.print(f"Location: {item.location or '—'}")
    console.print(f"Notes: {item.notes or '—'}")
    if item.units:
        console.print("Units: " + ", ".join(unit.id for unit in item.units))


@gear_app.command("usage")
def gear_usage_cmd(gear_id: str) -> None:
    try:
        usage = gear_usage.usage_for(gear_id)
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"[bold]USAGE — {usage['gear_id']}[/bold]")
    console.print("")
    console.print("CURRENT routing:")
    if usage["routing"]:
        for ref in usage["routing"]:
            console.print(
                f"  {ref['path']}/{ref['branch']}  {ref['node']} — {ref['label']}"
            )
    else:
        console.print("  (none)")
    console.print("Wishlist:")
    if usage["wishlist"]:
        for name in usage["wishlist"]:
            console.print(f"  {name}")
    else:
        console.print("  (none)")
    console.print("Patchbay gear refs: (schema has no gear_ref field)")


def _commit_inventory_preview(
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
                current_service.commit_inventory(
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
        result = current_service.commit_inventory(
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


@current_gear_app.command("add")
def current_gear_add(
    gear_id: Optional[str] = typer.Option(None, "--id"),
    name: Optional[str] = typer.Option(None, "--name"),
    manufacturer: Optional[str] = typer.Option(None, "--manufacturer"),
    model: Optional[str] = typer.Option(None, "--model"),
    category: Optional[str] = typer.Option(None, "--category"),
    quantity: Optional[int] = typer.Option(None, "--quantity", min=1),
    notes: Optional[str] = typer.Option(None, "--notes"),
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    question: Optional[str] = typer.Option(None, "--question"),
    change: Optional[str] = typer.Option(None, "--change"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    if name is None:
        name = typer.prompt("Name")
    if manufacturer is None:
        manufacturer = typer.prompt("Manufacturer (optional)", default="")
    if model is None:
        model = typer.prompt("Model (optional)", default="")
    if category is None:
        category = typer.prompt("Category")
    if quantity is None:
        quantity = typer.prompt("Quantity", default=1, type=int)
    if notes is None:
        notes = typer.prompt("Notes (optional)", default="")
    if gear_id is None:
        gear_id = typer.prompt("ID (blank to generate)", default="") or None
    try:
        preview, data = inventory_state.propose_add(
            gear_id=gear_id,
            name=name,
            manufacturer=manufacturer,
            model=model,
            category=category,
            quantity=quantity,
            notes=notes,
        )
    except (StoreError, ValueError) as exc:
        _fail(str(exc))
    _commit_inventory_preview(
        preview,
        data,
        yes=yes,
        dry_run=dry_run,
        question=question,
        change=change,
        answer_hint=preview.target,
        no_render=no_render,
    )


def _gear_field_mutation(
    preview,
    data,
    *,
    yes: bool,
    dry_run: bool,
    question: Optional[str],
    change: Optional[str],
    no_render: bool,
) -> None:
    _commit_inventory_preview(
        preview,
        data,
        yes=yes,
        dry_run=dry_run,
        question=question,
        change=change,
        answer_hint=str(next(iter(preview.after.values()), "")),
        no_render=no_render,
    )


@current_gear_app.command("set-status")
def current_gear_set_status(
    gear_id: str,
    status: str,
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    question: Optional[str] = typer.Option(None, "--question"),
    change: Optional[str] = typer.Option(None, "--change"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        preview, data = inventory_state.propose_set_status(
            gear_id, _parse_ownership(status)
        )
    except StoreError as exc:
        _fail(str(exc))
    _gear_field_mutation(preview, data, yes=yes, dry_run=dry_run, question=question, change=change, no_render=no_render)


@current_gear_app.command("set-condition")
def current_gear_set_condition(
    gear_id: str,
    condition: str,
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    question: Optional[str] = typer.Option(None, "--question"),
    change: Optional[str] = typer.Option(None, "--change"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        preview, data = inventory_state.propose_set_condition(
            gear_id, _parse_condition(condition)
        )
    except StoreError as exc:
        _fail(str(exc))
    _gear_field_mutation(preview, data, yes=yes, dry_run=dry_run, question=question, change=change, no_render=no_render)


@current_gear_app.command("set-location")
def current_gear_set_location(
    gear_id: str,
    location: str,
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    question: Optional[str] = typer.Option(None, "--question"),
    change: Optional[str] = typer.Option(None, "--change"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        preview, data = inventory_state.propose_set_location(gear_id, location)
    except StoreError as exc:
        _fail(str(exc))
    _gear_field_mutation(preview, data, yes=yes, dry_run=dry_run, question=question, change=change, no_render=no_render)


@current_gear_app.command("retire")
def current_gear_retire(
    gear_id: str,
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    question: Optional[str] = typer.Option(None, "--question"),
    change: Optional[str] = typer.Option(None, "--change"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        preview, data = inventory_state.propose_retire(gear_id)
    except StoreError as exc:
        _fail(str(exc))
    _gear_field_mutation(preview, data, yes=yes, dry_run=dry_run, question=question, change=change, no_render=no_render)


@current_gear_app.command("acquire")
def current_gear_acquire(
    wishlist_item_name: str,
    gear_id: Optional[str] = typer.Option(None, "--id"),
    name: Optional[str] = typer.Option(None, "--name"),
    manufacturer: Optional[str] = typer.Option(None, "--manufacturer"),
    model: Optional[str] = typer.Option(None, "--model"),
    category: Optional[str] = typer.Option(None, "--category"),
    quantity: Optional[int] = typer.Option(None, "--quantity", min=1),
    notes: Optional[str] = typer.Option(None, "--notes"),
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    question: Optional[str] = typer.Option(None, "--question"),
    change: Optional[str] = typer.Option(None, "--change"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        wish = wishlist_service.get_item(load_wishlist(), wishlist_item_name)
    except StoreError as exc:
        _fail(str(exc))
    manufacturer = manufacturer if manufacturer is not None else typer.prompt("Manufacturer (optional)", default="")
    model = model if model is not None else typer.prompt("Model (optional)", default="")
    category = category if category is not None else typer.prompt("Category", default=wish.category)
    quantity = quantity if quantity is not None else typer.prompt("Quantity", default=1, type=int)
    notes = notes if notes is not None else typer.prompt("Notes (optional)", default="")
    gear_id = gear_id if gear_id is not None else (typer.prompt("ID (blank to generate)", default="") or None)
    todo = load_todo()
    related = [todo.task_map()[ref] for ref in wish.todo_refs if ref in todo.task_map()]
    console.print("Related TODOs:")
    if related:
        for task in related:
            console.print(f"  {task.id} {task.status.value} — {task.task}")
    else:
        console.print("  (none)")
    waiting = [task for task in related if task.status == TodoStatus.WAITING]
    ready = False
    if waiting and not yes:
        ready = typer.confirm("Change related WAITING TODOs to READY?", default=False)
    try:
        preview, inventory, wishes, todos = inventory_state.propose_acquire(
            wishlist_item_name,
            name=name,
            gear_id=gear_id,
            manufacturer=manufacturer,
            model=model,
            category=category,
            quantity=quantity,
            notes=notes,
            make_waiting_ready=ready,
        )
    except (StoreError, ValueError) as exc:
        _fail(str(exc))
    if not _confirm_current(preview, yes=yes, dry_run=dry_run):
        if dry_run:
            current_service.commit_acquisition(
                inventory,
                wishes,
                todos,
                preview,
                dry_run=True,
                render=False,
                question_id=question,
                change_id=change,
            )
            raise typer.Exit(0)
        raise typer.Abort()
    resolve_q, apply_chg, answer = _maybe_resolve_evidence(
        question_id=question,
        change_id=change,
        answer_hint=preview.target,
        yes=yes,
    )
    try:
        result = current_service.commit_acquisition(
            inventory,
            wishes,
            todos,
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


@current_pb_app.command("set-connection")
def current_pb_set_connection(
    bay_id: str,
    jack: str = typer.Argument(..., help="Upper jack N or pair N/M"),
    upper: Optional[str] = typer.Option(None, "--upper", help="Upper connection label"),
    lower: Optional[str] = typer.Option(None, "--lower", help="Lower connection label"),
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    """Set patchbay pair upper/lower endpoint connection labels."""
    if upper is None and lower is None:
        _fail("Provide --upper and/or --lower")
    try:
        preview, data = patchbay_state.propose_set_connection(
            bay_id,
            jack,
            upper_connection=upper,
            lower_connection=lower,
        )
    except StoreError as exc:
        _fail(str(exc))
    console.print(format_current_preview(preview).rstrip())
    if dry_run:
        console.print("[dim]Dry-run: nothing written.[/dim]")
        raise typer.Exit(0)
    if not preview.changed:
        console.print(preview.message)
        raise typer.Exit(0)
    if not yes and not typer.confirm("Apply?", default=False):
        raise typer.Abort()
    try:
        result = current_service.commit_patchbay(
            data,
            preview,
            render=not no_render,
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


def _midi_ref(value) -> str:
    return value.endpoint_ref or value.gear_ref or ""


@midi_app.command("summary")
def midi_summary() -> None:
    """Summarize canonical MIDI evidence without implying unknown links."""
    try:
        doc = midi_state.load_document()
    except StoreError as exc:
        _fail(str(exc))
    counts = {status.value: 0 for status in MidiEvidenceStatus}
    evidence = [
        *(item.status for item in doc.connections),
        *(item.status for item in doc.channels),
        *(item.status for item in doc.clock.destinations),
        *(item.status for item in doc.ableton_ports),
        doc.clock.transport.status,
    ]
    if doc.clock.master:
        evidence.append(doc.clock.master.status)
    for status in evidence:
        counts[status.value] += 1
    master = _midi_ref(doc.clock.master) if doc.clock.master else "UNKNOWN"
    console.print("[bold]MIDI SUMMARY[/bold]")
    console.print(f"Devices:       {len(doc.devices)}")
    console.print(f"Endpoints:     {len(doc.endpoints)}")
    console.print(f"Physical links:{len(doc.connections):>3}")
    console.print(f"Clock master:  {master}")
    console.print(
        "Evidence:      "
        + "  ".join(f"{key} {value}" for key, value in counts.items())
    )


@midi_app.command("devices")
def midi_devices() -> None:
    try:
        doc = load_midi()
    except StoreError as exc:
        _fail(str(exc))
    table = Table(title="MIDI DEVICES")
    for label in ("Gear ref", "Role", "Notes"):
        table.add_column(label)
    for item in doc.devices:
        table.add_row(item.gear_ref, item.role, item.notes or "—")
    console.print(table)


@midi_app.command("links")
def midi_links() -> None:
    try:
        doc = load_midi()
    except StoreError as exc:
        _fail(str(exc))
    table = Table(title="MIDI PHYSICAL LINKS")
    for label in ("ID", "Source", "Destination", "Transport", "Evidence"):
        table.add_column(label)
    for item in doc.connections:
        table.add_row(
            item.id,
            f"{item.source} / {item.source_port}",
            f"{item.destination} / {item.destination_port}",
            item.transport.value,
            item.status.value,
        )
    if not doc.connections:
        table.add_row("—", "UNKNOWN", "UNKNOWN", "—", "UNKNOWN")
    console.print(table)


@midi_app.command("channels")
def midi_channels() -> None:
    try:
        doc = load_midi()
    except StoreError as exc:
        _fail(str(exc))
    table = Table(title="MIDI CHANNELS")
    for label in ("Gear ref", "Channel", "Evidence", "Notes"):
        table.add_column(label)
    for item in doc.channels:
        table.add_row(
            item.gear_ref, str(item.channel), item.status.value, item.notes or "—"
        )
    console.print(table)


@midi_app.command("clock")
def midi_clock() -> None:
    try:
        doc = load_midi()
    except StoreError as exc:
        _fail(str(exc))
    if doc.clock.master:
        console.print(
            f"Master: {_midi_ref(doc.clock.master)} "
            f"({doc.clock.master.status.value})"
        )
    else:
        console.print("Master: UNKNOWN")
    table = Table(title="CLOCK DESTINATIONS")
    for label in ("Destination", "Enabled", "Evidence", "Notes"):
        table.add_column(label)
    for item in doc.clock.destinations:
        table.add_row(
            _midi_ref(item),
            item.enabled.value.upper(),
            item.status.value,
            item.notes or "—",
        )
    console.print(table)
    console.print(f"Transport start/stop: {doc.clock.transport.status.value}")


@midi_app.command("ableton")
def midi_ableton() -> None:
    try:
        doc = load_midi()
    except StoreError as exc:
        _fail(str(exc))
    table = Table(title="ABLETON MIDI PORTS")
    for label in ("ID", "Direction", "Reference", "Track", "Sync", "Remote", "Evidence"):
        table.add_column(label)
    for item in doc.ableton_ports:
        ref = item.endpoint_ref or item.gear_ref or item.port_name or "—"
        table.add_row(
            item.id,
            item.direction,
            ref,
            item.track.value.upper(),
            item.sync.value.upper(),
            item.remote.value.upper(),
            item.status.value,
        )
    if not doc.ableton_ports:
        table.add_row("—", "—", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN")
    console.print(table)


def _commit_midi_preview(
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
                current_service.commit_midi(
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
        result = current_service.commit_midi(
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


def _midi_mutation_options(
    preview,
    data,
    *,
    yes: bool,
    dry_run: bool,
    question: Optional[str],
    change: Optional[str],
    no_render: bool,
) -> None:
    _commit_midi_preview(
        preview,
        data,
        yes=yes,
        dry_run=dry_run,
        question=question,
        change=change,
        answer_hint=preview.message,
        no_render=no_render,
    )


@current_midi_app.command("set-channel")
def current_midi_set_channel(
    gear: str,
    channel: str,
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    question: Optional[str] = typer.Option(None, "--question"),
    change: Optional[str] = typer.Option(None, "--change"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        preview, data = midi_state.propose_set_channel(gear, channel)
    except StoreError as exc:
        _fail(str(exc))
    _midi_mutation_options(preview, data, yes=yes, dry_run=dry_run, question=question, change=change, no_render=no_render)


@current_midi_app.command("add-link")
def current_midi_add_link(
    source: str = typer.Option(..., "--source"),
    source_port: str = typer.Option(..., "--source-port"),
    destination: str = typer.Option(..., "--destination"),
    destination_port: str = typer.Option(..., "--destination-port"),
    transport: str = typer.Option(..., "--transport"),
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    question: Optional[str] = typer.Option(None, "--question"),
    change: Optional[str] = typer.Option(None, "--change"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        preview, data = midi_state.propose_add_link(
            source=source,
            source_port=source_port,
            destination=destination,
            destination_port=destination_port,
            transport=transport,
        )
    except StoreError as exc:
        _fail(str(exc))
    _midi_mutation_options(preview, data, yes=yes, dry_run=dry_run, question=question, change=change, no_render=no_render)


@current_midi_app.command("remove-link")
def current_midi_remove_link(
    link_id: str,
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    question: Optional[str] = typer.Option(None, "--question"),
    change: Optional[str] = typer.Option(None, "--change"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        preview, data = midi_state.propose_remove_link(link_id)
    except StoreError as exc:
        _fail(str(exc))
    _midi_mutation_options(preview, data, yes=yes, dry_run=dry_run, question=question, change=change, no_render=no_render)


@current_midi_app.command("set-clock-master")
def current_midi_set_clock_master(
    endpoint: str,
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    question: Optional[str] = typer.Option(None, "--question"),
    change: Optional[str] = typer.Option(None, "--change"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        preview, data = midi_state.propose_set_clock_master(endpoint)
    except StoreError as exc:
        _fail(str(exc))
    _midi_mutation_options(preview, data, yes=yes, dry_run=dry_run, question=question, change=change, no_render=no_render)


@current_midi_app.command("set-clock")
def current_midi_set_clock(
    gear_or_endpoint: str,
    enabled: str,
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    question: Optional[str] = typer.Option(None, "--question"),
    change: Optional[str] = typer.Option(None, "--change"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        preview, data = midi_state.propose_set_clock_destination(
            gear_or_endpoint, enabled
        )
    except StoreError as exc:
        _fail(str(exc))
    _midi_mutation_options(preview, data, yes=yes, dry_run=dry_run, question=question, change=change, no_render=no_render)


@current_midi_app.command("ableton-set")
def current_midi_ableton_set(
    port_id: str,
    track: Optional[str] = typer.Option(None, "--track"),
    sync: Optional[str] = typer.Option(None, "--sync"),
    remote: Optional[str] = typer.Option(None, "--remote"),
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    question: Optional[str] = typer.Option(None, "--question"),
    change: Optional[str] = typer.Option(None, "--change"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        preview, data = midi_state.propose_ableton_set(
            port_id, track=track, sync=sync, remote=remote
        )
    except StoreError as exc:
        _fail(str(exc))
    _midi_mutation_options(preview, data, yes=yes, dry_run=dry_run, question=question, change=change, no_render=no_render)


@current_midi_app.command("verify")
def current_midi_verify(
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    question: Optional[str] = typer.Option(None, "--question"),
    change: Optional[str] = typer.Option(None, "--change"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    """Walk known MIDI facts and apply selected verification as one transaction."""
    try:
        doc = midi_state.load_document()
    except StoreError as exc:
        _fail(str(exc))
    mutations: list[dict] = []
    for item in doc.channels:
        value = typer.prompt(
            f"Channel for {item.gear_ref}", default=str(item.channel)
        ).strip()
        if value:
            mutations.append(
                {"op": "set_channel", "gear_ref": item.gear_ref, "channel": value}
            )
    if doc.clock.master:
        master = typer.prompt(
            "Clock master", default=_midi_ref(doc.clock.master)
        ).strip()
        if master:
            mutations.append({"op": "set_clock_master", "ref": master})
    for item in doc.clock.destinations:
        value = typer.prompt(
            f"Clock to {_midi_ref(item)} (on/off/unknown)",
            default=item.enabled.value,
        ).strip()
        if value.lower() != "unknown" or item.enabled != MidiTriState.UNKNOWN:
            mutations.append(
                {
                    "op": "set_clock_destination",
                    "ref": _midi_ref(item),
                    "enabled": value,
                }
            )
    for port in doc.ableton_ports:
        values = {}
        for field in ("track", "sync", "remote"):
            current = getattr(port, field).value
            values[field] = typer.prompt(
                f"{port.id} {field} (on/off/unknown)", default=current
            ).strip()
        mutations.append({"op": "ableton_set", "port_id": port.id, **values})
    for link in doc.connections:
        label = (
            f"{link.id}: {link.source}/{link.source_port} -> "
            f"{link.destination}/{link.destination_port}"
        )
        if typer.confirm(
            f"Verified physical link {label}?",
            default=link.status == MidiEvidenceStatus.VERIFIED,
        ):
            mutations.append({"op": "verify_link", "link_id": link.id})
    try:
        preview, data = midi_state.propose_batch(mutations)
    except StoreError as exc:
        _fail(str(exc))
    _midi_mutation_options(preview, data, yes=yes, dry_run=dry_run, question=question, change=change, no_render=no_render)


def _controller_record(gear: str):
    doc = control_state.load_document()
    record = next((item for item in doc.controllers if item.gear_ref == gear), None)
    if record is None:
        raise StoreError(f"Unknown controller gear_ref {gear!r}.")
    return doc, record


@controls_app.command("summary")
def controls_summary() -> None:
    try:
        doc = control_state.load_document()
    except StoreError as exc:
        _fail(str(exc))
    table = Table(title="CONTROLLER MAPPINGS")
    for label in ("Gear ref", "Coverage", "Contexts", "Controls", "Mapped", "Gaps"):
        table.add_column(label)
    gaps = control_state.find_gaps(doc)
    for item in doc.controllers:
        controls = [control for context in item.contexts for control in context.controls]
        mapped = sum(control.target.state == TargetState.MAPPED for control in controls)
        item_gaps = sum(gap["gear"] == item.gear_ref for gap in gaps)
        table.add_row(
            item.gear_ref,
            item.coverage.value,
            str(len(item.contexts)),
            str(len(controls)),
            str(mapped),
            str(item_gaps),
        )
    console.print(table)


@controls_app.command("devices")
def controls_devices() -> None:
    controls_summary()


@controls_app.command("show")
def controls_show(gear: str) -> None:
    try:
        _doc, record = _controller_record(gear)
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"[bold]{record.gear_ref}[/bold] — {record.coverage.value}")
    console.print(record.notes or "—")
    table = Table(title="CONTROLS")
    for label in ("Context", "Control", "Type", "Availability", "Messages", "Target", "Evidence"):
        table.add_column(label)
    for context in record.contexts:
        for control in context.controls:
            messages = "; ".join(
                f"{m.type.value} {m.number} ch {m.channel or '—'} ({m.value_behavior.value})"
                for m in control.messages
            ) or "—"
            target = control.target.state.value
            if control.target.state == TargetState.MAPPED:
                ref = control.target.track or control.target.send or control.target.action or control.target.notes or "—"
                target = f"{control.target.kind.value}: {ref}"
            table.add_row(
                context.id,
                control.id,
                control.physical_type.value,
                control.availability.value,
                messages,
                target,
                control.evidence.value,
            )
    console.print(table)


@controls_app.command("contexts")
def controls_contexts(gear: Optional[str] = None) -> None:
    try:
        doc = control_state.load_document()
    except StoreError as exc:
        _fail(str(exc))
    table = Table(title="CONTROLLER CONTEXTS")
    for label in ("Gear ref", "ID", "Label", "Kind", "Evidence", "Controls"):
        table.add_column(label)
    for controller in doc.controllers:
        if gear and controller.gear_ref != gear:
            continue
        for context in controller.contexts:
            table.add_row(
                controller.gear_ref,
                context.id,
                context.label,
                context.kind.value,
                context.evidence.value,
                str(len(context.controls)),
            )
    console.print(table)


@controls_app.command("context")
def controls_context(gear: str, context_id: str) -> None:
    try:
        _doc, record = _controller_record(gear)
        context = next((item for item in record.contexts if item.id == context_id), None)
        if context is None:
            raise StoreError(f"Unknown controller context {gear}/{context_id}.")
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"[bold]{gear}/{context.id}[/bold] — {context.label}")
    console.print(f"Kind: {context.kind.value}  Evidence: {context.evidence.value}")
    console.print(context.notes or "—")
    for control in context.controls:
        console.print(
            f"{control.id}  {control.physical_type.value}  "
            f"{control.availability.value}  {control.target.state.value}"
        )
    if not context.controls:
        console.print("(no controls modeled)")


@controls_app.command("gaps")
def controls_gaps(gear: Optional[str] = None) -> None:
    try:
        gaps = control_state.find_gaps(control_state.load_document())
    except StoreError as exc:
        _fail(str(exc))
    table = Table(title="CONTROLLER MAPPING GAPS")
    for label in ("Gear ref", "Context", "Control", "Gap"):
        table.add_column(label)
    for gap in gaps:
        if gear and gap["gear"] != gear:
            continue
        table.add_row(gap["gear"], gap["context"], gap["control"], gap["gap"])
    console.print(table)


@controls_app.command("conflicts")
def controls_conflicts(gear: Optional[str] = None) -> None:
    try:
        conflicts = control_state.find_conflicts(control_state.load_document())
    except StoreError as exc:
        _fail(str(exc))
    table = Table(title="CONTROLLER MESSAGE CONFLICTS")
    for label in ("Gear ref", "Context", "Message", "Controls"):
        table.add_column(label)
    for conflict in conflicts:
        if gear and conflict["gear"] != gear:
            continue
        table.add_row(
            conflict["gear"],
            conflict["context"],
            conflict["message"],
            conflict["controls"],
        )
    if not conflicts:
        table.add_row("—", "—", "—", "none")
    console.print(table)


def _ableton_table(title: str, items, label_field: str) -> None:
    table = Table(title=title)
    for label in ("ID", "Label", "Evidence", "Notes"):
        table.add_column(label)
    for item in items:
        table.add_row(
            item.id,
            getattr(item, label_field),
            item.evidence.value,
            item.notes or "—",
        )
    console.print(table)


@ableton_app.command("tracks")
def ableton_tracks() -> None:
    try:
        doc = load_ableton()
    except StoreError as exc:
        _fail(str(exc))
    _ableton_table("ABLETON TRACKS", doc.tracks, "name")


@ableton_app.command("sends")
def ableton_sends() -> None:
    try:
        doc = load_ableton()
    except StoreError as exc:
        _fail(str(exc))
    _ableton_table("ABLETON SENDS", doc.sends, "label")


@ableton_app.command("targets")
def ableton_targets() -> None:
    try:
        doc = load_ableton()
    except StoreError as exc:
        _fail(str(exc))
    _ableton_table("ABLETON TRACKS", doc.tracks, "name")
    _ableton_table("ABLETON SENDS", doc.sends, "label")
    _ableton_table("ABLETON ACTIONS", doc.actions, "label")


@ableton_app.command("templates")
def ableton_templates() -> None:
    try:
        doc = ableton_state.load_document()
    except StoreError as exc:
        _fail(str(exc))
    table = Table(title="ABLETON TEMPLATES")
    for label in ("ID", "Label", "Tracks", "Sends", "Requirements", "Evidence"):
        table.add_column(label)
    for template in doc.templates:
        table.add_row(
            template.id,
            template.label,
            str(len(template.tracks)),
            str(len(template.sends)),
            ", ".join(template.requirements) or "—",
            template.evidence.value,
        )
    console.print(table)


@ableton_app.command("template")
def ableton_template(template_id: str) -> None:
    try:
        doc = ableton_state.load_document()
    except StoreError as exc:
        _fail(str(exc))
    template = next((item for item in doc.templates if item.id == template_id), None)
    if template is None:
        _fail(f"Unknown Ableton template {template_id!r}.")
    console.print(f"[bold]{template.label}[/bold]  {template.evidence.value}")
    console.print(template.notes or "—")
    tracks = Table(title="Tracks")
    for label in ("Track", "Role", "Active", "Record ready"):
        tracks.add_column(label)
    for track in template.tracks:
        tracks.add_row(
            track.track_ref,
            track.role,
            str(track.active).lower(),
            str(track.record_ready).lower(),
        )
    console.print(tracks)
    sends = Table(title="Sends")
    for label in ("Send", "Role", "Notes"):
        sends.add_column(label)
    for send in template.sends:
        sends.add_row(send.send_ref, send.role, send.notes or "—")
    console.print(sends)


def _performance_doc():
    try:
        return performance_state.load_document()
    except StoreError as exc:
        _fail(str(exc))


@performance_app.command("summary")
def performance_summary() -> None:
    doc = _performance_doc()
    readiness = performance_state.evaluate_readiness(doc)
    console.print("[bold]PERFORMANCE[/bold]")
    console.print(f"Modes:      {len(doc.modes)}")
    console.print(f"Actions:    {len(doc.actions)}")
    console.print(f"Bindings:   {len(doc.bindings)}")
    console.print(f"Recovery:   {len(doc.recovery)}")
    console.print(f"Readiness:  {readiness.result.value}")


@performance_app.command("modes")
def performance_modes() -> None:
    doc = _performance_doc()
    table = Table(title="PERFORMANCE MODES")
    for label in ("ID", "Label", "Required", "Optional", "Evidence"):
        table.add_column(label)
    for mode in doc.modes:
        table.add_row(
            mode.id,
            mode.label,
            str(len(mode.required_actions)),
            str(len(mode.optional_actions)),
            mode.evidence.value,
        )
    console.print(table)


@performance_app.command("mode")
def performance_mode(mode_id: str) -> None:
    doc = _performance_doc()
    mode = next((item for item in doc.modes if item.id == mode_id), None)
    if mode is None:
        _fail(f"Unknown performance mode {mode_id!r}.")
    console.print(f"[bold]{mode.label}[/bold]  {mode.evidence.value}")
    console.print(mode.purpose)
    console.print("")
    console.print("Required actions:")
    for action in mode.required_actions:
        console.print(f"  {action}")
    console.print("Optional actions:")
    for action in mode.optional_actions:
        console.print(f"  {action}")
    if mode.notes:
        console.print("")
        console.print(f"Notes: {mode.notes}")


@performance_app.command("actions")
def performance_actions() -> None:
    doc = _performance_doc()
    table = Table(title="PERFORMANCE ACTIONS")
    for label in ("ID", "Label", "Category", "Criticality", "Evidence", "Bindings"):
        table.add_column(label)
    for action in doc.actions:
        count = sum(binding.action_ref == action.id for binding in doc.bindings)
        table.add_row(
            action.id,
            action.label,
            action.category.value,
            action.criticality.value,
            action.evidence.value,
            str(count),
        )
    console.print(table)


@performance_app.command("action")
def performance_action(action_id: str) -> None:
    doc = _performance_doc()
    action = next((item for item in doc.actions if item.id == action_id), None)
    if action is None:
        _fail(f"Unknown performance action {action_id!r}.")
    console.print(
        f"[bold]{action.label}[/bold]  {action.category.value} / "
        f"{action.criticality.value} / {action.evidence.value}"
    )
    for effect in action.effects:
        console.print(
            f"  {effect.kind.value}: {effect.action_ref or effect.effect_id} "
            f"[{effect.evidence.value}]"
        )
    bindings = [item for item in doc.bindings if item.action_ref == action.id]
    console.print("Bindings:")
    for binding in bindings:
        console.print(
            f"  {binding.id}: {binding.controller_ref or binding.surface_ref}/"
            f"{binding.context_ref}/{binding.control_ref} [{binding.evidence.value}]"
        )
    if not bindings:
        console.print("  (none)")


@performance_app.command("bindings")
def performance_bindings() -> None:
    doc = _performance_doc()
    table = Table(title="PERFORMANCE BINDINGS")
    for label in ("ID", "Action", "Source", "Context", "Control", "Evidence", "Notes"):
        table.add_column(label)
    for binding in doc.bindings:
        table.add_row(
            binding.id,
            binding.action_ref,
            binding.controller_ref or binding.surface_ref or "—",
            binding.context_ref,
            binding.control_ref,
            binding.evidence.value,
            binding.notes or "—",
        )
    console.print(table)


@performance_app.command("recovery")
def performance_recovery(recovery_id: Optional[str] = None) -> None:
    doc = _performance_doc()
    values = doc.recovery
    if recovery_id is not None:
        values = [item for item in values if item.id == recovery_id]
        if not values:
            _fail(f"Unknown recovery scenario {recovery_id!r}.")
    table = Table(title="LIVE RECOVERY")
    for label in ("ID", "Label", "Severity", "Actions", "Keyboard/mouse", "Evidence"):
        table.add_column(label)
    for scenario in values:
        table.add_row(
            scenario.id,
            scenario.label,
            scenario.severity.value,
            ", ".join(scenario.action_refs) or "—",
            str(scenario.keyboard_mouse_required).lower(),
            scenario.evidence.value,
        )
    console.print(table)


@performance_app.command("readiness")
def performance_readiness() -> None:
    doc = _performance_doc()
    readiness = performance_state.evaluate_readiness(doc)
    console.print(f"[bold]{readiness.result.value}[/bold]")
    for reason in readiness.reasons:
        console.print(f"- {reason}")


@performance_app.command("gaps")
def performance_gaps() -> None:
    doc = _performance_doc()
    gaps = performance_state.find_gaps(doc)
    conflicts = performance_state.find_conflicts(doc)
    table = Table(title="PERFORMANCE GAPS")
    table.add_column("Scope")
    table.add_column("Gap")
    for gap in gaps:
        table.add_row(gap["scope"], gap["gap"])
    for conflict in conflicts:
        table.add_row(conflict["binding"], conflict["conflict"])
    if not gaps and not conflicts:
        table.add_row("—", "none")
    console.print(table)


@performance_app.command("plan")
def performance_plan_cmd(action_id: str) -> None:
    doc = _performance_doc()
    try:
        action = automation.get_action(doc, action_id)
    except StoreError as exc:
        _fail(str(exc))
    plan = automation.compile_action_plan(action)
    console.print(f"[bold]PLAN[/bold]  {plan.action_id}  ({plan.overall.value})")
    table = Table()
    for label in ("#", "Kind", "Ref", "Adapter", "State", "Detail"):
        table.add_column(label)
    for step in plan.steps:
        ref = step.effect.effect_id or step.effect.action_ref or "—"
        table.add_row(
            str(step.index),
            step.effect.kind.value,
            ref,
            step.adapter.value,
            step.state.value,
            step.detail,
        )
    console.print(table)


@performance_app.command("simulate")
def performance_simulate_cmd(action_id: str) -> None:
    doc = _performance_doc()
    try:
        action = automation.get_action(doc, action_id)
    except StoreError as exc:
        _fail(str(exc))
    report = automation.simulate_action(action)
    console.print(f"[bold]{report.banner}[/bold]")
    console.print("")
    console.print(f"Action: {report.action_id}")
    console.print(f"Result: {report.result.value}")
    for note in report.notes:
        console.print(f"- {note}")
    console.print("")
    table = Table(title="Simulated steps (not executed)")
    for label in ("#", "Kind", "Adapter", "State"):
        table.add_column(label)
    for step in report.plan.steps:
        table.add_row(
            str(step.index),
            step.effect.kind.value,
            step.adapter.value,
            step.state.value,
        )
    console.print(table)


@performance_app.command("preflight")
def performance_preflight_cmd(
    mode: str = typer.Option("pfl-jam", "--mode", help="Performance mode id"),
) -> None:
    try:
        report = automation.preflight(mode=mode)
    except StoreError as exc:
        _fail(str(exc))
    console.print(
        f"[bold]PREFLIGHT[/bold]  mode={report.mode}  worst={report.worst.value}"
    )
    console.print("Advisory only — never blocks play; no files modified.")
    console.print("")
    by_section: dict[str, list] = {}
    for finding in report.findings:
        by_section.setdefault(finding.section, []).append(finding)
    for section, findings in by_section.items():
        console.print(f"[bold]{section}[/bold]")
        for finding in findings:
            console.print(f"  {finding.severity.value}: {finding.message}")
        console.print("")


@snapshot_app.command("create")
def snapshot_create_cmd(
    output: Optional[Path] = typer.Option(
        None, "--output", help="Parent directory for SNAP-* folders"
    ),
) -> None:
    try:
        manifest = snapshot_service.create_snapshot(output_dir=output)
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"[bold]SNAPSHOT[/bold]  {manifest.snapshot_id}")
    console.print(f"Created:   {manifest.created_at}")
    console.print(f"Commit:    {manifest.git_commit or '—'}")
    console.print(f"Branch:    {manifest.git_branch or '—'}")
    tree = (
        "clean"
        if manifest.working_tree_clean
        else "dirty"
        if manifest.working_tree_clean is not None
        else "—"
    )
    console.print(f"Tree:      {tree}")
    console.print(f"Files:     {len(manifest.canonical_files)}")
    sync = manifest.generated_docs_synchronized
    console.print(
        f"Docs sync: {'yes' if sync else 'no' if sync is False else 'unknown'}"
    )


@snapshot_app.command("list")
def snapshot_list_cmd() -> None:
    items = snapshot_service.list_snapshots()
    if not items:
        console.print("(none)")
        return
    table = Table(title="SNAPSHOTS")
    for label in ("ID", "Created", "Commit", "Files"):
        table.add_column(label)
    for item in items:
        table.add_row(
            item.snapshot_id,
            item.created_at,
            item.git_commit or "—",
            str(len(item.canonical_files)),
        )
    console.print(table)


@snapshot_app.command("show")
def snapshot_show_cmd(snapshot_id: str) -> None:
    try:
        manifest = snapshot_service.show_snapshot(snapshot_id)
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"[bold]{manifest.snapshot_id}[/bold]")
    console.print(f"Created: {manifest.created_at}")
    console.print(f"Commit:  {manifest.git_commit or '—'}")
    console.print(f"Branch:  {manifest.git_branch or '—'}")
    console.print(f"Version: {manifest.tool_version}")
    console.print("")
    for record in manifest.canonical_files:
        console.print(f"  {record.path}  {record.sha256[:12]}…")


@snapshot_app.command("diff")
def snapshot_diff_cmd(left_id: str, right_id: str) -> None:
    try:
        diff = snapshot_service.diff_snapshots(left_id, right_id)
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"[bold]DIFF[/bold]  {diff['left']} → {diff['right']}")
    if not any((diff["only_left"], diff["only_right"], diff["changed"])):
        console.print("(identical)")
        return
    if diff["changed"]:
        console.print("Changed:")
        for path in diff["changed"]:
            console.print(f"  {path}")
    if diff["only_left"]:
        console.print(f"Only in {diff['left']}:")
        for path in diff["only_left"]:
            console.print(f"  {path}")
    if diff["only_right"]:
        console.print(f"Only in {diff['right']}:")
        for path in diff["only_right"]:
            console.print(f"  {path}")


@snapshot_app.command("verify")
def snapshot_verify_cmd(snapshot_id: str) -> None:
    try:
        ok, problems = snapshot_service.verify_snapshot(snapshot_id)
    except StoreError as exc:
        _fail(str(exc))
    if ok:
        console.print(f"[green]OK[/green]  {snapshot_id}")
        raise typer.Exit(0)
    console.print(f"[red]FAIL[/red]  {snapshot_id}")
    for problem in problems:
        console.print(f"  {problem}")
    raise typer.Exit(1)


@backup_app.command("plan")
def backup_plan_cmd() -> None:
    try:
        items = backup_state.plan_items()
    except StoreError as exc:
        _fail(str(exc))
    table = Table(title="BACKUP PLAN")
    for label in ("ID", "Kind", "Importance", "Locator", "Evidence"):
        table.add_column(label)
    for item in items:
        table.add_row(
            item.id,
            item.kind.value,
            item.importance.value,
            item.locator_key or "—",
            item.evidence.value,
        )
    console.print(table)


@backup_app.command("status")
def backup_status_cmd() -> None:
    try:
        statuses = backup_state.status_items()
    except StoreError as exc:
        _fail(str(exc))
    local = load_local_config()
    console.print(f"Local config: {'present' if local is not None else 'absent'}")
    table = Table(title="BACKUP STATUS")
    for label in ("ID", "Kind", "Importance", "Status", "Detail"):
        table.add_column(label)
    for status in statuses:
        table.add_row(
            status.item.id,
            status.item.kind.value,
            status.item.importance.value,
            status.readiness.value,
            status.detail or "—",
        )
    console.print(table)


@backup_app.command("create")
def backup_create_cmd(
    output: Optional[Path] = typer.Option(
        None, "--output", help="Parent directory for BACKUP-* packages"
    ),
) -> None:
    try:
        report = backup_state.create_backup_package(output=output)
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"[bold]BACKUP[/bold]  {report.backup_id}  {report.result.value}")
    console.print(f"Output:   {report.output_dir}")
    console.print(f"Snapshot: {report.snapshot_id or '—'}")
    for outcome in report.outcomes:
        console.print(f"  {outcome.item_id}: {outcome.status} — {outcome.detail}")
    if report.result == backup_state.BackupPackageResult.FAILED:
        raise typer.Exit(1)
    raise typer.Exit(0)


@automation_app.command("capabilities")
def automation_capabilities_cmd() -> None:
    table = Table(title="AUTOMATION CAPABILITIES")
    table.add_column("Adapter")
    table.add_column("Status")
    for family, status in automation.list_capabilities():
        table.add_row(family.value, status.value)
    console.print(table)
    console.print("")
    console.print(
        "OBS / Ableton / MIDI / macOS adapters are NOT_IMPLEMENTED — "
        "no fake success adapters."
    )


def _commit_performance_preview(
    preview, data: dict, *, yes: bool, dry_run: bool, no_render: bool
) -> None:
    if not _confirm_current(preview, yes=yes, dry_run=dry_run):
        if dry_run:
            current_service.commit_performance(
                data, preview, dry_run=True, render=False
            )
            raise typer.Exit(0)
        if not preview.changed:
            raise typer.Exit(0)
        raise typer.Abort()
    try:
        result = current_service.commit_performance(
            data, preview, render=not no_render
        )
    except StoreError as exc:
        _fail(str(exc))
    console.print(f"[green]Applied:[/green] {result.message}")


@current_performance_app.command("bind")
def current_performance_bind(
    action: str,
    controller: Optional[str] = typer.Option(None, "--controller"),
    surface: Optional[str] = typer.Option(None, "--surface"),
    context: str = typer.Option(..., "--context"),
    control: str = typer.Option(..., "--control"),
    evidence: str = typer.Option("INTENDED", "--evidence"),
    notes: str = typer.Option("", "--notes"),
    binding_id: Optional[str] = typer.Option(None, "--id"),
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        preview, data = performance_state.propose_bind(
            action,
            context,
            control,
            controller_ref=controller,
            surface_ref=surface,
            evidence=evidence,
            notes=notes,
            binding_id=binding_id,
        )
    except (StoreError, ValueError) as exc:
        _fail(str(exc))
    _commit_performance_preview(
        preview, data, yes=yes, dry_run=dry_run, no_render=no_render
    )


@current_performance_app.command("unbind")
def current_performance_unbind(
    binding_id: str,
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    doc = _performance_doc()
    binding = next((item for item in doc.bindings if item.id == binding_id), None)
    if binding is None:
        _fail(f"Unknown performance binding {binding_id!r}.")
    action = next(item for item in doc.actions if item.id == binding.action_ref)
    action_bindings = [item for item in doc.bindings if item.action_ref == action.id]
    if (
        action.criticality == PerformanceCriticality.EMERGENCY
        and len(action_bindings) == 1
    ):
        console.print(
            f"[yellow]Warning:[/yellow] {binding_id} is the last binding for "
            f"EMERGENCY action {action.id}."
        )
        if not dry_run and not yes and not typer.confirm("Remove it?", default=False):
            raise typer.Abort()
        if not dry_run:
            yes = True
    try:
        preview, data = performance_state.propose_unbind(binding_id)
    except StoreError as exc:
        _fail(str(exc))
    _commit_performance_preview(
        preview, data, yes=yes, dry_run=dry_run, no_render=no_render
    )


@current_performance_app.command("set-evidence")
def current_performance_set_evidence(
    binding_id: str,
    evidence: str,
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        preview, data = performance_state.propose_set_evidence(binding_id, evidence)
    except (StoreError, ValueError) as exc:
        _fail(str(exc))
    _commit_performance_preview(
        preview, data, yes=yes, dry_run=dry_run, no_render=no_render
    )


@current_performance_app.command("set-recovery-evidence")
def current_performance_set_recovery_evidence(
    recovery_id: str,
    evidence: str,
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        preview, data = performance_state.propose_set_recovery_evidence(
            recovery_id, evidence
        )
    except (StoreError, ValueError) as exc:
        _fail(str(exc))
    _commit_performance_preview(
        preview, data, yes=yes, dry_run=dry_run, no_render=no_render
    )


@current_performance_app.command("verify")
def current_performance_verify(
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    doc = _performance_doc()
    mutations = []
    for binding in doc.bindings:
        verified = typer.confirm(
            f"Verified binding {binding.id} as modeled?",
            default=binding.evidence == MidiEvidenceStatus.VERIFIED,
        )
        mutations.append(
            {
                "op": "set_evidence",
                "binding_id": binding.id,
                "evidence": "VERIFIED" if verified else binding.evidence.value,
            }
        )
    for scenario in doc.recovery:
        verified = typer.confirm(
            f"Verified recovery {scenario.id} as executable?",
            default=scenario.evidence == MidiEvidenceStatus.VERIFIED,
        )
        mutations.append(
            {
                "op": "set_recovery_evidence",
                "recovery_id": scenario.id,
                "evidence": "VERIFIED" if verified else scenario.evidence.value,
            }
        )
    try:
        preview, data = performance_state.propose_batch(mutations)
    except StoreError as exc:
        _fail(str(exc))
    _commit_performance_preview(
        preview, data, yes=yes, dry_run=dry_run, no_render=no_render
    )


def _commit_controls_preview(
    preview,
    data: dict,
    *,
    yes: bool,
    dry_run: bool,
    question: Optional[str],
    change: Optional[str],
    no_render: bool,
) -> None:
    if not _confirm_current(preview, yes=yes, dry_run=dry_run):
        if dry_run:
            current_service.commit_controllers(
                data,
                preview,
                dry_run=True,
                render=False,
                question_id=question,
                change_id=change,
            )
            raise typer.Exit(0)
        if not preview.changed:
            raise typer.Exit(0)
        raise typer.Abort()
    resolve_q, apply_chg, answer = _maybe_resolve_evidence(
        question_id=question,
        change_id=change,
        answer_hint=preview.message,
        yes=yes,
    )
    try:
        result = current_service.commit_controllers(
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


def _message_from_cli(
    message_type: str, number: int, channel: Optional[str], behavior: str
) -> MidiMessage:
    channel_value: int | str | None = channel
    if channel and channel.isdigit():
        channel_value = int(channel)
    return MidiMessage(
        type=MidiMessageType(message_type.strip().upper().replace("-", "_")),
        number=number,
        channel=channel_value,
        value_behavior=ValueBehavior(behavior.strip().lower()),
    )


def _control_options(preview, data, yes, dry_run, question, change, no_render):
    _commit_controls_preview(
        preview,
        data,
        yes=yes,
        dry_run=dry_run,
        question=question,
        change=change,
        no_render=no_render,
    )


@current_controls_app.command("set-message")
def current_controls_set_message(
    gear: str,
    context: str,
    control: str,
    message_type: str,
    number: int = typer.Argument(..., min=0, max=127),
    channel: Optional[str] = typer.Option(None, "--channel"),
    behavior: str = typer.Option("fixed", "--behavior"),
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    question: Optional[str] = typer.Option(None, "--question"),
    change: Optional[str] = typer.Option(None, "--change"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        preview, data = control_state.propose_set_message(
            gear, context, control, _message_from_cli(message_type, number, channel, behavior)
        )
    except (StoreError, ValueError) as exc:
        _fail(str(exc))
    _control_options(preview, data, yes, dry_run, question, change, no_render)


@current_controls_app.command("add-message")
def current_controls_add_message(
    gear: str,
    context: str,
    control: str,
    message_type: str,
    number: int = typer.Argument(..., min=0, max=127),
    channel: Optional[str] = typer.Option(None, "--channel"),
    behavior: str = typer.Option("fixed", "--behavior"),
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    question: Optional[str] = typer.Option(None, "--question"),
    change: Optional[str] = typer.Option(None, "--change"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        preview, data = control_state.add_message(
            gear, context, control, _message_from_cli(message_type, number, channel, behavior)
        )
    except (StoreError, ValueError) as exc:
        _fail(str(exc))
    _control_options(preview, data, yes, dry_run, question, change, no_render)


@current_controls_app.command("remove-message")
def current_controls_remove_message(
    gear: str,
    context: str,
    control: str,
    index: int = typer.Argument(0, min=0),
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    question: Optional[str] = typer.Option(None, "--question"),
    change: Optional[str] = typer.Option(None, "--change"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        preview, data = control_state.remove_message(gear, context, control, index)
    except StoreError as exc:
        _fail(str(exc))
    _control_options(preview, data, yes, dry_run, question, change, no_render)


@current_controls_app.command("clear-message")
def current_controls_clear_message(
    gear: str,
    context: str,
    control: str,
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    question: Optional[str] = typer.Option(None, "--question"),
    change: Optional[str] = typer.Option(None, "--change"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        preview, data = control_state.clear_messages(gear, context, control)
    except StoreError as exc:
        _fail(str(exc))
    _control_options(preview, data, yes, dry_run, question, change, no_render)


@current_controls_app.command("set-target")
def current_controls_set_target(
    gear: str,
    context: str,
    control: str,
    state: str,
    kind: Optional[str] = typer.Option(None, "--kind"),
    track: Optional[str] = typer.Option(None, "--track"),
    send: Optional[str] = typer.Option(None, "--send"),
    action: Optional[str] = typer.Option(None, "--action"),
    notes: Optional[str] = typer.Option(None, "--notes"),
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    question: Optional[str] = typer.Option(None, "--question"),
    change: Optional[str] = typer.Option(None, "--change"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        target = ControlTarget(
            state=TargetState(state.upper()),
            kind=TargetKind(kind.upper()) if kind else None,
            track=track,
            send=send,
            action=action,
            notes=notes,
        )
        preview, data = control_state.propose_set_target(gear, context, control, target)
    except (StoreError, ValueError) as exc:
        _fail(str(exc))
    _control_options(preview, data, yes, dry_run, question, change, no_render)


@current_controls_app.command("clear-target")
def current_controls_clear_target(
    gear: str,
    context: str,
    control: str,
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    question: Optional[str] = typer.Option(None, "--question"),
    change: Optional[str] = typer.Option(None, "--change"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        preview, data = control_state.clear_target(gear, context, control)
    except StoreError as exc:
        _fail(str(exc))
    _control_options(preview, data, yes, dry_run, question, change, no_render)


@current_controls_app.command("set-evidence")
def current_controls_set_evidence(
    gear: str,
    context: str,
    control: str,
    evidence: str,
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    question: Optional[str] = typer.Option(None, "--question"),
    change: Optional[str] = typer.Option(None, "--change"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        preview, data = control_state.propose_set_evidence(
            gear, context, control, evidence
        )
    except (StoreError, ValueError) as exc:
        _fail(str(exc))
    _control_options(preview, data, yes, dry_run, question, change, no_render)


@current_controls_app.command("set-availability")
def current_controls_set_availability(
    gear: str,
    context: str,
    control: str,
    availability: str,
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    question: Optional[str] = typer.Option(None, "--question"),
    change: Optional[str] = typer.Option(None, "--change"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    try:
        preview, data = control_state.propose_set_availability(
            gear, context, control, availability
        )
    except (StoreError, ValueError) as exc:
        _fail(str(exc))
    _control_options(preview, data, yes, dry_run, question, change, no_render)


@current_controls_app.command("verify")
def current_controls_verify(
    gear: str,
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    question: Optional[str] = typer.Option(None, "--question"),
    change: Optional[str] = typer.Option(None, "--change"),
    no_render: bool = typer.Option(False, "--no-render"),
) -> None:
    """Review modeled controls and apply evidence changes as one transaction."""
    try:
        _doc, record = _controller_record(gear)
    except StoreError as exc:
        _fail(str(exc))
    mutations = []
    for context in record.contexts:
        console.print(f"[bold]{context.id}[/bold] — {context.label}")
        if not context.controls:
            console.print("  no controls modeled; no assignments inferred")
        for control in context.controls:
            verified = typer.confirm(
                f"Verified {control.id} message/target as modeled?",
                default=control.evidence == MidiEvidenceStatus.VERIFIED,
            )
            mutations.append(
                {
                    "op": "set_evidence",
                    "context_id": context.id,
                    "control_id": control.id,
                    "evidence": "VERIFIED" if verified else control.evidence.value,
                }
            )
    try:
        preview, data = control_state.propose_batch(mutations, gear_ref=gear)
    except StoreError as exc:
        _fail(str(exc))
    _control_options(preview, data, yes, dry_run, question, change, no_render)


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


def _reconcile_emit(payload: dict, *, as_json: bool, exit_code: int = 0) -> None:
    if as_json:
        # Plain JSON only — no Rich markup / ANSI.
        typer.echo(json.dumps(payload, indent=2, default=str))
    else:
        if payload.get("ok"):
            console.print_json(data=payload.get("result", payload))
        else:
            err = payload.get("error") or {}
            console.print(f"[red]{err.get('code', 'error')}:[/red] {err.get('message')}")
    if exit_code:
        raise typer.Exit(exit_code)


@reconcile_app.command("status")
def reconcile_status_cmd(
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Legacy advisory summary (also the default for `rig reconcile`)."""
    try:
        text = build_reconcile_summary()
        if as_json:
            _reconcile_emit(
                ok_payload("status", {"text": text.rstrip()}), as_json=True
            )
        else:
            console.print(text.rstrip())
    except StoreError as exc:
        if as_json:
            _reconcile_emit(
                err_payload("store_error", str(exc)), as_json=True, exit_code=1
            )
        _fail(str(exc))


@reconcile_app.command("queue")
def reconcile_queue_cmd(
    artifact_type: Optional[str] = typer.Option(None, "--type"),
    state: Optional[str] = typer.Option(None, "--state"),
    ready: bool = typer.Option(False, "--ready"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    try:
        items = reconcile_service.build_queue(
            artifact_type=artifact_type, state=state, ready=ready
        )
        payload = ok_payload(
            "queue", {"items": [i.to_dict() for i in items], "count": len(items)}
        )
        if as_json:
            _reconcile_emit(payload, as_json=True)
            return
        console.print(f"[bold]RECONCILE QUEUE[/bold] ({len(items)})")
        for item in items:
            console.print(
                f"  {item.artifact_type:<8} {item.artifact_id:<8} "
                f"{item.state.value:<20} {item.summary[:60]}"
            )
    except StoreError as exc:
        if as_json:
            _reconcile_emit(
                err_payload("store_error", str(exc)), as_json=True, exit_code=1
            )
            return
        _fail(str(exc))
    except ValueError as exc:
        if as_json:
            _reconcile_emit(
                err_payload("invalid_state", str(exc)), as_json=True, exit_code=1
            )
            return
        _fail(str(exc))


@reconcile_app.command("show")
def reconcile_show_cmd(
    artifact_type: str = typer.Argument(...),
    artifact_id: str = typer.Argument(...),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    try:
        result = reconcile_service.show_artifact(artifact_type, artifact_id)
        if as_json:
            _reconcile_emit(ok_payload("show", result), as_json=True)
            return
        if "advisory" in result:
            console.print(result["advisory"])
        else:
            console.print_json(data=result)
    except StoreError as exc:
        if as_json:
            _reconcile_emit(
                err_payload("store_error", str(exc)), as_json=True, exit_code=1
            )
            return
        _fail(str(exc))


@reconcile_app.command("plan")
def reconcile_plan_cmd(
    artifact_type: str = typer.Argument(...),
    artifact_id: str = typer.Argument(...),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    try:
        kind = artifact_type.strip().lower()
        if kind not in {"question", "questions", "q"}:
            raise StoreError("plan currently supports question artifacts only")
        plan = reconcile_service.plan_question(artifact_id)
        payload = ok_payload("plan", plan.to_dict())
        if as_json:
            # Exit 0 even for NEEDS_AGENT_ACTION
            _reconcile_emit(payload, as_json=True, exit_code=0)
            return
        console.print(f"[bold]PLAN {artifact_id}[/bold]  {plan.state.value}")
        console.print(f"Capability: {plan.capability.value}")
        if plan.current is not None:
            console.print(f"CURRENT: {plan.current}")
        if plan.desired is not None:
            console.print(f"Desired: {plan.desired}")
        for op in plan.operations:
            console.print(f"  op: {op}")
        for b in plan.blockers:
            console.print(f"  blocker: {b}")
        for cmd in plan.suggested_commands:
            console.print(f"  $ {cmd}")
    except StoreError as exc:
        if as_json:
            _reconcile_emit(
                err_payload("store_error", str(exc)), as_json=True, exit_code=1
            )
            return
        _fail(str(exc))


@reconcile_app.command("apply")
def reconcile_apply_cmd(
    artifact_type: str = typer.Argument(...),
    artifact_id: str = typer.Argument(...),
    dry_run: bool = typer.Option(False, "--dry-run"),
    yes: bool = typer.Option(False, "--yes"),
    snapshot_before: bool = typer.Option(False, "--snapshot-before"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    try:
        kind = artifact_type.strip().lower()
        if kind not in {"question", "questions", "q"}:
            raise StoreError("apply currently supports question artifacts only")
        result = reconcile_service.apply_question(
            artifact_id,
            dry_run=dry_run,
            yes=yes,
            snapshot_before=snapshot_before,
        )
        payload = ok_payload("apply", result)
        if as_json:
            _reconcile_emit(payload, as_json=True)
            return
        console.print(f"[bold]APPLY {artifact_id}[/bold]")
        console.print_json(data=result)
    except StoreError as exc:
        if as_json:
            _reconcile_emit(
                err_payload("store_error", str(exc)), as_json=True, exit_code=1
            )
            return
        _fail(str(exc))
    except NotImplementedError as exc:
        if as_json:
            _reconcile_emit(
                err_payload("not_supported", str(exc)), as_json=True, exit_code=1
            )
            return
        _fail(str(exc))


@reconcile_app.command("verify")
def reconcile_verify_cmd(
    artifact_type: str = typer.Argument(...),
    artifact_id: str = typer.Argument(...),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    try:
        kind = artifact_type.strip().lower()
        if kind not in {"question", "questions", "q"}:
            raise StoreError("verify currently supports question artifacts only")
        result = reconcile_service.verify_question(artifact_id)
        verification = result.get("verification")
        exit_code = 1 if verification == "MISMATCH" else 0
        payload = ok_payload("verify", result)
        # Documented: ok:true with verification=MISMATCH and exit 1
        if as_json:
            _reconcile_emit(payload, as_json=True, exit_code=exit_code)
            return
        console.print(
            f"[bold]VERIFY {artifact_id}[/bold]  {verification}  state={result.get('state')}"
        )
        console.print(result.get("verify", {}).get("message", ""))
        if exit_code:
            raise typer.Exit(exit_code)
    except StoreError as exc:
        if as_json:
            _reconcile_emit(
                err_payload("store_error", str(exc)), as_json=True, exit_code=1
            )
            return
        _fail(str(exc))


@reconcile_app.command("finalize")
def reconcile_finalize_cmd(
    artifact_type: str = typer.Argument(...),
    artifact_id: str = typer.Argument(...),
    dry_run: bool = typer.Option(False, "--dry-run"),
    yes: bool = typer.Option(False, "--yes"),
    as_json: bool = typer.Option(False, "--json"),
    complete_linked_todos: bool = typer.Option(False, "--complete-linked-todos"),
    apply_linked_changes: bool = typer.Option(False, "--apply-linked-changes"),
    confirm_dod: bool = typer.Option(False, "--confirm-dod"),
    no_current_change: bool = typer.Option(False, "--no-current-change"),
    note: str = typer.Option("", "--note"),
    snapshot_before: bool = typer.Option(False, "--snapshot-before"),
) -> None:
    try:
        kind = artifact_type.strip().lower()
        if kind not in {"question", "questions", "q"}:
            raise StoreError("finalize currently supports question artifacts only")
        result = reconcile_service.finalize_question(
            artifact_id,
            dry_run=dry_run,
            yes=yes,
            complete_linked_todos=complete_linked_todos,
            apply_linked_changes=apply_linked_changes,
            confirm_dod=confirm_dod,
            no_current_change=no_current_change,
            note=note,
            snapshot_before=snapshot_before,
        )
        payload = ok_payload("finalize", result)
        if as_json:
            _reconcile_emit(payload, as_json=True)
            return
        console.print(f"[bold]FINALIZE {artifact_id}[/bold]")
        console.print_json(data=result)
    except StoreError as exc:
        if as_json:
            _reconcile_emit(
                err_payload("store_error", str(exc)), as_json=True, exit_code=1
            )
            return
        _fail(str(exc))


@reconcile_app.command("sweep")
def reconcile_sweep_cmd(
    dry_run: bool = typer.Option(True, "--dry-run/--write"),
    yes: bool = typer.Option(False, "--yes"),
    confirm_dod: bool = typer.Option(False, "--confirm-dod"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Finalize CURRENT_MATCHES / READY_TO_FINALIZE only. Never answers OPEN."""
    try:
        # Default dry-run=True; --write clears dry_run
        result = reconcile_service.sweep(
            dry_run=dry_run, yes=yes, confirm_dod=confirm_dod
        )
        payload = ok_payload("sweep", result)
        if as_json:
            _reconcile_emit(payload, as_json=True)
            return
        console.print("[bold]SWEEP[/bold]")
        console.print_json(data=result)
    except StoreError as exc:
        if as_json:
            _reconcile_emit(
                err_payload("store_error", str(exc)), as_json=True, exit_code=1
            )
            return
        _fail(str(exc))


@reconcile_app.command("change")
def reconcile_change_cmd(
    chg_id: str,
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Legacy: wrap show change."""
    try:
        if as_json:
            result = reconcile_service.show_change(chg_id)
            _reconcile_emit(ok_payload("show", result), as_json=True)
            return
        console.print(format_reconcile_change(chg_id).rstrip())
    except StoreError as exc:
        if as_json:
            _reconcile_emit(
                err_payload("store_error", str(exc)), as_json=True, exit_code=1
            )
            return
        _fail(str(exc))


@reconcile_app.command("question")
def reconcile_question_cmd(
    question_id: str,
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Legacy: wrap show question."""
    try:
        if as_json:
            result = reconcile_service.show_question(question_id)
            _reconcile_emit(ok_payload("show", result), as_json=True)
            return
        console.print(format_reconcile_question(question_id).rstrip())
    except StoreError as exc:
        if as_json:
            _reconcile_emit(
                err_payload("store_error", str(exc)), as_json=True, exit_code=1
            )
            return
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


@app.command("tui")
def tui_cmd(
    domain: Optional[str] = typer.Argument(
        None,
        help="Optional domain route (question, patchbay, todo, …).",
    ),
    object_id: Optional[str] = typer.Argument(
        None,
        help="Optional object id (Q-008, PB-B, …).",
    ),
) -> None:
    """Interactive Textual TUI (presentation only; mutations via shared services)."""
    from music_rig.tui import run_tui
    from music_rig.tui.navigation import normalize_route

    if domain is not None and normalize_route(domain) is None:
        _fail(
            f"Unknown TUI domain {domain!r}. "
            "Try: question, patchbay, todo, wish, inbox, changes, gear, channels, "
            "routing, midi, controls, ableton, performance, snapshot, backup, session, "
            "doctor, status, reconcile, automation"
        )
    run_tui(route=domain, object_id=object_id)


@inspect_app.command("domains")
def inspect_domains(
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    from music_rig import inspect_service

    payload = inspect_service.list_domains()
    console.print(inspect_service.dumps(payload, as_json=as_json))


@inspect_app.command("schema")
def inspect_schema(
    domain: str,
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    from music_rig import inspect_service

    try:
        payload = inspect_service.schema_for(domain)
    except StoreError as exc:
        _fail(str(exc))
    console.print(inspect_service.dumps(payload, as_json=True if as_json else True))


@inspect_app.command("list")
def inspect_list(
    domain: str,
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    from music_rig import inspect_service

    try:
        payload = inspect_service.list_records(domain)
    except StoreError as exc:
        _fail(str(exc))
    console.print(inspect_service.dumps(payload, as_json=as_json))


@inspect_app.command("show")
def inspect_show(
    domain: str,
    record_id: str,
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    from music_rig import inspect_service

    try:
        payload = inspect_service.show_record(domain, record_id)
    except StoreError as exc:
        _fail(str(exc))
    console.print(inspect_service.dumps(payload, as_json=True if as_json else True))


@inspect_app.command("refs")
def inspect_refs(
    record_id: str,
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    from music_rig import inspect_service

    payload = inspect_service.find_refs(record_id)
    console.print(inspect_service.dumps(payload, as_json=as_json or True))


@inspect_app.command("cleanup")
def inspect_cleanup(
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Scan for dangling refs / BROKEN+mapped. No --fix-all."""
    from music_rig import inspect_service

    payload = inspect_service.cleanup_scan()
    console.print(inspect_service.dumps(payload, as_json=as_json or True))
    if payload.get("count"):
        raise typer.Exit(1)


@rename_app.command("preview")
def rename_preview(domain: str, old_id: str, new_id: str) -> None:
    from music_rig import rename_service

    preview = rename_service.analyze_rename(domain, old_id, new_id)
    console.print(f"Domain: {preview.domain}")
    console.print(f"{preview.old_id} -> {preview.new_id}")
    for line in preview.replacements:
        console.print(f"  - {line}")
    for path in preview.affected_files:
        console.print(f"  file: {path}")
    for err in preview.errors:
        err_console.print(f"[red]{err}[/red]")
    if not preview.ok:
        raise typer.Exit(1)


@rename_app.command("apply")
def rename_apply(
    domain: str,
    old_id: str,
    new_id: str,
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    from music_rig import rename_service

    preview = rename_service.analyze_rename(domain, old_id, new_id)
    for err in preview.errors:
        err_console.print(f"[red]{err}[/red]")
    if not preview.ok:
        raise typer.Exit(1)
    console.print(f"Will rename {preview.old_id} -> {preview.new_id}")
    for line in preview.replacements:
        console.print(f"  - {line}")
    if dry_run:
        console.print("[dim]Dry-run: nothing written.[/dim]")
        raise typer.Exit(0)
    if not yes and not typer.confirm("Apply all-or-nothing rename?", default=False):
        raise typer.Abort()
    rename_service.apply_rename(domain, old_id, new_id)
    console.print("[green]Rename applied.[/green]")


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
