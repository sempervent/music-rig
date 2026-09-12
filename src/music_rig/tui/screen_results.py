"""Typed screen results and single-shot completion helpers.

Architectural rules:
- A result-bearing Screen/ModalScreen completes its result exactly once.
- Child screens return navigation *intent*; the requester owns subsequent pushes.
- Never push a sibling screen and then dismiss the child underneath it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TypeVar

from music_rig.tui.save_outcome import SaveOutcome

T = TypeVar("T")


class AnswerNextAction(StrEnum):
    """Post-answer navigation intent — parent performs the push."""

    NONE = "none"
    RECONCILE = "reconcile"


@dataclass(frozen=True, slots=True)
class AnswerResult:
    """Structured AnswerScreen dismiss payload."""

    outcome: SaveOutcome
    question_id: str | None = None
    next_action: AnswerNextAction = AnswerNextAction.NONE


class SingleShotMixin:
    """Mixin: ``complete(result)`` dismisses at most once.

    Prefer correcting event ownership (one binding *or* one button path per
    physical action) over relying on this guard. The guard exists so a stray
    duplicate handler cannot finish Textual's result Future twice.
    """

    _result_completed: bool

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._result_completed = False

    def complete(self, result: T) -> bool:
        """Dismiss with ``result`` at most once. Returns whether dismiss ran."""
        if self._result_completed:
            return False
        self._result_completed = True
        self.dismiss(result)  # type: ignore[attr-defined]
        return True
