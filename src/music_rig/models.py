"""Pydantic models for canonical planning and inbox data."""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

RIG_ID_RE = re.compile(r"^RIG-\d{3}$")
CAP_ID_RE = re.compile(r"^CAP-\d{3}$")
CHG_ID_RE = re.compile(r"^CHG-\d{3}$")
SES_ID_RE = re.compile(r"^SES-\d{8}-\d{6}$")
Q_ID_RE = re.compile(r"^Q-\d{3}$")
RigId = Annotated[str, Field(pattern=r"^RIG-\d{3}$")]
CapId = Annotated[str, Field(pattern=r"^CAP-\d{3}$")]
ChgId = Annotated[str, Field(pattern=r"^CHG-\d{3}$")]
SesId = Annotated[str, Field(pattern=r"^SES-\d{8}-\d{6}$")]
QuestionId = Annotated[str, Field(pattern=r"^Q-\d{3}$")]

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


class SessionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"


class SessionEventType(str, Enum):
    NOTE = "NOTE"
    DISCOVERY = "DISCOVERY"
    TODO_STARTED = "TODO_STARTED"
    TODO_COMPLETED = "TODO_COMPLETED"
    CAPTURE = "CAPTURE"
    CHANGE = "CHANGE"


class SessionEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: datetime
    type: SessionEventType
    text: str = Field(min_length=1)
    todo_id: RigId | None = None
    capture_id: CapId | None = None
    change_id: ChgId | None = None


class SessionLog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: SesId
    started_at: datetime
    ended_at: datetime | None = None
    status: SessionStatus
    focus: str = ""
    events: list[SessionEvent] = Field(default_factory=list)

    @model_validator(mode="after")
    def _ended_rules(self) -> SessionLog:
        if self.status == SessionStatus.ACTIVE and self.ended_at is not None:
            raise ValueError("ACTIVE sessions must not have ended_at")
        if self.status != SessionStatus.ACTIVE and self.ended_at is None:
            raise ValueError("Completed/aborted sessions require ended_at")
        return self


class ChangeStatus(str, Enum):
    OPEN = "OPEN"
    APPLIED = "APPLIED"
    DISMISSED = "DISMISSED"


class ChangeCategory(str, Enum):
    AUDIO_ROUTING = "AUDIO_ROUTING"
    PEDAL_CHAIN = "PEDAL_CHAIN"
    PATCHBAY = "PATCHBAY"
    MIDI = "MIDI"
    ABLETON = "ABLETON"
    INVENTORY = "INVENTORY"
    CONTROLLERS = "CONTROLLERS"
    VIDEO = "VIDEO"
    OTHER = "OTHER"


class ChangeRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: ChgId
    created_at: datetime
    category: ChangeCategory
    summary: str = Field(min_length=1)
    details: str = ""
    status: ChangeStatus = ChangeStatus.OPEN
    session_id: SesId | None = None
    affected_areas: list[str] = Field(default_factory=list)
    related_questions: list[QuestionId] = Field(default_factory=list)

    @field_validator("related_questions")
    @classmethod
    def _unique_q_refs(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("related_questions must not contain duplicates")
        return value


class ChangesDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ChangeRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_ids(self) -> ChangesDocument:
        ids = [item.id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("change CHG IDs must be unique")
        return self

    def item_map(self) -> dict[str, ChangeRecord]:
        return {item.id: item for item in self.items}

    def next_id(self) -> str:
        numbers = [int(item.id.split("-")[1]) for item in self.items]
        nxt = (max(numbers) + 1) if numbers else 1
        return f"CHG-{nxt:03d}"


class QuestionStatus(str, Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    DEFERRED = "DEFERRED"


class QuestionTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: str  # patchbay.mode | patchbay.model | channel.source | routing.verify
    bay: str | None = None
    pair: str | None = None
    device: str | None = None
    channel: str | None = None
    path: str | None = None
    branch: str | None = None
    node: str | None = None


class OpenQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: QuestionId
    question: str = Field(min_length=1)
    area: str = Field(min_length=1)
    status: QuestionStatus = QuestionStatus.OPEN
    related_todos: list[RigId] = Field(default_factory=list)
    related_changes: list[ChgId] = Field(default_factory=list)
    answer: str = ""
    notes: str = ""
    resolved_at: datetime | None = None
    target: QuestionTarget | None = None

    @field_validator("related_todos", "related_changes")
    @classmethod
    def _unique_refs(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("reference lists must not contain duplicates")
        return value

    @model_validator(mode="after")
    def _status_rules(self) -> OpenQuestion:
        if self.status == QuestionStatus.RESOLVED:
            if not self.answer.strip():
                raise ValueError(f"{self.id} RESOLVED requires a non-empty answer")
            if self.resolved_at is None:
                raise ValueError(f"{self.id} RESOLVED requires resolved_at")
        if self.status == QuestionStatus.OPEN and self.resolved_at is not None:
            raise ValueError(f"{self.id} OPEN must not have resolved_at")
        return self


class PatchbayMode(str, Enum):
    NORMAL = "normal"
    HALF_NORMAL = "half-normal"
    THRU = "thru"
    UNKNOWN = "unknown"


class CurrentPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: str
    target: str
    before: dict
    after: dict
    changed: bool
    affected_files: list[str] = Field(default_factory=list)
    message: str = ""


class OpenQuestionsDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    questions: list[OpenQuestion] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_ids(self) -> OpenQuestionsDocument:
        ids = [q.id for q in self.questions]
        if len(ids) != len(set(ids)):
            raise ValueError("question Q IDs must be unique")
        return self

    def question_map(self) -> dict[str, OpenQuestion]:
        return {q.id: q for q in self.questions}

    def next_id(self) -> str:
        numbers = [int(q.id.split("-")[1]) for q in self.questions]
        nxt = (max(numbers) + 1) if numbers else 1
        return f"Q-{nxt:03d}"


class PathTreeNode(BaseModel):
    """Display tree derived from named_paths branches."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1)
    children: list[PathTreeNode] = Field(default_factory=list)


PathTreeNode.model_rebuild()


class RoutingNode(BaseModel):
    """A single node in a CURRENT routing branch sequence."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    mode: str | None = None
    note: str | None = None
    signal: str | None = None  # optional mono/stereo annotation; read-only in Stage 6


class RoutingBranch(BaseModel):
    """Ordered node sequence within a named path (main or attached)."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1)
    nodes: list[RoutingNode] = Field(default_factory=list)
    attach: str | None = None  # parent node id when not main
    position: str = "before"  # before|after continue along main/parent chain


class NamedPath(BaseModel):
    """Structured CURRENT named path (canonical under data/routing.yaml named_paths)."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1)
    status: str = "CURRENT"
    route_ref: str | None = None
    notes: str | None = None
    branches: dict[str, RoutingBranch] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _require_main(self) -> NamedPath:
        if "main" not in self.branches:
            raise ValueError("named path must include a 'main' branch")
        if self.branches["main"].attach is not None:
            raise ValueError("main branch must not set attach")
        return self


class RoutingDocument(BaseModel):
    """Partial read model: routes mapping + optional named_paths."""

    model_config = ConfigDict(extra="allow")

    routes: dict[str, dict] = Field(default_factory=dict)
    named_paths: dict[str, NamedPath] = Field(default_factory=dict)


class NowKind(str, Enum):
    ACTIVE_SESSION = "ACTIVE_SESSION"
    IN_PROGRESS = "IN_PROGRESS"
    NEXT_SESSION = "NEXT_SESSION"
    READY = "READY"
    PLAY = "PLAY"


class NowRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: NowKind
    primary_reference: str
    title: str
    reason: str
    suggested_commands: list[str] = Field(default_factory=list)
    definition_of_done: str = ""
    priority: str = ""
    skipped_summary: list[str] = Field(default_factory=list)
    recent_event: str = ""
    duration: str = ""
    focus: str = ""
