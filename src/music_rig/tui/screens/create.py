"""Structured Add flows for planning/CURRENT domains via shared services.

A = Add on list screens. Shows proposed ID, blank form → review → Apply → select new row.
Does NOT add patchbay pairs.
"""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from music_rig import (
    change_service,
    current_service,
    inbox_service,
    inventory_state,
    question_service,
    todo_service,
    wishlist_service,
)
from music_rig.models import (
    ChangeCategory,
    TodoPriority,
    TodoStatus,
    TodoTask,
    WishPriority,
    WishStatus,
    WishlistItem,
)
from music_rig.store import StoreError, load_questions, load_todo
from music_rig.tui.debug import format_error
from music_rig.tui.screen_results import SingleShotMixin


class AddRecordModal(SingleShotMixin, ModalScreen[str | None]):
    """Generic multi-field add modal. Returns new record id or None."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("ctrl+s", "submit", "Create", show=False, priority=True),
    ]

    def __init__(
        self,
        title: str,
        *,
        proposed_id: str,
        fields: list[tuple[str, str, str]],  # (id, label, default)
        enum_fields: list[tuple[str, str, list[str], str]] | None = None,
        # (id, label, choices, default)
    ) -> None:
        super().__init__()
        self._title = title
        self._proposed_id = proposed_id
        self._fields = fields
        self._enum_fields = enum_fields or []

    def compose(self) -> ComposeResult:
        with Vertical(id="modal"):
            yield Label(self._title, id="modal-title")
            yield Static(f"Proposed ID: {self._proposed_id}", id="modal-body")
            for fid, label, default in self._fields:
                yield Label(label)
                yield Input(value=default, id=f"add-{fid}", placeholder=label)
            for fid, label, choices, default in self._enum_fields:
                yield Label(label)
                yield Select(
                    [(c, c) for c in choices],
                    value=default if default in choices else Select.BLANK,
                    id=f"add-{fid}",
                    allow_blank=False,
                )
            with Horizontal(id="modal-buttons"):
                yield Button("Create", variant="primary", id="confirm", action="screen.submit")
                yield Button("Cancel", id="cancel", action="screen.cancel")

    def on_mount(self) -> None:
        first = self.query(Input)
        if first:
            list(first)[0].focus()

    def action_cancel(self) -> None:
        self.complete(None)

    def _values(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for fid, _label, _default in self._fields:
            out[fid] = self.query_one(f"#add-{fid}", Input).value.strip()
        for fid, _label, _choices, _default in self._enum_fields:
            val = self.query_one(f"#add-{fid}", Select).value
            out[fid] = "" if val is Select.BLANK else str(val)
        return out

    def action_submit(self) -> None:
        self._finish()

    @on(Input.Submitted)
    def _input_submit(self) -> None:
        self._finish()

    def _finish(self) -> None:
        # Subclasses override create(); base dismisses with None
        try:
            new_id = self.create(self._values())
        except StoreError as exc:
            self.notify(format_error(exc), severity="error")
            return
        except Exception as exc:
            self.notify(format_error(exc, prefix="FAILED: "), severity="error")
            return
        self.complete(new_id)

    def create(self, values: dict[str, str]) -> str:
        raise NotImplementedError


class AddQuestionModal(AddRecordModal):
    def __init__(self) -> None:
        proposed = load_questions().next_id()
        super().__init__(
            "Add Question",
            proposed_id=proposed,
            fields=[
                ("question", "Question text", ""),
                ("area", "Area", "Docs"),
            ],
        )

    def create(self, values: dict[str, str]) -> str:
        item = question_service.add_question(
            values["question"], area=values["area"], render=True
        )
        return item.id


class AddTodoModal(AddRecordModal):
    def __init__(self) -> None:
        proposed = load_todo().next_id()
        super().__init__(
            "Add TODO",
            proposed_id=proposed,
            fields=[
                ("task", "Task", ""),
                ("area", "Area", "Docs"),
                ("definition_of_done", "Definition of done", "Done when…"),
            ],
            enum_fields=[
                ("priority", "Priority", [p.value for p in TodoPriority], "P2"),
            ],
        )

    def create(self, values: dict[str, str]) -> str:
        doc = load_todo()
        task = TodoTask(
            id=doc.next_id(),
            task=values["task"],
            area=values["area"],
            priority=TodoPriority(values["priority"]),
            status=TodoStatus.READY,
            definition_of_done=values["definition_of_done"],
        )
        todo_service.add_todo(task, render=True)
        return task.id


class AddWishModal(AddRecordModal):
    def __init__(self) -> None:
        super().__init__(
            "Add Wishlist item",
            proposed_id="(name is ID)",
            fields=[
                ("item", "Item name (ID)", ""),
                ("category", "Category", "gear"),
                ("problem_capability", "Problem / capability", ""),
            ],
            enum_fields=[
                ("priority", "Priority", [p.value for p in WishPriority], "P2"),
            ],
        )

    def create(self, values: dict[str, str]) -> str:
        item = WishlistItem(
            item=values["item"],
            category=values["category"],
            problem_capability=values["problem_capability"],
            priority=WishPriority(values["priority"]),
            status=WishStatus.IDEA,
        )
        wishlist_service.add_wish(item, render=True)
        return item.item


class AddInboxModal(AddRecordModal):
    def __init__(self) -> None:
        from music_rig.store import load_inbox

        proposed = load_inbox().next_id()
        super().__init__(
            "Add Inbox capture",
            proposed_id=proposed,
            fields=[("text", "Capture text", "")],
        )

    def create(self, values: dict[str, str]) -> str:
        item = inbox_service.capture_text(values["text"], render=False)
        return item.id


class AddChangeModal(AddRecordModal):
    def __init__(self) -> None:
        from music_rig.store import load_changes

        proposed = load_changes().next_id()
        cats = [c.value for c in ChangeCategory]
        super().__init__(
            "Add Change",
            proposed_id=proposed,
            fields=[
                ("summary", "Summary", ""),
                ("details", "Details", ""),
            ],
            enum_fields=[
                ("category", "Category", cats, cats[0] if cats else "OTHER"),
            ],
        )

    def create(self, values: dict[str, str]) -> str:
        record = change_service.create_change(
            values["summary"],
            category=ChangeCategory(values["category"]),
            details=values.get("details") or "",
            link_session=False,
        )
        return record.id


class AddGearModal(AddRecordModal):
    def __init__(self) -> None:
        super().__init__(
            "Add Gear",
            proposed_id="(auto from name)",
            fields=[
                ("name", "Name", ""),
                ("category", "Category", "utility"),
                ("notes", "Notes", ""),
            ],
        )

    def create(self, values: dict[str, str]) -> str:
        preview, data = inventory_state.propose_add(
            name=values["name"],
            category=values["category"],
            notes=values.get("notes") or "",
        )
        current_service.commit_inventory(data, preview, render=True)
        return str(preview.target)
