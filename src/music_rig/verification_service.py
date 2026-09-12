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
    ChangeCategory,
    OpenQuestion,
    QuestionStatus,
    QuestionVerification,
    TodoPriority,
    TodoStatus,
    VerificationOutcome,
    VerificationResult,
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
    operations: list[Any] = []
    try:
        plan = reconcile_service.plan_question(
            q.id, questions_path=questions_path
        )
        current = plan.current
        capability = plan.capability.value
        blockers = plan.blockers
        state = plan.state.value
        operations = plan.operations
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

    evidence = None
    if isinstance(current, dict):
        evidence = current.get("evidence") or current.get("status")

    vr = q.verification_result
    return {
        "question_id": q.id,
        "question": q.question,
        "area": q.area,
        "status": q.status.value,
        "answer_state": question_service.derive_answer_state(q).value,
        "question_status": q.status.value,
        "lifecycle_label": question_service.lifecycle_label(q),
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
        "verification_result": vr.model_dump(mode="json") if vr else None,
        "prompt": (v.prompt if v else "") or "",
        "accepted": accepted_answers(q, inventory_path=inventory_path),
        "current": current,
        "evidence": evidence,
        "reconciliation": {
            "capability": capability,
            "state": state,
            "blockers": blockers,
            "operations": operations,
            "after_answer_bucket": _after_answer_bucket(
                Capability(capability) if capability else None
            ),
            "after_observation_bucket": _after_observation_bucket(q, capability),
        },
        "related_work": related_work,
        "suggested_commands": [
            f"uv run rig verify run {q.id}",
            f"uv run rig verify record {q.id} --outcome confirmed --yes --json",
            f"uv run rig verify answer {q.id} --value \"…\" --json",
            f"uv run rig reconcile plan question {q.id} --json",
        ],
    }


def _after_observation_bucket(q: OpenQuestion, capability: str | None) -> str:
    """Capability projection once an explicit observation exists (or would)."""
    vr = q.verification_result
    if vr and vr.outcome == VerificationOutcome.FAILED_TEST:
        return "failed-test"
    if vr and vr.outcome == VerificationOutcome.UNKNOWN:
        return "unknown-observation"
    cap = Capability(capability) if capability else _capability_for(q)
    if cap == Capability.APPLY_AND_VERIFY:
        return "fully-reconcilable"
    if cap in {Capability.VERIFY_ONLY, Capability.HUMAN_VERIFY_THEN_APPLY}:
        return "fully-reconcilable"
    if cap == Capability.MANUAL:
        return "agent-action"
    if cap == Capability.UNSUPPORTED or cap is None:
        return "descriptive-or-agent"
    return "agent-action"


def _infer_outcome_vs_current(
    q: OpenQuestion,
    value: str,
    *,
    questions_path: Path | None = None,
) -> VerificationOutcome:
    """CONFIRMED if value matches CURRENT documented value; else CORRECTED."""
    normalized = value.strip()
    if normalized.casefold() == "unknown":
        return VerificationOutcome.UNKNOWN
    try:
        plan = reconcile_service.plan_question(q.id, questions_path=questions_path)
        current = plan.current
    except StoreError:
        current = None
    if isinstance(current, dict):
        candidates = [
            current.get("master"),
            current.get("mode"),
            current.get("evidence"),
            current.get("status"),
        ]
        for c in candidates:
            if c is not None and str(c).strip().casefold() == normalized.casefold():
                return VerificationOutcome.CONFIRMED
    if q.answer.strip() and q.answer.strip().casefold() == normalized.casefold():
        return VerificationOutcome.CONFIRMED
    return VerificationOutcome.CORRECTED


def record_observation(
    question_id: str,
    outcome: VerificationOutcome | str,
    *,
    value: str | None = None,
    note: str | None = None,
    dry_run: bool = False,
    yes: bool = False,
    create_change: bool = False,
    clock: Clock = default_clock,
    render: bool = True,
    questions_path: Path | None = None,
    inventory_path: Path | None = None,
    changes_path: Path | None = None,
) -> dict[str, Any]:
    """Record explicit human verification_result; optionally update answer.

    Observation ≠ answer. FAILED_TEST / UNKNOWN do not invent VERIFIED evidence.
    Value-bearing CONFIRMED/CORRECTED may resolve/update the Question answer.
    """
    _ = yes  # CLI confirm gate
    q = question_service.get_question(question_id, questions_path=questions_path)
    if isinstance(outcome, str):
        key = outcome.strip().upper().replace("-", "_")
        aliases = {
            "CONFIRMED": VerificationOutcome.CONFIRMED,
            "CONFIRM": VerificationOutcome.CONFIRMED,
            "CORRECTED": VerificationOutcome.CORRECTED,
            "CORRECT": VerificationOutcome.CORRECTED,
            "UNKNOWN": VerificationOutcome.UNKNOWN,
            "FAILED_TEST": VerificationOutcome.FAILED_TEST,
            "FAILED": VerificationOutcome.FAILED_TEST,
            "FAIL": VerificationOutcome.FAILED_TEST,
        }
        if key not in aliases:
            raise StoreError(
                f"Invalid outcome {outcome!r}; expected "
                "confirmed|corrected|unknown|failed_test"
            )
        outcome_e = aliases[key]
    else:
        outcome_e = outcome

    observed_value = (value or "").strip()
    if outcome_e in {
        VerificationOutcome.CONFIRMED,
        VerificationOutcome.CORRECTED,
    } and observed_value:
        observed_value = normalize_answer(
            q, observed_value, inventory_path=inventory_path
        )
    elif outcome_e == VerificationOutcome.UNKNOWN and not observed_value:
        observed_value = "UNKNOWN"
    elif outcome_e == VerificationOutcome.UNKNOWN and observed_value:
        observed_value = normalize_answer(
            q, observed_value, inventory_path=inventory_path
        )

    if outcome_e == VerificationOutcome.CORRECTED and not observed_value:
        raise StoreError("CORRECTED requires --value")
    if outcome_e == VerificationOutcome.CONFIRMED and not observed_value:
        # Allow confirm of existing answer / CURRENT without re-stating value
        if q.answer.strip():
            observed_value = q.answer.strip()
        else:
            raise StoreError("CONFIRMED requires --value when Question has no answer")

    result = VerificationResult(
        outcome=outcome_e,
        observed_at=clock(),
        observed_value=observed_value,
        note=(note or "").strip(),
        source="HUMAN",
    )

    resolve_answer = False
    answer_value = q.answer
    if outcome_e in {
        VerificationOutcome.CONFIRMED,
        VerificationOutcome.CORRECTED,
    } and observed_value and observed_value.casefold() != "unknown":
        resolve_answer = True
        answer_value = observed_value
    elif outcome_e == VerificationOutcome.UNKNOWN:
        # Do not resolve unless explicitly answering UNKNOWN as the fact
        resolve_answer = False

    # Evidence plan (no write)
    evidence_plan = None
    try:
        # Preview plan as if observation were already on the question
        preview_q = OpenQuestion.model_validate(
            {
                **q.model_dump(mode="json"),
                "verification_result": result.model_dump(mode="json"),
                **(
                    {
                        "status": QuestionStatus.RESOLVED.value,
                        "answer": answer_value,
                        "resolved_at": (q.resolved_at or clock()).isoformat(),
                    }
                    if resolve_answer
                    else {}
                ),
            }
        )
        # Temporarily plan via adapter with mutated in-memory question
        from music_rig.reconciliation.adapters import get_adapter

        adapter = get_adapter(preview_q.target.domain if preview_q.target else None)
        paths = reconcile_service._paths(questions=questions_path)  # noqa: SLF001
        plan = adapter.plan(preview_q, paths=paths)
        evidence_plan = {
            "state": plan.state.value,
            "capability": plan.capability.value,
            "operations": plan.operations,
            "blockers": plan.blockers,
            "details": plan.details,
        }
    except Exception as exc:  # noqa: BLE001 — dry-run preview best-effort
        evidence_plan = {"error": str(exc)}

    change_preview = None
    if create_change and outcome_e == VerificationOutcome.FAILED_TEST:
        change_preview = {
            "category": ChangeCategory.OTHER.value,
            "summary": f"FAILED_TEST {q.id}: expected vs observed",
            "details": (
                f"Question: {q.question}\n"
                f"Expected/documented: {q.answer or '(none)'}\n"
                f"Observed: {observed_value or '(failed)'}\n"
                f"Note: {result.note or '(none)'}\n"
                f"Target: {q.target.model_dump() if q.target else None}"
            ),
            "affected_areas": [q.area] if q.area else [],
        }

    payload: dict[str, Any] = {
        "question_id": q.id,
        "dry_run": dry_run,
        "verification_result": result.model_dump(mode="json"),
        "will_resolve_answer": resolve_answer,
        "answer": answer_value if resolve_answer else q.answer,
        "evidence_plan": evidence_plan,
        "create_change": change_preview,
        "message": (
            f"Observation {outcome_e.value} recorded"
            if not dry_run
            else f"dry-run: would record {outcome_e.value}"
        ),
        "next_command": f"uv run rig reconcile plan question {q.id} --json",
    }

    if dry_run:
        return payload

    from music_rig.store import load_questions, write_documents
    from music_rig.models import OpenQuestionsDocument

    qdoc = load_questions(questions_path)
    data = q.model_dump(mode="json")
    data["verification_result"] = result.model_dump(mode="json")
    if note is not None:
        data["verification_note"] = note.strip()
    if resolve_answer:
        data["status"] = QuestionStatus.RESOLVED.value
        data["answer"] = answer_value
        data["resolved_at"] = (q.resolved_at or clock()).isoformat()
        data["reconciled_at"] = None
        data["reconciliation_note"] = ""
    updated = OpenQuestion.model_validate(data)
    new_qdoc = OpenQuestionsDocument(
        questions=[updated if x.id == q.id else x for x in qdoc.questions]
    )

    created_change_id = None
    if create_change and outcome_e == VerificationOutcome.FAILED_TEST and change_preview:
        from music_rig import change_service

        chg = change_service.create_change(
            change_preview["summary"],
            category=ChangeCategory.OTHER,
            details=change_preview["details"],
            affected_areas=change_preview["affected_areas"],
            clock=clock,
            changes_path=changes_path,
            link_session=False,
        )
        created_change_id = chg.id
        # link change on question
        refs = list(updated.related_changes)
        if chg.id not in refs:
            refs.append(chg.id)
        updated = OpenQuestion.model_validate(
            {**updated.model_dump(mode="json"), "related_changes": refs}
        )
        new_qdoc = OpenQuestionsDocument(
            questions=[updated if x.id == q.id else x for x in qdoc.questions]
        )
        # bidirectional link
        from music_rig.store import load_changes
        from music_rig.models import ChangeRecord, ChangesDocument

        cdoc = load_changes(changes_path)
        items = []
        for item in cdoc.items:
            if item.id == chg.id:
                qrefs = list(item.related_questions)
                if q.id not in qrefs:
                    qrefs.append(q.id)
                items.append(
                    ChangeRecord(**{**item.model_dump(), "related_questions": qrefs})
                )
            else:
                items.append(item)
        write_documents(
            questions=new_qdoc,
            changes=ChangesDocument(items=items),
            questions_path=questions_path,
            changes_path=changes_path,
        )
    else:
        write_documents(questions=new_qdoc, questions_path=questions_path)

    if render:
        from music_rig.render import render_docs

        try:
            render_docs(write=True)
        except StoreError:
            pass

    payload["question"] = updated
    payload["created_change_id"] = created_change_id
    payload["status"] = updated.status.value
    return payload


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
    after_obs: dict[str, int] = {
        "fully-reconcilable": 0,
        "agent-action": 0,
        "descriptive-or-agent": 0,
        "failed-test": 0,
        "unknown-observation": 0,
    }
    for item in queue:
        by_area[item.area] = by_area.get(item.area, 0) + 1
        by_kind[item.kind] = by_kind.get(item.kind, 0) + 1
        cap = Capability(item.capability) if item.capability else None
        bucket = _after_answer_bucket(cap)
        # Treat UNSUPPORTED without target as manual; VERIFY_ONLY as verify-only
        if cap == Capability.UNSUPPORTED:
            bucket = "agent"
        by_bucket[bucket] = by_bucket.get(bucket, 0) + 1
        # Project after explicit human observation (design-time estimate)
        obs_bucket = "fully-reconcilable"
        if cap == Capability.APPLY_AND_VERIFY:
            obs_bucket = "fully-reconcilable"
        elif cap in {Capability.VERIFY_ONLY, Capability.HUMAN_VERIFY_THEN_APPLY}:
            obs_bucket = "fully-reconcilable"
        elif cap == Capability.MANUAL:
            obs_bucket = "agent-action"
        else:
            obs_bucket = "descriptive-or-agent"
        after_obs[obs_bucket] = after_obs.get(obs_bucket, 0) + 1
    return {
        "total_open_guided": len(queue),
        "by_area": dict(sorted(by_area.items())),
        "by_kind": dict(sorted(by_kind.items())),
        "after_answer_capability": by_bucket,
        "after_observation_capability": after_obs,
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
    "record_observation",
    "summary",
    "production_readiness_matrix",
    "open_questions_for_todo",
    "ok_payload",
    "err_payload",
    "BOOL_CHOICES",
    "PATCHBAY_MODE_CHOICES",
]
