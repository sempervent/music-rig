"""Record edit screen: FieldForm + Ctrl+S review/apply lifecycle + Vim modes."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, DataTable, Footer, Label, Static

from music_rig.store import StoreError
from music_rig.tui.debug import debug_log, format_error, is_debug
from music_rig.tui.dialogs import CommandLineModal, ConfirmModal, DiscardModal, HelpScreen
from music_rig.tui.editable import BaseEditableAdapter, DiffRow, WorkingRecord
from music_rig.tui.editors import FieldForm
from music_rig.tui.fields import FieldSpec, FieldType
from music_rig.tui.modes import VIM_HELP_COMMON, EditorMode, ModeController, parse_command
from music_rig.tui.pickers import OrderedListEditorModal, ReferencePickerModal, load_ref_choices
from music_rig.tui.save_outcome import SaveOutcome
from music_rig.tui.working import ConcurrentModificationError
from music_rig.tui.header import RigHeader


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
    """Concurrency conflict: reload/discard, view diff, or cancel. Retains edits on cancel/diff."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("1", "reload", show=False),
        Binding("2", "diff", show=False),
        Binding("3", "cancel", show=False),
        Binding("enter", "cancel", show=False, priority=True),
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
                "Blind overwrite is not allowed. Your staged edits are kept until you Reload.",
                id="modal-body",
            )
            with Vertical(id="mode-choices"):
                yield Button("1 Reload and discard mine", id="reload")
                yield Button("2 View my staged difference", id="diff")
                yield Button("3 Cancel (keep edits)", variant="primary", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#cancel", Button).focus()

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
        Binding("ctrl+s", "review_apply", "Review/Apply", priority=True),
        Binding("i", "enter_insert", "Insert", show=False),
        Binding("escape", "escape", "Esc", show=False, priority=True),
        Binding("colon", "command_mode", ":", show=False),
        Binding("u", "undo_staged", "Undo", show=False),
        Binding("U", "redo_staged", "Redo", show=False),
        Binding("q", "back", "Back"),
        Binding("question_mark", "help", "Help"),
    ]

    def __init__(self, adapter: BaseEditableAdapter, record_id: str) -> None:
        super().__init__()
        self.adapter = adapter
        self.record_id = record_id
        self._working: WorkingRecord | None = None
        self._form: FieldForm | None = None
        self._modes = ModeController()
        self._last_outcome: SaveOutcome | None = None
        self._quit_after_apply = False

    def compose(self) -> ComposeResult:
        yield RigHeader(show_clock=False)
        with Vertical(id="screen-body"):
            yield Static(f"Edit {self.adapter.label} · {self.record_id}", id="screen-title")
            yield Static("", id="dirty-label")
            yield Static(self._modes.banner(), id="mode-banner")
            with VerticalScroll(id="field-form-scroll"):
                yield Static("Loading…", id="form-placeholder")
        yield Footer()

    def on_mount(self) -> None:
        try:
            self._working = self.adapter.create_working(self.record_id)
        except StoreError as exc:
            self.notify(format_error(exc), severity="error")
            self._last_outcome = SaveOutcome.FAILED
            self.dismiss(False)
            return
        self._mount_form()
        self._set_mode(EditorMode.NORMAL)

    def _set_mode(self, mode: EditorMode) -> None:
        self._modes.set_mode(mode)
        try:
            self.query_one("#mode-banner", Static).update(self._modes.banner())
        except Exception:
            pass

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
            on_change=self._sync_dirty,
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
            label.update(
                f"{len(self._working.mutations)} unsaved change(s) · "
                "Ctrl+S / :w to review/apply · Enter does not apply"
            )
        else:
            label.update("No unsaved changes · Esc back · Enter does not apply")

    def action_enter_insert(self) -> None:
        if self._modes.mode is EditorMode.COMMAND:
            return
        if self._form is not None:
            self._form.focus_first_editable()
        self._set_mode(EditorMode.INSERT)

    def action_escape(self) -> None:
        if self._modes.mode is EditorMode.INSERT:
            self._sync_dirty()
            self._set_mode(EditorMode.NORMAL)
            return
        if self._modes.mode is EditorMode.COMMAND:
            self._set_mode(EditorMode.NORMAL)
            return
        self.action_back()

    def action_command_mode(self) -> None:
        self._set_mode(EditorMode.COMMAND)

        def _done(raw: str | None) -> None:
            self._set_mode(EditorMode.NORMAL)
            if raw is None:
                self._last_outcome = SaveOutcome.CANCELLED
                return
            self._run_command(raw)

        self.app.push_screen(CommandLineModal(), _done)

    def _run_command(self, raw: str) -> None:
        cmd, _args = parse_command(raw)
        if cmd in {"",}:
            return
        if cmd == "write":
            self.action_review_apply()
            return
        if cmd == "wq":
            self._quit_after_apply = True
            self.action_review_apply()
            return
        if cmd == "quit":
            if self._working is not None:
                if self._form is not None:
                    self._harvest_into_working()
                if self._working.is_dirty:
                    self.notify(
                        "Unsaved changes — use :q! to discard or :w to save",
                        severity="warning",
                    )
                    self._last_outcome = SaveOutcome.CANCELLED
                    return
            self.dismiss(False)
            return
        if cmd == "quit!":
            if self._working is not None:
                self._working.discard()
            self.dismiss(False)
            return
        self.notify(f"Unknown command :{cmd}", severity="warning")

    def action_undo_staged(self) -> None:
        if self._modes.mode is EditorMode.INSERT:
            return
        if self._working is None:
            return
        if self._form is not None:
            self._harvest_into_working()
        if not self._working.undo():
            self.notify("Nothing to undo")
            return
        if self._form is not None:
            self._form.apply_values(self._working.merged())
        self._sync_dirty()
        self.notify("Undo")

    def action_redo_staged(self) -> None:
        if self._modes.mode is EditorMode.INSERT:
            return
        if self._working is None:
            return
        if not self._working.redo():
            self.notify("Nothing to redo")
            return
        if self._form is not None:
            self._form.apply_values(self._working.merged())
        self._sync_dirty()
        self.notify("Redo")

    def action_review_apply(self) -> None:
        if self._working is None or self._form is None:
            return
        self._harvest_into_working()
        if not self._working.is_dirty:
            self.notify("No changes to apply")
            self._last_outcome = SaveOutcome.CANCELLED
            return
        errors = self.adapter.validate_working(self._working)
        if errors:
            self.notify("; ".join(errors), severity="error")
            self._last_outcome = SaveOutcome.VALIDATION_ERROR
            debug_log("validation_error", record=self.record_id, errors=errors)
            return
        rows = self.adapter.diff(self._working)

        def _after_review(ok: bool | None) -> None:
            if not ok:
                self._last_outcome = SaveOutcome.CANCELLED
                self.notify("Save cancelled", severity="information")
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
            self._last_outcome = SaveOutcome.CONCURRENT_MODIFICATION
            self._handle_conflict(str(exc))
            return
        except StoreError as exc:
            self._last_outcome = SaveOutcome.FAILED
            self.notify(format_error(exc, prefix="FAILED: "), severity="error")
            debug_log("commit_failed", record=self.record_id, error=str(exc))
            # retain form + dirty
            return
        except Exception as exc:
            self._last_outcome = SaveOutcome.FAILED
            self.notify(format_error(exc, prefix="FAILED: "), severity="error")
            if is_debug():
                raise
            return
        self._last_outcome = SaveOutcome.SUCCESS
        # Discard working copy, reload from store, rebuild view
        self._working.discard()
        self._working = self.adapter.create_working(self.record_id)
        self._mount_form()
        msg = result.message
        if not msg.lower().startswith("saved") and not msg.lower().startswith("updated"):
            msg = f"Saved {result.record_id}."
        if result.hidden_by_filter and result.filter_hint:
            msg = f"{msg} {result.filter_hint}"
        self.notify(msg)
        debug_log("commit_success", record=self.record_id, message=msg)
        if self._quit_after_apply:
            self.dismiss(True)
            return
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
            else:
                # Cancel — retain edits, stay dirty
                self.notify(
                    "CONCURRENT_MODIFICATION — edits retained; resolve conflict to apply",
                    severity="warning",
                )
                self._sync_dirty()

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
                    self._last_outcome = SaveOutcome.CANCELLED
                    self.dismiss(False)

            self.app.push_screen(DiscardModal(len(self._working.mutations)), _done)
            return
        self.dismiss(False)

    def action_help(self) -> None:
        self.app.push_screen(
            HelpScreen(
                "Record editor\n\n"
                "Ctrl+S / :w  review changes then apply\n"
                "i            INSERT (edit fields)\n"
                "Esc          NORMAL (keeps values) / back from NORMAL\n"
                ":q / :q! / :wq  quit / discard quit / apply+quit\n"
                "u / U        undo / redo staged mutations\n"
                "Enter        does NOT apply mutations\n\n"
                f"{VIM_HELP_COMMON}\n"
                "Widgets never write YAML; Apply goes through the domain service."
            )
        )
