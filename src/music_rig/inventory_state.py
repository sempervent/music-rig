"""Typed CURRENT inventory mutations for data/inventory.yaml."""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

from music_rig.models import (
    CurrentPreview,
    GearCondition,
    InventoryDocument,
    InventoryItem,
    OwnershipStatus,
    TodoDocument,
    TodoStatus,
    WishlistDocument,
    WishlistItem,
    WishStatus,
)
from music_rig.store import (
    INVENTORY_PATH,
    StoreError,
    _dump_yaml,
    load_todo,
    load_wishlist,
    parse_existing_yaml,
)

INVENTORY_HEADER = (
    "# Canonical owned-equipment inventory.\n"
    "# Owned ≠ CURRENT signal-path membership (see data/routing.yaml).\n"
    "# Stable gear IDs are durable; do not rename casually.\n"
    "# Wishlist items are not owned until recorded via inventory / acquire.\n"
)
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _extract_leading_comment_header(text: str) -> str:
    lines = text.splitlines(keepends=True)
    index = 0
    saw_comment = False
    while index < len(lines):
        stripped = lines[index].lstrip()
        if stripped.startswith("#"):
            saw_comment = True
            index += 1
        elif not stripped.strip() and (saw_comment or index == 0):
            index += 1
        else:
            break
    return "".join(lines[:index]) if saw_comment else ""


def load_raw(path: Path | None = None) -> dict[str, Any]:
    target = path or INVENTORY_PATH
    raw = parse_existing_yaml(target)
    if not isinstance(raw, dict):
        raise StoreError(f"{target} must contain a YAML mapping")
    return raw


def load_document(path: Path | None = None) -> InventoryDocument:
    try:
        return InventoryDocument.model_validate(load_raw(path))
    except Exception as exc:
        if isinstance(exc, StoreError):
            raise
        raise StoreError(f"Inventory schema validation failed: {exc}") from exc


def dump_with_header(data: dict[str, Any], *, existing_text: str | None = None) -> str:
    header = INVENTORY_HEADER
    if existing_text is not None:
        header = _extract_leading_comment_header(existing_text) or header
    if header and not header.endswith("\n"):
        header += "\n"
    return header + _dump_yaml(data)


def validate_inventory_doc(data: dict[str, Any]) -> list[str]:
    if not isinstance(data, dict):
        return ["inventory document must be a mapping"]
    try:
        doc = InventoryDocument.model_validate(data)
    except Exception as exc:
        return [str(exc)]
    errors: list[str] = []
    for item in doc.items:
        if not _ID_RE.fullmatch(item.id):
            errors.append(f"{item.id!r}: inventory IDs use lowercase letters, digits, and hyphens")
        for unit in item.units:
            if not _ID_RE.fullmatch(unit.id):
                errors.append(f"{unit.id!r}: unit IDs use lowercase letters, digits, and hyphens")
    return errors


def slugify(*parts: str | None) -> str:
    """Create a stable-looking ID, preferring manufacturer/model identity."""
    useful = [p.strip() for p in parts if p and p.strip() and p.strip().upper() != "UNKNOWN"]
    source = " ".join(useful)
    slug = re.sub(r"[^a-z0-9]+", "-", source.casefold()).strip("-")
    if not slug:
        raise StoreError("Cannot generate inventory ID from empty fields.")
    return slug


def _new_id(
    doc: InventoryDocument,
    *,
    explicit_id: str | None,
    name: str,
    manufacturer: str | None,
    model: str | None,
) -> str:
    base = (
        slugify(explicit_id)
        if explicit_id
        else slugify(manufacturer, model)
        if manufacturer and model
        else slugify(name)
    )
    known = {
        value.casefold()
        for item in doc.items
        for value in [item.id, *(unit.id for unit in item.units)]
    }
    if explicit_id and base.casefold() in known:
        raise StoreError(f"Inventory ID {base!r} already exists.")
    candidate = base
    suffix = 2
    while candidate.casefold() in known:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _validated_raw(raw: dict[str, Any]) -> InventoryDocument:
    errors = validate_inventory_doc(raw)
    if errors:
        raise StoreError("Inventory validation failed: " + "; ".join(errors))
    return InventoryDocument.model_validate(raw)


def _item_snapshot(item: InventoryItem) -> dict[str, Any]:
    return item.model_dump(mode="json", exclude_none=True)


def _replace_item(
    raw: dict[str, Any], gear_id: str, updates: dict[str, Any], *, domain: str
) -> tuple[CurrentPreview, dict[str, Any]]:
    result = copy.deepcopy(raw)
    doc = _validated_raw(result)
    item = doc.resolve(gear_id)
    if item is None:
        raise StoreError(f"Unknown gear ID {gear_id!r}.")
    before = _item_snapshot(item)
    payload = {**before, **updates}
    updated = InventoryItem.model_validate(payload)
    result["items"] = [
        _item_snapshot(updated) if existing.id == item.id else _item_snapshot(existing)
        for existing in doc.items
    ]
    errors = validate_inventory_doc(result)
    if errors:
        raise StoreError("Inventory validation failed: " + "; ".join(errors))
    after = _item_snapshot(updated)
    return (
        CurrentPreview(
            domain=domain,
            target=item.id,
            before=before,
            after=after,
            changed=before != after,
            affected_files=["data/inventory.yaml"],
            message=f"{item.id}: {domain.removeprefix('inventory.')} updated",
        ),
        result,
    )


def propose_add(
    *,
    name: str,
    category: str,
    manufacturer: str | None = None,
    model: str | None = None,
    quantity: int = 1,
    notes: str = "",
    gear_id: str | None = None,
    condition: GearCondition = GearCondition.UNKNOWN,
    ownership_status: OwnershipStatus = OwnershipStatus.OWNED,
    location: str | None = None,
    inventory_path: Path | None = None,
    data: dict[str, Any] | None = None,
) -> tuple[CurrentPreview, dict[str, Any]]:
    raw = copy.deepcopy(data if data is not None else load_raw(inventory_path))
    doc = _validated_raw(raw)
    clean_name = name.strip()
    clean_category = category.strip()
    if not clean_name or not clean_category:
        raise StoreError("Name and category are required.")
    item_id = _new_id(
        doc,
        explicit_id=gear_id,
        name=clean_name,
        manufacturer=manufacturer,
        model=model,
    )
    item = InventoryItem(
        id=item_id,
        name=clean_name,
        manufacturer=manufacturer.strip() if manufacturer and manufacturer.strip() else None,
        model=model.strip() if model and model.strip() else None,
        category=clean_category,
        quantity=quantity,
        ownership_status=ownership_status,
        condition=condition,
        location=location.strip() if location and location.strip() else None,
        notes=notes.strip(),
    )
    raw.setdefault("items", []).append(_item_snapshot(item))
    errors = validate_inventory_doc(raw)
    if errors:
        raise StoreError("Inventory validation failed: " + "; ".join(errors))
    return (
        CurrentPreview(
            domain="inventory.add",
            target=item.id,
            before={},
            after=_item_snapshot(item),
            changed=True,
            affected_files=["data/inventory.yaml"],
            message=f"Add owned gear {item.id} ({item.name})",
        ),
        raw,
    )


def propose_set_status(
    gear_id: str,
    status: OwnershipStatus,
    *,
    inventory_path: Path | None = None,
    routing_path: Path | None = None,
    data: dict[str, Any] | None = None,
) -> tuple[CurrentPreview, dict[str, Any]]:
    if status in {
        OwnershipStatus.RETIRED,
        OwnershipStatus.SOLD,
        OwnershipStatus.LOANED_OUT,
    }:
        from music_rig.gear_usage import assert_inactive_allowed

        assert_inactive_allowed(gear_id, routing_path=routing_path, inventory_path=inventory_path)
    raw = copy.deepcopy(data if data is not None else load_raw(inventory_path))
    return _replace_item(
        raw, gear_id, {"ownership_status": status.value}, domain="inventory.status"
    )


def propose_set_condition(
    gear_id: str,
    condition: GearCondition,
    *,
    inventory_path: Path | None = None,
    data: dict[str, Any] | None = None,
) -> tuple[CurrentPreview, dict[str, Any]]:
    raw = copy.deepcopy(data if data is not None else load_raw(inventory_path))
    return _replace_item(raw, gear_id, {"condition": condition.value}, domain="inventory.condition")


def propose_set_location(
    gear_id: str,
    location: str,
    *,
    inventory_path: Path | None = None,
    data: dict[str, Any] | None = None,
) -> tuple[CurrentPreview, dict[str, Any]]:
    value = location.strip()
    if not value:
        raise StoreError("Location must be non-empty; use an explicit known location.")
    raw = copy.deepcopy(data if data is not None else load_raw(inventory_path))
    return _replace_item(raw, gear_id, {"location": value}, domain="inventory.location")


def propose_retire(
    gear_id: str,
    *,
    inventory_path: Path | None = None,
    routing_path: Path | None = None,
    data: dict[str, Any] | None = None,
) -> tuple[CurrentPreview, dict[str, Any]]:
    return propose_set_status(
        gear_id,
        OwnershipStatus.RETIRED,
        inventory_path=inventory_path,
        routing_path=routing_path,
        data=data,
    )


def propose_acquire(
    wishlist_item_name: str,
    *,
    name: str | None = None,
    category: str | None = None,
    manufacturer: str | None = None,
    model: str | None = None,
    quantity: int = 1,
    notes: str = "",
    gear_id: str | None = None,
    inventory_path: Path | None = None,
    wishlist_path: Path | None = None,
    todo_path: Path | None = None,
    make_waiting_ready: bool = False,
) -> tuple[CurrentPreview, dict[str, Any], WishlistDocument, TodoDocument]:
    wish_doc = load_wishlist(wishlist_path)
    index = wish_doc.find_index(wishlist_item_name)
    if index is None:
        raise StoreError(f'Wishlist item "{wishlist_item_name}" does not exist.')
    wish = wish_doc.items[index]
    if wish.status == WishStatus.ACQUIRED:
        raise StoreError(f'Wishlist item "{wish.item}" is already ACQUIRED.')
    preview, inventory = propose_add(
        name=name or wish.item,
        category=category or wish.category,
        manufacturer=manufacturer,
        model=model,
        quantity=quantity,
        notes=notes,
        gear_id=gear_id,
        inventory_path=inventory_path,
    )
    acquired_id = preview.target
    wish_payload = wish.model_dump()
    wish_payload.update(status=WishStatus.ACQUIRED, inventory_ref=acquired_id)
    updated_wish = WishlistItem.model_validate(wish_payload)
    wishes = list(wish_doc.items)
    wishes[index] = updated_wish
    new_wish_doc = WishlistDocument(items=wishes)

    todo_doc = load_todo(todo_path)
    if make_waiting_ready:
        refs = set(wish.todo_refs)
        tasks = []
        for task in todo_doc.tasks:
            if task.id in refs and task.status == TodoStatus.WAITING:
                tasks.append(
                    task.model_copy(update={"status": TodoStatus.READY, "waiting_on": None})
                )
            else:
                tasks.append(task)
        todo_doc = TodoDocument(next_session=list(todo_doc.next_session), tasks=tasks)

    preview = preview.model_copy(
        update={
            "domain": "inventory.acquire",
            "before": {"wishlist_status": wish.status.value},
            "after": {
                "wishlist_status": WishStatus.ACQUIRED.value,
                "inventory_ref": acquired_id,
                "inventory": preview.after,
            },
            "affected_files": [
                "data/inventory.yaml",
                "data/wishlist.yaml",
                *(["data/todo.yaml"] if make_waiting_ready else []),
            ],
            "message": f'Acquire wishlist item "{wish.item}" as {acquired_id}',
        }
    )
    return preview, inventory, new_wish_doc, todo_doc
