"""Repository consistency checks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from music_rig.models import (
    INACTIVE_OWNERSHIP,
    TERMINAL_FOR_NEXT,
    ChangeStatus,
    QuestionStatus,
)
from music_rig.render import check_render_sync
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
    CHANGES_PATH,
    CHANNEL_MAP_PATH,
    EXISTING_YAML,
    INBOX_PATH,
    PATCHBAYS_PATH,
    QUESTIONS_PATH,
    StoreError,
    load_changes,
    load_inbox,
    load_inventory,
    load_questions,
    load_routing,
    load_todo,
    load_wishlist,
    parse_existing_yaml,
)


@dataclass
class CheckResult:
    ok: bool
    errors: list[str]
    warnings: list[str]


def run_checks(
    *,
    todo_path: Path | None = None,
    wishlist_path: Path | None = None,
    inbox_path: Path | None = None,
    changes_path: Path | None = None,
    questions_path: Path | None = None,
    docs_todo: Path | None = None,
    docs_wishlist: Path | None = None,
    docs_questions: Path | None = None,
    routing_path: Path | None = None,
    docs_routing: Path | None = None,
    docs_pedal_chains: Path | None = None,
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
) -> CheckResult:
    errors: list[str] = []
    warnings: list[str] = []

    todo = None
    wishlist = None
    questions = None
    changes = None
    try:
        todo = load_todo(todo_path)
    except StoreError as exc:
        errors.append(str(exc))

    try:
        midi = midi_state.load_raw(midi_path)
        for err in midi_state.validate_midi_doc(
            midi, inventory_path=inventory_path
        ):
            errors.append(f"midi: {err}")
    except StoreError as exc:
        errors.append(str(exc))

    try:
        wishlist = load_wishlist(wishlist_path)
    except StoreError as exc:
        errors.append(str(exc))

    try:
        ableton_raw = ableton_state.load_raw(ableton_path)
        for err in ableton_state.validate_ableton_doc(ableton_raw):
            errors.append(f"ableton: {err}")
        controllers_raw = control_state.load_raw(controllers_path)
        for err in control_state.validate_controllers_doc(
            controllers_raw,
            inventory_path=inventory_path,
            midi_path=midi_path,
            ableton_path=ableton_path,
            performance_path=performance_path,
        ):
            errors.append(f"controllers: {err}")
        surfaces_raw = control_surface_state.load_raw(surfaces_path)
        for err in control_surface_state.validate_control_surfaces_doc(
            surfaces_raw, inventory_path=inventory_path
        ):
            errors.append(f"control-surfaces: {err}")
        performance_raw = performance_state.load_raw(performance_path)
        for err in performance_state.validate_performance_doc(
            performance_raw,
            controllers_path=controllers_path,
            surfaces_path=surfaces_path,
            ableton_path=ableton_path,
            inventory_path=inventory_path,
            midi_path=midi_path,
        ):
            errors.append(f"performance: {err}")
    except StoreError as exc:
        errors.append(str(exc))

    try:
        inbox = load_inbox(inbox_path)
        for item in inbox.items:
            if not item.text.strip():
                errors.append(f"{item.id} has empty capture text")
    except StoreError as Exc:
        errors.append(str(Exc))

    try:
        changes = load_changes(changes_path)
        open_count = sum(
            1 for item in changes.items if item.status == ChangeStatus.OPEN
        )
        if open_count:
            warnings.append(
                f"{open_count} unreconciled rig change(s) are OPEN."
            )
    except StoreError as exc:
        errors.append(str(exc))

    try:
        questions = load_questions(questions_path)
        open_q = sum(
            1 for q in questions.questions if q.status == QuestionStatus.OPEN
        )
        if open_q:
            warnings.append(f"{open_q} open question(s) remain unresolved.")
    except StoreError as exc:
        errors.append(str(exc))

    routing_doc = None
    try:
        routing_doc = load_routing(routing_path)
        routing = routing_state.load_raw(routing_path)
        for err in routing_state.validate_routing_doc(routing):
            errors.append(f"routing: {err}")
    except StoreError as exc:
        errors.append(str(exc))

    inventory = None
    try:
        inventory = load_inventory(inventory_path)
        raw_inventory = inventory_state.load_raw(inventory_path)
        for err in inventory_state.validate_inventory_doc(raw_inventory):
            errors.append(f"inventory: {err}")
    except StoreError as exc:
        errors.append(str(exc))

    if inventory is not None and routing_doc is not None:
        for path_id, path in routing_doc.named_paths.items():
            for branch_id, branch in path.branches.items():
                for node in branch.nodes:
                    if not node.gear_ref:
                        continue
                    item = inventory.resolve(node.gear_ref)
                    where = f"{path_id}/{branch_id}:{node.id}"
                    if item is None:
                        errors.append(
                            f"routing gear_ref {node.gear_ref!r} at {where} "
                            "does not resolve in inventory"
                        )
                    elif item.ownership_status in INACTIVE_OWNERSHIP:
                        errors.append(
                            f"routing gear_ref {node.gear_ref!r} at {where} resolves "
                            f"to inactive inventory status {item.ownership_status.value}"
                        )

    try:
        pb = patchbay_state.load_raw()
        for err in patchbay_state.validate_patchbays_doc(pb):
            errors.append(f"patchbays: {err}")
    except StoreError as exc:
        errors.append(str(exc))

    try:
        ch = channel_state.load_raw()
        for err in channel_state.validate_channel_map(ch):
            errors.append(f"channel-map: {err}")
    except StoreError as exc:
        errors.append(str(exc))

    if todo is not None and wishlist is not None:
        known = {t.id for t in todo.tasks}
        for item in wishlist.items:
            for ref in item.todo_refs:
                if ref not in known:
                    errors.append(
                        f"Wishlist '{item.item}' references unknown TODO {ref}"
                    )
        if todo_path is None or controllers_path is not None:
            try:
                controllers = control_state.load_document(
                    controllers_path,
                    inventory_path=inventory_path,
                    midi_path=midi_path,
                    ableton_path=ableton_path,
                )
                for controller in controllers.controllers:
                    for ref in controller.related_todos:
                        if ref not in known:
                            errors.append(
                                f"Controller {controller.gear_ref!r} references unknown TODO {ref}"
                            )
            except StoreError:
                pass

    if todo is not None:
        by_id = todo.task_map()
        if len(todo.next_session) > 3:
            errors.append("next_session has more than 3 tasks")
        if len(todo.next_session) != len(set(todo.next_session)):
            errors.append("next_session has duplicate IDs")
        for tid in todo.next_session:
            task = by_id.get(tid)
            if task and task.status.value in TERMINAL_FOR_NEXT:
                errors.append(f"{tid} is {task.status.value} but still in next_session")

    if questions is not None and todo is not None:
        known_todos = todo.task_map()
        known_changes = changes.item_map() if changes is not None else {}
        for q in questions.questions:
            for tid in q.related_todos:
                if tid not in known_todos:
                    errors.append(f"{q.id} references unknown TODO {tid}")
            for cid in q.related_changes:
                if cid not in known_changes:
                    errors.append(f"{q.id} references unknown change {cid}")
            # bidirectional agreement when change also lists questions
            for cid in q.related_changes:
                chg = known_changes.get(cid)
                if chg is not None and q.id not in chg.related_questions:
                    errors.append(
                        f"{q.id} lists {cid} but {cid} does not list {q.id}"
                    )

    if changes is not None and questions is not None:
        qmap = questions.question_map()
        for chg in changes.items:
            for qid in chg.related_questions:
                q = qmap.get(qid)
                if q is None:
                    errors.append(f"{chg.id} references unknown question {qid}")
                elif chg.id not in q.related_changes:
                    errors.append(
                        f"{chg.id} lists {qid} but {qid} does not list {chg.id}"
                    )

    try:
        stale = check_render_sync(
            todo_path=todo_path,
            wishlist_path=wishlist_path,
            questions_path=questions_path,
            docs_todo=docs_todo,
            docs_wishlist=docs_wishlist,
            docs_questions=docs_questions,
            routing_path=routing_path,
            docs_routing=docs_routing,
            docs_pedal_chains=docs_pedal_chains,
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
        )
        for path in stale:
            errors.append(
                f"{path} is out of date with canonical YAML\nRun: uv run rig render"
            )
    except StoreError as exc:
        errors.append(str(exc))

    for path in EXISTING_YAML:
        try:
            parse_existing_yaml(path)
        except StoreError as exc:
            errors.append(str(exc))

    _ = INBOX_PATH
    _ = CHANGES_PATH
    _ = QUESTIONS_PATH
    _ = PATCHBAYS_PATH
    _ = CHANNEL_MAP_PATH

    return CheckResult(ok=not errors, errors=errors, warnings=warnings)
