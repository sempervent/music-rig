"""Pydantic models for canonical planning and inbox data."""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
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


class TodoPriority(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class TodoStatus(StrEnum):
    READY = "READY"
    BLOCKED = "BLOCKED"
    IN_PROGRESS = "IN PROGRESS"
    WAITING = "WAITING"
    DONE = "DONE"
    DEFERRED = "DEFERRED"
    CANCELLED = "CANCELLED"


class WishPriority(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class WishStatus(StrEnum):
    IDEA = "IDEA"
    RESEARCH = "RESEARCH"
    BORROW_FIRST = "BORROW FIRST"
    BUY_LATER = "BUY LATER"
    BUY_NOW = "BUY NOW"
    ACQUIRED = "ACQUIRED"
    REDUNDANT = "REDUNDANT"
    REJECTED = "REJECTED"
    WAITING = "WAITING"
    DEFERRED = "DEFERRED"


class InboxStatus(StrEnum):
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
    inventory_ref: str | None = None

    @field_validator("todo_refs")
    @classmethod
    def _unique_refs(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("todo_refs must not contain duplicates")
        return value

    @model_validator(mode="after")
    def _acquired_requires_inventory(self) -> WishlistItem:
        if self.status == WishStatus.ACQUIRED and not (
            self.inventory_ref and self.inventory_ref.strip()
        ):
            raise ValueError(f"Wishlist item {self.item!r} ACQUIRED requires inventory_ref")
        return self


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


class SessionStatus(StrEnum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"


class SessionEventType(StrEnum):
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


class ChangeStatus(StrEnum):
    OPEN = "OPEN"
    APPLIED = "APPLIED"
    DISMISSED = "DISMISSED"


class ChangeCategory(StrEnum):
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


class QuestionStatus(StrEnum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    DEFERRED = "DEFERRED"


class ReconciliationState(StrEnum):
    NEEDS_ANSWER = "NEEDS_ANSWER"
    DRAFT_ANSWER = "DRAFT_ANSWER"
    READY_TO_APPLY = "READY_TO_APPLY"
    NEEDS_AGENT_ACTION = "NEEDS_AGENT_ACTION"
    CURRENT_MATCHES = "CURRENT_MATCHES"
    READY_TO_FINALIZE = "READY_TO_FINALIZE"
    RECONCILED = "RECONCILED"
    BLOCKED = "BLOCKED"


class AnswerState(StrEnum):
    """Derived (not persisted) answer lifecycle for OPEN/RESOLVED questions."""

    UNANSWERED = "UNANSWERED"
    DRAFT = "DRAFT"
    FINAL = "FINAL"


class QuestionTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: str  # patchbay.* | channel.* | routing.* | inventory.* | midi.* | controls.*
    bay: str | None = None
    pair: str | None = None
    device: str | None = None
    channel: str | None = None
    path: str | None = None
    branch: str | None = None
    node: str | None = None
    gear: str | None = None
    context: str | None = None


class QuestionVerification(BaseModel):
    """How a human should inspect and answer an OPEN question (guide only).

    Never invent answers from this metadata. Choices/schemas constrain input;
    the human supplies the observed fact (UNKNOWN is valid).
    """

    model_config = ConfigDict(extra="forbid")

    kind: str = Field(min_length=1)
    prompt: str = ""
    answer_type: str = Field(min_length=1)  # ENUM | BOOL | REF | TEXT
    choices: list[str] = Field(default_factory=list)
    ref_domain: str | None = None

    @model_validator(mode="after")
    def _answer_type_rules(self) -> QuestionVerification:
        at = self.answer_type.strip().upper()
        if at not in {"ENUM", "BOOL", "REF", "TEXT"}:
            raise ValueError(f"answer_type must be ENUM|BOOL|REF|TEXT, got {self.answer_type!r}")
        object.__setattr__(self, "answer_type", at)
        if at in {"ENUM", "BOOL"} and not self.choices:
            raise ValueError(f"{at} verification requires non-empty choices")
        if at == "REF" and not (self.ref_domain and self.ref_domain.strip()):
            raise ValueError("REF verification requires ref_domain")
        return self


class VerificationOutcome(StrEnum):
    """Explicit human observation outcome (distinct from Question answer)."""

    CONFIRMED = "CONFIRMED"
    CORRECTED = "CORRECTED"
    UNKNOWN = "UNKNOWN"
    FAILED_TEST = "FAILED_TEST"


class VerificationResult(BaseModel):
    """Durable record that a human performed the requested check.

    Observation ≠ answer. Complete YAML alone never implies VERIFIED evidence.
    Never invent verification_result from inference.
    """

    model_config = ConfigDict(extra="forbid")

    outcome: VerificationOutcome
    observed_at: datetime
    observed_value: str = ""
    note: str = ""
    source: str = "HUMAN"


class OwnershipStatus(StrEnum):
    OWNED = "OWNED"
    RETIRED = "RETIRED"
    SOLD = "SOLD"
    LOANED_OUT = "LOANED_OUT"
    UNKNOWN = "UNKNOWN"


class GearCondition(StrEnum):
    WORKING = "WORKING"
    ISSUE = "ISSUE"
    BROKEN = "BROKEN"
    UNKNOWN = "UNKNOWN"


INACTIVE_OWNERSHIP = frozenset(
    {
        OwnershipStatus.RETIRED,
        OwnershipStatus.SOLD,
        OwnershipStatus.LOANED_OUT,
    }
)


class InventoryUnit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    notes: str = ""


class InventoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    manufacturer: str | None = None
    model: str | None = None
    category: str = Field(min_length=1)
    quantity: int = Field(default=1, ge=1)
    ownership_status: OwnershipStatus = OwnershipStatus.OWNED
    condition: GearCondition = GearCondition.UNKNOWN
    location: str | None = None
    notes: str = ""
    units: list[InventoryUnit] = Field(default_factory=list)

    @model_validator(mode="after")
    def _units_match_quantity(self) -> InventoryItem:
        if self.units and len(self.units) != self.quantity:
            raise ValueError(
                f"{self.id}: units length ({len(self.units)}) must equal quantity ({self.quantity})"
            )
        return self


class InventoryDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[InventoryItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_ids(self) -> InventoryDocument:
        ids = [i.id for i in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("inventory item IDs must be unique")
        unit_ids: list[str] = []
        for item in self.items:
            for unit in item.units:
                unit_ids.append(unit.id)
                if unit.id in ids:
                    raise ValueError(f"unit id {unit.id!r} collides with inventory item id")
        if len(unit_ids) != len(set(unit_ids)):
            raise ValueError("inventory unit IDs must be unique")
        return self

    def item_map(self) -> dict[str, InventoryItem]:
        return {i.id: i for i in self.items}

    def resolve(self, gear_id: str) -> InventoryItem | None:
        """Resolve item id or unit id to parent InventoryItem."""
        key = gear_id.strip().lower()
        for item in self.items:
            if item.id.lower() == key:
                return item
            for unit in item.units:
                if unit.id.lower() == key:
                    return item
        return None


class AnswerActor(StrEnum):
    """Provenance of a Question's answer text."""

    HUMAN = "HUMAN"
    BOT = "BOT"
    LEGACY_UNKNOWN = "LEGACY_UNKNOWN"


class OpenQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: QuestionId
    question: str = Field(min_length=1)
    area: str = Field(min_length=1)
    status: QuestionStatus = QuestionStatus.OPEN
    related_todos: list[RigId] = Field(default_factory=list)
    related_changes: list[ChgId] = Field(default_factory=list)
    answer: str = ""
    # Provenance of answer text. None + non-empty answer ⇒ treat as LEGACY_UNKNOWN.
    answer_actor: AnswerActor | None = None
    notes: str = ""
    resolved_at: datetime | None = None
    reconciled_at: datetime | None = None
    reconciliation_note: str = ""
    target: QuestionTarget | None = None
    verification: QuestionVerification | None = None
    verification_note: str = ""
    verification_result: VerificationResult | None = None
    # Linked clarification Question created by an agent when answer is insufficient.
    clarifies_question: QuestionId | None = None

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
        if self.status == QuestionStatus.OPEN and self.reconciled_at is not None:
            raise ValueError(f"{self.id} OPEN must not have reconciled_at")
        if self.reconciled_at is not None:
            if self.status != QuestionStatus.RESOLVED:
                raise ValueError(f"{self.id} reconciled_at requires status RESOLVED")
            if not self.answer.strip():
                raise ValueError(f"{self.id} reconciled_at requires a non-empty answer")
        if not self.answer.strip() and self.answer_actor is not None:
            raise ValueError(f"{self.id} answer_actor requires non-empty answer")
        if self.clarifies_question is not None:
            parent = self.clarifies_question.strip().upper()
            if parent == self.id:
                raise ValueError(f"{self.id} cannot clarify itself")
            object.__setattr__(self, "clarifies_question", parent)
        return self


class PatchbayMode(StrEnum):
    NORMAL = "normal"
    HALF_NORMAL = "half-normal"
    THRU = "thru"
    UNKNOWN = "unknown"


class MidiEvidenceStatus(StrEnum):
    VERIFIED = "VERIFIED"
    INTENDED = "INTENDED"
    UNKNOWN = "UNKNOWN"


class ControlCoverage(StrEnum):
    PARTIAL = "PARTIAL"
    COMPLETE = "COMPLETE"
    UNKNOWN = "UNKNOWN"


class ContextKind(StrEnum):
    BANK = "BANK"
    TEMPLATE = "TEMPLATE"
    MODE = "MODE"
    GLOBAL = "GLOBAL"


class PhysicalControlType(StrEnum):
    BUTTON = "BUTTON"
    SWITCH = "SWITCH"
    FOOTSWITCH = "FOOTSWITCH"
    KNOB = "KNOB"
    ENCODER = "ENCODER"
    FADER = "FADER"
    PAD = "PAD"
    EXPRESSION = "EXPRESSION"
    OTHER = "OTHER"


class ControlAvailability(StrEnum):
    AVAILABLE = "AVAILABLE"
    BROKEN = "BROKEN"
    UNKNOWN = "UNKNOWN"


class MidiMessageType(StrEnum):
    CC = "CC"
    NOTE = "NOTE"
    PROGRAM_CHANGE = "PROGRAM_CHANGE"


class ValueBehavior(StrEnum):
    FIXED = "fixed"
    TOGGLE = "toggle"
    RANGE = "range"
    MOMENTARY = "momentary"


class TargetState(StrEnum):
    MAPPED = "MAPPED"
    UNASSIGNED = "UNASSIGNED"
    UNKNOWN = "UNKNOWN"


class TargetKind(StrEnum):
    ABLETON_TRACK = "ABLETON_TRACK"
    ABLETON_SEND = "ABLETON_SEND"
    ABLETON_ACTION = "ABLETON_ACTION"
    PERFORMANCE_ACTION = "PERFORMANCE_ACTION"
    EXTERNAL_MIDI = "EXTERNAL_MIDI"
    OTHER = "OTHER"


class MidiMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: MidiMessageType
    number: int = Field(ge=0, le=127)
    channel: int | str | None = None
    value_behavior: ValueBehavior

    @field_validator("channel")
    @classmethod
    def _valid_controller_channel(cls, value: int | str | None) -> int | str | None:
        if value is None:
            return None
        if isinstance(value, int):
            if 1 <= value <= 16:
                return value
            raise ValueError("controller MIDI channel must be 1-16, DEVICE, or null")
        if value.strip().upper() != "DEVICE":
            raise ValueError("controller MIDI channel must be 1-16, DEVICE, or null")
        return "DEVICE"


class ControlTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: TargetState
    kind: TargetKind | None = None
    track: str | None = None
    send: str | None = None
    action: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _mapped_target_has_kind(self) -> ControlTarget:
        if self.state == TargetState.MAPPED and self.kind is None:
            raise ValueError("MAPPED control target requires kind")
        if self.state != TargetState.MAPPED and any(
            (self.kind, self.track, self.send, self.action)
        ):
            raise ValueError("UNASSIGNED/UNKNOWN target cannot contain mapping fields")
        required = {
            TargetKind.ABLETON_TRACK: self.track,
            TargetKind.ABLETON_SEND: self.send,
            TargetKind.ABLETON_ACTION: self.action,
            TargetKind.PERFORMANCE_ACTION: self.action,
        }
        if self.kind in required and not required[self.kind]:
            raise ValueError(f"{self.kind.value} target requires its reference field")
        return self


class ControlMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    physical_type: PhysicalControlType
    availability: ControlAvailability
    evidence: MidiEvidenceStatus
    messages: list[MidiMessage] = Field(default_factory=list)
    target: ControlTarget
    notes: str = ""

    @model_validator(mode="after")
    def _broken_is_unassigned(self) -> ControlMapping:
        if (
            self.availability == ControlAvailability.BROKEN
            and self.target.state != TargetState.UNASSIGNED
        ):
            raise ValueError(f"{self.id}: BROKEN controls must be UNASSIGNED")
        return self


class ControllerContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    kind: ContextKind
    evidence: MidiEvidenceStatus
    notes: str = ""
    controls: list[ControlMapping] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_controls(self) -> ControllerContext:
        ids = [control.id.casefold() for control in self.controls]
        if len(ids) != len(set(ids)):
            raise ValueError(f"{self.id}: control IDs must be unique")
        return self


class ControllerRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gear_ref: str = Field(min_length=1)
    coverage: ControlCoverage
    related_todos: list[RigId] = Field(default_factory=list)
    notes: str = ""
    contexts: list[ControllerContext] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_contexts(self) -> ControllerRecord:
        ids = [context.id.casefold() for context in self.contexts]
        if len(ids) != len(set(ids)):
            raise ValueError(f"{self.gear_ref}: context IDs must be unique")
        return self


class ControllersDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    controllers: list[ControllerRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_controllers(self) -> ControllersDocument:
        refs = [controller.gear_ref.casefold() for controller in self.controllers]
        if len(refs) != len(set(refs)):
            raise ValueError("controller gear_refs must be unique")
        return self


class AbletonTrack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    evidence: MidiEvidenceStatus
    notes: str = ""


class AbletonSend(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    evidence: MidiEvidenceStatus
    notes: str = ""


class AbletonAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    evidence: MidiEvidenceStatus
    notes: str = ""


class AbletonTemplateTrack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    track_ref: str = Field(min_length=1)
    role: str = Field(min_length=1)
    active: bool
    record_ready: bool | str

    @field_validator("record_ready")
    @classmethod
    def _record_ready_state(cls, value: bool | str) -> bool | str:
        if isinstance(value, bool):
            return value
        if value.strip().lower() != "unknown":
            raise ValueError("record_ready must be true, false, or unknown")
        return "unknown"


class AbletonTemplateSend(BaseModel):
    model_config = ConfigDict(extra="forbid")

    send_ref: str = Field(min_length=1)
    role: str = Field(min_length=1)
    notes: str = ""


class AbletonTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    evidence: MidiEvidenceStatus
    related_todos: list[RigId] = Field(default_factory=list)
    notes: str = ""
    tracks: list[AbletonTemplateTrack] = Field(default_factory=list)
    sends: list[AbletonTemplateSend] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)


class AbletonDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tracks: list[AbletonTrack] = Field(default_factory=list)
    sends: list[AbletonSend] = Field(default_factory=list)
    actions: list[AbletonAction] = Field(default_factory=list)
    templates: list[AbletonTemplate] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_target_ids(self) -> AbletonDocument:
        for label, values in (
            ("Ableton track", [item.id.casefold() for item in self.tracks]),
            ("Ableton send", [item.id.casefold() for item in self.sends]),
            ("Ableton action", [item.id.casefold() for item in self.actions]),
            ("Ableton template", [item.id.casefold() for item in self.templates]),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{label} IDs must be unique")
        tracks = {item.id for item in self.tracks}
        sends = {item.id for item in self.sends}
        for template in self.templates:
            track_refs = [item.track_ref for item in template.tracks]
            send_refs = [item.send_ref for item in template.sends]
            if len(track_refs) != len(set(track_refs)):
                raise ValueError(f"{template.id}: template track_refs must be unique")
            if len(send_refs) != len(set(send_refs)):
                raise ValueError(f"{template.id}: template send_refs must be unique")
            for ref in track_refs:
                if ref not in tracks:
                    raise ValueError(f"{template.id}: unknown Ableton track {ref!r}")
            for ref in send_refs:
                if ref not in sends:
                    raise ValueError(f"{template.id}: unknown Ableton send {ref!r}")
        return self


class PerformanceCriticality(StrEnum):
    NORMAL = "NORMAL"
    IMPORTANT = "IMPORTANT"
    EMERGENCY = "EMERGENCY"


class PerformanceActionCategory(StrEnum):
    RECOVERY = "RECOVERY"
    RECORDING = "RECORDING"
    LOOPING = "LOOPING"
    MIDI = "MIDI"
    SCENE = "SCENE"
    AUDIO = "AUDIO"


class PerformanceEffectKind(StrEnum):
    ABLETON_ACTION = "ABLETON_ACTION"
    OBS_ACTION = "OBS_ACTION"
    MIDI_ACTION = "MIDI_ACTION"
    HARDWARE_PROCEDURE = "HARDWARE_PROCEDURE"
    MANUAL_STEP = "MANUAL_STEP"


class PerformanceEffect(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: PerformanceEffectKind
    effect_id: str | None = None
    action_ref: str | None = None
    evidence: MidiEvidenceStatus
    notes: str = ""

    @model_validator(mode="after")
    def _effect_reference(self) -> PerformanceEffect:
        if self.kind == PerformanceEffectKind.ABLETON_ACTION:
            if not self.action_ref or self.effect_id:
                raise ValueError("ABLETON_ACTION requires action_ref only")
        elif not self.effect_id or self.action_ref:
            raise ValueError(f"{self.kind.value} requires effect_id only")
        return self


class PerformanceAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    category: PerformanceActionCategory
    criticality: PerformanceCriticality
    evidence: MidiEvidenceStatus
    effects: list[PerformanceEffect] = Field(default_factory=list)
    related_todos: list[RigId] = Field(default_factory=list)
    notes: str = ""


class PerformanceMode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    evidence: MidiEvidenceStatus
    required_actions: list[str] = Field(default_factory=list)
    optional_actions: list[str] = Field(default_factory=list)
    related_todos: list[RigId] = Field(default_factory=list)
    notes: str = ""


class PerformanceBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    action_ref: str = Field(min_length=1)
    controller_ref: str | None = None
    surface_ref: str | None = None
    context_ref: str = Field(min_length=1)
    control_ref: str = Field(min_length=1)
    evidence: MidiEvidenceStatus
    notes: str = ""

    @model_validator(mode="after")
    def _one_source(self) -> PerformanceBinding:
        if bool(self.controller_ref) == bool(self.surface_ref):
            raise ValueError("binding requires exactly one controller_ref or surface_ref")
        return self


class RecoveryScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    severity: PerformanceCriticality
    symptom: str = Field(min_length=1)
    action_refs: list[str] = Field(default_factory=list)
    manual_steps: list[str] = Field(default_factory=list)
    keyboard_mouse_required: bool | str
    evidence: MidiEvidenceStatus
    related_todos: list[RigId] = Field(default_factory=list)

    @field_validator("keyboard_mouse_required")
    @classmethod
    def _keyboard_state(cls, value: bool | str) -> bool | str:
        if isinstance(value, bool):
            return value
        if value.strip().lower() != "unknown":
            raise ValueError("keyboard_mouse_required must be true, false, or unknown")
        return "unknown"


class PerformanceRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    evidence: MidiEvidenceStatus
    related_todos: list[RigId] = Field(default_factory=list)


class PerformanceDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    modes: list[PerformanceMode] = Field(default_factory=list)
    actions: list[PerformanceAction] = Field(default_factory=list)
    bindings: list[PerformanceBinding] = Field(default_factory=list)
    recovery: list[RecoveryScenario] = Field(default_factory=list)
    requirements: list[PerformanceRequirement] = Field(default_factory=list)

    @model_validator(mode="after")
    def _references_and_unique_ids(self) -> PerformanceDocument:
        groups = {
            "mode": [item.id for item in self.modes],
            "action": [item.id for item in self.actions],
            "binding": [item.id for item in self.bindings],
            "recovery": [item.id for item in self.recovery],
            "requirement": [item.id for item in self.requirements],
        }
        for label, values in groups.items():
            if len(values) != len(set(values)):
                raise ValueError(f"Performance {label} IDs must be unique")
        actions = set(groups["action"])
        for mode in self.modes:
            refs = [*mode.required_actions, *mode.optional_actions]
            if len(refs) != len(set(refs)):
                raise ValueError(f"{mode.id}: action references must be unique")
            for ref in refs:
                if ref not in actions:
                    raise ValueError(f"{mode.id}: unknown performance action {ref!r}")
        for binding in self.bindings:
            if binding.action_ref not in actions:
                raise ValueError(f"{binding.id}: unknown performance action {binding.action_ref!r}")
        for scenario in self.recovery:
            for ref in scenario.action_refs:
                if ref not in actions:
                    raise ValueError(f"{scenario.id}: unknown performance action {ref!r}")
        return self


class SurfaceControl(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    availability: ControlAvailability
    evidence: MidiEvidenceStatus
    notes: str = ""


class SurfaceContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    evidence: MidiEvidenceStatus
    notes: str = ""
    controls: list[SurfaceControl] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_controls(self) -> SurfaceContext:
        ids = [item.id.casefold() for item in self.controls]
        if len(ids) != len(set(ids)):
            raise ValueError(f"{self.id}: surface control IDs must be unique")
        return self


class ControlSurface(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gear_ref: str = Field(min_length=1)
    coverage: ControlCoverage
    related_todos: list[RigId] = Field(default_factory=list)
    notes: str = ""
    contexts: list[SurfaceContext] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_contexts(self) -> ControlSurface:
        ids = [item.id.casefold() for item in self.contexts]
        if len(ids) != len(set(ids)):
            raise ValueError(f"{self.gear_ref}: surface context IDs must be unique")
        return self


class ControlSurfacesDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    surfaces: list[ControlSurface] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_surfaces(self) -> ControlSurfacesDocument:
        refs = [item.gear_ref.casefold() for item in self.surfaces]
        if len(refs) != len(set(refs)):
            raise ValueError("surface gear_refs must be unique")
        return self


class ReadinessResult(StrEnum):
    READY = "READY"
    PARTIAL = "PARTIAL"
    NOT_READY = "NOT_READY"


class BackupCategory(StrEnum):
    ABLETON = "Ableton"
    CONTROLLERS = "Controllers"
    OBS = "OBS"
    STREAM_DECK = "Stream Deck"
    KAOSS_REPLAY = "KAOSS Replay"
    REPOSITORY = "Repository"
    SAMPLES = "Samples"
    PROJECTS = "Projects"


class BackupKind(StrEnum):
    REPOSITORY_STATE = "REPOSITORY_STATE"
    FILE_COPY = "FILE_COPY"
    DIRECTORY_COPY = "DIRECTORY_COPY"
    MANUAL_EXPORT = "MANUAL_EXPORT"
    UNKNOWN = "UNKNOWN"


class BackupImportance(StrEnum):
    CRITICAL = "CRITICAL"
    IMPORTANT = "IMPORTANT"
    OPTIONAL = "OPTIONAL"


BACKUP_LOCATOR_KEYS = frozenset(
    {
        "repository-state",
        "backup_root",
        "pfl_jam_ableton_set",
        "obs_export",
        "stream_deck_export",
        "kaoss_backup",
        "controller_mappings_export",
    }
)
LOCAL_PATH_KEYS = frozenset(
    {
        "backup_root",
        "pfl_jam_ableton_set",
        "obs_export",
        "stream_deck_export",
        "kaoss_backup",
        "controller_mappings_export",
    }
)


class BackupItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    category: BackupCategory
    kind: BackupKind
    importance: BackupImportance
    evidence: MidiEvidenceStatus
    locator_key: str | None = None
    manual_instructions: str = ""
    related_todos: list[RigId] = Field(default_factory=list)
    notes: str = ""

    @field_validator("locator_key")
    @classmethod
    def _known_locator(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value not in BACKUP_LOCATOR_KEYS:
            raise ValueError(f"unknown backup locator_key {value!r}")
        return value


class BackupsDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[BackupItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_ids(self) -> BackupsDocument:
        ids = [item.id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("backup item IDs must be unique")
        return self

    def item_map(self) -> dict[str, BackupItem]:
        return {item.id: item for item in self.items}


class LocalPathsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    backup_root: str | None = None
    pfl_jam_ableton_set: str | None = None
    obs_export: str | None = None
    stream_deck_export: str | None = None
    kaoss_backup: str | None = None
    controller_mappings_export: str | None = None


class CursorProviderLocalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executable: str | None = None
    model: str | None = None


class OllamaProviderLocalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_url: str = "http://127.0.0.1:11434"
    model: str | None = None
    # When False/True, sent as Ollama `think` if the model accepts it.
    # None omits the parameter (provider default).
    think: bool | None = False


class AgentLocalConfig(BaseModel):
    """Machine-local agent provider settings (never committed secrets)."""

    model_config = ConfigDict(extra="forbid")

    provider: str | None = None  # cursor | ollama | command
    fallback: str | None = None  # optional: ollama | cursor | command
    argv: list[str] = Field(default_factory=list)  # command provider only
    timeout_seconds: int = Field(default=120, ge=1, le=600)
    env_forward: list[str] = Field(default_factory=list)
    max_context_rounds: int = Field(default=5, ge=1, le=10)
    max_stdout_bytes: int = Field(default=1_000_000, ge=1024, le=5_000_000)
    cursor: CursorProviderLocalConfig = Field(default_factory=CursorProviderLocalConfig)
    ollama: OllamaProviderLocalConfig = Field(default_factory=OllamaProviderLocalConfig)


class LocalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paths: LocalPathsConfig = Field(default_factory=LocalPathsConfig)
    agent: AgentLocalConfig = Field(default_factory=AgentLocalConfig)


class MidiTransport(StrEnum):
    DIN = "DIN"
    USB = "USB"
    VIRTUAL = "VIRTUAL"


class MidiTriState(StrEnum):
    ON = "on"
    OFF = "off"
    UNKNOWN = "unknown"


class MidiEndpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    kind: str = Field(pattern=r"^(software|host)$")
    name: str = Field(min_length=1)


class MidiDevice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gear_ref: str = Field(min_length=1)
    role: str = Field(min_length=1)
    notes: str = ""


class MidiConnection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^midi-link-\d{3}$")
    source: str = Field(min_length=1)
    source_port: str = Field(min_length=1)
    destination: str = Field(min_length=1)
    destination_port: str = Field(min_length=1)
    transport: MidiTransport
    status: MidiEvidenceStatus
    notes: str = ""


class MidiChannelAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gear_ref: str = Field(min_length=1)
    channel: int | str
    status: MidiEvidenceStatus
    notes: str = ""

    @field_validator("channel")
    @classmethod
    def _valid_channel(cls, value: int | str) -> int | str:
        if isinstance(value, int):
            if 1 <= value <= 16:
                return value
            raise ValueError("MIDI channel must be 1-16, OMNI, or UNKNOWN")
        normalized = value.strip().upper()
        if normalized not in {"OMNI", "UNKNOWN"}:
            raise ValueError("MIDI channel must be 1-16, OMNI, or UNKNOWN")
        return normalized


class MidiClockMaster(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint_ref: str | None = None
    gear_ref: str | None = None
    status: MidiEvidenceStatus
    notes: str = ""

    @model_validator(mode="after")
    def _one_reference(self) -> MidiClockMaster:
        if bool(self.endpoint_ref) == bool(self.gear_ref):
            raise ValueError("clock master requires exactly one endpoint_ref or gear_ref")
        return self


class MidiClockDestination(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint_ref: str | None = None
    gear_ref: str | None = None
    enabled: MidiTriState
    status: MidiEvidenceStatus
    notes: str = ""

    @model_validator(mode="after")
    def _one_reference(self) -> MidiClockDestination:
        if bool(self.endpoint_ref) == bool(self.gear_ref):
            raise ValueError("clock destination requires exactly one endpoint_ref or gear_ref")
        return self


class MidiClockTransportState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: MidiEvidenceStatus
    notes: str = ""


class MidiClock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    master: MidiClockMaster | None = None
    destinations: list[MidiClockDestination] = Field(default_factory=list)
    transport: MidiClockTransportState


class MidiAbletonPort(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    direction: str = Field(pattern=r"^(input|output)$")
    endpoint_ref: str | None = None
    gear_ref: str | None = None
    port_name: str | None = None
    track: MidiTriState
    sync: MidiTriState
    remote: MidiTriState
    status: MidiEvidenceStatus
    notes: str = ""

    @model_validator(mode="after")
    def _one_reference(self) -> MidiAbletonPort:
        refs = (self.endpoint_ref, self.gear_ref, self.port_name)
        if sum(bool(ref) for ref in refs) != 1:
            raise ValueError(
                "Ableton port requires exactly one endpoint_ref, gear_ref, or port_name"
            )
        return self


class MidiRoute(BaseModel):
    """A programmable MIDI route; fields remain minimal until routes are verified."""

    model_config = ConfigDict(extra="allow")

    id: str | None = None
    source: str | None = None
    destination: str | None = None
    status: MidiEvidenceStatus = MidiEvidenceStatus.UNKNOWN
    notes: str = ""


class MidiDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoints: list[MidiEndpoint] = Field(default_factory=list)
    devices: list[MidiDevice] = Field(default_factory=list)
    connections: list[MidiConnection] = Field(default_factory=list)
    channels: list[MidiChannelAssignment] = Field(default_factory=list)
    clock: MidiClock
    ableton_ports: list[MidiAbletonPort] = Field(default_factory=list)
    routes: list[MidiRoute] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_ids_and_refs(self) -> MidiDocument:
        for label, values in (
            ("MIDI endpoint IDs", [item.id for item in self.endpoints]),
            ("MIDI connection IDs", [item.id for item in self.connections]),
            ("MIDI device gear_refs", [item.gear_ref for item in self.devices]),
            ("MIDI channel gear_refs", [item.gear_ref for item in self.channels]),
            ("Ableton port IDs", [item.id for item in self.ableton_ports]),
            ("MIDI route IDs", [item.id for item in self.routes if item.id]),
        ):
            folded = [value.casefold() for value in values]
            if len(folded) != len(set(folded)):
                raise ValueError(f"{label} must be unique")
        return self


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
    gear_ref: str | None = None  # explicit inventory item/unit id
    kind: str | None = None  # device | endpoint | utility


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
    # Optional human-verification evidence (path.status remains lifecycle CURRENT/…)
    evidence: MidiEvidenceStatus | None = None
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


class NowKind(StrEnum):
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
