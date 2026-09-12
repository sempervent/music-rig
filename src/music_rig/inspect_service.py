"""`rig inspect` — structured discovery for agents and humans."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from music_rig.store import (
    StoreError,
    load_changes,
    load_controllers,
    load_inbox,
    load_inventory,
    load_questions,
    load_todo,
    load_wishlist,
)
from music_rig.tui.editable_domains import registry


def list_domains() -> list[dict[str, Any]]:
    rows = []
    for adapter in registry.all_adapters():
        rows.append(
            {
                "id": adapter.id,
                "label": adapter.label,
                "editable": True,
                "fields": len(adapter.get_field_specs()),
                "source": str(adapter.source_path()) if adapter.source_path() else None,
            }
        )
    # Specialized / non-adapter domains
    rows.extend(
        [
            {"id": "patchbay", "label": "Patchbays", "editable": True, "fields": None, "source": "data/patchbays.yaml"},
            {"id": "snapshot", "label": "Snapshots", "editable": False, "fields": None, "source": ".rig/snapshots"},
            {"id": "session", "label": "Sessions", "editable": "partial", "fields": None, "source": "data/sessions"},
            {"id": "doctor", "label": "Doctor", "editable": False, "fields": None, "source": None},
            {"id": "status", "label": "Status", "editable": False, "fields": None, "source": None},
            {"id": "reconcile", "label": "Reconcile", "editable": False, "fields": None, "source": None},
            {"id": "automation", "label": "Automation", "editable": False, "fields": None, "source": None},
        ]
    )
    return rows


def schema_for(domain: str) -> dict[str, Any]:
    adapter = registry.get_adapter(domain)
    if adapter is None:
        if domain in {"patchbay", "patchbays"}:
            from music_rig.tui.adapters.patchbays import PAIR_FIELD_SPECS

            return {
                "domain": "patchbay",
                "fields": [f.to_dict() for f in PAIR_FIELD_SPECS],
                "notes": "Bay editor also stages hardware_model; apply via propose_* + commit_patchbay.",
            }
        raise StoreError(f"Unknown domain {domain!r}")
    return {
        "domain": adapter.id,
        "label": adapter.label,
        "source": str(adapter.source_path()) if adapter.source_path() else None,
        "fields": [f.to_dict() for f in adapter.get_field_specs()],
    }


def list_records(domain: str, *, search: str = "") -> list[dict[str, Any]]:
    adapter = registry.get_adapter(domain)
    if adapter is None:
        raise StoreError(f"Unknown or non-listable domain {domain!r}")
    return [
        {"id": r["id"], "cells": r["cells"], "search_text": r.get("search_text", "")}
        for r in adapter.list_records(search=search)
    ]


def show_record(domain: str, record_id: str) -> dict[str, Any]:
    adapter = registry.get_adapter(domain)
    if adapter is None:
        raise StoreError(f"Unknown domain {domain!r}")
    return adapter.get_record(record_id)


def find_refs(record_id: str) -> dict[str, Any]:
    """Find structured references pointing at an ID across planning docs."""
    key = record_id.strip()
    key_upper = key.upper()
    hits: list[dict[str, str]] = []

    for q in load_questions().questions:
        if key_upper == q.id or key in q.related_todos or key_upper in q.related_todos:
            hits.append({"domain": "question", "id": q.id, "via": "id/related_todos"})
        if key_upper in q.related_changes:
            hits.append({"domain": "question", "id": q.id, "via": "related_changes"})
        if q.target and (
            q.target.gear == key
            or q.target.bay == key_upper
            or q.target.path == key
            or q.target.device == key
        ):
            hits.append({"domain": "question", "id": q.id, "via": "target"})

    for t in load_todo().tasks:
        if t.id == key_upper:
            hits.append({"domain": "todo", "id": t.id, "via": "id"})
        if key_upper in t.depends_on:
            hits.append({"domain": "todo", "id": t.id, "via": "depends_on"})
    doc = load_todo()
    if key_upper in doc.next_session:
        hits.append({"domain": "todo", "id": key_upper, "via": "next_session"})

    for w in load_wishlist().items:
        if key_upper in w.todo_refs or (w.inventory_ref and w.inventory_ref == key):
            hits.append({"domain": "wish", "id": w.item, "via": "todo_refs/inventory_ref"})

    for c in load_changes().items:
        if c.id == key_upper:
            hits.append({"domain": "changes", "id": c.id, "via": "id"})
        if key_upper in c.related_questions:
            hits.append({"domain": "changes", "id": c.id, "via": "related_questions"})

    for g in load_inventory().items:
        if g.id == key or g.id.lower() == key.lower():
            hits.append({"domain": "gear", "id": g.id, "via": "id"})
        for u in g.units:
            if u.id == key or u.id.lower() == key.lower():
                hits.append({"domain": "gear", "id": g.id, "via": f"unit:{u.id}"})

    return {"id": record_id, "refs": hits, "count": len(hits)}


def cleanup_scan() -> dict[str, Any]:
    """Report dangling refs / BROKEN+mapped / empty optional noise — no aesthetic rules."""
    issues: list[dict[str, str]] = []

    todo_ids = set(load_todo().task_map())
    change_ids = set(load_changes().item_map())
    question_ids = set(load_questions().question_map())
    gear_ids = {g.id for g in load_inventory().items}
    gear_ids |= {u.id for g in load_inventory().items for u in g.units}

    for q in load_questions().questions:
        for tid in q.related_todos:
            if tid not in todo_ids:
                issues.append(
                    {"severity": "error", "code": "dangling_ref", "id": q.id, "detail": f"related_todos {tid}"}
                )
        for cid in q.related_changes:
            if cid not in change_ids:
                issues.append(
                    {
                        "severity": "error",
                        "code": "dangling_ref",
                        "id": q.id,
                        "detail": f"related_changes {cid}",
                    }
                )

    for w in load_wishlist().items:
        for tid in w.todo_refs:
            if tid not in todo_ids:
                issues.append(
                    {"severity": "error", "code": "dangling_ref", "id": w.item, "detail": f"todo_refs {tid}"}
                )
        if w.inventory_ref and w.inventory_ref not in gear_ids:
            issues.append(
                {
                    "severity": "error",
                    "code": "dangling_ref",
                    "id": w.item,
                    "detail": f"inventory_ref {w.inventory_ref}",
                }
            )

    for c in load_changes().items:
        for qid in c.related_questions:
            if qid not in question_ids:
                issues.append(
                    {
                        "severity": "error",
                        "code": "dangling_ref",
                        "id": c.id,
                        "detail": f"related_questions {qid}",
                    }
                )

    # BROKEN + mapped invariant (controllers)
    try:
        from music_rig.control_state import load_raw
        from music_rig.models import ControlAvailability, TargetState

        raw = load_raw()
        for body in raw.get("controllers") or []:
            if not isinstance(body, dict):
                continue
            gear = body.get("gear_ref")
            for ctx in body.get("contexts") or []:
                if not isinstance(ctx, dict):
                    continue
                for ctl in ctx.get("controls") or []:
                    if not isinstance(ctl, dict):
                        continue
                    avail = str(ctl.get("availability") or "")
                    target = ctl.get("target") or {}
                    state = str(target.get("state") or "")
                    if avail == ControlAvailability.BROKEN.value and state == TargetState.MAPPED.value:
                        issues.append(
                            {
                                "severity": "error",
                                "code": "broken_mapped",
                                "id": f"{gear}/{ctx.get('id')}/{ctl.get('id')}",
                                "detail": "BROKEN control must not be MAPPED",
                            }
                        )
    except Exception as exc:
        issues.append(
            {"severity": "warning", "code": "controllers_scan_failed", "id": "controls", "detail": str(exc)}
        )

    return {"issues": issues, "count": len(issues)}


def dumps(payload: Any, *, as_json: bool) -> str:
    if as_json:
        return json.dumps(payload, indent=2, default=str)
    if isinstance(payload, list):
        lines = []
        for row in payload:
            if isinstance(row, dict) and "id" in row:
                extra = row.get("label") or row.get("cells") or ""
                lines.append(f"{row['id']}\t{extra}")
            else:
                lines.append(str(row))
        return "\n".join(lines)
    if isinstance(payload, dict):
        return json.dumps(payload, indent=2, default=str)
    return str(payload)
