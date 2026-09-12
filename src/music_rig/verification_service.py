"""Guided human verification for OPEN questions (`rig verify`).

Guides observation; the human supplies facts. UNKNOWN is valid.
Answer recording always goes through question_service; CURRENT mutation
always through reconciliation.service — no parallel engines.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from music_rig import question_service
from music_rig.inbox_service import default_clock
from music_rig.models import (
    OpenQuestion,
    QuestionStatus,
    QuestionVerification,
    TodoPriority,
    TodoStatus,
)
from music_rig.reconciliation import service as reconcile_service
from music_rig.reconciliation.adapters import get_adapter
from music_rig.reconciliation.types import Capability, err_payload, ok_payload
from music_rig.store import StoreError, load_inventory, load_questions, load_todo

Clock = Callable[[], datetime]

BOOL_CHOICES = ["YES", "NO", "UNKNOWN"]
PATCHBAY_MODE_CHOICES = ["normal", "half-normal", "thru", "UNKNOWN"]

# Priority tiers (lower = higher priority)
TIER_NEXT_SESSION = 0
TIER_P0 = 1
TIER_ENUM_REF = 2
TIER_APPLY = 3
TIER_REMAINING = 4


@dataclass
class VerifyQueueItem:
    question_id: str
    area: str
    kind: str
    target_label: str
    question: str
    next_hint: str
    priority_tier: int
    priority_reason: str
    answer_type: str
    capability: str | None = None
    related_todos: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _q_number(qid: str) -> int:
    try:
        return int(qid.split("-", 1)[1])
    except (IndexError, ValueError):
        return 9999


def _target_label(q: OpenQuestion) -> str:
    if q.target is None:
        return "—"
    parts = [q.target.domain]
    for key in ("bay", "pair", "path", "gear", "device", "channel"):
        val = getattr(q.target, key, None)
        if val:
            parts.append(str(val))
    return " ".join(parts)


def _truncate(text: str, n: int = 56) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= n:
        return cleaned
    return cleaned[: n - 1] + "…"


def _has_structured_recipe(v: QuestionVerification | None) -> bool:
    if v is None:
        return False
    return v.answer_type in {"ENUM", "BOOL", "REF"}


def _capability_for(q: OpenQuestion) -> Capability | None:
    if q.target is None or not q.target.domain:
        return None
    return get_adapter(q.target.domain).capability


def _after_answer_bucket(cap: Capability | None) -> str:
    """Summary grouping: auto-applicable / verify-only / agent / manual."""
    if cap == Capability.APPLY_AND_VERIFY:
        return "auto-applicable"
    if cap == Capability.VERIFY_ONLY:
        return "verify-only"
    if cap == Capability.MANUAL:
        return "manual"
    if cap == Capability.UNSUPPORTED or cap is None:
        return "manual"
    return "manual"


def _priority(
    q: OpenQuestion,
    *,
    next_session: set[str],
    p0_ids: set[str],
) -> tuple[int, str]:
    related = set(q.related_todos)
    if related & next_session:
        return TIER_NEXT_SESSION, "linked to Next Session TODO"
    if related & p0_ids:
        return TIER_P0, "linked to P0 TODO"
    if _has_structured_recipe(q.verification):
        return TIER_ENUM_REF, "deterministic enum/ref recipe"
    cap = _capability_for(q)
    if cap == Capability.APPLY_AND_VERIFY:
        return TIER_APPLY, "APPLY_AND_VERIFY after answer"
    return TIER_REMAINING, "remaining OPEN"


def list_verify_queue(
    *,
    area: str | None = None,
    questions_path: Path | None = None,
    todo_path: Path | None = None,
) -> list[VerifyQueueItem]:
    """OPEN unanswered questions that have verification metadata."""
    todo = load_todo(todo_path)
    next_session = set(todo.next_session)
    p0_ids = {
        t.id
        for t in todo.tasks
        if t.priority == TodoPriority.P0
        and t.status
        not in {TodoStatus.DONE, TodoStatus.CANCELLED, TodoStatus.DEFERRED}
    }
    items: list[VerifyQueueItem] = []
    for q in load_questions(questions_path).questions:
        if q.status != QuestionStatus.OPEN:
            continue
        if q.reconciled_at is not None:
            continue
        if q.answer.strip():
            continue
        if q.verification is None:
            continue
        if area and area.casefold() not in q.area.casefold():
            continue
        tier, reason = _priority(q, next_session=next_session, p0_ids=p0_ids)
        cap = _capability_for(q)
        items.append(
            VerifyQueueItem(
                question_id=q.id,
                area=q.area,
                kind=q.verification.kind,
                target_label=_target_label(q),
                question=_truncate(q.question),
                next_hint=reason,
                priority_tier=tier,
                priority_reason=reason,
                answer_type=q.verification.answer_type,
                capability=cap.value if cap else None,
                related_todos=list(q.related_todos),
            )
        )
    items.sort(key=lambda i: (i.priority_tier, _q_number(i.question_id), i.question_id))
    return items


def recommend_next(
    *,
    area: str | None = None,
    questions_path: Path | None = None,
    todo_path: Path | None = None,
) -> dict[str, Any] | None:
    queue = list_verify_queue(
        area=area, questions_path=questions_path, todo_path=todo_path
    )
    if not queue:
        return None
    top = queue[0]
    card = build_card(
        top.question_id, questions_path=questions_path, todo_path=todo_path
    )
    return {
        "question_id": top.question_id,
        "why": top.priority_reason,
        "kind": top.kind,
        "area": top.area,
        "current_hint": card.get("current"),
        "start_command": f"uv run rig verify run {top.question_id}",
        "card": card,
    }


def _ref_choices(
    v: QuestionVerification,
    *,
    inventory_path: Path | None = None,
) -> list[str]:
    if v.answer_type != "REF":
        return list(v.choices)
    if v.choices:
        return list(v.choices)
    domain = (v.ref_domain or "").strip().lower()
    if domain in {"gear", "inventory"}:
        inv = load_inventory(inventory_path)
        return sorted(item.id for item in inv.items)
    return []


def accepted_answers(
    q: OpenQuestion,
    *,
    inventory_path: Path | None = None,
) -> dict[str, Any]:
    v = q.verification
    if v is None:
        return {"answer_type": None, "choices": [], "note": "no verification metadata"}
    choices = list(v.choices)
    if v.answer_type == "REF":
        choices = _ref_choices(v, inventory_path=inventory_path)
    if v.answer_type == "TEXT":
        return {
            "answer_type": "TEXT",
            "choices": [],
            "note": "Free-text observation; UNKNOWN is valid",
        }
    return {
        "answer_type": v.answer_type,
        "choices": choices,
        "ref_domain": v.ref_domain,
        "note": "Pick a listed value or UNKNOWN when unsure",
    }


def normalize_answer(
    q: OpenQuestion,
    raw: str,
    *,
    inventory_path: Path | None = None,
) -> str:
    """Validate + normalize against verification schema. Raises StoreError if invalid."""
    cleaned = raw.strip()
    if not cleaned:
        raise StoreError("Answer cannot be empty (use UNKNOWN if unsure).")
    v = q.verification
    if v is None:
        return cleaned

    # UNKNOWN always allowed (any case)
    if cleaned.casefold() == "unknown":
        return "UNKNOWN"

    at = v.answer_type
    if at == "TEXT":
        return cleaned

    if at == "BOOL":
        choices = v.choices or BOOL_CHOICES
        mapping = {c.casefold(): c for c in choices}
        # Accept yes/no/y/n aliases → canonical YES/NO when present
        aliases = {
            "y": "YES",
            "yes": "YES",
            "n": "NO",
            "no": "NO",
            "true": "YES",
            "false": "NO",
        }
        key = cleaned.casefold()
        if key in aliases and aliases[key].casefold() in mapping:
            return mapping[aliases[key].casefold()]
        if key in mapping:
            return mapping[key]
        raise StoreError(
            f"Invalid BOOL answer {raw!r}; expected one of: {', '.join(choices)}"
        )

    if at == "ENUM":
        choices = v.choices
        mapping: dict[str, str] = {}
        for c in choices:
            mapping[c.casefold()] = c
            mapping[c.casefold().replace("_", "-").replace(" ", "-")] = c
        key = cleaned.casefold().replace("_", "-").replace(" ", "-")
        while "--" in key:
            key = key.replace("--", "-")
        if key in mapping:
            return mapping[key]
        raise StoreError(
            f"Invalid ENUM answer {raw!r}; expected one of: {', '.join(choices)}"
        )

    if at == "REF":
        choices = _ref_choices(v, inventory_path=inventory_path)
        mapping = {c.casefold(): c for c in choices}
        if cleaned.casefold() in mapping:
            return mapping[cleaned.casefold()]
        raise StoreError(
            f"Invalid REF answer {raw!r}; expected a known "
            f"{v.ref_domain or 'ref'} id"
            + (f" ({', '.join(choices[:12])}…)" if len(choices) > 12 else
               f" ({', '.join(choices)})" if choices else "")
        )

    return cleaned


def build_card(
    question_id: str,
    *,
    questions_path: Path | None = None,
    todo_path: Path | None = None,
    inventory_path: Path | None = None,
) -> dict[str, Any]:
    q = question_service.get_question(question_id, questions_path=questions_path)
    v = q.verification
    current = None
    capability = None
    blockers: list[Any] = []
    state = None
    try:
        plan = reconcile_service.plan_question(
            q.id, questions_path=questions_path
        )
        current = plan.current
        capability = plan.capability.value
        blockers = plan.blockers
        state = plan.state.value
    except StoreError:
        capability = (
            _capability_for(q).value if _capability_for(q) else None
        )

    todo = load_todo(todo_path)
    related_work = []
    for tid in q.related_todos:
        task = todo.task_map().get(tid)
        if task:
            related_work.append(
                {
                    "id": task.id,
                    "task": task.task,
                    "priority": task.priority.value,
                    "status": task.status.value,
                    "in_next_session": tid in todo.next_session,
                }
            )
        else:
            related_work.append({"id": tid, "missing": True})

    return {
        "question_id": q.id,
        "question": q.question,
        "area": q.area,
        "status": q.status.value,
        "answer": q.answer,
        "resolved_at": q.resolved_at.isoformat() if q.resolved_at else None,
        "reconciled_at": q.reconciled_at.isoformat() if q.reconciled_at else None,
        "target": (
            {k: val for k, val in q.target.model_dump().items() if val is not None}
            if q.target
            else None
        ),
        "verification": v.model_dump() if v else None,
        "verification_note": q.verification_note,
        "prompt": (v.prompt if v else "") or "",
        "accepted": accepted_answers(q, inventory_path=inventory_path),
        "current": current,
        "reconciliation": {
            "capability": capability,
            "state": state,
            "blockers": blockers,
            "after_answer_bucket": _after_answer_bucket(
                Capability(capability) if capability else None
            ),
        },
        "related_work": related_work,
        "suggested_commands": [
            f"uv run rig verify run {q.id}",
            f"uv run rig verify answer {q.id} --value \"…\" --json",
            f"uv run rig reconcile plan question {q.id} --json",
        ],
    }


def record_verified_answer(
    question_id: str,
    value: str,
    *,
    note: str | None = None,
    dry_run: bool = False,
    yes: bool = False,
    clock: Clock = default_clock,
    render: bool = True,
    questions_path: Path | None = None,
    inventory_path: Path | None = None,
    changes_path: Path | None = None,
) -> dict[str, Any]:
    """Validate schema → normalize → question_service.answer_question."""
    q = question_service.get_question(question_id, questions_path=questions_path)
    if q.status != QuestionStatus.OPEN:
        raise StoreError(f"{q.id} is {q.status.value}; verify answer expects OPEN")
    normalized = normalize_answer(q, value, inventory_path=inventory_path)
    if dry_run:
        result = question_service.answer_question(
            q.id,
            normalized,
            dry_run=True,
            verification_note=note,
            clock=clock,
            render=False,
            questions_path=questions_path,
            changes_path=changes_path,
        )
        result["normalized_value"] = normalized
        result["raw_value"] = value
        return result
    # Noninteractive answer always writes; --yes is for CLI confirm UX only
    _ = yes
    result = question_service.answer_question(
        q.id,
        normalized,
        dry_run=False,
        verification_note=note,
        clock=clock,
        render=render,
        questions_path=questions_path,
        changes_path=changes_path,
    )
    result["normalized_value"] = normalized
    result["raw_value"] = value
    return result


def summary(
    *,
    questions_path: Path | None = None,
    todo_path: Path | None = None,
) -> dict[str, Any]:
    queue = list_verify_queue(questions_path=questions_path, todo_path=todo_path)
    by_area: dict[str, int] = {}
    by_bucket: dict[str, int] = {
        "auto-applicable": 0,
        "verify-only": 0,
        "agent": 0,
        "manual": 0,
    }
    by_kind: dict[str, int] = {}
    for item in queue:
        by_area[item.area] = by_area.get(item.area, 0) + 1
        by_kind[item.kind] = by_kind.get(item.kind, 0) + 1
        cap = Capability(item.capability) if item.capability else None
        bucket = _after_answer_bucket(cap)
        # Treat UNSUPPORTED without target as manual; VERIFY_ONLY as verify-only
        if cap == Capability.UNSUPPORTED:
            bucket = "agent"
        by_bucket[bucket] = by_bucket.get(bucket, 0) + 1
    return {
        "total_open_guided": len(queue),
        "by_area": dict(sorted(by_area.items())),
        "by_kind": dict(sorted(by_kind.items())),
        "after_answer_capability": by_bucket,
        "top": [i.question_id for i in queue[:5]],
    }


def production_readiness_matrix(
    *, questions_path: Path | None = None
) -> list[dict[str, Any]]:
    """Metadata-only matrix for production questions (no answers invented)."""
    rows = []
    for q in load_questions(questions_path).questions:
        v = q.verification
        cap = _capability_for(q)
        rows.append(
            {
                "id": q.id,
                "area": q.area,
                "status": q.status.value,
                "answer": q.answer,
                "resolved_at": (
                    q.resolved_at.isoformat() if q.resolved_at else None
                ),
                "reconciled_at": (
                    q.reconciled_at.isoformat() if q.reconciled_at else None
                ),
                "kind": v.kind if v else None,
                "answer_type": v.answer_type if v else None,
                "target": _target_label(q),
                "capability_after_answer": cap.value if cap else None,
                "after_answer_bucket": _after_answer_bucket(cap),
            }
        )
    return rows


def open_questions_for_todo(
    todo_id: str,
    *,
    questions_path: Path | None = None,
) -> list[str]:
    """OPEN questions that list this TODO in related_todos."""
    key = todo_id.strip().upper()
    return [
        q.id
        for q in load_questions(questions_path).questions
        if q.status == QuestionStatus.OPEN and key in q.related_todos
    ]


# Re-export envelope helpers for CLI
__all__ = [
    "VerifyQueueItem",
    "list_verify_queue",
    "recommend_next",
    "build_card",
    "normalize_answer",
    "accepted_answers",
    "record_verified_answer",
    "summary",
    "production_readiness_matrix",
    "open_questions_for_todo",
    "ok_payload",
    "err_payload",
    "BOOL_CHOICES",
    "PATCHBAY_MODE_CHOICES",
]
