"""Read-only / lightly-mutable domain adapters for ListDetail screens."""

from __future__ import annotations

from music_rig import automation, snapshot_service, todo_service
from music_rig.backup_state import status_items
from music_rig.doctor import build_doctor_text
from music_rig.models import ChangeStatus, InboxStatus, WishStatus
from music_rig.performance_state import evaluate_readiness
from music_rig.performance_state import load_document as load_performance
from music_rig.reconcile import build_reconcile_summary
from music_rig.session_service import list_sessions
from music_rig.status import build_status_text
from music_rig.store import (
    load_ableton,
    load_changes,
    load_controllers,
    load_inbox,
    load_inventory,
    load_midi,
    load_todo,
    load_wishlist,
)
from music_rig.tui.adapters.base import AdapterAction, AdapterRow, SimpleAdapter


def _todo_adapter() -> SimpleAdapter:
    def rows() -> list[AdapterRow]:
        doc = load_todo()
        out: list[AdapterRow] = []
        for t in doc.tasks:
            mark = "★" if t.id in doc.next_session else ""
            out.append(
                AdapterRow(
                    t.id,
                    [t.id, t.priority.value, t.status.value, mark, t.task[:50]],
                    search_text=f"{t.id} {t.task} {t.area} {t.status.value}",
                )
            )
        return out

    def detail(row_id: str) -> str:
        doc = load_todo()
        t = doc.task_map().get(row_id.upper())
        if t is None:
            return f"Unknown TODO {row_id}"
        in_next = t.id in doc.next_session
        return "\n".join(
            [
                f"# {t.id}",
                "",
                t.task,
                "",
                f"Area: {t.area}",
                f"Priority: {t.priority.value}",
                f"Status: {t.status.value}",
                f"Next Session: {'yes' if in_next else 'no'}",
                f"DoD: {t.definition_of_done}",
                f"Notes: {t.notes or '—'}",
                f"Depends: {', '.join(t.depends_on) or '—'}",
            ]
        )

    def action(action_id: str, row_id: str | None) -> str | None:
        if action_id == "next" and row_id:
            todo_service.next_add(row_id, render=True)
            return f"Added {row_id.upper()} to Next Session"
        return None

    return SimpleAdapter(
        id="todo",
        label="TODO",
        columns=["ID", "Pri", "Status", "Next", "Task"],
        _rows_fn=rows,
        _detail_fn=detail,
        _actions=[AdapterAction("next", "Mark next-session", key="n")],
        _action_fn=action,
    )


def _wish_adapter() -> SimpleAdapter:
    def rows() -> list[AdapterRow]:
        return [
            AdapterRow(
                w.item,
                [
                    w.item[:40],
                    w.priority.value if w.priority else "—",
                    w.status.value,
                ],
                search_text=f"{w.item} {w.status.value} {w.notes}",
            )
            for w in load_wishlist().items
            if w.status not in {WishStatus.REJECTED, WishStatus.ACQUIRED}
        ]

    def detail(row_id: str) -> str:
        for w in load_wishlist().items:
            if w.item == row_id:
                return "\n".join(
                    [
                        f"# {w.item}",
                        "",
                        f"Status: {w.status.value}",
                        f"Priority: {w.priority.value if w.priority else '—'}",
                        f"Category: {w.category}",
                        f"Notes: {w.notes or '—'}",
                    ]
                )
        return f"Unknown wish {row_id}"

    return SimpleAdapter("wish", "Wishlist", ["Name", "Pri", "Status"], rows, detail)


def _inbox_adapter() -> SimpleAdapter:
    def rows() -> list[AdapterRow]:
        return [
            AdapterRow(
                i.id,
                [i.id, i.status.value, i.text[:50]],
                search_text=f"{i.id} {i.text} {i.status.value}",
            )
            for i in load_inbox().items
            if i.status == InboxStatus.OPEN
        ]

    def detail(row_id: str) -> str:
        item = load_inbox().item_map().get(row_id.upper())
        if item is None:
            return f"Unknown {row_id}"
        return f"# {item.id}\n\n{item.text}\n\nStatus: {item.status.value}"

    return SimpleAdapter("inbox", "Inbox", ["ID", "Status", "Text"], rows, detail)


def _changes_adapter() -> SimpleAdapter:
    def rows() -> list[AdapterRow]:
        return [
            AdapterRow(
                c.id,
                [c.id, c.status.value, c.category.value, c.summary[:40]],
                search_text=f"{c.id} {c.summary} {c.category.value}",
            )
            for c in load_changes().items
            if c.status == ChangeStatus.OPEN
        ]

    def detail(row_id: str) -> str:
        item = load_changes().item_map().get(row_id.upper())
        if item is None:
            return f"Unknown {row_id}"
        return "\n".join(
            [
                f"# {item.id}",
                "",
                item.summary,
                "",
                f"Category: {item.category.value}",
                f"Status: {item.status.value}",
                f"Details: {item.details or '—'}",
            ]
        )

    return SimpleAdapter(
        "changes", "Changes", ["ID", "Status", "Category", "Summary"], rows, detail
    )


def _gear_adapter() -> SimpleAdapter:
    def rows() -> list[AdapterRow]:
        return [
            AdapterRow(
                g.id,
                [g.id, g.name[:30], g.ownership_status.value, g.condition.value],
                search_text=f"{g.id} {g.name} {g.category}",
            )
            for g in load_inventory().items
        ]

    def detail(row_id: str) -> str:
        item = load_inventory().resolve(row_id)
        if item is None:
            return f"Unknown gear {row_id}"
        units = ", ".join(u.id for u in item.units) or "—"
        return "\n".join(
            [
                f"# {item.id} — {item.name}",
                "",
                f"Manufacturer: {item.manufacturer or '—'}",
                f"Model: {item.model or '—'}",
                f"Category: {item.category}",
                f"Ownership: {item.ownership_status.value}",
                f"Condition: {item.condition.value}",
                f"Location: {item.location or '—'}",
                f"Qty: {item.quantity}",
                f"Units: {units}",
                f"Notes: {item.notes or '—'}",
            ]
        )

    return SimpleAdapter("gear", "Gear", ["ID", "Name", "Ownership", "Condition"], rows, detail)


def _midi_adapter() -> SimpleAdapter:
    def rows() -> list[AdapterRow]:
        doc = load_midi()
        return [
            AdapterRow("summary", ["summary", "Overview"], "summary overview"),
            AdapterRow("endpoints", ["endpoints", f"{len(doc.endpoints)} endpoints"], "endpoints"),
            AdapterRow("links", ["links", f"{len(doc.connections)} links"], "links connections"),
            AdapterRow("channels", ["channels", f"{len(doc.channels)} channels"], "channels"),
            AdapterRow("clock", ["clock", "Clock / Ableton"], "clock ableton"),
        ]

    def detail(row_id: str) -> str:
        doc = load_midi()
        if row_id == "summary":
            master = "UNKNOWN"
            if doc.clock.master is not None:
                m = doc.clock.master
                master = f"{m.endpoint_ref or m.gear_ref} ({m.status.value})"
            return "\n".join(
                [
                    "# MIDI summary",
                    "",
                    f"Endpoints: {len(doc.endpoints)}",
                    f"Devices: {len(doc.devices)}",
                    f"Links: {len(doc.connections)}",
                    f"Channels: {len(doc.channels)}",
                    f"Clock master: {master}",
                ]
            )
        if row_id == "endpoints":
            lines = ["# Endpoints", ""]
            for e in doc.endpoints:
                lines.append(f"- {e.id}: {e.kind} — {e.name}")
            return "\n".join(lines)
        if row_id == "links":
            lines = ["# Physical links", ""]
            if not doc.connections:
                lines.append("— none —")
            for link in doc.connections:
                lines.append(
                    f"- {link.id}: {link.source} → {link.destination} "
                    f"[{link.transport.value}/{link.status.value}]"
                )
            return "\n".join(lines)
        if row_id == "channels":
            lines = ["# Channels", ""]
            for ch in doc.channels:
                lines.append(f"- {ch.gear_ref}: ch {ch.channel} [{ch.status.value}]")
            return "\n".join(lines)
        if row_id == "clock":
            lines = ["# Clock", ""]
            if doc.clock.master is None:
                lines.append("Master: UNKNOWN")
            else:
                m = doc.clock.master
                lines.append(f"Master: {m.endpoint_ref or m.gear_ref} — {m.status.value}")
            lines.append("")
            lines.append("Destinations:")
            for d in doc.clock.destinations:
                lines.append(
                    f"- {d.endpoint_ref or d.gear_ref}: enabled={d.enabled} [{d.status.value}]"
                )
            return "\n".join(lines)
        return f"Unknown section {row_id}"

    return SimpleAdapter("midi", "MIDI", ["Section", "Info"], rows, detail)


def _controls_adapter() -> SimpleAdapter:
    def rows() -> list[AdapterRow]:
        doc = load_controllers()
        return [
            AdapterRow(
                c.gear_ref,
                [c.gear_ref, c.coverage.value, str(len(c.contexts))],
                search_text=f"{c.gear_ref} {c.notes}",
            )
            for c in doc.controllers
        ]

    def detail(row_id: str) -> str:
        doc = load_controllers()
        ctrl = next((c for c in doc.controllers if c.gear_ref == row_id), None)
        if ctrl is None:
            return f"Unknown controller {row_id}"
        lines = [
            f"# {ctrl.gear_ref}",
            "",
            f"Coverage: {ctrl.coverage.value}",
            f"Notes: {ctrl.notes or '—'}",
            "",
            "## Contexts",
        ]
        for ctx in ctrl.contexts:
            lines.append(f"### {ctx.id} — {ctx.label} [{ctx.evidence.value}]")
            for physical in ctx.controls:
                lines.append(f"- {physical.id}: {physical.label} [{physical.availability.value}]")
        return "\n".join(lines)

    return SimpleAdapter("controls", "Controllers", ["Gear", "Coverage", "Contexts"], rows, detail)


def _ableton_adapter() -> SimpleAdapter:
    def rows() -> list[AdapterRow]:
        doc = load_ableton()
        out = [
            AdapterRow(t.id, ["track", t.id, t.name], f"track {t.id} {t.name}") for t in doc.tracks
        ]
        out.extend(
            AdapterRow(s.id, ["send", s.id, s.label], f"send {s.id} {s.label}") for s in doc.sends
        )
        out.extend(
            AdapterRow(a.id, ["action", a.id, a.label], f"action {a.id} {a.label}")
            for a in doc.actions
        )
        return out

    def detail(row_id: str) -> str:
        doc = load_ableton()
        for t in doc.tracks:
            if t.id == row_id:
                return (
                    f"# Track {t.id}\n\n{t.name}\n\n"
                    f"Evidence: {t.evidence.value}\nNotes: {t.notes or '—'}"
                )
        for s in doc.sends:
            if s.id == row_id:
                return (
                    f"# Send {s.id}\n\n{s.label}\n\n"
                    f"Evidence: {s.evidence.value}\nNotes: {s.notes or '—'}"
                )
        for a in doc.actions:
            if a.id == row_id:
                return (
                    f"# Action {a.id}\n\n{a.label}\n\n"
                    f"Evidence: {a.evidence.value}\nNotes: {a.notes or '—'}"
                )
        return f"Unknown {row_id}"

    return SimpleAdapter("ableton", "Ableton", ["Kind", "ID", "Name"], rows, detail)


def _performance_adapter() -> SimpleAdapter:
    def rows() -> list[AdapterRow]:
        doc = load_performance()
        readiness = evaluate_readiness(doc)
        out = [
            AdapterRow("readiness", ["readiness", readiness.result.value, ""], "readiness"),
            AdapterRow("panic", ["panic", "display only", ""], "panic recovery"),
        ]
        for mode in doc.modes:
            out.append(
                AdapterRow(
                    f"mode:{mode.id}",
                    ["mode", mode.id, mode.label],
                    f"mode {mode.id} {mode.label}",
                )
            )
        for action in doc.actions:
            out.append(
                AdapterRow(
                    f"action:{action.id}",
                    ["action", action.id, action.label],
                    f"action {action.id} {action.label}",
                )
            )
        for binding in doc.bindings:
            out.append(
                AdapterRow(
                    f"binding:{binding.id}",
                    ["binding", binding.id, binding.action_ref],
                    f"binding {binding.id}",
                )
            )
        for rec in doc.recovery:
            out.append(
                AdapterRow(
                    f"recovery:{rec.id}",
                    ["recovery", rec.id, rec.label],
                    f"recovery {rec.id} {rec.label}",
                )
            )
        return out

    def detail(row_id: str) -> str:
        doc = load_performance()
        if row_id == "readiness":
            readiness = evaluate_readiness(doc)
            lines = [f"# Readiness: {readiness.result.value}", ""]
            for reason in readiness.reasons:
                lines.append(f"- {reason}")
            return "\n".join(lines) if readiness.reasons else "\n".join(lines + ["—"])
        if row_id == "panic":
            lines = [
                "# Panic / emergency (display only)",
                "",
                "TUI does not execute panic actions or external automation.",
                "",
            ]
            panic = next((a for a in doc.actions if a.id == "panic"), None)
            if panic is not None:
                lines.append(f"## Action `{panic.id}` — {panic.label}")
                lines.append(f"Criticality: {panic.criticality.value}")
                lines.append(f"Notes: {panic.notes or '—'}")
                lines.append("")
                lines.append("Effects (not executed):")
                for effect in panic.effects:
                    lines.append(
                        f"- {effect.kind.value}: {effect.effect_id} [{effect.evidence.value}]"
                    )
            for rec in doc.recovery:
                lines.append("")
                lines.append(f"## Recovery `{rec.id}` — {rec.label}")
                lines.append(f"Symptom: {rec.symptom}")
                for step in rec.manual_steps:
                    lines.append(f"- {step}")
            return "\n".join(lines)
        if row_id.startswith("mode:"):
            mid = row_id.removeprefix("mode:")
            mode = next((m for m in doc.modes if m.id == mid), None)
            if mode is None:
                return "Unknown mode"
            return "\n".join(
                [
                    f"# {mode.label}",
                    "",
                    mode.purpose,
                    "",
                    f"Evidence: {mode.evidence.value}",
                    f"Required: {', '.join(mode.required_actions) or '—'}",
                    f"Optional: {', '.join(mode.optional_actions) or '—'}",
                ]
            )
        if row_id.startswith("action:"):
            aid = row_id.removeprefix("action:")
            action = next((a for a in doc.actions if a.id == aid), None)
            if action is None:
                return "Unknown action"
            return (
                f"# {action.label}\n\n{action.notes or '—'}\n\n"
                f"Criticality: {action.criticality.value}\n"
                f"Category: {action.category.value}"
            )
        if row_id.startswith("binding:"):
            bid = row_id.removeprefix("binding:")
            binding = next((b for b in doc.bindings if b.id == bid), None)
            if binding is None:
                return "Unknown binding"
            return (
                f"# Binding {binding.id}\n\n"
                f"Action: {binding.action_ref}\n"
                f"Control: {binding.control_ref}\n"
                f"Controller: {binding.controller_ref}\n"
                f"Evidence: {binding.evidence.value}"
            )
        if row_id.startswith("recovery:"):
            rid = row_id.removeprefix("recovery:")
            rec = next((r for r in doc.recovery if r.id == rid), None)
            if rec is None:
                return "Unknown recovery"
            steps = "\n".join(f"- {s}" for s in rec.manual_steps) or "—"
            return f"# {rec.label}\n\nSymptom: {rec.symptom}\n\n## Manual steps\n{steps}"
        return f"Unknown {row_id}"

    return SimpleAdapter("performance", "Performance", ["Kind", "ID", "Label"], rows, detail)


def _snapshots_adapter() -> SimpleAdapter:
    def rows() -> list[AdapterRow]:
        return [
            AdapterRow(
                s.snapshot_id,
                [s.snapshot_id, s.created_at, s.git_branch or "—"],
                search_text=s.snapshot_id,
            )
            for s in snapshot_service.list_snapshots()
        ]

    def detail(row_id: str) -> str:
        for s in snapshot_service.list_snapshots():
            if s.snapshot_id == row_id:
                files = "\n".join(f"- {f.path}" for f in s.canonical_files)
                return (
                    f"# {s.snapshot_id}\n\n"
                    f"Created: {s.created_at}\n"
                    f"Git: {s.git_branch} @ {s.git_commit}\n"
                    f"Clean: {s.working_tree_clean}\n\n"
                    f"## Files\n{files}"
                )
        return f"Unknown snapshot {row_id}"

    def action(action_id: str, row_id: str | None) -> str | None:
        if action_id == "create":
            manifest = snapshot_service.create_snapshot()
            return f"Created {manifest.snapshot_id}"
        return None

    return SimpleAdapter(
        "snapshot",
        "Snapshots",
        ["ID", "Created", "Branch"],
        rows,
        detail,
        _actions=[AdapterAction("create", "Create Snapshot", key="c", needs_selection=False)],
        _action_fn=action,
    )


def _backups_adapter() -> SimpleAdapter:
    def rows() -> list[AdapterRow]:
        return [
            AdapterRow(
                s.item.id,
                [s.item.id, s.readiness.value, (s.detail or "")[:40]],
                search_text=s.item.id,
            )
            for s in status_items()
        ]

    def detail(row_id: str) -> str:
        for s in status_items():
            if s.item.id == row_id:
                return (
                    f"# {s.item.id} — {s.item.label}\n\n"
                    f"Readiness: {s.readiness.value}\n"
                    f"Detail: {s.detail or '—'}\n"
                    f"Kind: {s.item.kind.value}\n"
                    f"Instructions: {s.item.manual_instructions or '—'}"
                )
        return f"Unknown backup item {row_id}"

    return SimpleAdapter("backup", "Backups", ["ID", "Readiness", "Detail"], rows, detail)


def _sessions_adapter() -> SimpleAdapter:
    def rows() -> list[AdapterRow]:
        return [
            AdapterRow(
                s.id,
                [s.id, s.status.value, (s.focus or "")[:30]],
                search_text=f"{s.id} {s.focus}",
            )
            for s in list_sessions(limit=50)
        ]

    def detail(row_id: str) -> str:
        for s in list_sessions(limit=200):
            if s.id == row_id:
                events = "\n".join(f"- [{e.type.value}] {e.text}" for e in s.events[:30])
                return (
                    f"# {s.id}\n\nStatus: {s.status.value}\n"
                    f"Focus: {s.focus or '—'}\n\n## Events\n{events or '—'}"
                )
        return f"Unknown session {row_id}"

    return SimpleAdapter("session", "Sessions", ["ID", "Status", "Focus"], rows, detail)


def _text_row_adapter(domain_id: str, label: str, text_fn) -> SimpleAdapter:
    def rows() -> list[AdapterRow]:
        return [AdapterRow("body", [label, "full text"], label)]

    def detail(row_id: str) -> str:
        return text_fn()

    return SimpleAdapter(domain_id, label, ["View", ""], rows, detail)


def _automation_adapter() -> SimpleAdapter:
    def rows() -> list[AdapterRow]:
        return [
            AdapterRow(
                fam.value,
                [fam.value, status.value],
                f"{fam.value} {status.value}",
            )
            for fam, status in automation.CAPABILITIES.items()
        ]

    def detail(row_id: str) -> str:
        for fam, status in automation.CAPABILITIES.items():
            if fam.value == row_id:
                return (
                    f"# {fam.value}\n\n"
                    f"Status: **{status.value}**\n\n"
                    "OBS / Ableton / MIDI / macOS automation remain NOT_IMPLEMENTED.\n"
                    "TUI never executes external adapters."
                )
        return f"Unknown capability {row_id}"

    return SimpleAdapter("automation", "Automation", ["Family", "Status"], rows, detail)


def get_adapter(domain_key: str) -> SimpleAdapter | None:
    mapping = {
        "todo": _todo_adapter,
        "wish": _wish_adapter,
        "inbox": _inbox_adapter,
        "changes": _changes_adapter,
        "gear": _gear_adapter,
        "midi": _midi_adapter,
        "controls": _controls_adapter,
        "ableton": _ableton_adapter,
        "performance": _performance_adapter,
        "snapshot": _snapshots_adapter,
        "backup": _backups_adapter,
        "session": _sessions_adapter,
        "doctor": lambda: _text_row_adapter("doctor", "Doctor", build_doctor_text),
        "status": lambda: _text_row_adapter("status", "Status", build_status_text),
        "reconcile": lambda: _text_row_adapter("reconcile", "Reconcile", build_reconcile_summary),
        "automation": _automation_adapter,
    }
    factory = mapping.get(domain_key)
    if factory is None:
        return None
    return factory()
