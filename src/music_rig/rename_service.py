"""Safe ID rename / refactor for structured domains."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from music_rig import store as store_mod
from music_rig.models import InventoryDocument, InventoryItem, WishlistDocument
from music_rig.store import (
    _dump_yaml,
    load_inventory,
    load_wishlist,
    parse_existing_yaml,
    write_documents,
    write_text_files,
)

SUPPORTED_RENAME_DOMAINS = ("gear",)
DEFERRED_RENAME_DOMAINS = (
    "question",
    "todo",
    "changes",
    "inbox",
    "patchbay",
    "midi",
    "controls",
    "routing",
    "ableton",
    "performance",
)


@dataclass
class RenamePreview:
    domain: str
    old_id: str
    new_id: str
    affected_files: list[str] = field(default_factory=list)
    replacements: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def analyze_rename(domain: str, old_id: str, new_id: str) -> RenamePreview:
    domain = domain.strip().lower()
    old_id = old_id.strip()
    new_id = new_id.strip()
    preview = RenamePreview(domain=domain, old_id=old_id, new_id=new_id)
    if domain in DEFERRED_RENAME_DOMAINS:
        preview.errors.append(
            f"Rename for domain {domain!r} is deferred. Supported: {', '.join(SUPPORTED_RENAME_DOMAINS)}"
        )
        return preview
    if domain not in SUPPORTED_RENAME_DOMAINS:
        preview.errors.append(f"Unknown rename domain {domain!r}")
        return preview
    if not new_id or " " in new_id:
        preview.errors.append("New ID must be a non-empty slug without spaces")
        return preview
    if old_id == new_id:
        preview.errors.append("Old and new IDs are identical")
        return preview
    if domain == "gear":
        return _analyze_gear_rename(preview)
    return preview


def _analyze_gear_rename(preview: RenamePreview) -> RenamePreview:
    inv = load_inventory()
    if inv.resolve(preview.new_id) is not None:
        preview.errors.append(f"Collision: {preview.new_id} already exists in inventory")
        return preview
    item = inv.resolve(preview.old_id)
    if item is None:
        preview.errors.append(f"Unknown gear {preview.old_id}")
        return preview
    if item.id != preview.old_id:
        preview.errors.append(
            f"{preview.old_id} resolves to parent {item.id}; rename the item id, not a unit id"
        )
        return preview
    preview.affected_files.append(str(store_mod.INVENTORY_PATH))
    preview.replacements.append(f"inventory item id {preview.old_id} -> {preview.new_id}")

    # Wishlist inventory_ref
    for w in load_wishlist().items:
        if w.inventory_ref == preview.old_id:
            preview.affected_files.append(str(store_mod.WISHLIST_PATH))
            preview.replacements.append(f"wishlist {w.item} inventory_ref")

    # Scan CURRENT YAML for gear_ref string matches (all-or-nothing list)
    for path in (
        store_mod.MIDI_PATH,
        store_mod.CONTROLLERS_PATH,
        store_mod.ROUTING_PATH,
        store_mod.PERFORMANCE_PATH,
        store_mod.ABLETON_PATH,
    ):
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if preview.old_id in text:
            preview.affected_files.append(str(path))
            preview.replacements.append(f"string gear_ref/id occurrences in {path.name}")

    preview.affected_files = list(dict.fromkeys(preview.affected_files))
    return preview


def apply_rename(domain: str, old_id: str, new_id: str, *, dry_run: bool = False) -> RenamePreview:
    preview = analyze_rename(domain, old_id, new_id)
    if not preview.ok:
        return preview
    if dry_run:
        return preview
    if domain == "gear":
        _apply_gear_rename(preview)
    return preview


def _apply_gear_rename(preview: RenamePreview) -> None:
    """All-or-nothing transactional-ish rewrite of known structured refs."""
    old, new = preview.old_id, preview.new_id
    inv = load_inventory()
    items: list[InventoryItem] = []
    for item in inv.items:
        if item.id == old:
            data = item.model_dump()
            data["id"] = new
            items.append(InventoryItem.model_validate(data))
        else:
            items.append(item)
    new_inv = InventoryDocument(items=items)

    wish = load_wishlist()
    wish_items = []
    for w in wish.items:
        data = w.model_dump()
        if data.get("inventory_ref") == old:
            data["inventory_ref"] = new
        wish_items.append(type(w).model_validate(data))
    new_wish = WishlistDocument(items=wish_items)

    # Rewrite CURRENT files with careful token replace for gear_ref values
    file_writes: list[tuple[Path, str]] = []
    skip = {str(store_mod.INVENTORY_PATH), str(store_mod.WISHLIST_PATH)}
    for rel in preview.affected_files:
        if rel in skip:
            continue
        path = Path(rel)
        raw = parse_existing_yaml(path)
        replaced = _replace_gear_refs(raw, old, new)
        file_writes.append((path, _dump_yaml(replaced)))

    write_documents(wishlist=new_wish)
    from music_rig.store import save_inventory

    save_inventory(new_inv)
    if file_writes:
        write_text_files(file_writes)


def _replace_gear_refs(obj: Any, old: str, new: str) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in {"gear_ref", "gear", "inventory_ref"} and v == old:
                out[k] = new
            else:
                out[k] = _replace_gear_refs(v, old, new)
        return out
    if isinstance(obj, list):
        return [_replace_gear_refs(x, old, new) for x in obj]
    return obj
