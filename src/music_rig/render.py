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
from music_rig.routing_projections import (
    render_aux_send_loop_mermaid,
    render_current_routing_section,
    render_pedal_chains_section,
)
from music_rig.inventory_projections import render_inventory_section
from music_rig.midi_projections import (
    render_midi_clock_section,
    render_midi_topology_mermaid,
    render_midi_topology_section,
)
from music_rig.control_projections import render_controller_mappings_section
from music_rig.ableton_projections import render_ableton_section
from music_rig.performance_projections import (
    render_live_recovery_doc,
    render_performance_doc,
)
from music_rig import (
    ableton_state,
    channel_state,
    control_state,
    control_surface_state,
    inventory_state,
    midi_state,
    patchbay_state,
    performance_state,
    routing_state,
)
from music_rig.store import (
    ABLETON_PATH,
    CHANNEL_MAP_PATH,
    CONTROLLERS_PATH,
    CONTROL_SURFACES_PATH,
    DIAGRAM_AUX_LOOP_PATH,
    DIAGRAM_PATCHBAYS_PATH,
    DIAGRAM_TASCAM_PATH,
    DIAGRAM_MIDI_TOPOLOGY_PATH,
    DOCS_ALESIS_PATH,
    DOCS_ABLETON_PATH,
    DOCS_LIVE_RECOVERY_PATH,
    DOCS_PERFORMANCE_PATH,
    DOCS_CONTROLLERS_PATH,
    DOCS_PATCHBAYS_PATH,
    DOCS_PEDAL_CHAINS_PATH,
    DOCS_INVENTORY_PATH,
    DOCS_MIDI_CLOCK_PATH,
    DOCS_MIDI_TOPOLOGY_PATH,
    DOCS_QUESTIONS_PATH,
    DOCS_ROUTING_PATH,
    DOCS_TASCAM_PATH,
    DOCS_TODO_PATH,
    DOCS_WISHLIST_PATH,
    PATCHBAYS_PATH,
    QUESTIONS_PATH,
    ROUTING_PATH,
    INVENTORY_PATH,
    MIDI_PATH,
    PERFORMANCE_PATH,
    TODO_PATH,
    WISHLIST_PATH,
    StoreError,
    load_questions,
    load_inventory,
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
ROUTING_START = "<!-- rig:routing:start -->"
ROUTING_END = "<!-- rig:routing:end -->"
PEDAL_CHAINS_START = "<!-- rig:pedal-chains:start -->"
PEDAL_CHAINS_END = "<!-- rig:pedal-chains:end -->"
INVENTORY_START = "<!-- rig:inventory:start -->"
INVENTORY_END = "<!-- rig:inventory:end -->"
MIDI_TOPOLOGY_START = "<!-- rig:midi-topology:start -->"
MIDI_TOPOLOGY_END = "<!-- rig:midi-topology:end -->"
MIDI_CLOCK_START = "<!-- rig:midi-clock:start -->"
MIDI_CLOCK_END = "<!-- rig:midi-clock:end -->"
CONTROLLERS_START = "<!-- rig:controllers:start -->"
CONTROLLERS_END = "<!-- rig:controllers:end -->"
ABLETON_START = "<!-- rig:ableton:start -->"
ABLETON_END = "<!-- rig:ableton:end -->"

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


def apply_routing_render(markdown: str, data: dict) -> str:
    return _replace_region(
        markdown, ROUTING_START, ROUTING_END, render_current_routing_section(data)
    )


def apply_pedal_chains_render(markdown: str, data: dict) -> str:
    return _replace_region(
        markdown, PEDAL_CHAINS_START, PEDAL_CHAINS_END, render_pedal_chains_section(data)
    )


def apply_inventory_render(markdown: str, doc) -> str:
    return _replace_region(
        markdown, INVENTORY_START, INVENTORY_END, render_inventory_section(doc)
    )


def apply_midi_topology_render(markdown: str, doc) -> str:
    return _replace_region(
        markdown,
        MIDI_TOPOLOGY_START,
        MIDI_TOPOLOGY_END,
        render_midi_topology_section(doc),
    )


def apply_midi_clock_render(markdown: str, doc) -> str:
    return _replace_region(
        markdown, MIDI_CLOCK_START, MIDI_CLOCK_END, render_midi_clock_section(doc)
    )


def apply_controllers_render(markdown: str, doc) -> str:
    return _replace_region(
        markdown, CONTROLLERS_START, CONTROLLERS_END, render_controller_mappings_section(doc)
    )


def apply_ableton_render(markdown: str, doc) -> str:
    return _replace_region(
        markdown, ABLETON_START, ABLETON_END, render_ableton_section(doc)
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
    docs_routing: Path | None = None,
    docs_pedal_chains: Path | None = None,
    diagram_patchbays: Path | None = None,
    diagram_tascam: Path | None = None,
    diagram_aux_loop: Path | None = None,
    routing_path: Path | None = None,
    inventory_path: Path | None = None,
    docs_inventory: Path | None = None,
    midi_path: Path | None = None,
    docs_midi_topology: Path | None = None,
    docs_midi_clock: Path | None = None,
    diagram_midi_topology: Path | None = None,
    controllers_path: Path | None = None,
    ableton_path: Path | None = None,
    docs_controllers: Path | None = None,
    docs_ableton: Path | None = None,
    performance_path: Path | None = None,
    surfaces_path: Path | None = None,
    docs_performance: Path | None = None,
    docs_live_recovery: Path | None = None,
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
    using_custom_rt = routing_path is not None and routing_path != ROUTING_PATH
    using_custom_inv = (
        inventory_path is not None and inventory_path != INVENTORY_PATH
    )
    using_custom_midi = midi_path is not None and midi_path != MIDI_PATH
    using_custom_controllers = (
        controllers_path is not None and controllers_path != CONTROLLERS_PATH
    )
    using_custom_ableton = ableton_path is not None and ableton_path != ABLETON_PATH
    using_custom_performance = (
        performance_path is not None and performance_path != PERFORMANCE_PATH
    )
    using_custom_surfaces = (
        surfaces_path is not None and surfaces_path != CONTROL_SURFACES_PATH
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
    if using_custom_rt and (docs_routing is None or docs_pedal_chains is None):
        raise StoreError(
            "docs_routing and docs_pedal_chains are required when rendering "
            "with a custom routing_path"
        )
    if using_custom_inv and docs_inventory is None:
        raise StoreError(
            "docs_inventory is required when rendering with a custom inventory_path"
        )
    if using_custom_midi and (
        docs_midi_topology is None
        or docs_midi_clock is None
        or diagram_midi_topology is None
    ):
        raise StoreError(
            "docs_midi_topology, docs_midi_clock, and diagram_midi_topology are "
            "required when rendering with a custom midi_path"
        )
    if using_custom_controllers and docs_controllers is None:
        raise StoreError(
            "docs_controllers is required when rendering with a custom controllers_path"
        )
    if using_custom_ableton and docs_ableton is None:
        raise StoreError(
            "docs_ableton is required when rendering with a custom ableton_path"
        )
    if (using_custom_performance or using_custom_surfaces) and (
        docs_performance is None or docs_live_recovery is None
    ):
        raise StoreError(
            "docs_performance and docs_live_recovery are required with custom "
            "performance/surface paths"
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
        and not using_custom_rt
        and not using_custom_midi
        and not using_custom_controllers
        and not using_custom_ableton
        and not using_custom_performance
        and not using_custom_surfaces
    )
    if planning_fixture_only:
        return changed, messages

    custom_inputs = any(
        (
            using_custom_todo,
            using_custom_wish,
            using_custom_q,
            using_custom_pb,
            using_custom_ch,
            using_custom_rt,
            using_custom_midi,
            using_custom_controllers,
            using_custom_ableton,
            using_custom_performance,
            using_custom_surfaces,
        )
    )
    if not custom_inputs or inventory_path is not None or docs_inventory is not None:
        inventory = load_inventory(inventory_path)
        inventory_md_path = docs_inventory or DOCS_INVENTORY_PATH
        new_inventory = apply_inventory_render(
            inventory_md_path.read_text(encoding="utf-8"), inventory
        )
        if _write_if_changed(
            inventory_md_path,
            new_inventory,
            display_name="docs/inventory.md",
            write=write,
            messages=messages,
        ):
            changed = True

    if not custom_inputs or midi_path is not None or docs_midi_topology is not None:
        midi = midi_state.load_document(midi_path, inventory_path=inventory_path)
        midi_topology_path = docs_midi_topology or DOCS_MIDI_TOPOLOGY_PATH
        midi_clock_path = docs_midi_clock or DOCS_MIDI_CLOCK_PATH
        midi_diagram_path = diagram_midi_topology or DIAGRAM_MIDI_TOPOLOGY_PATH
        midi_pairs = [
            (
                midi_topology_path,
                apply_midi_topology_render(
                    midi_topology_path.read_text(encoding="utf-8"), midi
                ),
                "docs/midi-topology.md",
            ),
            (
                midi_clock_path,
                apply_midi_clock_render(
                    midi_clock_path.read_text(encoding="utf-8"), midi
                ),
                "docs/midi-clock.md",
            ),
            (
                midi_diagram_path,
                render_midi_topology_mermaid(midi),
                "diagrams/midi-topology.mmd",
            ),
        ]
        for path, new_text, display in midi_pairs:
            if _write_if_changed(
                path, new_text, display_name=display, write=write, messages=messages
            ):
                changed = True

    if not custom_inputs or controllers_path is not None or docs_controllers is not None:
        ableton = ableton_state.load_document(ableton_path)
        controllers = control_state.load_document(
            controllers_path,
            inventory_path=inventory_path,
            midi_path=midi_path,
            ableton_path=ableton_path,
        )
        controller_md_path = docs_controllers or DOCS_CONTROLLERS_PATH
        new_text = apply_controllers_render(
            controller_md_path.read_text(encoding="utf-8"), controllers
        )
        if _write_if_changed(
            controller_md_path,
            new_text,
            display_name="docs/controller-mappings.md",
            write=write,
            messages=messages,
        ):
            changed = True

    if not custom_inputs or ableton_path is not None or docs_ableton is not None:
        ableton = ableton_state.load_document(ableton_path)
        ableton_md_path = docs_ableton or DOCS_ABLETON_PATH
        new_text = apply_ableton_render(
            ableton_md_path.read_text(encoding="utf-8"), ableton
        )
        if _write_if_changed(
            ableton_md_path,
            new_text,
            display_name="docs/ableton-track-map.md",
            write=write,
            messages=messages,
        ):
            changed = True

    if (
        not custom_inputs
        or performance_path is not None
        or surfaces_path is not None
        or docs_performance is not None
    ):
        performance = performance_state.load_document(
            performance_path,
            controllers_path=controllers_path,
            surfaces_path=surfaces_path,
            ableton_path=ableton_path,
            inventory_path=inventory_path,
            midi_path=midi_path,
        )
        surfaces = control_surface_state.load_document(
            surfaces_path, inventory_path=inventory_path
        )
        readiness = performance_state.evaluate_readiness(
            performance,
            controllers_path=controllers_path,
            surfaces_path=surfaces_path,
            ableton_path=ableton_path,
            inventory_path=inventory_path,
            midi_path=midi_path,
        )
        performance_md_path = docs_performance or DOCS_PERFORMANCE_PATH
        recovery_md_path = docs_live_recovery or DOCS_LIVE_RECOVERY_PATH
        for path, new_text, display in (
            (
                performance_md_path,
                render_performance_doc(performance, surfaces, readiness),
                "docs/performance.md",
            ),
            (
                recovery_md_path,
                render_live_recovery_doc(performance),
                "docs/live-recovery.md",
            ),
        ):
            if _write_if_changed(
                path, new_text, display_name=display, write=write, messages=messages
            ):
                changed = True

    patchbays = patchbay_state.load_raw(patchbays_path)
    channels = channel_state.load_raw(channel_map_path)
    routing = routing_state.load_raw(routing_path)
    pb_md_path = docs_patchbays or DOCS_PATCHBAYS_PATH
    tascam_md_path = docs_tascam or DOCS_TASCAM_PATH
    alesis_md_path = docs_alesis or DOCS_ALESIS_PATH
    routing_md_path = docs_routing or DOCS_ROUTING_PATH
    pedal_md_path = docs_pedal_chains or DOCS_PEDAL_CHAINS_PATH
    pb_mmd_path = diagram_patchbays or DIAGRAM_PATCHBAYS_PATH
    tascam_mmd_path = diagram_tascam or DIAGRAM_TASCAM_PATH
    aux_mmd_path = diagram_aux_loop or DIAGRAM_AUX_LOOP_PATH

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
        (
            routing_md_path,
            apply_routing_render(routing_md_path.read_text(encoding="utf-8"), routing),
            "docs/current-routing.md",
        ),
        (
            pedal_md_path,
            apply_pedal_chains_render(pedal_md_path.read_text(encoding="utf-8"), routing),
            "docs/pedal-chains.md",
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
    if not using_custom_rt or diagram_aux_loop is not None:
        aux_mmd = render_aux_send_loop_mermaid(routing)
        if _write_if_changed(
            aux_mmd_path,
            aux_mmd,
            display_name="diagrams/aux-send-loop.mmd",
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
    routing_path: Path | None = None,
    docs_todo: Path | None = None,
    docs_wishlist: Path | None = None,
    docs_questions: Path | None = None,
    docs_patchbays: Path | None = None,
    docs_tascam: Path | None = None,
    docs_alesis: Path | None = None,
    docs_routing: Path | None = None,
    docs_pedal_chains: Path | None = None,
    diagram_patchbays: Path | None = None,
    diagram_tascam: Path | None = None,
    diagram_aux_loop: Path | None = None,
    inventory_path: Path | None = None,
    docs_inventory: Path | None = None,
    midi_path: Path | None = None,
    docs_midi_topology: Path | None = None,
    docs_midi_clock: Path | None = None,
    diagram_midi_topology: Path | None = None,
    controllers_path: Path | None = None,
    ableton_path: Path | None = None,
    docs_controllers: Path | None = None,
    docs_ableton: Path | None = None,
    performance_path: Path | None = None,
    surfaces_path: Path | None = None,
    docs_performance: Path | None = None,
    docs_live_recovery: Path | None = None,
) -> list[str]:
    """Return list of stale doc paths. Empty if synchronized."""
    _, messages = render_docs(
        todo_path=todo_path,
        wishlist_path=wishlist_path,
        questions_path=questions_path,
        patchbays_path=patchbays_path,
        channel_map_path=channel_map_path,
        routing_path=routing_path,
        docs_todo=docs_todo,
        docs_wishlist=docs_wishlist,
        docs_questions=docs_questions,
        docs_patchbays=docs_patchbays,
        docs_tascam=docs_tascam,
        docs_alesis=docs_alesis,
        docs_routing=docs_routing,
        docs_pedal_chains=docs_pedal_chains,
        diagram_patchbays=diagram_patchbays,
        diagram_tascam=diagram_tascam,
        diagram_aux_loop=diagram_aux_loop,
        inventory_path=inventory_path,
        docs_inventory=docs_inventory,
        midi_path=midi_path,
        docs_midi_topology=docs_midi_topology,
        docs_midi_clock=docs_midi_clock,
        diagram_midi_topology=diagram_midi_topology,
        controllers_path=controllers_path,
        ableton_path=ableton_path,
        docs_controllers=docs_controllers,
        docs_ableton=docs_ableton,
        performance_path=performance_path,
        surfaces_path=surfaces_path,
        docs_performance=docs_performance,
        docs_live_recovery=docs_live_recovery,
        write=False,
    )
    return messages
