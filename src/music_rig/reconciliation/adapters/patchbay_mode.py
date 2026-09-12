"""patchbay.mode — APPLY_AND_VERIFY when pair + normalizable mode are known."""

from __future__ import annotations

from typing import Any

from music_rig import current_service, patchbay_state
from music_rig.models import OpenQuestion, QuestionStatus, ReconciliationState
from music_rig.reconciliation.adapters.base import ReconciliationAdapter
from music_rig.reconciliation.types import (
    Capability,
    Plan,
    VerificationStatus,
    VerifyResult,
)
from music_rig.store import StoreError


def normalize_mode(raw: str) -> str | None:
    """Deterministic mode normalize. Rejects prose; no NLP guessing."""
    cleaned = str(raw).strip().lower().replace("_", "-").replace(" ", "-")
    # Collapse repeated hyphens from mixed separators
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    if cleaned not in patchbay_state.PATCHBAY_MODES:
        return None
    if cleaned == "unknown":
        return None
    return cleaned


class PatchbayModeAdapter(ReconciliationAdapter):
    domain = "patchbay.mode"
    capability = Capability.APPLY_AND_VERIFY

    def read_current(self, question: OpenQuestion, *, paths: dict[str, Any]) -> Any:
        target = question.target
        if target is None or not target.bay:
            return None
        data = patchbay_state.load_raw(paths.get("patchbays"))
        bay = target.bay.strip().upper()
        if target.pair:
            try:
                upper_n, lower_n, upper, lower = patchbay_state.resolve_pair(bay, target.pair, data)
            except StoreError:
                return None
            snap = patchbay_state._pair_snapshot(upper_n, lower_n, upper, lower)
            pair_label = f"{upper_n}/{lower_n}" if lower_n is not None else str(upper_n)
            return {
                "bay": bay,
                "pair": pair_label,
                "mode": snap["mode"],
            }
        pairs = patchbay_state.list_pairs(bay, data)
        return {
            "bay": bay,
            "pairs": [
                {
                    "pair": (
                        f"{p['upper_n']}/{p['lower_n']}"
                        if p["lower_n"] is not None
                        else str(p["upper_n"])
                    ),
                    "mode": p["mode"],
                }
                for p in pairs
            ],
        }

    def plan(self, question: OpenQuestion, *, paths: dict[str, Any]) -> Plan:
        from music_rig.reconciliation.suggestions import (
            ActionSuggestion,
            SuggestionKind,
            render_suggestions,
            suggest_answer,
            suggest_finalize,
            suggest_resolve,
            suggest_target_pair,
        )

        target = question.target
        blockers: list[Any] = []
        ops: list[dict[str, Any]] = []
        if target is None or not target.bay:
            bay_sug = [
                ActionSuggestion(
                    kind=SuggestionKind.TARGET,
                    intent=(
                        f"question target set {question.id} --domain patchbay.mode --bay PB-B --yes"
                    ),
                    description="Set target.bay for patchbay.mode",
                    code="missing_target_field",
                    params={"question_id": question.id, "bay": "PB-B"},
                )
            ]
            return Plan(
                artifact_type="question",
                artifact_id=question.id,
                state=ReconciliationState.BLOCKED,
                capability=self.capability,
                blockers=[
                    {
                        "code": "missing_target_field",
                        "field": "bay",
                        "message": "Missing target.bay for patchbay.mode",
                        "candidates": [],
                        "suggestions": [s.to_dict() for s in bay_sug],
                        "suggested_commands": render_suggestions(bay_sug),
                    }
                ],
                suggestions=bay_sug,
            )
        bay = target.bay.strip().upper()
        current = self.read_current(question, paths=paths)

        if question.status == QuestionStatus.OPEN and question.answer.strip():
            return Plan(
                artifact_type="question",
                artifact_id=question.id,
                state=ReconciliationState.DRAFT_ANSWER,
                capability=self.capability,
                current=current,
                desired=question.answer.strip(),
                blockers=[
                    {
                        "code": "draft_answer",
                        "message": "OPEN with draft answer — resolve before reconcile",
                    }
                ],
                suggestions=[suggest_resolve(question.id)],
            )

        if question.status != QuestionStatus.RESOLVED or not question.answer.strip():
            return Plan(
                artifact_type="question",
                artifact_id=question.id,
                state=ReconciliationState.NEEDS_ANSWER,
                capability=self.capability,
                current=current,
                desired=None,
                blockers=["Question must be RESOLVED with a non-empty answer"],
                suggestions=[
                    suggest_answer(question.id, placeholder="<mode>"),
                ],
            )

        mode = normalize_mode(question.answer)
        if mode is None:
            ans = [suggest_answer(question.id, placeholder="half-normal")]
            return Plan(
                artifact_type="question",
                artifact_id=question.id,
                state=ReconciliationState.NEEDS_AGENT_ACTION,
                capability=self.capability,
                current=current,
                desired=question.answer.strip(),
                blockers=[
                    {
                        "code": "answer_not_normalizable",
                        "field": "answer",
                        "message": (
                            "Answer does not normalize to a patchbay mode "
                            "(normal | half-normal | thru)"
                        ),
                        "candidates": ["normal", "half-normal", "thru"],
                        "suggestions": [s.to_dict() for s in ans],
                        "suggested_commands": render_suggestions(ans),
                    }
                ],
                suggestions=ans,
            )

        if not target.pair:
            data = patchbay_state.load_raw(paths.get("patchbays"))
            pairs = patchbay_state.list_pairs(bay, data)
            unknown = [p for p in pairs if p["mode"] == "unknown"]
            candidates: list[str] = []
            suggestions: list[ActionSuggestion] = []
            for p in unknown or pairs:
                pair_label = (
                    f"{p['upper_n']}/{p['lower_n']}"
                    if p["lower_n"] is not None
                    else str(p["upper_n"])
                )
                candidates.append(pair_label)
                suggestions.append(suggest_target_pair(question.id, pair_label))
            # Prefer target-set for reconcile; keep one set-mode hint as fallback
            if candidates:
                suggestions.append(
                    ActionSuggestion(
                        kind=SuggestionKind.CLI_HINT,
                        intent=(
                            f"current patchbay set-mode {bay} {candidates[0]} "
                            f"{mode} --question {question.id}"
                        ),
                        description="Direct set-mode fallback",
                        code="set_mode_fallback",
                        params={
                            "bay": bay,
                            "pair": candidates[0],
                            "mode": mode,
                            "question_id": question.id,
                        },
                    )
                )
            pair_sug = [suggest_target_pair(question.id, c) for c in candidates[:8]]
            return Plan(
                artifact_type="question",
                artifact_id=question.id,
                state=ReconciliationState.NEEDS_AGENT_ACTION,
                capability=self.capability,
                current=current,
                desired=mode,
                blockers=[
                    {
                        "code": "missing_target_field",
                        "field": "pair",
                        "message": "target.pair missing — set pair before apply",
                        "candidates": candidates,
                        "suggestions": [s.to_dict() for s in pair_sug],
                        "suggested_commands": render_suggestions(pair_sug),
                    }
                ],
                suggestions=suggestions,
                details={
                    "unknown_pair_count": len(unknown),
                    "bay": bay,
                    "pair_candidates": candidates,
                },
            )

        pair = target.pair.strip()
        try:
            preview, _ = patchbay_state.propose_set_mode(
                bay, pair, mode, path=paths.get("patchbays")
            )
        except StoreError as exc:
            return Plan(
                artifact_type="question",
                artifact_id=question.id,
                state=ReconciliationState.BLOCKED,
                capability=self.capability,
                current=current,
                desired=mode,
                blockers=[str(exc)],
            )

        cur_mode = None
        if isinstance(current, dict):
            cur_mode = current.get("mode")
        if question.reconciled_at is not None:
            state = ReconciliationState.RECONCILED
        elif cur_mode == mode or not preview.changed:
            state = ReconciliationState.CURRENT_MATCHES
        else:
            state = ReconciliationState.READY_TO_APPLY

        ops.append(
            {
                "op": "set-mode",
                "bay": bay,
                "pair": pair,
                "mode": mode,
                "changed": preview.changed,
                "message": preview.message,
            }
        )
        suggestions = [
            ActionSuggestion(
                kind=SuggestionKind.CLI_HINT,
                intent=f"reconcile apply question {question.id} --yes",
                description=f"Apply set-mode for {question.id}",
                code="apply",
                params={"question_id": question.id},
            ),
            ActionSuggestion(
                kind=SuggestionKind.VERIFY,
                intent=f"reconcile verify question {question.id}",
                description=f"Verify {question.id} after apply",
                code="verify",
                params={"question_id": question.id},
            ),
            suggest_finalize(question.id),
        ]

        return Plan(
            artifact_type="question",
            artifact_id=question.id,
            state=state,
            capability=self.capability,
            current=current,
            desired=mode,
            operations=ops,
            postconditions=[f"{bay} {pair} mode == {mode}"],
            closable=list(question.related_todos) + list(question.related_changes),
            blockers=blockers,
            suggestions=suggestions,
            details={"preview": preview.model_dump(mode="json")},
        )

    def apply(
        self,
        question: OpenQuestion,
        *,
        paths: dict[str, Any],
        dry_run: bool = True,
        yes: bool = False,
    ) -> dict[str, Any]:
        plan = self.plan(question, paths=paths)
        if plan.state == ReconciliationState.NEEDS_AGENT_ACTION:
            return {
                "applied": False,
                "reason": "NEEDS_AGENT_ACTION",
                "plan": plan.to_dict(),
            }
        if plan.state not in {
            ReconciliationState.READY_TO_APPLY,
            ReconciliationState.CURRENT_MATCHES,
            ReconciliationState.READY_TO_FINALIZE,
        }:
            raise StoreError(f"Cannot apply {question.id} in state {plan.state.value}")
        if not yes and not dry_run:
            raise StoreError("apply requires --yes (or --dry-run)")
        target = question.target
        assert target is not None and target.bay and target.pair
        mode = normalize_mode(question.answer)
        if mode is None:
            raise StoreError("Answer does not normalize to a patchbay mode")
        preview, data = patchbay_state.propose_set_mode(
            target.bay, target.pair, mode, path=paths.get("patchbays")
        )
        if dry_run:
            return {
                "applied": False,
                "dry_run": True,
                "preview": preview.model_dump(mode="json"),
            }
        from music_rig import store as store_mod

        committed = current_service.commit_patchbay(
            data,
            preview,
            dry_run=False,
            render=False,
            question_id=question.id,
            resolve_q=False,
            patchbays_path=paths.get("patchbays") or store_mod.PATCHBAYS_PATH,
            questions_path=paths.get("questions") or store_mod.QUESTIONS_PATH,
            changes_path=paths.get("changes") or store_mod.CHANGES_PATH,
        )
        # Render planning + patchbay projections only (avoid full midi/inventory coupling
        # when callers monkeypatch a subset of store paths).
        try:
            from music_rig.reconciliation.service import _render_planning_and_patchbay

            _render_planning_and_patchbay(paths)
        except StoreError:
            pass
        return {
            "applied": committed.changed,
            "dry_run": False,
            "preview": committed.model_dump(mode="json"),
        }

    def verify(self, question: OpenQuestion, *, paths: dict[str, Any]) -> VerifyResult:
        target = question.target
        if target is None or not target.bay or not target.pair:
            return VerifyResult(
                status=VerificationStatus.BLOCKED,
                message="Need target.bay and target.pair to verify",
            )
        mode = normalize_mode(question.answer) if question.answer.strip() else None
        if mode is None:
            return VerifyResult(
                status=VerificationStatus.UNVERIFIABLE,
                message="Answer does not normalize to a mode",
                expected=question.answer,
            )
        current = self.read_current(question, paths=paths)
        cur_mode = current.get("mode") if isinstance(current, dict) else None
        if cur_mode == mode:
            return VerifyResult(
                status=VerificationStatus.MATCH,
                current=current,
                expected=mode,
                message=f"{target.bay} {target.pair} mode matches {mode}",
            )
        return VerifyResult(
            status=VerificationStatus.MISMATCH,
            current=current,
            expected=mode,
            message=f"{target.bay} {target.pair} mode is {cur_mode!r}, expected {mode!r}",
        )
