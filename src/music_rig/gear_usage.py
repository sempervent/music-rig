"""Cross-reference stable inventory identities from CURRENT and planning data."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from music_rig.store import (
    StoreError,
    load_inventory,
    load_routing,
    load_wishlist,
)


def usage_for(
    gear_id: str,
    *,
    inventory_path: Path | None = None,
    routing_path: Path | None = None,
    wishlist_path: Path | None = None,
) -> dict[str, Any]:
    inventory = load_inventory(inventory_path)
    item = inventory.resolve(gear_id)
    if item is None:
        raise StoreError(f"Unknown gear ID {gear_id!r}.")
    exact = gear_id.strip().casefold()
    # Parent status changes must also account for CURRENT references to a specific unit.
    matching_ids = {item.id.casefold(), *(unit.id.casefold() for unit in item.units)}
    routing = load_routing(routing_path)
    route_refs: list[dict[str, str]] = []
    for path_id, path in routing.named_paths.items():
        if path.status.casefold() != "current":
            continue
        for branch_id, branch in path.branches.items():
            for node in branch.nodes:
                ref = (node.gear_ref or "").casefold()
                if ref and (ref == exact or exact == item.id.casefold() and ref in matching_ids):
                    route_refs.append(
                        {
                            "path": path_id,
                            "branch": branch_id,
                            "node": node.id,
                            "label": node.label,
                            "gear_ref": node.gear_ref or "",
                        }
                    )

    wishes = load_wishlist(wishlist_path)
    wish_refs = [
        wish.item
        for wish in wishes.items
        if wish.inventory_ref
        and (
            wish.inventory_ref.casefold() == exact
            or exact == item.id.casefold()
            and wish.inventory_ref.casefold() in matching_ids
        )
    ]
    return {
        "gear_id": gear_id.strip(),
        "inventory_item": item.id,
        "routing": route_refs,
        "wishlist": wish_refs,
        # data/patchbays.yaml has no gear_ref field in the current schema.
        "patchbay": [],
    }


def assert_inactive_allowed(
    gear_id: str,
    *,
    inventory_path: Path | None = None,
    routing_path: Path | None = None,
    wishlist_path: Path | None = None,
) -> None:
    usage = usage_for(
        gear_id,
        inventory_path=inventory_path,
        routing_path=routing_path,
        wishlist_path=wishlist_path,
    )
    refs = usage["routing"]
    if refs:
        where = ", ".join(f"{ref['path']}/{ref['branch']}:{ref['node']}" for ref in refs)
        raise StoreError(
            f"Cannot make {gear_id!r} inactive: CURRENT routing references it at {where}."
        )
