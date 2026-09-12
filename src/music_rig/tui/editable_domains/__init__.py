"""Editable domain adapters package."""

from __future__ import annotations

from music_rig.tui.editable_domains import registry
from music_rig.tui.editable_domains.questions import QuestionsEditableAdapter

__all__ = ["QuestionsEditableAdapter", "get_editable_adapter", "registry"]


def get_editable_adapter(domain_key: str):
    return registry.get_adapter(domain_key)
