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
