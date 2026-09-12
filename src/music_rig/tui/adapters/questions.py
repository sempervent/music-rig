"""Question helpers used by the Questions screen (mutations via question_service)."""

from __future__ import annotations

from music_rig import question_service
from music_rig.models import OpenQuestion, QuestionStatus
from music_rig.tui.widgets import format_target


def filter_questions(
    items: list[OpenQuestion],
    status_filter: str,
    search: str = "",
) -> list[OpenQuestion]:
    """Filter questions for the list.

    ACTIVE (default): OPEN unanswered + OPEN draft + RESOLVED unreconciled.
    Excludes RECONCILED and DEFERRED unless explicitly requested.
    """
    status_filter = status_filter.upper()
    if status_filter == "ACTIVE":
        items = [
            q
            for q in items
            if q.status == QuestionStatus.OPEN
            or (q.status == QuestionStatus.RESOLVED and q.reconciled_at is None)
        ]
    elif status_filter == "OPEN":
        items = [q for q in items if q.status == QuestionStatus.OPEN]
    elif status_filter == "RESOLVED":
        items = [q for q in items if q.status == QuestionStatus.RESOLVED]
    elif status_filter == "DEFERRED":
        items = [q for q in items if q.status == QuestionStatus.DEFERRED]
    elif status_filter == "UNRECONCILED":
        items = [
            q for q in items if q.status == QuestionStatus.RESOLVED and q.reconciled_at is None
        ]
    elif status_filter != "ALL":
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
                    question_service.lifecycle_label(q),
                    format_target(q.target),
                ]
            ).casefold()
            if needle in blob:
                filtered.append(q)
        items = filtered
    return items


def question_detail_markdown(q: OpenQuestion) -> str:
    from music_rig.reconciliation.service import question_state

    fields = question_service.question_json_fields(q)
    try:
        state = question_state(q).value
    except Exception:
        state = "—"
    human_recon = state
    if state == "NEEDS_AGENT_ACTION":
        human_recon = "Needs agent reconciliation"
    elif state == "DRAFT_ANSWER":
        human_recon = "DRAFT_ANSWER — resolve before reconcile"
    lines = [
        f"# {q.id} — {fields['lifecycle_label']}",
        "",
        q.question,
        "",
        f"**Area:** {q.area}",
        f"**Status:** {fields['question_status']}",
        f"**Answer state:** {fields['answer_state']}",
        f"**Lifecycle:** {fields['lifecycle_label']}",
        f"**Reconciliation state:** {human_recon}",
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


# ACTIVE = work still requiring attention (default)
STATUS_CYCLE = ("ACTIVE", "OPEN", "RESOLVED", "UNRECONCILED", "DEFERRED", "ALL")
