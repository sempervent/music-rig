"""Pydantic models for canonical planning and inbox data."""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

RIG_ID_RE = re.compile(r"^RIG-\d{3}$")
CAP_ID_RE = re.compile(r"^CAP-\d{3}$")
RigId = Annotated[str, Field(pattern=r"^RIG-\d{3}$")]
CapId = Annotated[str, Field(pattern=r"^CAP-\d{3}$")]

TERMINAL_FOR_NEXT = frozenset({"DONE", "CANCELLED", "DEFERRED"})


class TodoPriority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class TodoStatus(str, Enum):
    READY = "READY"
    BLOCKED = "BLOCKED"
    IN_PROGRESS = "IN PROGRESS"
    WAITING = "WAITING"
    DONE = "DONE"
    DEFERRED = "DEFERRED"
    CANCELLED = "CANCELLED"


class WishPriority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class WishStatus(str, Enum):
    IDEA = "IDEA"
    RESEARCH = "RESEARCH"
    BORROW_FIRST = "BORROW FIRST"
    BUY_LATER = "BUY LATER"
    BUY_NOW = "BUY NOW"
    REDUNDANT = "REDUNDANT"
    REJECTED = "REJECTED"
    WAITING = "WAITING"
    DEFERRED = "DEFERRED"


class InboxStatus(str, Enum):
    OPEN = "OPEN"
    TRIAGED = "TRIAGED"
    DISMISSED = "DISMISSED"


class TodoTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: RigId
    task: str = Field(min_length=1)
    area: str = Field(min_length=1)
    priority: TodoPriority
    status: TodoStatus
    depends_on: list[RigId] = Field(default_factory=list)
    depends_hint: str | None = None
    definition_of_done: str = Field(min_length=1)
    notes: str = ""
    waiting_on: str | None = None
    next_session_why: str | None = None

    @field_validator("depends_on")
    @classmethod
    def _unique_deps(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("depends_on must not contain duplicates")
        return value

    @model_validator(mode="after")
    def _no_self_dependency(self) -> TodoTask:
        if self.id in self.depends_on:
            raise ValueError(f"{self.id} cannot depend on itself")
        return self


class TodoDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    next_session: list[RigId] = Field(default_factory=list)
    tasks: list[TodoTask] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_document(self) -> TodoDocument:
        ids = [task.id for task in self.tasks]
        if len(ids) != len(set(ids)):
            raise ValueError("TODO IDs must be unique")

        by_id = {task.id: task for task in self.tasks}

        for task in self.tasks:
            for dep in task.depends_on:
                if dep not in by_id:
                    raise ValueError(f"{task.id} depends on unknown TODO {dep}")

        if len(self.next_session) > 3:
            raise ValueError("next_session may contain at most 3 tasks")

        if len(self.next_session) != len(set(self.next_session)):
            raise ValueError("next_session IDs must be unique")

        for session_id in self.next_session:
            if session_id not in by_id:
                raise ValueError(f"next_session references unknown TODO {session_id}")
            status = by_id[session_id].status
            if status.value in TERMINAL_FOR_NEXT:
                raise ValueError(
                    f"{session_id} is {status.value} and cannot appear in next_session"
                )

        return self

    def task_map(self) -> dict[str, TodoTask]:
        return {task.id: task for task in self.tasks}

    def next_id(self) -> str:
        numbers = [int(task.id.split("-")[1]) for task in self.tasks]
        nxt = (max(numbers) + 1) if numbers else 1
        return f"RIG-{nxt:03d}"


class WishlistItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item: str = Field(min_length=1)
    category: str = Field(min_length=1)
    problem_capability: str = Field(min_length=1)
    priority: WishPriority | None = None
    status: WishStatus
    duplication: str = ""
    cost: str = ""
    friction: str = ""
    likely_music_impact: str = ""
    notes: str = ""
    details: str = ""
    todo_refs: list[RigId] = Field(default_factory=list)

    @field_validator("todo_refs")
    @classmethod
    def _unique_refs(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("todo_refs must not contain duplicates")
        return value


class WishlistDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[WishlistItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_items(self) -> WishlistDocument:
        names = [item.item.casefold() for item in self.items]
        if len(names) != len(set(names)):
            raise ValueError("wishlist item names must be unique (case-insensitive)")
        return self

    def find(self, name: str) -> WishlistItem | None:
        needle = name.casefold()
        for item in self.items:
            if item.item.casefold() == needle:
                return item
        return None

    def find_index(self, name: str) -> int | None:
        needle = name.casefold()
        for idx, item in enumerate(self.items):
            if item.item.casefold() == needle:
                return idx
        return None


class InboxItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: CapId
    created_at: datetime
    text: str = Field(min_length=1)
    status: InboxStatus = InboxStatus.OPEN
    category_hint: str | None = None
    source: str | None = None
    notes: str = ""


class InboxDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[InboxItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_ids(self) -> InboxDocument:
        ids = [item.id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("inbox CAP IDs must be unique")
        return self

    def item_map(self) -> dict[str, InboxItem]:
        return {item.id: item for item in self.items}

    def next_id(self) -> str:
        numbers = [int(item.id.split("-")[1]) for item in self.items]
        nxt = (max(numbers) + 1) if numbers else 1
        return f"CAP-{nxt:03d}"
