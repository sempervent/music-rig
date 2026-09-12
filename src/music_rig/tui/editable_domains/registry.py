"""Registry of editable domain adapters."""

from __future__ import annotations

from music_rig.tui.editable import BaseEditableAdapter
from music_rig.tui.editable_domains.current import (
    AbletonEditableAdapter,
    BackupEditableAdapter,
    ChannelsEditableAdapter,
    ControllersEditableAdapter,
    GearEditableAdapter,
    MidiEditableAdapter,
    PerformanceEditableAdapter,
    RoutingEditableAdapter,
)
from music_rig.tui.editable_domains.planning import (
    ChangesEditableAdapter,
    InboxEditableAdapter,
    WishlistEditableAdapter,
)
from music_rig.tui.editable_domains.questions import QuestionsEditableAdapter
from music_rig.tui.editable_domains.todo import TodoEditableAdapter

_ADAPTERS: dict[str, BaseEditableAdapter] = {}


def _register(adapter: BaseEditableAdapter) -> None:
    _ADAPTERS[adapter.id] = adapter


def _ensure() -> None:
    if _ADAPTERS:
        return
    for adapter in (
        QuestionsEditableAdapter(),
        TodoEditableAdapter(),
        WishlistEditableAdapter(),
        InboxEditableAdapter(),
        ChangesEditableAdapter(),
        GearEditableAdapter(),
        ChannelsEditableAdapter(),
        RoutingEditableAdapter(),
        MidiEditableAdapter(),
        ControllersEditableAdapter(),
        AbletonEditableAdapter(),
        PerformanceEditableAdapter(),
        BackupEditableAdapter(),
    ):
        _register(adapter)


def get_adapter(domain_key: str) -> BaseEditableAdapter | None:
    _ensure()
    key = domain_key.strip().lower()
    aliases = {
        "questions": "question",
        "wishlist": "wish",
        "change": "changes",
        "channel": "channels",
        "channel-map": "channels",
        "control": "controls",
        "controllers": "controls",
        "backups": "backup",
        "patchbay": None,  # specialized screen
        "patchbays": None,
    }
    if key in aliases:
        mapped = aliases[key]
        if mapped is None:
            return None
        key = mapped
    return _ADAPTERS.get(key)


def all_adapters() -> list[BaseEditableAdapter]:
    _ensure()
    return list(_ADAPTERS.values())


def domain_keys() -> list[str]:
    _ensure()
    return sorted(_ADAPTERS.keys())


# Stage 18 coverage markers: View / Edit / Add / Round-trip / Vim-modal
# Used by tests and docs/tui.md matrix.
COVERAGE: dict[str, dict[str, str]] = {
    "question": {
        "view": "yes",
        "edit": "yes",
        "add": "yes",
        "round_trip": "yes",
        "vim_modal": "yes",
        "notes": "Answer screen keeps question visible; a=Answer A=Add r=Resolve",
    },
    "todo": {
        "view": "yes",
        "edit": "yes",
        "add": "yes",
        "round_trip": "yes",
        "vim_modal": "yes",
        "notes": "",
    },
    "wish": {
        "view": "yes",
        "edit": "yes",
        "add": "yes",
        "round_trip": "yes",
        "vim_modal": "yes",
        "notes": "",
    },
    "inbox": {
        "view": "yes",
        "edit": "yes",
        "add": "yes",
        "round_trip": "yes",
        "vim_modal": "yes",
        "notes": "",
    },
    "changes": {
        "view": "yes",
        "edit": "yes",
        "add": "yes",
        "round_trip": "yes",
        "vim_modal": "yes",
        "notes": "",
    },
    "gear": {
        "view": "yes",
        "edit": "yes",
        "add": "yes",
        "round_trip": "yes",
        "vim_modal": "yes",
        "notes": "",
    },
    "channels": {
        "view": "yes",
        "edit": "yes",
        "add": "no",
        "round_trip": "yes",
        "vim_modal": "yes",
        "notes": "Add via CLI channel tools",
    },
    "routing": {
        "view": "yes",
        "edit": "yes",
        "add": "no",
        "round_trip": "yes",
        "vim_modal": "yes",
        "notes": "Structural path edits via CLI",
    },
    "midi": {
        "view": "yes",
        "edit": "yes",
        "add": "partial",
        "round_trip": "yes",
        "vim_modal": "yes",
        "notes": "Link add deferred unless services mature; no MIDI TX",
    },
    "controls": {
        "view": "yes",
        "edit": "yes",
        "add": "partial",
        "round_trip": "yes",
        "vim_modal": "yes",
        "notes": "Controller context add deferred",
    },
    "ableton": {
        "view": "yes",
        "edit": "yes",
        "add": "no",
        "round_trip": "yes",
        "vim_modal": "yes",
        "notes": "Metadata only",
    },
    "performance": {
        "view": "yes",
        "edit": "partial",
        "add": "partial",
        "round_trip": "yes",
        "vim_modal": "yes",
        "notes": "Evidence fields; no panic/record execution",
    },
    "backup": {
        "view": "yes",
        "edit": "yes",
        "add": "partial",
        "round_trip": "yes",
        "vim_modal": "yes",
        "notes": "Plan fields; no .rig.local secrets",
    },
    "patchbay": {
        "view": "yes",
        "edit": "yes",
        "add": "no",
        "round_trip": "yes",
        "vim_modal": "yes",
        "notes": "Specialized screen; do not Add Pair",
    },
}


def coverage_for(domain_key: str) -> dict[str, str] | None:
    return COVERAGE.get(domain_key)


def editable_domains_with_adapters() -> list[str]:
    """Every editable=true domain that must have an adapter or specialized screen."""
    return sorted(set(domain_keys()) | {"patchbay"})
