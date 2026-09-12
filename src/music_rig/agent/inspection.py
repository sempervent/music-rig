"""Typed read-only inspection requests for agent context expansion."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from music_rig.reconciliation.context import ReconciliationContext
from music_rig.store import StoreError

MAX_RESULT_CHARS = 24_000
MAX_COLLECTION_ITEMS = 40


@dataclass(frozen=True, slots=True)
class InspectionRequest:
    kind: str
    id: str | None = None
    filters: dict[str, Any] = field(default_factory=dict)

    def fingerprint(self) -> str:
        blob = json.dumps(
            {"kind": self.kind, "id": self.id, "filters": self.filters},
            sort_keys=True,
            default=str,
        )
        return blob

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "id": self.id, "filters": dict(self.filters)}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> InspectionRequest:
        return cls(
            kind=str(raw.get("kind") or "").strip(),
            id=(str(raw["id"]) if raw.get("id") is not None else None),
            filters=dict(raw.get("filters") or {}),
        )


Inspector = Callable[[InspectionRequest, ReconciliationContext], dict[str, Any]]

_INSPECTORS: dict[str, Inspector] = {}


def _register(kind: str, fn: Inspector) -> None:
    _INSPECTORS[kind] = fn


def _bound(payload: dict[str, Any]) -> dict[str, Any]:
    text = json.dumps(payload, default=str)
    if len(text) <= MAX_RESULT_CHARS:
        return payload
    return {
        "truncated": True,
        "max_chars": MAX_RESULT_CHARS,
        "summary": text[:MAX_RESULT_CHARS],
        "stable_ids": payload.get("stable_ids") or payload.get("ids") or [],
    }


def _inspect_question(req: InspectionRequest, ctx: ReconciliationContext) -> dict[str, Any]:
    from music_rig import question_service

    qid = req.id or req.filters.get("question_id")
    if not qid:
        raise StoreError("question.show requires id")
    q = question_service.get_question(str(qid), questions_path=ctx.paths.questions)
    return {"kind": req.kind, "question": question_service.question_json_fields(q)}


def _inspect_todo(req: InspectionRequest, ctx: ReconciliationContext) -> dict[str, Any]:
    from music_rig.store import load_todo

    tid = req.id
    doc = load_todo(ctx.paths.todo)
    if tid:
        t = doc.task_map().get(str(tid).upper())
        if t is None:
            raise StoreError(f"unknown todo {tid}")
        return {"kind": req.kind, "todo": t.model_dump(mode="json")}
    items = [
        {"id": t.id, "task": t.task, "status": t.status.value}
        for t in doc.tasks[:MAX_COLLECTION_ITEMS]
    ]
    return {
        "kind": req.kind,
        "todos": items,
        "ids": [i["id"] for i in items],
        "truncated": len(doc.tasks) > MAX_COLLECTION_ITEMS,
    }


def _inspect_change(req: InspectionRequest, ctx: ReconciliationContext) -> dict[str, Any]:
    from music_rig.store import load_changes

    cid = req.id
    doc = load_changes(ctx.paths.changes)
    if not cid:
        raise StoreError("change.show requires id")
    item = doc.item_map().get(str(cid).upper())
    if item is None:
        raise StoreError(f"unknown change {cid}")
    return {"kind": req.kind, "change": item.model_dump(mode="json")}


def _inspect_gear(req: InspectionRequest, ctx: ReconciliationContext) -> dict[str, Any]:
    from music_rig.store import load_inventory

    gid = req.id
    doc = load_inventory(ctx.paths.inventory)
    if not gid:
        raise StoreError("gear.show requires id")
    item = doc.item_map().get(str(gid))
    if item is None:
        # try case-insensitive
        for k, v in doc.item_map().items():
            if k.casefold() == str(gid).casefold():
                item = v
                break
    if item is None:
        raise StoreError(f"unknown gear {gid}")
    return {"kind": req.kind, "gear": item.model_dump(mode="json")}


def _inspect_patchbay(req: InspectionRequest, ctx: ReconciliationContext) -> dict[str, Any]:
    from music_rig import patchbay_state

    bay = (req.id or "").upper()
    if not bay:
        raise StoreError("patchbay.show requires id")
    data = patchbay_state.load_raw(ctx.paths.patchbays)
    body = (data.get("patchbays") or {}).get(bay)
    if body is None:
        raise StoreError(f"unknown bay {bay}")
    return {"kind": req.kind, "bay_id": bay, "current": body}


def _inspect_channels(req: InspectionRequest, ctx: ReconciliationContext) -> dict[str, Any]:
    from music_rig import channel_state

    data = channel_state.load_raw(ctx.paths.channels)
    device = req.filters.get("device") or req.id
    if device:
        section = data.get(str(device).lower())
        return {"kind": req.kind, "device": device, "channels": section}
    # bounded summary
    summary = {
        k: sorted(v.keys()) if isinstance(v, dict) else v
        for k, v in data.items()
        if isinstance(v, dict)
    }
    return {"kind": req.kind, "channel_devices": summary}


def _inspect_routing_path(req: InspectionRequest, ctx: ReconciliationContext) -> dict[str, Any]:
    from music_rig import routing_state

    pid = req.id
    if not pid:
        raise StoreError("routing.path requires id")
    raw = routing_state.load_raw(ctx.paths.routing)
    path_id, named = routing_state.get_named_path(raw, str(pid))
    return {
        "kind": req.kind,
        "path_id": path_id,
        "path": named.model_dump(mode="json"),
    }


def _inspect_midi_device(req: InspectionRequest, ctx: ReconciliationContext) -> dict[str, Any]:
    from music_rig.store import load_midi

    did = req.id
    if not did:
        raise StoreError("midi.device requires id")
    doc = load_midi(ctx.paths.midi)
    for d in doc.devices:
        if d.gear_ref == did or d.gear_ref.casefold() == str(did).casefold():
            return {"kind": req.kind, "device": d.model_dump(mode="json")}
    raise StoreError(f"unknown midi device {did}")


def _inspect_midi_links(req: InspectionRequest, ctx: ReconciliationContext) -> dict[str, Any]:
    from music_rig.store import load_midi

    doc = load_midi(ctx.paths.midi)
    links = [x.model_dump(mode="json") for x in doc.connections[:MAX_COLLECTION_ITEMS]]
    return {
        "kind": req.kind,
        "connections": links,
        "ids": [x.get("id") for x in links],
        "truncated": len(doc.connections) > MAX_COLLECTION_ITEMS,
    }


def _inspect_controls(req: InspectionRequest, ctx: ReconciliationContext) -> dict[str, Any]:
    from music_rig.store import load_controllers

    doc = load_controllers(ctx.paths.controllers)
    gid = req.id or req.filters.get("gear_ref")
    if gid:
        for g in doc.controllers:
            if g.gear_ref == gid or g.gear_ref.casefold() == str(gid).casefold():
                return {"kind": req.kind, "controller": g.model_dump(mode="json")}
        raise StoreError(f"unknown controller gear_ref {gid}")
    ids = [g.gear_ref for g in doc.controllers[:MAX_COLLECTION_ITEMS]]
    return {
        "kind": req.kind,
        "gear_refs": ids,
        "truncated": len(doc.controllers) > MAX_COLLECTION_ITEMS,
    }


def _inspect_ableton(req: InspectionRequest, ctx: ReconciliationContext) -> dict[str, Any]:
    from music_rig.store import load_ableton

    doc = load_ableton(ctx.paths.ableton)
    tid = req.id
    if tid:
        for t in doc.templates:
            if t.id == tid:
                return {"kind": req.kind, "template": t.model_dump(mode="json")}
        raise StoreError(f"unknown ableton template {tid}")
    return {
        "kind": req.kind,
        "template_ids": [t.id for t in doc.templates[:MAX_COLLECTION_ITEMS]],
        "track_ids": [t.id for t in doc.tracks[:MAX_COLLECTION_ITEMS]],
    }


def _inspect_performance(req: InspectionRequest, ctx: ReconciliationContext) -> dict[str, Any]:
    from music_rig import store as store_mod

    doc = store_mod.load_performance()
    aid = req.id
    if aid:
        for a in doc.actions:
            if a.id == aid:
                return {"kind": req.kind, "action": a.model_dump(mode="json")}
        raise StoreError(f"unknown performance action {aid}")
    return {
        "kind": req.kind,
        "action_ids": [a.id for a in doc.actions[:MAX_COLLECTION_ITEMS]],
    }


def _inspect_refs(req: InspectionRequest, ctx: ReconciliationContext) -> dict[str, Any]:
    """Bounded cross-ref: related todos/changes for a question id."""
    from music_rig import question_service
    from music_rig.store import load_todo, load_changes

    qid = req.id
    if not qid:
        raise StoreError("refs requires question id")
    q = question_service.get_question(str(qid), questions_path=ctx.paths.questions)
    tdoc = load_todo(ctx.paths.todo)
    cdoc = load_changes(ctx.paths.changes)
    return {
        "kind": req.kind,
        "question_id": q.id,
        "todos": [
            {"id": t, "status": tdoc.task_map()[t].status.value}
            for t in q.related_todos
            if t in tdoc.task_map()
        ],
        "changes": [
            {"id": c, "status": cdoc.item_map()[c].status.value}
            for c in q.related_changes
            if c in cdoc.item_map()
        ],
    }


def _bootstrap() -> None:
    if _INSPECTORS:
        return
    _register("question.show", _inspect_question)
    _register("todo.show", _inspect_todo)
    _register("change.show", _inspect_change)
    _register("gear.show", _inspect_gear)
    _register("patchbay.show", _inspect_patchbay)
    _register("channels.show", _inspect_channels)
    _register("routing.path", _inspect_routing_path)
    _register("midi.device", _inspect_midi_device)
    _register("midi.links", _inspect_midi_links)
    _register("controls.context", _inspect_controls)
    _register("ableton.template", _inspect_ableton)
    _register("performance.action", _inspect_performance)
    _register("refs", _inspect_refs)


FORBIDDEN_KINDS = frozenset(
    {
        "read_file",
        "glob",
        "shell",
        "git",
        "web",
        "filesystem",
    }
)


def list_inspection_kinds() -> list[str]:
    _bootstrap()
    return sorted(_INSPECTORS)


def execute_inspection(
    req: InspectionRequest,
    *,
    ctx: ReconciliationContext | None = None,
) -> dict[str, Any]:
    _bootstrap()
    ctx = ctx or ReconciliationContext.default()
    if not req.kind:
        raise StoreError("inspection kind required")
    if req.kind in FORBIDDEN_KINDS or req.kind.split(".", 1)[0] in FORBIDDEN_KINDS:
        raise StoreError(f"forbidden inspection kind: {req.kind}")
    fn = _INSPECTORS.get(req.kind)
    if fn is None:
        raise StoreError(f"unregistered inspection kind: {req.kind}")
    return _bound(fn(req, ctx))
