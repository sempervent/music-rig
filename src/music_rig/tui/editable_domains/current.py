"""Gear / CURRENT-domain editable adapters (pragmatic FieldSpec coverage)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from music_rig import current_service, inventory_state
from music_rig import store as store_mod
from music_rig.channel_state import propose_set_source
from music_rig.midi_state import (
    propose_ableton_set,
    propose_set_channel,
    propose_set_clock_master,
)
from music_rig.models import GearCondition, InventoryDocument, InventoryItem, OwnershipStatus
from music_rig.routing_state import propose_set_mode as routing_propose_set_mode
from music_rig.store import (
    StoreError,
    load_inventory,
    parse_existing_yaml,
)
from music_rig.tui.editable import ApplyResult, BaseEditableAdapter, WorkingRecord
from music_rig.tui.fields import FieldSpec, FieldType, enum_spec, readonly_spec, text_spec


class GearEditableAdapter(BaseEditableAdapter):
    id = "gear"
    label = "Gear"

    def columns(self) -> list[str]:
        return ["ID", "Name", "Ownership", "Condition"]

    def source_path(self) -> Path | None:
        return store_mod.INVENTORY_PATH

    def get_field_specs(self) -> list[FieldSpec]:
        return [
            readonly_spec("id", "ID", help="Rename via rename_service / rig rename"),
            text_spec("name", "Name", required=True),
            text_spec("manufacturer", "Manufacturer"),
            text_spec("model", "Model"),
            text_spec("category", "Category", required=True),
            FieldSpec(
                name="quantity", label="Quantity", type=FieldType.INT, required=True, min_value=1
            ),
            enum_spec("ownership_status", "Ownership", [s.value for s in OwnershipStatus]),
            enum_spec("condition", "Condition", [s.value for s in GearCondition]),
            text_spec("location", "Location"),
            text_spec("notes", "Notes", multiline=True),
        ]

    def list_records(
        self, *, status_filter: str | None = None, search: str = ""
    ) -> list[dict[str, Any]]:
        needle = search.casefold()
        rows = []
        for g in load_inventory().items:
            blob = f"{g.id} {g.name} {g.category}"
            if needle and needle not in blob.casefold():
                continue
            rows.append(
                {
                    "id": g.id,
                    "cells": [g.id, g.name[:30], g.ownership_status.value, g.condition.value],
                    "search_text": blob,
                }
            )
        return rows

    def get_record(self, record_id: str) -> dict[str, Any]:
        item = load_inventory().resolve(record_id)
        if item is None:
            raise StoreError(f"Unknown gear {record_id}")
        return {
            "id": item.id,
            "name": item.name,
            "manufacturer": item.manufacturer or "",
            "model": item.model or "",
            "category": item.category,
            "quantity": item.quantity,
            "ownership_status": item.ownership_status.value,
            "condition": item.condition.value,
            "location": item.location or "",
            "notes": item.notes,
        }

    def detail_markdown(self, record_id: str) -> str:
        r = self.get_record(record_id)
        return "\n".join(
            [
                f"# {r['id']} — {r['name']}",
                "",
                f"Ownership: {r['ownership_status']}",
                f"Condition: {r['condition']}",
                f"Location: {r['location'] or '—'}",
                f"Notes: {r['notes'] or '—'}",
            ]
        )

    def semantic_actions(self) -> list[tuple[str, str, str]]:
        return [("retire", "x", "Retire")]

    def run_semantic(
        self, action_id: str, record_id: str, *, payload: dict[str, Any] | None = None
    ) -> ApplyResult:
        if action_id != "retire":
            raise StoreError(f"Unknown action {action_id}")
        preview, data = inventory_state.propose_retire(record_id)
        current_service.commit_inventory(data, preview, render=True)
        return ApplyResult(record_id=record_id, message=preview.message)

    def commit(self, working: WorkingRecord, *, render: bool = True) -> ApplyResult:
        working.ensure_current()
        doc = load_inventory()
        items = []
        found = None
        for item in doc.items:
            if item.id == working.record_id or item.id.lower() == working.record_id.lower():
                data = item.model_dump()
                data.update(working.mutations)
                for opt in ("manufacturer", "model", "location"):
                    if not data.get(opt):
                        data[opt] = None
                found = InventoryItem.model_validate(data)
                items.append(found)
            else:
                items.append(item)
        if found is None:
            raise StoreError(f"Unknown gear {working.record_id}")
        from music_rig.store import save_inventory

        save_inventory(InventoryDocument(items=items))
        if render:
            from music_rig.render import render_docs

            render_docs(write=True)
        working.discard()
        working.baseline = self.get_record(found.id)
        working.refresh_source_hash()
        return ApplyResult(record_id=found.id, message=f"{found.id} saved")


def _yaml_rows(path: Path, key: str, id_fn, cell_fn, search_fn) -> list[dict[str, Any]]:
    raw = parse_existing_yaml(path)
    if not isinstance(raw, dict):
        return []
    container = raw.get(key) or {}
    rows = []
    if isinstance(container, dict):
        items = container.items()
    elif isinstance(container, list):
        items = ((id_fn(x), x) for x in container)
    else:
        return []
    for iid, obj in items:
        rows.append(
            {
                "id": str(iid),
                "cells": cell_fn(iid, obj),
                "search_text": search_fn(iid, obj),
                "raw": obj,
            }
        )
    return rows


class ChannelsEditableAdapter(BaseEditableAdapter):
    id = "channels"
    label = "Channel map"

    def columns(self) -> list[str]:
        return ["Device", "Channel", "Source"]

    def source_path(self) -> Path | None:
        return store_mod.CHANNEL_MAP_PATH

    def get_field_specs(self) -> list[FieldSpec]:
        return [
            readonly_spec("device", "Device"),
            readonly_spec("channel", "Channel"),
            text_spec("source", "Source", help="Empty clears source"),
        ]

    def list_records(
        self, *, status_filter: str | None = None, search: str = ""
    ) -> list[dict[str, Any]]:
        from music_rig.channel_state import load_raw

        data = load_raw()
        needle = search.casefold()
        rows = []
        for device, channels in data.items():
            if not isinstance(channels, dict):
                continue
            for ch, meta in channels.items():
                if isinstance(meta, dict):
                    source = meta.get("source") or ""
                else:
                    source = str(meta or "")
                rid = f"{device}/{ch}"
                blob = f"{rid} {source}"
                if needle and needle not in blob.casefold():
                    continue
                rows.append(
                    {
                        "id": rid,
                        "cells": [str(device), str(ch), str(source)[:40] or "—"],
                        "search_text": blob,
                    }
                )
        return rows

    def get_record(self, record_id: str) -> dict[str, Any]:
        device, _, channel = record_id.partition("/")
        from music_rig.channel_state import load_raw, resolve_channel_key

        data = load_raw()
        section = data.get(device.strip().lower()) or data.get(device) or {}
        if not isinstance(section, dict):
            raise StoreError(f"Unknown device {device}")
        key = resolve_channel_key(device.strip().lower(), channel, section)
        meta = section[key]
        source = meta.get("source") or "" if isinstance(meta, dict) else str(meta or "")
        return {"device": device.strip().lower(), "channel": str(key), "source": source or ""}

    def detail_markdown(self, record_id: str) -> str:
        r = self.get_record(record_id)
        return f"# {r['device']} ch {r['channel']}\n\nSource: {r['source'] or '—'}"

    def commit(self, working: WorkingRecord, *, render: bool = True) -> ApplyResult:
        working.ensure_current()
        device = working.baseline["device"]
        channel = working.baseline["channel"]
        source = working.mutations.get("source", working.baseline.get("source"))
        cleaned = None if source in (None, "") else str(source)
        preview, data = propose_set_source(device, channel, cleaned)
        current_service.commit_channel(data, preview, render=render)
        working.discard()
        working.baseline = self.get_record(working.record_id)
        working.refresh_source_hash()
        return ApplyResult(record_id=working.record_id, message=preview.message)


class RoutingEditableAdapter(BaseEditableAdapter):
    id = "routing"
    label = "Routing"

    def columns(self) -> list[str]:
        return ["Path", "Mode", "Nodes"]

    def source_path(self) -> Path | None:
        return store_mod.ROUTING_PATH

    def get_field_specs(self) -> list[FieldSpec]:
        return [
            readonly_spec("path", "Path"),
            readonly_spec("status", "Status"),
            text_spec(
                "node_mode_edit",
                "Set node mode (Advanced)",
                help="Format: <node_token>=<mode> — uses routing_state.propose_set_mode. "
                "Structural move/insert/remove: rig current path …",
            ),
        ]

    def list_records(
        self, *, status_filter: str | None = None, search: str = ""
    ) -> list[dict[str, Any]]:
        from music_rig.routing_state import load_raw

        data = load_raw()
        needle = search.casefold()
        rows = []
        for path, info in (data.get("named_paths") or {}).items():
            status = str((info or {}).get("status") or "—")
            branches = (info or {}).get("branches") or {}
            node_count = 0
            if isinstance(branches, dict):
                for br in branches.values():
                    node_count += len((br or {}).get("nodes") or [])
            blob = f"{path} {status}"
            if needle and needle not in blob.casefold():
                continue
            rows.append(
                {
                    "id": path,
                    "cells": [path, status, str(node_count)],
                    "search_text": blob,
                }
            )
        return rows

    def get_record(self, record_id: str) -> dict[str, Any]:
        from music_rig.routing_state import load_raw

        data = load_raw()
        info = (data.get("named_paths") or {}).get(record_id) or {}
        return {
            "path": record_id,
            "status": str(info.get("status") or ""),
            "node_mode_edit": "",
        }

    def detail_markdown(self, record_id: str) -> str:
        from music_rig.routing_state import load_raw

        data = load_raw()
        info = (data.get("named_paths") or {}).get(record_id) or {}
        lines = [
            f"# {record_id}",
            "",
            f"Status: {info.get('status') or '—'}",
            "",
            "## Branches / nodes",
        ]
        for bid, br in (
            (info.get("branches") or {}) if isinstance(info.get("branches"), dict) else {}
        ).items():
            lines.append(f"### {bid}")
            for i, n in enumerate((br or {}).get("nodes") or []):
                if isinstance(n, dict):
                    lines.append(
                        f"{i}. {n.get('id') or n.get('label')} mode={n.get('mode') or '—'}"
                    )
                else:
                    lines.append(f"{i}. {n}")
        lines.append("")
        lines.append("Structural edits: `rig current path move|insert|remove|set-mode`.")
        return "\n".join(lines)

    def commit(self, working: WorkingRecord, *, render: bool = True) -> ApplyResult:
        working.ensure_current()
        path = working.record_id
        edit = str(working.mutations.get("node_mode_edit") or "").strip()
        if not edit:
            raise StoreError("Provide node_mode_edit as node_token=mode")
        if "=" not in edit:
            raise StoreError("node_mode_edit must be node_token=mode")
        node_token, _, mode = edit.partition("=")
        preview, data = routing_propose_set_mode(path, node_token.strip(), mode.strip())
        current_service.commit_routing(data, preview, render=render)
        working.discard()
        working.baseline = self.get_record(working.record_id)
        working.refresh_source_hash()
        return ApplyResult(record_id=path, message=preview.message)


class MidiEditableAdapter(BaseEditableAdapter):
    id = "midi"
    label = "MIDI"

    def columns(self) -> list[str]:
        return ["Kind", "ID", "Summary"]

    def source_path(self) -> Path | None:
        return store_mod.MIDI_PATH

    def get_field_specs(self) -> list[FieldSpec]:
        return [
            readonly_spec("kind", "Kind"),
            readonly_spec("id", "ID"),
            text_spec(
                "value", "Value", help="Channel number, clock endpoint, or Ableton port field"
            ),
            text_spec("notes", "Notes", multiline=True),
        ]

    def list_records(
        self, *, status_filter: str | None = None, search: str = ""
    ) -> list[dict[str, Any]]:
        from music_rig.midi_state import load_raw

        raw = load_raw()
        needle = search.casefold()
        rows: list[dict[str, Any]] = []
        for item in raw.get("channels") or []:
            if not isinstance(item, dict):
                continue
            gear = str(item.get("gear_ref") or "")
            ch = item.get("channel")
            rid = f"channel:{gear}"
            blob = f"{rid} {ch}"
            if not needle or needle in blob.casefold():
                rows.append({"id": rid, "cells": ["channel", gear, str(ch)], "search_text": blob})
        for link in raw.get("connections") or []:
            if isinstance(link, dict):
                lid = str(link.get("id") or "")
                rid = f"link:{lid}"
                summary = f"{link.get('source')} -> {link.get('destination')}"
                blob = f"{rid} {summary}"
                if not needle or needle in blob.casefold():
                    rows.append(
                        {"id": rid, "cells": ["link", lid, summary[:40]], "search_text": blob}
                    )
        master = (raw.get("clock") or {}).get("master") or {}
        if isinstance(master, dict):
            ep = str(master.get("endpoint_ref") or "—")
            rows.append(
                {
                    "id": "clock:master",
                    "cells": ["clock", "master", ep],
                    "search_text": f"clock {ep}",
                }
            )
        for port in raw.get("ableton_ports") or []:
            if isinstance(port, dict):
                pid = str(port.get("id") or "")
                rid = f"ableton:{pid}"
                summary = f"track={port.get('track')} sync={port.get('sync')}"
                rows.append(
                    {
                        "id": rid,
                        "cells": ["ableton", pid, summary[:40]],
                        "search_text": f"{rid} {summary}",
                    }
                )
        return rows

    def get_record(self, record_id: str) -> dict[str, Any]:
        kind, _, oid = record_id.partition(":")
        from music_rig.midi_state import load_raw

        raw = load_raw()
        value = ""
        if kind == "channel":
            for item in raw.get("channels") or []:
                if isinstance(item, dict) and item.get("gear_ref") == oid:
                    value = str(item.get("channel") or "")
                    break
        elif kind == "clock":
            master = (raw.get("clock") or {}).get("master") or {}
            value = str(master.get("endpoint_ref") or "") if isinstance(master, dict) else ""
        elif kind == "ableton":
            for port in raw.get("ableton_ports") or []:
                if isinstance(port, dict) and str(port.get("id")) == oid:
                    value = f"track={port.get('track')}"
                    break
        elif kind == "link":
            for link in raw.get("connections") or []:
                if isinstance(link, dict) and str(link.get("id")) == oid:
                    value = f"{link.get('source')}->{link.get('destination')}"
                    break
        return {"kind": kind, "id": oid, "value": value, "notes": ""}

    def detail_markdown(self, record_id: str) -> str:
        r = self.get_record(record_id)
        return f"# MIDI {r['kind']} {r['id']}\n\nValue: {r['value'] or '—'}\n\nDocumented state only — no MIDI TX."

    def commit(self, working: WorkingRecord, *, render: bool = True) -> ApplyResult:
        working.ensure_current()
        kind = working.baseline["kind"]
        oid = working.baseline["id"]
        value = str(working.mutations.get("value", working.baseline.get("value") or "")).strip()
        if kind == "channel":
            preview, data = propose_set_channel(oid, value)
        elif kind == "clock" and oid == "master":
            preview, data = propose_set_clock_master(value)
        elif kind == "ableton":
            # value like track=on
            if value.startswith("track="):
                preview, data = propose_ableton_set(oid, track=value.split("=", 1)[1])
            elif value.startswith("sync="):
                preview, data = propose_ableton_set(oid, sync=value.split("=", 1)[1])
            elif value.startswith("remote="):
                preview, data = propose_ableton_set(oid, remote=value.split("=", 1)[1])
            else:
                raise StoreError("Ableton value must be track=…, sync=…, or remote=…")
        else:
            raise StoreError(f"Editing {kind} via form deferred; use CLI midi mutations")
        current_service.commit_midi(data, preview, render=render)
        working.discard()
        working.baseline = self.get_record(working.record_id)
        working.refresh_source_hash()
        return ApplyResult(record_id=working.record_id, message=preview.message)


class ControllersEditableAdapter(BaseEditableAdapter):
    id = "controls"
    label = "Controllers"

    def columns(self) -> list[str]:
        return ["Gear", "Context", "Control", "Avail"]

    def source_path(self) -> Path | None:
        return store_mod.CONTROLLERS_PATH

    def get_field_specs(self) -> list[FieldSpec]:
        return [
            readonly_spec("gear", "Gear"),
            readonly_spec("context", "Context"),
            readonly_spec("control", "Control"),
            enum_spec(
                "availability", "Availability", ("AVAILABLE", "BROKEN", "UNKNOWN"), required=False
            ),
            text_spec("evidence", "Evidence", multiline=True),
            text_spec(
                "notes",
                "Notes",
                multiline=True,
                help="BROKEN+mapped invariant enforced by control_state",
            ),
        ]

    def list_records(
        self, *, status_filter: str | None = None, search: str = ""
    ) -> list[dict[str, Any]]:
        from music_rig.control_state import load_raw

        raw = load_raw()
        needle = search.casefold()
        rows = []
        for body in raw.get("controllers") or []:
            if not isinstance(body, dict):
                continue
            gear = str(body.get("gear_ref") or body.get("id") or "")
            contexts = body.get("contexts") or []
            if isinstance(contexts, dict):
                ctx_iter = contexts.items()
            else:
                ctx_iter = ((str(c.get("id")), c) for c in contexts if isinstance(c, dict))
            for ctx_id, ctx in ctx_iter:
                controls = (ctx or {}).get("controls") or []
                if isinstance(controls, dict):
                    ctl_iter = controls.items()
                else:
                    ctl_iter = ((str(c.get("id")), c) for c in controls if isinstance(c, dict))
                for ctl_id, ctl in ctl_iter:
                    avail = str((ctl or {}).get("availability") or "—")
                    rid = f"{gear}/{ctx_id}/{ctl_id}"
                    blob = f"{rid} {avail}"
                    if needle and needle not in blob.casefold():
                        continue
                    rows.append(
                        {
                            "id": rid,
                            "cells": [gear[:16], str(ctx_id)[:16], str(ctl_id)[:16], avail],
                            "search_text": blob,
                        }
                    )
        return rows

    def get_record(self, record_id: str) -> dict[str, Any]:
        parts = record_id.split("/", 2)
        if len(parts) != 3:
            raise StoreError(f"Invalid control id {record_id}")
        gear, context, control = parts
        from music_rig.control_state import load_raw

        raw = load_raw()
        ctl: dict[str, Any] = {}
        for body in raw.get("controllers") or []:
            if not isinstance(body, dict):
                continue
            if str(body.get("gear_ref") or body.get("id")) != gear:
                continue
            contexts = body.get("contexts") or []
            ctx_list = (
                list(contexts.values())
                if isinstance(contexts, dict)
                else [c for c in contexts if isinstance(c, dict)]
            )
            for ctx in ctx_list:
                if str(ctx.get("id")) != context:
                    continue
                controls = ctx.get("controls") or []
                ctl_list = (
                    list(controls.values())
                    if isinstance(controls, dict)
                    else [c for c in controls if isinstance(c, dict)]
                )
                for c in ctl_list:
                    if str(c.get("id")) == control:
                        ctl = c
                        break
        return {
            "gear": gear,
            "context": context,
            "control": control,
            "availability": str(ctl.get("availability") or ""),
            "evidence": str(ctl.get("evidence") or ""),
            "notes": str(ctl.get("notes") or ""),
        }

    def detail_markdown(self, record_id: str) -> str:
        r = self.get_record(record_id)
        return (
            f"# {r['gear']} / {r['context']} / {r['control']}\n\n"
            f"Availability: {r['availability'] or '—'}\n"
            f"Evidence: {r['evidence'] or '—'}\n"
        )

    def commit(self, working: WorkingRecord, *, render: bool = True) -> ApplyResult:
        working.ensure_current()
        from music_rig.control_state import propose_set_availability, propose_set_evidence

        gear = working.baseline["gear"]
        context = working.baseline["context"]
        control = working.baseline["control"]
        data = None
        messages = []
        if "availability" in working.mutations and working.mutations["availability"]:
            preview, data = propose_set_availability(
                gear, context, control, working.mutations["availability"], data=data
            )
            messages.append(preview.message)
        if "evidence" in working.mutations:
            preview, data = propose_set_evidence(
                gear, context, control, working.mutations["evidence"], data=data
            )
            messages.append(preview.message)
        if data is None:
            raise StoreError("No controller mutations to apply")
        # Use last preview for commit metadata
        current_service.commit_controllers(data, preview, render=render)
        working.discard()
        working.baseline = self.get_record(working.record_id)
        working.refresh_source_hash()
        return ApplyResult(record_id=working.record_id, message="; ".join(messages))


class AbletonEditableAdapter(BaseEditableAdapter):
    id = "ableton"
    label = "Ableton"

    def columns(self) -> list[str]:
        return ["Kind", "ID", "Name"]

    def source_path(self) -> Path | None:
        return store_mod.ABLETON_PATH

    def get_field_specs(self) -> list[FieldSpec]:
        return [
            readonly_spec("kind", "Kind"),
            readonly_spec("id", "ID"),
            text_spec("name", "Name"),
            text_spec("notes", "Notes", multiline=True),
        ]

    def list_records(
        self, *, status_filter: str | None = None, search: str = ""
    ) -> list[dict[str, Any]]:
        raw = parse_existing_yaml(store_mod.ABLETON_PATH)
        if not isinstance(raw, dict):
            return []
        needle = search.casefold()
        rows = []
        for kind in ("tracks", "sends", "actions", "templates"):
            block = raw.get(kind) or {}
            if isinstance(block, dict):
                iterable = block.items()
            elif isinstance(block, list):
                iterable = ((str(i), x) for i, x in enumerate(block))
            else:
                continue
            for kid, obj in iterable:
                name = ""
                if isinstance(obj, dict):
                    name = str(obj.get("name") or obj.get("label") or "")
                    kid = str(obj.get("id") or kid)
                rid = f"{kind}:{kid}"
                blob = f"{rid} {name}"
                if needle and needle not in blob.casefold():
                    continue
                rows.append(
                    {
                        "id": rid,
                        "cells": [kind, str(kid)[:20], name[:40] or "—"],
                        "search_text": blob,
                    }
                )
        return rows

    def get_record(self, record_id: str) -> dict[str, Any]:
        kind, _, oid = record_id.partition(":")
        raw = parse_existing_yaml(store_mod.ABLETON_PATH)
        block = (raw or {}).get(kind) or {}
        obj: Any = {}
        if isinstance(block, dict):
            obj = block.get(oid) or {}
        elif isinstance(block, list):
            for item in block:
                if isinstance(item, dict) and str(item.get("id")) == oid:
                    obj = item
                    break
        return {
            "kind": kind,
            "id": oid,
            "name": str((obj or {}).get("name") or (obj or {}).get("label") or ""),
            "notes": str((obj or {}).get("notes") or ""),
        }

    def detail_markdown(self, record_id: str) -> str:
        r = self.get_record(record_id)
        return f"# Ableton {r['kind']} {r['id']}\n\nName: {r['name'] or '—'}\nNotes: {r['notes'] or '—'}"

    def commit(self, working: WorkingRecord, *, render: bool = True) -> ApplyResult:
        working.ensure_current()
        from music_rig.store import _dump_yaml, write_text_files

        raw = parse_existing_yaml(store_mod.ABLETON_PATH)
        if not isinstance(raw, dict):
            raise StoreError("ableton.yaml invalid")
        kind = working.baseline["kind"]
        oid = working.baseline["id"]
        block = raw.get(kind)
        if isinstance(block, dict) and oid in block and isinstance(block[oid], dict):
            if "name" in working.mutations:
                block[oid]["name"] = working.mutations["name"]
            if "notes" in working.mutations:
                block[oid]["notes"] = working.mutations["notes"]
        elif isinstance(block, list):
            for item in block:
                if isinstance(item, dict) and str(item.get("id")) == oid:
                    if "name" in working.mutations:
                        item["name"] = working.mutations["name"]
                    if "notes" in working.mutations:
                        item["notes"] = working.mutations["notes"]
                    break
        else:
            raise StoreError(f"Cannot locate Ableton {working.record_id}")
        write_text_files([(store_mod.ABLETON_PATH, _dump_yaml(raw))])
        working.discard()
        working.baseline = self.get_record(working.record_id)
        working.refresh_source_hash()
        return ApplyResult(record_id=working.record_id, message=f"{working.record_id} saved")


class PerformanceEditableAdapter(BaseEditableAdapter):
    id = "performance"
    label = "Performance"

    def columns(self) -> list[str]:
        return ["Kind", "ID", "Summary"]

    def source_path(self) -> Path | None:
        return store_mod.PERFORMANCE_PATH

    def get_field_specs(self) -> list[FieldSpec]:
        return [
            readonly_spec("kind", "Kind"),
            readonly_spec("id", "ID"),
            text_spec("summary", "Summary / label"),
            text_spec("evidence", "Evidence", multiline=True),
            text_spec(
                "notes",
                "Notes",
                multiline=True,
                help="No panic/record execution from TUI — documentation only.",
            ),
        ]

    def list_records(
        self, *, status_filter: str | None = None, search: str = ""
    ) -> list[dict[str, Any]]:
        from music_rig.performance_state import load_document

        doc = load_document()
        raw = doc.model_dump() if hasattr(doc, "model_dump") else {}
        needle = search.casefold()
        rows = []
        for kind in ("modes", "actions", "effects", "bindings", "recovery", "requirements"):
            block = raw.get(kind) or []
            if isinstance(block, dict):
                iterable = block.items()
            elif isinstance(block, list):
                iterable = (
                    (str(x.get("id") if isinstance(x, dict) else i), x) for i, x in enumerate(block)
                )
            else:
                continue
            for kid, obj in iterable:
                summary = ""
                if isinstance(obj, dict):
                    kid = str(obj.get("id") or kid)
                    summary = str(obj.get("name") or obj.get("label") or obj.get("action") or "")
                rid = f"{kind}:{kid}"
                blob = f"{rid} {summary}"
                if needle and needle not in blob.casefold():
                    continue
                rows.append(
                    {
                        "id": rid,
                        "cells": [kind, str(kid)[:20], summary[:40] or "—"],
                        "search_text": blob,
                    }
                )
        return rows

    def get_record(self, record_id: str) -> dict[str, Any]:
        kind, _, oid = record_id.partition(":")
        from music_rig.performance_state import load_document

        raw = load_document().model_dump()
        block = raw.get(kind) or []
        obj: Any = {}
        if isinstance(block, dict):
            obj = block.get(oid) or {}
        elif isinstance(block, list):
            for item in block:
                if isinstance(item, dict) and str(item.get("id")) == oid:
                    obj = item
                    break
        return {
            "kind": kind,
            "id": oid,
            "summary": str((obj or {}).get("name") or (obj or {}).get("label") or ""),
            "evidence": str((obj or {}).get("evidence") or ""),
            "notes": str((obj or {}).get("notes") or ""),
        }

    def detail_markdown(self, record_id: str) -> str:
        r = self.get_record(record_id)
        return (
            f"# Performance {r['kind']} {r['id']}\n\n"
            f"{r['summary'] or '—'}\n\nEvidence: {r['evidence'] or '—'}\n\n"
            "_No execution of panic/record from TUI._"
        )

    def commit(self, working: WorkingRecord, *, render: bool = True) -> ApplyResult:
        working.ensure_current()
        if "evidence" in working.mutations and working.baseline["kind"] == "bindings":
            from music_rig.performance_state import propose_set_evidence

            preview, data = propose_set_evidence(
                working.baseline["id"], working.mutations["evidence"]
            )
            current_service.commit_performance(data, preview, render=render)
            msg = preview.message
        else:
            raise StoreError(
                "General performance field edits: use evidence on bindings, "
                "or CLI `rig current performance …`"
            )
        working.discard()
        working.baseline = self.get_record(working.record_id)
        working.refresh_source_hash()
        return ApplyResult(record_id=working.record_id, message=msg)


class BackupEditableAdapter(BaseEditableAdapter):
    id = "backup"
    label = "Backups"

    def columns(self) -> list[str]:
        return ["ID", "Kind", "Path"]

    def source_path(self) -> Path | None:
        return store_mod.BACKUPS_PATH

    def get_field_specs(self) -> list[FieldSpec]:
        return [
            readonly_spec("id", "ID"),
            text_spec("label", "Label"),
            readonly_spec(
                "locator_key", "Locator key", help="Paths live in .rig.local.yaml — not edited here"
            ),
            text_spec("notes", "Notes", multiline=True),
            text_spec("manual_instructions", "Manual instructions", multiline=True),
        ]

    def list_records(
        self, *, status_filter: str | None = None, search: str = ""
    ) -> list[dict[str, Any]]:
        raw = parse_existing_yaml(store_mod.BACKUPS_PATH)
        if not isinstance(raw, dict):
            return []
        needle = search.casefold()
        rows = []
        for obj in raw.get("items") or []:
            if not isinstance(obj, dict):
                continue
            rid = str(obj.get("id") or "")
            kind = str(obj.get("kind") or "—")
            label = str(obj.get("label") or "")
            blob = f"{rid} {label} {kind}"
            if needle and needle not in blob.casefold():
                continue
            rows.append({"id": rid, "cells": [rid, kind, label[:40] or "—"], "search_text": blob})
        return rows

    def get_record(self, record_id: str) -> dict[str, Any]:
        raw = parse_existing_yaml(store_mod.BACKUPS_PATH)
        obj: dict[str, Any] = {}
        for item in (raw or {}).get("items") or []:
            if isinstance(item, dict) and str(item.get("id")) == record_id:
                obj = item
                break
        if not obj:
            raise StoreError(f"Backup {record_id} not found")
        return {
            "id": record_id,
            "label": str(obj.get("label") or ""),
            "locator_key": str(obj.get("locator_key") or ""),
            "notes": str(obj.get("notes") or ""),
            "manual_instructions": str(obj.get("manual_instructions") or ""),
        }

    def detail_markdown(self, record_id: str) -> str:
        r = self.get_record(record_id)
        return (
            f"# Backup {r['id']}\n\n{r['label']}\n"
            f"Locator: {r['locator_key']}\nNotes: {r['notes'] or '—'}"
        )

    def commit(self, working: WorkingRecord, *, render: bool = True) -> ApplyResult:
        working.ensure_current()
        from music_rig.store import _dump_yaml, write_text_files

        raw = parse_existing_yaml(store_mod.BACKUPS_PATH)
        if not isinstance(raw, dict):
            raise StoreError("backups.yaml invalid")
        found = False
        for obj in raw.get("items") or []:
            if isinstance(obj, dict) and str(obj.get("id")) == working.record_id:
                for field in ("label", "notes", "manual_instructions"):
                    if field in working.mutations:
                        obj[field] = working.mutations[field]
                found = True
                break
        if not found:
            raise StoreError(f"Backup {working.record_id} not found")
        write_text_files([(store_mod.BACKUPS_PATH, _dump_yaml(raw))])
        working.discard()
        working.baseline = self.get_record(working.record_id)
        working.refresh_source_hash()
        return ApplyResult(record_id=working.record_id, message=f"{working.record_id} saved")
