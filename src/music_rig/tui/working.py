"""Staged working document with dirty tracking and source-hash concurrency."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Generic, TypeVar

T = TypeVar("T")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass
class DirtyState:
    """Summary of staged mutations."""

    count: int = 0
    keys: list[str] = field(default_factory=list)

    @property
    def is_dirty(self) -> bool:
        return self.count > 0

    def label(self) -> str:
        if not self.is_dirty:
            return ""
        return f"{self.count} unsaved change{'s' if self.count != 1 else ''}"


class ConcurrentModificationError(RuntimeError):
    """Raised when the source file changed since the editor was opened."""


class WorkingDocument(Generic[T]):
    """Baseline data plus staged mutations; commits only via an explicit apply callback."""

    def __init__(
        self,
        baseline: T,
        *,
        source_path: Path | None = None,
        source_hash: str | None = None,
    ) -> None:
        self.baseline = baseline
        self.source_path = source_path
        self.source_hash = source_hash
        if source_path is not None and source_hash is None and source_path.exists():
            self.source_hash = sha256_file(source_path)
        self._mutations: dict[str, Any] = {}

    @property
    def mutations(self) -> dict[str, Any]:
        return dict(self._mutations)

    def stage(self, key: str, value: Any) -> None:
        self._mutations[key] = value

    def unstage(self, key: str) -> None:
        self._mutations.pop(key, None)

    def get(self, key: str, default: Any = None) -> Any:
        if key in self._mutations:
            return self._mutations[key]
        return default

    def has(self, key: str) -> bool:
        return key in self._mutations

    def dirty_state(self) -> DirtyState:
        keys = sorted(self._mutations.keys())
        return DirtyState(count=len(keys), keys=keys)

    @property
    def dirty_count(self) -> int:
        return len(self._mutations)

    @property
    def is_dirty(self) -> bool:
        return bool(self._mutations)

    def discard(self) -> None:
        self._mutations.clear()

    def current_source_hash(self) -> str | None:
        if self.source_path is None or not self.source_path.exists():
            return None
        return sha256_file(self.source_path)

    def source_unchanged(self) -> bool:
        if self.source_path is None or self.source_hash is None:
            return True
        current = self.current_source_hash()
        return current == self.source_hash

    def refresh_source_hash(self) -> None:
        if self.source_path is not None and self.source_path.exists():
            self.source_hash = sha256_file(self.source_path)

    def apply(self, commit: Callable[["WorkingDocument[T]"], None]) -> None:
        """Validate concurrency, then invoke commit callback. Keeps mutations on failure."""
        if not self.source_unchanged():
            raise ConcurrentModificationError(
                "CURRENT data changed since this editor was opened. Reload before applying."
            )
        commit(self)
