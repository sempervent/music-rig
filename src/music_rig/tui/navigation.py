"""Domain registry and home navigation metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from music_rig.tui.queries import HomeCounts, home_counts


@dataclass(frozen=True)
class DomainSpec:
    key: str
    label: str
    section: str  # Planning | CURRENT | Performance | Operations
    aliases: tuple[str, ...] = ()
    editable: bool = False
    count_fn: Callable[[HomeCounts], str] | None = None


def _c(fn: Callable[[HomeCounts], object]) -> Callable[[HomeCounts], str]:
    return lambda counts: str(fn(counts))


DOMAINS: list[DomainSpec] = [
    DomainSpec(
        "question",
        "Questions",
        "Planning",
        aliases=("questions",),
        editable=True,
        count_fn=_c(lambda c: f"{c.open_questions} open"),
    ),
    DomainSpec(
        "todo",
        "TODO",
        "Planning",
        editable=True,
        count_fn=_c(lambda c: f"{c.todo_total} total / {c.next_session} next"),
    ),
    DomainSpec(
        "wish",
        "Wishlist",
        "Planning",
        aliases=("wishlist",),
        editable=True,
        count_fn=_c(lambda c: f"{c.wishlist} active"),
    ),
    DomainSpec(
        "inbox",
        "Inbox",
        "Planning",
        editable=True,
        count_fn=_c(lambda c: f"{c.inbox_open} open"),
    ),
    DomainSpec(
        "changes",
        "Changes",
        "Planning",
        editable=True,
        count_fn=_c(lambda c: f"{c.changes_open} open"),
    ),
    DomainSpec(
        "patchbay",
        "Patchbays",
        "CURRENT",
        aliases=("patchbays",),
        editable=True,
        count_fn=_c(lambda c: f"{c.patchbay_bays} bays / {c.patchbay_unknown_modes} unknown"),
    ),
    DomainSpec(
        "gear",
        "Gear",
        "CURRENT",
        editable=True,
        count_fn=_c(lambda c: str(c.gear)),
    ),
    DomainSpec(
        "channels",
        "Channel map",
        "CURRENT",
        aliases=("channel", "channel-map"),
        editable=True,
    ),
    DomainSpec(
        "routing",
        "Routing",
        "CURRENT",
        editable=True,
    ),
    DomainSpec(
        "midi",
        "MIDI",
        "CURRENT",
        editable=True,
    ),
    DomainSpec(
        "controls",
        "Controllers",
        "CURRENT",
        aliases=("control", "controllers"),
        editable=True,
    ),
    DomainSpec(
        "ableton",
        "Ableton",
        "CURRENT",
        editable=True,
    ),
    DomainSpec(
        "performance",
        "Performance",
        "Performance",
        editable=True,
    ),
    DomainSpec(
        "snapshot",
        "Snapshots",
        "Operations",
        aliases=("snapshots",),
        count_fn=_c(lambda c: str(c.snapshots)),
    ),
    DomainSpec(
        "backup",
        "Backups",
        "Operations",
        aliases=("backups",),
        editable=True,
    ),
    DomainSpec(
        "session",
        "Sessions",
        "Operations",
        aliases=("sessions",),
        count_fn=_c(
            lambda c: f"{c.sessions}"
            + (f" (active {c.active_session})" if c.active_session else "")
        ),
    ),
    DomainSpec("doctor", "Doctor", "Operations"),
    DomainSpec("status", "Status", "Operations"),
    DomainSpec("reconcile", "Reconcile", "Operations"),
    DomainSpec("automation", "Automation", "Operations"),
]

SECTION_ORDER = ("Planning", "CURRENT", "Performance", "Operations")

_ALIAS_MAP: dict[str, str] = {}
for _spec in DOMAINS:
    _ALIAS_MAP[_spec.key] = _spec.key
    for _alias in _spec.aliases:
        _ALIAS_MAP[_alias] = _spec.key


def normalize_route(raw: str | None) -> str | None:
    if raw is None or not str(raw).strip():
        return None
    key = str(raw).strip().lower()
    return _ALIAS_MAP.get(key)


def domain_by_key(key: str) -> DomainSpec | None:
    canon = normalize_route(key)
    if canon is None:
        return None
    for spec in DOMAINS:
        if spec.key == canon:
            return spec
    return None


def home_rows() -> list[tuple[str, str, str, str]]:
    """Return (section, key, label, count_label) for home navigation."""
    counts = home_counts()
    rows: list[tuple[str, str, str, str]] = []
    for section in SECTION_ORDER:
        for spec in DOMAINS:
            if spec.section != section:
                continue
            count = spec.count_fn(counts) if spec.count_fn else ""
            mark = " ✎" if spec.editable else ""
            rows.append((section, spec.key, f"{spec.label}{mark}", count))
    return rows
