"""Generated Markdown projection for canonical inventory data."""

from __future__ import annotations

from music_rig.models import InventoryDocument


def _cell(value: object) -> str:
    if value is None or value == "":
        return "—"
    return str(value).replace("|", "\\|").replace("\n", " ").strip() or "—"


def _title(category: str) -> str:
    return category.replace("_", " ").replace("-", " ").title()


def render_inventory_section(doc: InventoryDocument | dict | None = None) -> str:
    if doc is None:
        from music_rig.store import load_inventory

        document = load_inventory()
    elif isinstance(doc, dict):
        document = InventoryDocument.model_validate(doc)
    else:
        document = doc

    lines = [
        "<!-- GENERATED FROM data/inventory.yaml BY `uv run rig render`. "
        "DO NOT EDIT THIS SECTION DIRECTLY. -->",
        "",
    ]
    categories: dict[str, list] = {}
    for item in document.items:
        categories.setdefault(item.category, []).append(item)
    for category, items in categories.items():
        lines.extend(
            [
                f"## {_title(category)}",
                "",
                "| ID | Name | Manufacturer | Model | Qty | Status | Condition | Notes |",
                "|---|---|---|---|---:|---|---|---|",
            ]
        )
        for item in items:
            lines.append(
                f"| {_cell(item.id)} | {_cell(item.name)} | {_cell(item.manufacturer)} | {_cell(item.model)} | {item.quantity} | "
                f"{item.ownership_status.value} | {item.condition.value} | {_cell(item.notes)} |"
            )
        lines.append("")
    if not categories:
        lines.append("_No inventory records._")
        lines.append("")
    return "\n".join(lines)
