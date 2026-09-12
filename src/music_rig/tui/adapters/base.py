"""Domain adapter protocol for read-only list/detail screens."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class AdapterAction:
    id: str
    label: str
    key: str | None = None
    needs_selection: bool = True


@dataclass
class AdapterRow:
    id: str
    cells: list[str]
    search_text: str = ""


class DomainAdapter(Protocol):
    id: str
    label: str
    columns: list[str]

    def rows(self) -> list[AdapterRow]: ...

    def detail(self, row_id: str) -> str: ...

    def actions(self) -> list[AdapterAction]: ...

    def run_action(self, action_id: str, row_id: str | None) -> str | None: ...


@dataclass
class SimpleAdapter:
    """Concrete adapter used by most read-only domains."""

    id: str
    label: str
    columns: list[str]
    _rows_fn: Callable[[], list[AdapterRow]]
    _detail_fn: Callable[[str], str]
    _actions: list[AdapterAction] = field(default_factory=list)
    _action_fn: Callable[[str, str | None], str | None] | None = None

    def rows(self) -> list[AdapterRow]:
        return self._rows_fn()

    def detail(self, row_id: str) -> str:
        return self._detail_fn(row_id)

    def actions(self) -> list[AdapterAction]:
        return list(self._actions)

    def run_action(self, action_id: str, row_id: str | None) -> str | None:
        if self._action_fn is None:
            return None
        return self._action_fn(action_id, row_id)
