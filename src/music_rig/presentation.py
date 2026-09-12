"""Shared Rich presentation helpers for human CLI output.

JSON/agent paths must never use this module for serialization — keep ANSI out
of `--json` payloads. Width-aware tables replace fragile tab-separated dumps.
"""

from __future__ import annotations

from io import StringIO
from typing import Any, Sequence

from rich.console import Console
from rich.table import Table
from rich.text import Text


def capture_console(*, width: int | None = None) -> Console:
    """Console that writes into a StringIO buffer at a fixed width."""
    return Console(
        file=StringIO(),
        width=width,
        force_terminal=True,
        color_system=None,
        highlight=False,
        soft_wrap=False,
    )


def render_table(
    columns: Sequence[str],
    rows: Sequence[Sequence[Any]],
    *,
    title: str | None = None,
    width: int | None = None,
    show_header: bool = True,
) -> str:
    """Render a Rich Table to plain text (no color). Guarantees no literal tabs."""
    console = capture_console(width=width)
    table = Table(
        title=title,
        show_header=show_header,
        header_style="bold",
        expand=False,
        pad_edge=False,
    )
    for col in columns:
        table.add_column(col, overflow="fold", no_wrap=False)
    for row in rows:
        cells = ["" if c is None else str(c) for c in row]
        # Guard: never emit raw tabs into cells
        cells = [c.replace("\t", " ") for c in cells]
        table.add_row(*cells)
    console.print(table)
    text = console.file.getvalue()  # type: ignore[union-attr]
    assert "\t" not in text, "presentation table must not contain tabs"
    return text.rstrip("\n")


def print_table(
    console: Console,
    columns: Sequence[str],
    rows: Sequence[Sequence[Any]],
    *,
    title: str | None = None,
    show_header: bool = True,
) -> None:
    """Print a Rich Table to an existing Console (uses console width)."""
    table = Table(
        title=title,
        show_header=show_header,
        header_style="bold",
        expand=False,
        pad_edge=False,
    )
    for col in columns:
        table.add_column(col, overflow="fold", no_wrap=False)
    for row in rows:
        cells = ["" if c is None else str(c).replace("\t", " ") for c in row]
        table.add_row(*cells)
    console.print(table)


def format_domains_table(
    rows: list[dict[str, Any]],
    *,
    width: int | None = None,
) -> str:
    """Human `rig inspect domains` — Domain / Name (+ optional columns by width)."""
    w = width if width is not None else 80
    columns = ["Domain", "Name"]
    if w >= 80:
        columns.append("Inspect")
    if w >= 100:
        columns.append("Edit")
    if w >= 120:
        columns.append("Reconcile")

    table_rows: list[list[str]] = []
    for row in rows:
        cells = [str(row.get("id") or ""), str(row.get("label") or "")]
        if "Inspect" in columns:
            cells.append("yes" if row.get("inspectable", True) else "—")
        if "Edit" in columns:
            editable = row.get("editable")
            if editable is True:
                cells.append("yes")
            elif editable == "partial":
                cells.append("partial")
            else:
                cells.append("—")
        if "Reconcile" in columns:
            cells.append("yes" if row.get("supports_reconcile") else "—")
        table_rows.append(cells)

    return render_table(columns, table_rows, title="DOMAINS", width=w)


def format_reconcile_queue_table(
    items: Sequence[Any],
    *,
    width: int | None = None,
) -> str:
    """Human `rig reconcile queue` — Type / ID / State / Target / Summary."""
    rows: list[list[str]] = []
    for item in items:
        if hasattr(item, "to_dict"):
            d = item.to_dict()
        elif isinstance(item, dict):
            d = item
        else:
            d = {
                "artifact_type": getattr(item, "artifact_type", ""),
                "artifact_id": getattr(item, "artifact_id", ""),
                "state": getattr(getattr(item, "state", None), "value", str(getattr(item, "state", ""))),
                "summary": getattr(item, "summary", ""),
                "area": getattr(item, "area", ""),
            }
        target = d.get("area") or ""
        cap = d.get("capability") or ""
        if cap:
            target = f"{target} [{cap}]" if target else f"[{cap}]"
        rows.append(
            [
                str(d.get("artifact_type") or ""),
                str(d.get("artifact_id") or ""),
                str(d.get("state") or ""),
                target,
                str(d.get("summary") or "")[:72],
            ]
        )
    return render_table(
        ["Type", "ID", "State", "Target", "Summary"],
        rows,
        title="RECONCILE QUEUE",
        width=width,
    )


def format_id_label_rows(
    rows: Sequence[dict[str, Any]],
    *,
    title: str | None = None,
    width: int | None = None,
    id_key: str = "id",
    label_key: str = "label",
) -> str:
    """Generic two-column Domain/Name style list (no tabs)."""
    table_rows = []
    for row in rows:
        label = row.get(label_key)
        if label is None:
            label = row.get("cells") or ""
            if isinstance(label, list):
                label = " ".join(str(c) for c in label)
        table_rows.append([str(row.get(id_key) or ""), str(label)])
    return render_table(["ID", "Name"], table_rows, title=title, width=width)


def blocker_message(blocker: Any) -> str:
    """Human-readable line for a string or structured blocker."""
    if isinstance(blocker, dict):
        code = blocker.get("code") or "blocker"
        field = blocker.get("field")
        msg = blocker.get("message") or code
        if field:
            return f"{code} ({field}): {msg}"
        return f"{code}: {msg}"
    return str(blocker)


def format_verify_queue_table(
    items: Sequence[Any],
    *,
    width: int | None = None,
) -> str:
    """Human `rig verify queue` — ID / Area / Kind / Target / Question / Next."""
    rows: list[list[str]] = []
    for item in items:
        if hasattr(item, "to_dict"):
            d = item.to_dict()
        elif isinstance(item, dict):
            d = item
        else:
            d = {
                "question_id": getattr(item, "question_id", ""),
                "area": getattr(item, "area", ""),
                "kind": getattr(item, "kind", ""),
                "target_label": getattr(item, "target_label", ""),
                "question": getattr(item, "question", ""),
                "next_hint": getattr(item, "next_hint", ""),
            }
        rows.append(
            [
                str(d.get("question_id") or ""),
                str(d.get("area") or ""),
                str(d.get("kind") or ""),
                str(d.get("target_label") or "—"),
                str(d.get("question") or "")[:56],
                str(d.get("next_hint") or ""),
            ]
        )
    return render_table(
        ["ID", "Area", "Kind", "Target", "Question", "Next"],
        rows,
        title="VERIFY QUEUE",
        width=width,
    )


def format_verify_summary_table(
    summary: dict[str, Any],
    *,
    width: int | None = None,
) -> str:
    """Human `rig verify summary` — grouped counts."""
    sections: list[str] = []
    total = summary.get("total_open_guided", 0)
    sections.append(f"Guided OPEN questions: {total}")

    by_area = summary.get("by_area") or {}
    if by_area:
        rows = [[k, str(v)] for k, v in by_area.items()]
        sections.append(
            render_table(["Area", "Count"], rows, title="BY AREA", width=width)
        )

    by_cap = summary.get("after_answer_capability") or {}
    if by_cap:
        rows = [[k, str(v)] for k, v in by_cap.items()]
        sections.append(
            render_table(
                ["After-answer capability", "Count"],
                rows,
                title="AFTER ANSWER",
                width=width,
            )
        )

    by_obs = summary.get("after_observation_capability") or {}
    if by_obs:
        rows = [[k, str(v)] for k, v in by_obs.items()]
        sections.append(
            render_table(
                ["After-observation capability", "Count"],
                rows,
                title="AFTER OBSERVATION",
                width=width,
            )
        )

    by_kind = summary.get("by_kind") or {}
    if by_kind:
        rows = [[k, str(v)] for k, v in by_kind.items()]
        sections.append(
            render_table(["Kind", "Count"], rows, title="BY KIND", width=width)
        )

    top = summary.get("top") or []
    if top:
        sections.append("Top of queue: " + ", ".join(top))

    text = "\n\n".join(sections)
    assert "\t" not in text
    return text


def plain_text(message: str) -> Text:
    return Text(message.replace("\t", " "))
