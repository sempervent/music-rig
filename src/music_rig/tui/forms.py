"""Record edit screen: FieldForm + Ctrl+S review/apply lifecycle."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, DataTable, Footer, Header, Label, Static

from music_rig.store import StoreError
from music_rig.tui.dialogs import ConfirmModal, DiscardModal, HelpScreen
from music_rig.tui.editable import BaseEditableAdapter, DiffRow, WorkingRecord
from music_rig.tui.editors import FieldForm
from music_rig.tui.fields import FieldSpec, FieldType
from music_rig.tui.pickers import OrderedListEditorModal, ReferencePickerModal, load_ref_choices
from music_rig.tui.working import ConcurrentModificationError


class ReviewChangesModal(ModalScreen[bool]):
    """Show before/after table; Enter/Apply confirms."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("enter", "confirm", "Apply", show=False, priority=True),
    ]

    def __init__(self, title: str, rows: list[DiffRow]) -> None:
        super().__init__()
        self._title = title
        self._rows = rows

    def compose(self) -> ComposeResult:
        with Vertical(id="modal"):
            yield Label(self._title, id="modal-title")
            table = DataTable(id="diff-table", cursor_type="row")
            yield table
            with Horizontal(id="modal-buttons"):
                yield Button("Apply", variant="primary", id="confirm")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        table = self.query_one("#diff-table", DataTable)
        table.add_columns("Field", "Before", "After")
        for row in self._rows:
            table.add_row(row.field, row.before[:40], row.after[:40])
        self.query_one("#confirm", Button).focus()

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)

    @on(Button.Pressed, "#confirm")
    def _ok(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#cancel")
    def _cancel(self) -> None:
        self.dismiss(False)


class ConflictModal(ModalScreen[str | None]):
    """Concurrency conflict: reload/discard, view diff, or cancel. No blind overwrite."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("1", "reload", show=False),
        Binding("2", "diff", show=False),
        Binding("3", "cancel", show=False),
    ]

    def __init__(self, message: str, diff_rows: list[DiffRow]) -> None:
        super().__init__()
        self._message = message
        self._diff_rows = diff_rows

    def compose(self) -> ComposeResult:
        with Vertical(id="modal"):
            yield Label("Concurrency conflict", id="modal-title")
            yield Static(
                self._message
                + "\n\nThis record changed on disk since editing began.\n"
                "Blind overwrite is not allowed.",
                id="modal-body",
            )
            with Vertical(id="mode-choices"):
                yield Button("1 Reload and discard mine", id="reload")
                yield Button("2 View my staged difference", id="diff")
                yield Button("3 Cancel", id="cancel")

    def action_reload(self) -> None:
        self.dismiss("reload")

    def action_diff(self) -> None:
        self.dismiss("diff")

    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#reload")
    def _reload(self) -> None:
        self.dismiss("reload")

    @on(Button.Pressed, "#diff")
    def _diff(self) -> None:
        self.dismiss("diff")

    @on(Button.Pressed, "#cancel")
    def _cancel(self) -> None:
        self.dismiss(None)


class RecordEditScreen(Screen[bool]):
    """Edit one record via FieldSpecs. Ctrl+S reviews then applies. Enter does NOT apply."""

    BINDINGS = [
        Binding("ctrl+s", "review_apply", "Review/Apply"),
        Binding("escape", "back", "Back"),
        Binding("q", "back", "Back"),
        Binding("question_mark", "help", "Help"),
    ]

    def __init__(self, adapter: BaseEditableAdapter, record_id: str) -> None:
        super().__init__()
        self.adapter = adapter
        self.record_id = record_id
        self._working: WorkingRecord | None = None
        self._form: FieldForm | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="screen-body"):
            yield Static(f"Edit {self.adapter.label} · {self.record_id}", id="screen-title")
            yield Static("", id="dirty-label")
            with VerticalScroll(id="field-form-scroll"):
                yield Static("Loading…", id="form-placeholder")
        yield Footer()

    def on_mount(self) -> None:
        try:
            self._working = self.adapter.create_working(self.record_id)
        except StoreError as exc:
            self.notify(str(exc), severity="error")
            self.dismiss(False)
            return
        self._mount_form()

    def _mount_form(self) -> None:
        assert self._working is not None
        scroll = self.query_one("#field-form-scroll", VerticalScroll)
        try:
            placeholder = self.query_one("#form-placeholder", Static)
            placeholder.remove()
        except Exception:
            pass
        for child in list(scroll.children):
            if isinstance(child, FieldForm) or (child.id and child.id == "field-form"):
                child.remove()

        def on_pick(spec: FieldSpec, current: list[str]) -> None:
            choices = load_ref_choices(spec.ref_domain or "")
            multi = spec.type == FieldType.REF_LIST

            def _done(ids: list[str] | None) -> None:
                if ids is None or self._form is None:
                    return
                self._form.set_field(spec.name, ids if multi else (ids[0] if ids else ""))
                self._sync_dirty()

            self.app.push_screen(
                ReferencePickerModal(
                    f"Pick {spec.label}",
                    choices,
                    selected=current if multi else ([current[0]] if current else []),
                    multi=multi,
                    max_items=spec.max_items,
                ),
                _done,
            )

        def on_edit_list(spec: FieldSpec, current: list[str]) -> None:
            choices = load_ref_choices(spec.ref_domain) if spec.ref_domain else None

            def _done(items: list[str] | None) -> None:
                if items is None or self._form is None:
                    return
                self._form.set_field(spec.name, items)
                self._sync_dirty()

            self.app.push_screen(
                OrderedListEditorModal(
                    f"Edit {spec.label}",
                    current,
                    max_items=spec.max_items,
                    choices=choices,
                ),
                _done,
            )

        form = FieldForm(
            self.adapter.get_field_specs(),
            self._working.merged(),
            on_pick_refs=on_pick,
            on_edit_list=on_edit_list,
        )
        self._form = form
        scroll.mount(form)
        self._sync_dirty()

    def _harvest_into_working(self) -> None:
        assert self._working is not None and self._form is not None
        for name, value in self._form.collect().items():
            self._working.stage(name, value)

    def _sync_dirty(self) -> None:
        if self._working is None or self._form is None:
            return
        self._harvest_into_working()
        label = self.query_one("#dirty-label", Static)
        if self._working.is_dirty:
            label.update(f"{len(self._working.mutations)} unsaved change(s) · Ctrl+S to review/apply")
        else:
            label.update("No unsaved changes · Esc to leave · Enter does not apply")

    def action_review_apply(self) -> None:
        if self._working is None or self._form is None:
            return
        self._harvest_into_working()
        if not self._working.is_dirty:
            self.notify("No changes to apply")
            return
        errors = self.adapter.validate_working(self._working)
        if errors:
            self.notify("; ".join(errors), severity="error")
            return
        rows = self.adapter.diff(self._working)

        def _after_review(ok: bool | None) -> None:
            if not ok:
                return
            self._do_apply()

        self.app.push_screen(
            ReviewChangesModal(f"Apply changes to {self.record_id}?", rows),
            _after_review,
        )

    def _do_apply(self) -> None:
        assert self._working is not None
        try:
            result = self.adapter.commit(self._working, render=True)
        except ConcurrentModificationError as exc:
            self._handle_conflict(str(exc))
            return
        except StoreError as exc:
            self.notify(str(exc), severity="error")
            return
        except Exception as exc:
            self.notify(f"Apply failed: {exc}", severity="error")
            return
        msg = result.message
        if result.hidden_by_filter and result.filter_hint:
            msg = f"{msg} {result.filter_hint}"
        self.notify(msg)
        self.dismiss(True)

    def _handle_conflict(self, message: str) -> None:
        assert self._working is not None
        rows = self.adapter.diff(self._working)

        def _done(choice: str | None) -> None:
            if choice == "reload":
                self._working = self.adapter.create_working(self.record_id)
                scroll = self.query_one("#field-form-scroll", VerticalScroll)
                for child in list(scroll.children):
                    child.remove()
                scroll.mount(Static("Loading…", id="form-placeholder"))
                self._mount_form()
                self.notify("Reloaded from disk; staged edits discarded")
            elif choice == "diff":
                self.app.push_screen(
                    ReviewChangesModal("Your staged difference (not applied)", rows),
                    lambda _ok: None,
                )

        self.app.push_screen(ConflictModal(message, rows), _done)

    def action_back(self) -> None:
        if self._working is None:
            self.dismiss(False)
            return
        if self._form is not None:
            self._harvest_into_working()
        if self._working.is_dirty:

            def _done(ok: bool | None) -> None:
                if ok:
                    self.dismiss(False)

            self.app.push_screen(DiscardModal(len(self._working.mutations)), _done)
            return
        self.dismiss(False)

    def action_help(self) -> None:
        self.app.push_screen(
            HelpScreen(
                "Record editor\n\n"
                "Ctrl+S  review changes then apply\n"
                "Esc/q   back (prompts if dirty)\n"
                "Enter   does NOT apply mutations\n\n"
                "Widgets never write YAML; Apply goes through the domain service."
            )
        )
