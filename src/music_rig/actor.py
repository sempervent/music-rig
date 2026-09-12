"""CLI / service actor provenance — HUMAN vs BOT.

Default actor is HUMAN. Automated agents must invoke ``rig --am-bot …``.
"""

from __future__ import annotations

from contextvars import ContextVar
from enum import StrEnum

from music_rig.models import AnswerActor
from music_rig.store import StoreError

__all__ = [
    "ActorKind",
    "AnswerActor",
    "EvidenceBasis",
    "get_actor",
    "set_actor",
    "reset_actor",
    "is_bot",
    "is_human",
    "require_human",
    "require_human_observation",
]


class ActorKind(StrEnum):
    HUMAN = "HUMAN"
    BOT = "BOT"


class EvidenceBasis(StrEnum):
    """Why CURRENT evidence may escalate — never invent observations."""

    NONE = "NONE"
    HUMAN_ANSWER = "HUMAN_ANSWER"
    HUMAN_OBSERVATION = "HUMAN_OBSERVATION"


_actor: ContextVar[ActorKind] = ContextVar("music_rig_actor", default=ActorKind.HUMAN)


def get_actor() -> ActorKind:
    return _actor.get()


def set_actor(actor: ActorKind) -> None:
    _actor.set(actor)


def reset_actor() -> None:
    _actor.set(ActorKind.HUMAN)


def is_bot() -> bool:
    return get_actor() is ActorKind.BOT


def is_human() -> bool:
    return get_actor() is ActorKind.HUMAN


def require_human(*, action: str) -> None:
    """Reject BOT invocations of human-authority operations."""
    if is_bot():
        raise StoreError(
            f"BOT actor cannot {action}.\n"
            "Human authority is required. Run without --am-bot, or use the TUI."
        )


def require_human_observation() -> None:
    if is_bot():
        raise StoreError(
            "BOT actor cannot create HUMAN observation evidence.\n"
            "Run without --am-bot (or use the TUI) after a real physical/software test."
        )
