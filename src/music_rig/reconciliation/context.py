"""Typed reconciliation path context — one place for production defaults."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping

from music_rig import store as store_mod


@dataclass(frozen=True, slots=True)
class ReconciliationPaths:
    """Canonical YAML / projection paths used by reconciliation."""

    questions: Path
    changes: Path
    todo: Path
    patchbays: Path
    routing: Path
    midi: Path
    controllers: Path
    ableton: Path
    inventory: Path
    channels: Path
    docs_todo: Path
    docs_wishlist: Path
    docs_questions: Path
    docs_patchbays: Path

    @classmethod
    def default(cls) -> ReconciliationPaths:
        """Assemble production defaults at call time (honors monkeypatches)."""
        return cls(
            questions=store_mod.QUESTIONS_PATH,
            changes=store_mod.CHANGES_PATH,
            todo=store_mod.TODO_PATH,
            patchbays=store_mod.PATCHBAYS_PATH,
            routing=store_mod.ROUTING_PATH,
            midi=store_mod.MIDI_PATH,
            controllers=store_mod.CONTROLLERS_PATH,
            ableton=store_mod.ABLETON_PATH,
            inventory=store_mod.INVENTORY_PATH,
            channels=store_mod.CHANNEL_MAP_PATH,
            docs_todo=store_mod.DOCS_TODO_PATH,
            docs_wishlist=store_mod.DOCS_WISHLIST_PATH,
            docs_questions=store_mod.DOCS_QUESTIONS_PATH,
            docs_patchbays=store_mod.DOCS_PATCHBAYS_PATH,
        )

    @classmethod
    def for_root(cls, root: Path) -> ReconciliationPaths:
        """Fixture helper: map standard filenames under a temp root."""
        root = Path(root)
        return cls(
            questions=root / "open-questions.yaml",
            changes=root / "changes.yaml",
            todo=root / "todo.yaml",
            patchbays=root / "patchbays.yaml",
            routing=root / "routing.yaml",
            midi=root / "midi.yaml",
            controllers=root / "controllers.yaml",
            ableton=root / "ableton.yaml",
            inventory=root / "inventory.yaml",
            channels=root / "channel-map.yaml",
            docs_todo=root / "todo.md",
            docs_wishlist=root / "wishlist.md",
            docs_questions=root / "open-questions.md",
            docs_patchbays=root / "patchbays.md",
        )

    def with_overrides(self, **overrides: Path | None) -> ReconciliationPaths:
        clean = {k: v for k, v in overrides.items() if v is not None}
        return replace(self, **clean) if clean else self

    def as_dict(self) -> dict[str, Path]:
        return {
            "questions": self.questions,
            "changes": self.changes,
            "todo": self.todo,
            "patchbays": self.patchbays,
            "routing": self.routing,
            "midi": self.midi,
            "controllers": self.controllers,
            "ableton": self.ableton,
            "inventory": self.inventory,
            "channels": self.channels,
            "docs_todo": self.docs_todo,
            "docs_wishlist": self.docs_wishlist,
            "docs_questions": self.docs_questions,
            "docs_patchbays": self.docs_patchbays,
        }


@dataclass(frozen=True, slots=True)
class ReconciliationContext:
    """Shared context for checks, plans, and agent packets."""

    paths: ReconciliationPaths

    @classmethod
    def default(cls) -> ReconciliationContext:
        return cls(paths=ReconciliationPaths.default())

    @classmethod
    def for_root(cls, root: Path) -> ReconciliationContext:
        return cls(paths=ReconciliationPaths.for_root(root))

    @classmethod
    def from_overrides(cls, overrides: Mapping[str, Any] | None = None) -> ReconciliationContext:
        """Accept legacy dict-style path overrides from service kwargs."""
        base = ReconciliationPaths.default()
        if not overrides:
            return cls(paths=base)
        # Normalize both short keys and *_path kwargs
        mapped: dict[str, Path] = {}
        alias = {
            "questions_path": "questions",
            "changes_path": "changes",
            "todo_path": "todo",
            "patchbays_path": "patchbays",
            "routing_path": "routing",
            "midi_path": "midi",
            "controllers_path": "controllers",
            "ableton_path": "ableton",
            "inventory_path": "inventory",
            "channels_path": "channels",
            "docs_todo": "docs_todo",
            "docs_wishlist": "docs_wishlist",
            "docs_questions": "docs_questions",
            "docs_patchbays": "docs_patchbays",
        }
        for key, value in overrides.items():
            if value is None:
                continue
            short = alias.get(key, key)
            if short in base.as_dict():
                mapped[short] = Path(value)
        return cls(paths=base.with_overrides(**mapped))

    @property
    def questions_path(self) -> Path:
        return self.paths.questions

    def path_dict(self) -> dict[str, Any]:
        """Legacy adapter-compatible dict."""
        return self.paths.as_dict()
