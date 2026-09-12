"""Structured reconciliation action suggestions (canonical); CLI strings are rendered."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from music_rig.actor import ActorKind
from music_rig.reconciliation.operations import RigOperation


class SuggestionKind(StrEnum):
    """Machine-oriented suggestion category."""

    OPERATION = "operation"
    CLI_HINT = "cli_hint"
    INSPECT = "inspect"
    VERIFY = "verify"
    FINALIZE = "finalize"
    ANSWER = "answer"
    RESOLVE = "resolve"
    TARGET = "target"
    SWEEP = "sweep"
    ADVISORY = "advisory"


@dataclass
class ActionSuggestion:
    """Canonical next-step suggestion — not a shell string.

    Presentation (``uv run rig …``) is produced by ``render_suggestion``.
    """

    kind: SuggestionKind | str
    intent: str
    description: str = ""
    operation: RigOperation | None = None
    params: dict[str, Any] = field(default_factory=dict)
    code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        kind = self.kind.value if isinstance(self.kind, SuggestionKind) else str(self.kind)
        data: dict[str, Any] = {
            "kind": kind,
            "intent": self.intent,
            "description": self.description,
            "params": dict(self.params),
            "code": self.code,
            "operation": self.operation.to_dict() if self.operation else None,
        }
        return data

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ActionSuggestion:
        op_raw = raw.get("operation")
        operation = RigOperation.from_dict(op_raw) if isinstance(op_raw, dict) else None
        kind_raw = raw.get("kind") or SuggestionKind.CLI_HINT.value
        try:
            kind: SuggestionKind | str = SuggestionKind(str(kind_raw))
        except ValueError:
            kind = str(kind_raw)
        return cls(
            kind=kind,
            intent=str(raw.get("intent") or ""),
            description=str(raw.get("description") or ""),
            operation=operation,
            params=dict(raw.get("params") or {}),
            code=raw.get("code"),
        )


def cli_prefix(*, actor: ActorKind | str = ActorKind.HUMAN) -> str:
    """Actor-aware CLI prefix for rendered suggestions."""
    kind = actor if isinstance(actor, ActorKind) else ActorKind(str(actor))
    if kind is ActorKind.BOT:
        return "uv run rig --am-bot"
    return "uv run rig"


def render_suggestion(
    suggestion: ActionSuggestion,
    *,
    actor: ActorKind | str = ActorKind.HUMAN,
) -> str:
    """Render one suggestion to a display CLI string (never for subprocess exec)."""
    from music_rig.reconciliation.operation_renderer import render_cli

    prefix = cli_prefix(actor=actor)
    if suggestion.operation is not None:
        return render_cli(suggestion.operation, prefix=prefix)

    # Fallback: intent/params as a soft CLI hint (presentation only).
    intent = suggestion.intent.strip()
    if intent.startswith("uv run rig"):
        # Already a full template — inject --am-bot for BOT when missing.
        if actor in (ActorKind.BOT, "BOT") and " --am-bot" not in intent:
            return intent.replace("uv run rig", "uv run rig --am-bot", 1)
        return intent
    if intent.startswith("rig "):
        return f"{prefix} {intent[4:]}"
    params = suggestion.params or {}
    extra = " ".join(f"--{k.replace('_', '-')} {v}" for k, v in sorted(params.items()))
    body = intent if not extra else f"{intent} {extra}".strip()
    return f"{prefix} {body}".strip()


def render_suggestions(
    suggestions: list[ActionSuggestion],
    *,
    actor: ActorKind | str = ActorKind.HUMAN,
) -> list[str]:
    return [render_suggestion(s, actor=actor) for s in suggestions]


# --- Convenience constructors for common intents ---------------------------------


def suggest_resolve(question_id: str) -> ActionSuggestion:
    return ActionSuggestion(
        kind=SuggestionKind.RESOLVE,
        intent="question resolve",
        description=f"Resolve draft answer on {question_id}",
        operation=RigOperation(
            namespace="question",
            action="resolve",
            args={"question_id": question_id},
            description="Resolve OPEN draft to RESOLVED",
        ),
        code="resolve_draft",
    )


def suggest_answer(question_id: str, *, placeholder: str = "…") -> ActionSuggestion:
    return ActionSuggestion(
        kind=SuggestionKind.ANSWER,
        intent=f'question answer {question_id} --answer "{placeholder}" --json',
        description=f"Record final human answer for {question_id}",
        code="needs_answer",
        params={"question_id": question_id},
    )


def suggest_plan(question_id: str) -> ActionSuggestion:
    return ActionSuggestion(
        kind=SuggestionKind.INSPECT,
        intent=f"reconcile plan question {question_id} --json",
        description=f"Inspect reconciliation plan for {question_id}",
        code="plan",
        params={"question_id": question_id},
    )


def suggest_finalize(
    question_id: str,
    *,
    confirm_current_reconciled: bool = False,
    note: str = "…",
    no_current_change: bool = False,
) -> ActionSuggestion:
    args: dict[str, Any] = {
        "question_id": question_id,
        "note": note,
        "complete_linked_todos": True,
        "confirm_dod": True,
    }
    op = RigOperation(
        namespace="question",
        action="finalize_manual",
        args=args,
        description="Finalize after CURRENT matches / agent interpretation",
    )
    # Renderer covers the common finalize path; flags beyond template stay in intent.
    if confirm_current_reconciled or no_current_change:
        flags = ["reconcile", "finalize", "question", question_id]
        if confirm_current_reconciled:
            flags.append("--confirm-current-reconciled")
        if no_current_change:
            flags.append("--no-current-change")
        flags += ["--note", note, "--yes", "--json"]
        return ActionSuggestion(
            kind=SuggestionKind.FINALIZE,
            intent=" ".join(flags),
            description=f"Finalize {question_id}",
            operation=op if not no_current_change else None,
            code="finalize",
            params={"question_id": question_id},
        )
    return ActionSuggestion(
        kind=SuggestionKind.FINALIZE,
        intent="question.finalize_manual",
        description=f"Finalize {question_id}",
        operation=op,
        code="finalize",
    )


def suggest_verify_record(
    question_id: str, *, outcome: str = "confirmed", value: str = "…"
) -> ActionSuggestion:
    return ActionSuggestion(
        kind=SuggestionKind.VERIFY,
        intent=(f"verify record {question_id} --outcome {outcome} --value {value} --yes --json"),
        description=f"Record human observation for {question_id}",
        code="verify_record",
        params={"question_id": question_id, "outcome": outcome, "value": value},
    )


def suggest_target_pair(question_id: str, pair: str) -> ActionSuggestion:
    return ActionSuggestion(
        kind=SuggestionKind.TARGET,
        intent=f"question target set {question_id} --pair {pair} --yes",
        description=f"Set target.pair={pair} on {question_id}",
        code="missing_target_field",
        params={"question_id": question_id, "pair": pair},
    )


def suggest_todo_done(todo_id: str) -> ActionSuggestion:
    return ActionSuggestion(
        kind=SuggestionKind.ADVISORY,
        intent=f"todo done {todo_id}",
        description=f"Mark {todo_id} done",
        code="todo_done",
        params={"todo_id": todo_id},
    )


def suggest_changes_apply(change_id: str) -> ActionSuggestion:
    return ActionSuggestion(
        kind=SuggestionKind.ADVISORY,
        intent=f"changes apply {change_id} --yes",
        description=f"Apply change {change_id}",
        code="changes_apply",
        params={"change_id": change_id},
    )


def suggestions_asdicts(suggestions: list[ActionSuggestion]) -> list[dict[str, Any]]:
    return [s.to_dict() for s in suggestions]


def legacy_command_to_suggestion(command: str) -> ActionSuggestion:
    """Wrap a legacy shell presentation string as a structured suggestion."""
    return ActionSuggestion(
        kind=SuggestionKind.CLI_HINT,
        intent=command,
        description="legacy presentation command",
        code="legacy_cli",
    )
