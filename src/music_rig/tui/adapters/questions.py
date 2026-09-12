"""Question helpers used by the Questions screen (mutations via question_service)."""

from __future__ import annotations

from music_rig.models import OpenQuestion
from music_rig.tui.widgets import format_target


def filter_questions(
    items: list[OpenQuestion],
    status_filter: str,
    search: str = "",
) -> list[OpenQuestion]:
    status_filter = status_filter.upper()
    if status_filter != "ALL":
        items = [q for q in items if q.status.value == status_filter]
    needle = search.strip().casefold()
    if needle:
        filtered: list[OpenQuestion] = []
        for q in items:
            blob = " ".join(
                [
                    q.id,
                    q.question,
                    q.area,
                    q.answer,
                    q.notes,
                    format_target(q.target),
                ]
            ).casefold()
            if needle in blob:
                filtered.append(q)
        items = filtered
    return items


def question_detail_markdown(q: OpenQuestion) -> str:
    from music_rig.reconciliation.service import question_state

    try:
        state = question_state(q).value
    except Exception:
        state = "—"
    lines = [
        f"# {q.id} — {q.status.value}",
        "",
        q.question,
        "",
        f"**Area:** {q.area}",
        f"**Status:** {q.status.value}",
        f"**Reconciliation state:** {state}",
        "",
        "## Typed target",
        "",
        f"`{format_target(q.target)}`" if q.target else "_none_",
        "",
        "## Answer",
        "",
        q.answer.strip() or "_—_",
    ]
    if q.related_todos:
        lines.extend(["", f"**Related TODOs:** {', '.join(q.related_todos)}"])
    else:
        lines.extend(["", "**Related TODOs:** —"])
    lines.append(f"**Related Changes:** {', '.join(q.related_changes) or '—'}")
    v = q.verification
    if v is not None:
        lines.extend(
            [
                "",
                "## Verification",
                "",
                f"Prompt: {v.prompt or '—'}",
                f"Kind: {v.kind.value if hasattr(v.kind, 'value') else v.kind}",
                f"Choices: {', '.join(v.choices) if v.choices else '—'}",
            ]
        )
    vr = q.verification_result
    if vr is not None:
        outcome = vr.outcome.value if hasattr(vr.outcome, "value") else vr.outcome
        lines.extend(
            [
                "",
                "## verification_result",
                "",
                f"Outcome: {outcome}",
                f"Observed: {vr.observed_value or '—'}",
            ]
        )
    else:
        lines.extend(["", "## verification_result", "", "_none_ (answer ≠ observation)"])
    lines.extend(
        [
            "",
            "## Notes",
            "",
            q.notes.strip() or "_—_",
        ]
    )
    if q.resolved_at is not None:
        lines.extend(["", f"**Resolved at:** {q.resolved_at.isoformat()}"])
    if q.reconciled_at is not None:
        lines.extend(["", f"**Reconciled at:** {q.reconciled_at.isoformat()}"])
    if q.reconciliation_note.strip():
        lines.extend(["", f"**Reconciliation note:** {q.reconciliation_note.strip()}"])
    # CURRENT target value
    if q.target is not None:
        try:
            from music_rig.reconciliation.adapters import get_adapter

            current = get_adapter(q.target.domain).read_current(q, paths={})
            lines.extend(["", "## CURRENT at target", "", f"```\n{current}\n```"])
        except Exception as exc:
            lines.extend(["", "## CURRENT at target", "", f"_unavailable: {exc}_"])
    return "\n".join(lines)


STATUS_CYCLE = ("OPEN", "RESOLVED", "DEFERRED", "ALL")
