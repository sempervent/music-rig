"""Human-facing advisory maintenance overview (not CI-blocking)."""

from __future__ import annotations

from pathlib import Path

from music_rig.checks import run_checks
from music_rig.models import (
    ChangeCategory,
    ChangeStatus,
    InboxStatus,
    QuestionStatus,
)
from music_rig.reconcile import reconciliation_advisories
from music_rig.rig_views import patchbay_unknown_mode_stats
from music_rig.session_service import find_active
from music_rig.status import git_summary
from music_rig.store import (
    ROOT,
    StoreError,
    load_changes,
    load_inbox,
    load_questions,
    load_inventory,
    load_routing,
    load_todo,
)


def build_doctor_text(
    *,
    todo_path: Path | None = None,
    wishlist_path: Path | None = None,
    inbox_path: Path | None = None,
    changes_path: Path | None = None,
    questions_path: Path | None = None,
    sessions_dir: Path | None = None,
    patchbays_path: Path | None = None,
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
) -> str:
    attention = 0
    lines = ["RIG DOCTOR", ""]

    # Planning
    lines.append("Planning")
    checks = run_checks(
        todo_path=todo_path,
        wishlist_path=wishlist_path,
        inbox_path=inbox_path,
        changes_path=changes_path,
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
    )
    planning_errors = [
        e
        for e in checks.errors
        if "TODO" in e
        or "Wishlist" in e
        or "inbox" in e.lower()
        or "out of date" in e
        or "question" in e.lower()
    ]
    if any("TODO schema" in e or ("TODO" in e and "validation" in e) for e in checks.errors):
        lines.append("✗ TODO data invalid")
        attention += 1
    else:
        try:
            load_todo(todo_path)
            lines.append("✓ TODO data valid")
        except StoreError:
            lines.append("✗ TODO data invalid")
            attention += 1

    if any("Wishlist" in e for e in checks.errors):
        lines.append("✗ Wishlist data invalid")
        attention += 1
    else:
        lines.append("✓ Wishlist data valid")

    try:
        todo = load_todo(todo_path)
        lines.append(f"✓ Next Session: {len(todo.next_session)} tasks")
    except StoreError:
        pass

    if any("out of date" in e for e in checks.errors):
        lines.append("✗ Generated planning docs out of sync")
        attention += 1
    else:
        lines.append("✓ Generated planning docs synchronized")

    # Knowledge state
    lines.append("")
    lines.append("Knowledge state")
    try:
        questions = load_questions(questions_path)
        open_q = sum(1 for q in questions.questions if q.status == QuestionStatus.OPEN)
        if open_q:
            lines.append(f"⚠ {open_q} OPEN question(s)")
            attention += 1
        else:
            lines.append("✓ No OPEN questions")
    except StoreError as exc:
        lines.append(f"✗ Questions data invalid: {exc}")
        attention += 1

    try:
        changes = load_changes(changes_path)
        open_chg = sum(1 for c in changes.items if c.status == ChangeStatus.OPEN)
        if open_chg:
            lines.append(f"⚠ {open_chg} OPEN change record(s)")
            attention += 1
        else:
            lines.append("✓ No OPEN change records")
    except StoreError as exc:
        lines.append(f"✗ Changes data invalid: {exc}")
        attention += 1

    try:
        inbox = load_inbox(inbox_path)
        open_inbox = sum(1 for i in inbox.items if i.status == InboxStatus.OPEN)
        if open_inbox:
            lines.append(f"⚠ {open_inbox} OPEN inbox capture(s)")
            attention += 1
        else:
            lines.append("✓ No OPEN inbox captures")
    except StoreError as exc:
        lines.append(f"✗ Inbox data invalid: {exc}")
        attention += 1

    for advisory in reconciliation_advisories(
        changes_path=changes_path,
        questions_path=questions_path,
        todo_path=todo_path,
    ):
        lines.append(f"⚠ {advisory}")
        attention += 1

    # Studio state
    lines.append("")
    lines.append("Studio state")
    active = find_active(sessions_dir)
    if active:
        lines.append(f"⚠ Active session {active.id}")
        attention += 1
    else:
        lines.append("✓ No active session")

    # Current-data gaps
    lines.append("")
    lines.append("Current-state maintenance")
    try:
        from music_rig import patchbay_state

        data = patchbay_state.load_raw(patchbays_path)
        stats = patchbay_unknown_mode_stats(patchbays_path=patchbays_path)
        model_unknown = [
            name
            for name, bay in (data.get("patchbays") or {}).items()
            if str(bay.get("hardware_model", "unknown")).lower() == "unknown"
        ]
        if stats:
            for name, count in stats:
                lines.append(f"⚠ {name}: {count} represented pair(s) still have mode UNKNOWN")
                attention += 1
        else:
            lines.append("✓ No populated UNKNOWN patchbay modes")
        for name in model_unknown:
            lines.append(f"⚠ {name}: hardware model UNKNOWN")
            attention += 1
        if not model_unknown:
            lines.append("✓ Patchbay hardware models documented")
    except StoreError as exc:
        lines.append(f"✗ Patchbay data invalid: {exc}")
        attention += 1

    pb_stale = [e for e in checks.errors if "patchbays.md" in e or "tascam-channel-map" in e or "alesis-mixer-map" in e or "patchbays.mmd" in e or "tascam-channel-map.mmd" in e]
    if pb_stale:
        lines.append("✗ CURRENT projection docs out of sync")
        attention += 1
    else:
        lines.append("✓ Channel-map and patchbay docs synchronized")

    # Routing
    lines.append("")
    lines.append("Routing")
    routing_errors = [
        e
        for e in checks.errors
        if e.startswith("routing:") or "routing.yaml" in e
    ]
    if routing_errors:
        lines.append("✗ Named paths invalid")
        attention += 1
    else:
        lines.append("✓ Named paths valid")

    routing_projection_names = (
        "current-routing.md",
        "pedal-chains.md",
        "aux-send-loop.mmd",
    )
    routing_stale = [
        e for e in checks.errors if any(name in e for name in routing_projection_names)
    ]
    if routing_stale:
        lines.append("✗ Generated pedal-chain/routing docs out of sync")
        attention += 1
    else:
        lines.append("✓ Generated pedal-chain/routing docs synchronized")

    try:
        questions = load_questions(questions_path)
        routing_questions = sum(
            1
            for q in questions.questions
            if q.status == QuestionStatus.OPEN
            and ("routing" in q.area.casefold() or "pedals" in q.area.casefold())
        )
        if routing_questions:
            lines.append(f"⚠ {routing_questions} OPEN routing-related question(s)")
            attention += 1
        else:
            lines.append("✓ No OPEN routing-related questions")
    except StoreError:
        pass

    try:
        changes = load_changes(changes_path)
        routing_changes = sum(
            1
            for change in changes.items
            if change.status == ChangeStatus.OPEN
            and change.category
            in {ChangeCategory.PEDAL_CHAIN, ChangeCategory.AUDIO_ROUTING}
        )
        if routing_changes:
            lines.append(f"⚠ {routing_changes} OPEN PEDAL_CHAIN / AUDIO_ROUTING change(s)")
            attention += 1
        else:
            lines.append("✓ No OPEN PEDAL_CHAIN / AUDIO_ROUTING changes")
    except StoreError:
        pass

    # MIDI detail stays out of compact `rig status`; doctor only checks validity/sync.
    lines.append("")
    lines.append("MIDI")
    midi_errors = [
        error
        for error in checks.errors
        if error.startswith("midi:") or "midi.yaml" in error
    ]
    midi_stale = [
        error
        for error in checks.errors
        if any(
            name in error
            for name in ("midi-topology.md", "midi-clock.md", "midi-topology.mmd")
        )
    ]
    if midi_errors:
        lines.append("✗ MIDI state invalid")
        attention += 1
    else:
        lines.append("✓ MIDI state valid")
    if midi_stale:
        lines.append("✗ MIDI projections out of sync")
        attention += 1
    else:
        lines.append("✓ MIDI projections synchronized")

    # Inventory identity
    lines.append("")
    lines.append("Inventory")
    try:
        inventory = load_inventory(inventory_path)
        lines.append(f"✓ Inventory valid: {len(inventory.items)} records")
        routing = load_routing(routing_path)
        refs = [
            node
            for path in routing.named_paths.values()
            for branch in path.branches.values()
            for node in branch.nodes
            if node.gear_ref
        ]
        unresolved = [node.gear_ref for node in refs if not inventory.resolve(node.gear_ref or "")]
        if unresolved:
            lines.append(f"✗ {len(unresolved)} routing gear_ref(s) unresolved")
            attention += 1
        else:
            lines.append(f"✓ {len(refs)} routing gear_ref(s) resolve")
        unlinked_devices = [
            node
            for path in routing.named_paths.values()
            for branch in path.branches.values()
            for node in branch.nodes
            if node.kind == "device" and not node.gear_ref
        ]
        if unlinked_devices:
            lines.append(
                f"⚠ {len(unlinked_devices)} device-kind routing node(s) lack gear_ref"
            )
            attention += 1
        else:
            lines.append("✓ All device-kind routing nodes have gear_ref")
        lines.append(
            "⚠ Patchbay model → PB letter mapping remains UNKNOWN (Q-007); "
            "do not infer unit assignments"
        )
        attention += 1
    except StoreError as exc:
        lines.append(f"✗ Inventory data invalid: {exc}")
        attention += 1

    # Repository
    lines.append("")
    lines.append("Repository")
    branch, tree = git_summary()
    if branch is None:
        lines.append("⚠ Git status unavailable")
        attention += 1
    else:
        if branch == "main":
            lines.append("✓ on main")
        else:
            lines.append(f"⚠ branch {branch}")
            attention += 1
        if tree == "clean":
            lines.append("✓ working tree clean")
        else:
            lines.append("⚠ working tree has changes")
            attention += 1

    # Documentation
    lines.append("")
    lines.append("Documentation")
    mkdocs = ROOT / "mkdocs.yml"
    docs = ROOT / "docs"
    if mkdocs.exists() and docs.is_dir():
        lines.append("✓ MkDocs source structure present")
    else:
        lines.append("✗ MkDocs source structure missing")
        attention += 1

    other_errors = [
        e
        for e in checks.errors
        if e not in planning_errors
        and "TODO" not in e
        and "Wishlist" not in e
        and "out of date" not in e
        and "inbox" not in e.lower()
        and "question" not in e.lower()
        and not e.startswith("routing:")
        and not any(name in e for name in routing_projection_names)
    ]
    if other_errors:
        lines.append("")
        lines.append("Validation")
        for err in other_errors:
            lines.append(f"✗ {err}")
            attention += 1

    lines.append("")
    if attention:
        lines.append(f"{attention} item(s) worth attention.")
    else:
        lines.append("Nothing needs attention.")
    return "\n".join(lines) + "\n"
