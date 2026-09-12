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
                upper_n, lower_n, upper, lower = patchbay_state.resolve_pair(
                    bay, target.pair, data
                )
            except StoreError:
                return None
            snap = patchbay_state._pair_snapshot(upper_n, lower_n, upper, lower)
            pair_label = (
                f"{upper_n}/{lower_n}" if lower_n is not None else str(upper_n)
            )
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
        target = question.target
        blockers: list[str] = []
        ops: list[dict[str, Any]] = []
        suggested: list[str] = []
        if target is None or not target.bay:
            return Plan(
                artifact_type="question",
                artifact_id=question.id,
                state=ReconciliationState.BLOCKED,
                capability=self.capability,
                blockers=["Missing target.bay for patchbay.mode"],
            )
        bay = target.bay.strip().upper()
        current = self.read_current(question, paths=paths)

        if question.status != QuestionStatus.RESOLVED or not question.answer.strip():
            return Plan(
                artifact_type="question",
                artifact_id=question.id,
                state=ReconciliationState.NEEDS_ANSWER,
                capability=self.capability,
                current=current,
                desired=None,
                blockers=["Question must be RESOLVED with a non-empty answer"],
                suggested_commands=[f"uv run rig question resolve {question.id}"],
            )

        mode = normalize_mode(question.answer)
        if mode is None:
            return Plan(
                artifact_type="question",
                artifact_id=question.id,
                state=ReconciliationState.NEEDS_AGENT_ACTION,
                capability=self.capability,
                current=current,
                desired=question.answer.strip(),
                blockers=[
                    "Answer does not normalize to a patchbay mode "
                    "(normal | half-normal | thru)"
                ],
                suggested_commands=[
                    f"uv run rig question resolve {question.id}  # re-answer with a mode token"
                ],
            )

        if not target.pair:
            data = patchbay_state.load_raw(paths.get("patchbays"))
            pairs = patchbay_state.list_pairs(bay, data)
            unknown = [p for p in pairs if p["mode"] == "unknown"]
            for p in (unknown or pairs):
                pair_label = (
                    f"{p['upper_n']}/{p['lower_n']}"
                    if p["lower_n"] is not None
                    else str(p["upper_n"])
                )
                suggested.append(
                    f"uv run rig current patchbay set-mode {bay} {pair_label} {mode} "
                    f"--question {question.id}"
                )
            return Plan(
                artifact_type="question",
                artifact_id=question.id,
                state=ReconciliationState.NEEDS_AGENT_ACTION,
                capability=self.capability,
                current=current,
                desired=mode,
                blockers=[
                    "target.pair missing — choose a pair or run suggested set-mode commands"
                ],
                suggested_commands=suggested,
                details={"unknown_pair_count": len(unknown), "bay": bay},
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
        suggested.append(
            f"uv run rig reconcile apply question {question.id} --yes"
        )
        suggested.append(f"uv run rig reconcile verify question {question.id}")
        suggested.append(f"uv run rig reconcile finalize question {question.id} --yes")

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
            suggested_commands=suggested,
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
            raise StoreError(
                f"Cannot apply {question.id} in state {plan.state.value}"
            )
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
