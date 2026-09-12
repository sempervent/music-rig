"""Editable Patchbay list + bay editor. Mutations via propose_* + commit_patchbay."""

from __future__ import annotations

from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

from music_rig.patchbay_state import list_pairs, load_raw
from music_rig.store import StoreError
from music_rig import store as store_mod
from music_rig.tui.adapters import patchbays as pb
from music_rig.tui.dialogs import (
    ApplyPatchbayModal,
    DiscardModal,
    HelpScreen,
    InputModal,
    SelectModeModal,
)
from music_rig.tui.widgets import mode_cell
from music_rig.tui.working import ConcurrentModificationError, WorkingDocument


class PatchbayListScreen(Screen):
    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("enter", "open", "Open"),
        Binding("ctrl+r", "refresh", "Refresh"),
        Binding("escape", "back", "Back"),
        Binding("q", "back", "Back"),
        Binding("question_mark", "help", "Help"),
    ]

    def __init__(self, *, initial_bay: str | None = None) -> None:
        super().__init__()
        self._initial_bay = initial_bay.upper() if initial_bay else None
        self._bay_ids: list[str] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="screen-body"):
            yield Static("Patchbays", id="screen-title")
            yield Static(
                "Edit mode, connections, hardware_model · Ctrl+S apply · staged bulk edits",
                id="home-subtitle",
            )
            yield DataTable(id="list-table", cursor_type="row")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#list-table", DataTable)
        table.add_columns("Bay", "Model", "Pairs", "Populated", "Unknown modes")
        table.focus()
        self.reload()
        if self._initial_bay:
            self.app.push_screen(PatchbayEditorScreen(self._initial_bay))

    def reload(self) -> None:
        table = self.query_one("#list-table", DataTable)
        table.clear()
        self._bay_ids = []
        for row in pb.bay_summaries():
            table.add_row(
                row["id"],
                row["model"],
                str(row["pairs"]),
                str(row["populated"]),
                str(row["unknown"]),
            )
            self._bay_ids.append(row["id"])

    def action_cursor_down(self) -> None:
        self.query_one("#list-table", DataTable).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one("#list-table", DataTable).action_cursor_up()

    def action_open(self) -> None:
        table = self.query_one("#list-table", DataTable)
        row = table.cursor_row
        if row is None or row < 0 or row >= len(self._bay_ids):
            return
        self.app.push_screen(PatchbayEditorScreen(self._bay_ids[row]))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.action_open()

    def action_refresh(self) -> None:
        self.reload()
        self.notify("Refreshed")

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_help(self) -> None:
        self.app.push_screen(
            HelpScreen(
                "Patchbay list\n\nEnter open bay editor\nCtrl+r refresh\nEsc/q back"
            )
        )


class PatchbayEditorScreen(Screen):
    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("e", "edit_mode", "Edit mode"),
        Binding("c", "edit_connections", "Connections"),
        Binding("m", "edit_model", "Model"),
        Binding("n", "next_unknown", "Next UNKNOWN"),
        Binding("ctrl+s", "apply", "Apply"),
        Binding("s", "apply", "Apply", show=False),
        Binding("o", "open_question", "Question"),
        Binding("ctrl+r", "refresh", "Refresh"),
        Binding("escape", "back", "Back"),
        Binding("q", "back", "Back"),
        Binding("question_mark", "help", "Help"),
    ]

    def __init__(
        self,
        bay_id: str,
        *,
        initial_pair: str | None = None,
        path: Path | None = None,
    ) -> None:
        super().__init__()
        self.bay_id = bay_id.upper()
        self._initial_pair = initial_pair
        self._path = path or store_mod.PATCHBAYS_PATH
        self._working: WorkingDocument | None = None
        self._pair_keys: list[str] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="screen-body"):
            yield Static(f"Patchbay {self.bay_id}", id="screen-title")
            yield Static("", id="dirty-label")
            with Horizontal(id="split"):
                yield DataTable(id="list-table", cursor_type="row")
                with VerticalScroll(id="detail-pane"):
                    yield Static("", id="detail")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#list-table", DataTable)
        table.add_columns("PAIR", "UPPER", "LOWER", "MODE")
        self._working = pb.open_working(self.bay_id, path=self._path)
        table.focus()
        self._reload_table(select_pair=self._initial_pair)

    def _pairs(self):
        assert self._working is not None
        return list_pairs(self.bay_id, self._working.baseline)

    def _reload_table(self, select_pair: str | None = None) -> None:
        assert self._working is not None
        table = self.query_one("#list-table", DataTable)
        table.clear()
        self._pair_keys = []
        model_now, model_base = pb.staged_model(self._working, self.bay_id)
        dirty = self._working.dirty_state()
        model_note = model_now
        if model_base is not None and model_now != model_base:
            model_note = f"{model_base} -> {model_now} *"
        self.query_one("#dirty-label", Static).update(
            f"Model: {model_note}  ·  {dirty.label() or 'clean'}  ·  Ctrl+S apply"
        )
        for pair in self._pairs():
            key = pb.pair_key(pair)
            effective, baseline = pb.staged_mode_for(self._working, self.bay_id, pair)
            upper, upper_base = pb.staged_connection(self._working, pair, "upper")
            lower, lower_base = pb.staged_connection(self._working, pair, "lower")
            upper_disp = upper or "—"
            if upper_base is not None and upper != upper_base:
                upper_disp = f"{upper_disp} *"
            lower_disp = lower or "—"
            if lower_base is not None and lower != lower_base:
                lower_disp = f"{lower_disp} *"
            table.add_row(
                key,
                upper_disp,
                lower_disp,
                mode_cell(effective, staged_from=baseline),
            )
            self._pair_keys.append(key)
        if select_pair and select_pair in self._pair_keys:
            table.move_cursor(row=self._pair_keys.index(select_pair))
        elif select_pair:
            for i, key in enumerate(self._pair_keys):
                if key == select_pair or key.startswith(f"{select_pair}/") or key.split("/")[0] == select_pair:
                    table.move_cursor(row=i)
                    break
        self._update_detail()

    def _selected_pair_key(self) -> str | None:
        table = self.query_one("#list-table", DataTable)
        row = table.cursor_row
        if row is None or row < 0 or row >= len(self._pair_keys):
            return None
        return self._pair_keys[row]

    def _selected_pair(self):
        key = self._selected_pair_key()
        if key is None:
            return None
        for pair in self._pairs():
            if pb.pair_key(pair) == key:
                return pair
        return None

    def _update_detail(self) -> None:
        assert self._working is not None
        detail = self.query_one("#detail", Static)
        pair = self._selected_pair()
        if pair is None:
            detail.update("Select a pair")
            return
        key = pb.pair_key(pair)
        effective, baseline = pb.staged_mode_for(self._working, self.bay_id, pair)
        mode_line = effective
        if baseline is not None:
            mode_line = f"{baseline} -> {effective} *"
        upper, _ = pb.staged_connection(self._working, pair, "upper")
        lower, _ = pb.staged_connection(self._working, pair, "lower")
        lines = [
            f"# Pair {key}",
            "",
            f"Upper {pair['upper_n']}: {upper or '—'}",
            f"Lower {pair.get('lower_n')}: {lower or '—'}",
            f"Mode: {mode_line}",
            f"Status: {pair.get('status') or '—'}",
            "",
            "e mode · c connections · m model · Ctrl+S apply",
            "",
            "## Related OPEN questions",
        ]
        related = pb.related_open_questions(self.bay_id, key)
        if not related:
            lines.append("—")
        for q in related:
            lines.append(f"- {q.id}: {q.question}")
        detail.update("\n".join(lines))

    def action_cursor_down(self) -> None:
        self.query_one("#list-table", DataTable).action_cursor_down()
        self._update_detail()

    def action_cursor_up(self) -> None:
        self.query_one("#list-table", DataTable).action_cursor_up()
        self._update_detail()

    @on(DataTable.RowHighlighted)
    def _on_highlight(self) -> None:
        self._update_detail()

    def action_edit_mode(self) -> None:
        assert self._working is not None
        pair = self._selected_pair()
        if pair is None:
            return
        key = pb.pair_key(pair)
        effective, _ = pb.staged_mode_for(self._working, self.bay_id, pair)

        def _done(mode: str | None) -> None:
            if mode is None:
                return
            baseline = str(pair.get("mode") or "unknown").lower()
            mut_key = f"mode:{key}"
            if mode == baseline:
                self._working.unstage(mut_key)
            else:
                self._working.stage(mut_key, mode)
            self._reload_table(select_pair=key)

        self.app.push_screen(SelectModeModal(key, effective), _done)

    def action_edit_connections(self) -> None:
        assert self._working is not None
        pair = self._selected_pair()
        if pair is None:
            return
        key = pb.pair_key(pair)
        upper_now, _ = pb.staged_connection(self._working, pair, "upper")
        lower_now, _ = pb.staged_connection(self._working, pair, "lower")

        def _after_upper(upper: str | None) -> None:
            if upper is None:
                return

            def _after_lower(lower: str | None) -> None:
                if lower is None:
                    return
                for side, value, baseline_key in (
                    ("upper", upper, "upper_conn"),
                    ("lower", lower, "lower_conn"),
                ):
                    baseline = str(pair.get(baseline_key) or "")
                    mut_key = f"{side}:{key}"
                    if value == baseline:
                        self._working.unstage(mut_key)
                    else:
                        self._working.stage(mut_key, value)
                self._reload_table(select_pair=key)

            self.app.push_screen(
                InputModal("Lower connection", default=lower_now, allow_empty=True),
                _after_lower,
            )

        self.app.push_screen(
            InputModal("Upper connection", default=upper_now, allow_empty=True),
            _after_upper,
        )

    def action_edit_model(self) -> None:
        assert self._working is not None
        model_now, _ = pb.staged_model(self._working, self.bay_id)

        def _done(value: str | None) -> None:
            if value is None:
                return
            bay = (self._working.baseline.get("patchbays") or {}).get(self.bay_id) or {}
            baseline = str(bay.get("hardware_model") or "unknown")
            if value == baseline:
                self._working.unstage("model")
            else:
                self._working.stage("model", value)
            self._reload_table(select_pair=self._selected_pair_key())

        self.app.push_screen(
            InputModal("Hardware model", default=model_now),
            _done,
        )

    def action_next_unknown(self) -> None:
        assert self._working is not None
        table = self.query_one("#list-table", DataTable)
        start = (table.cursor_row or 0) + 1
        n = len(self._pair_keys)
        if n == 0:
            return
        for offset in range(n):
            idx = (start + offset) % n
            key = self._pair_keys[idx]
            pair = next(p for p in self._pairs() if pb.pair_key(p) == key)
            effective, _ = pb.staged_mode_for(self._working, self.bay_id, pair)
            if effective == "unknown":
                table.move_cursor(row=idx)
                self._update_detail()
                return
        self.notify("No UNKNOWN modes remaining", severity="information")

    def action_open_question(self) -> None:
        pair = self._selected_pair()
        key = pb.pair_key(pair) if pair else None
        related = pb.related_open_questions(self.bay_id, key)
        if not related:
            self.notify("No related OPEN questions", severity="warning")
            return
        self.app.open_domain("question", related[0].id)  # type: ignore[attr-defined]

    def action_apply(self) -> None:
        assert self._working is not None
        if not self._working.is_dirty:
            self.notify("No staged changes", severity="information")
            return
        summary = pb.change_summary(self._working, self.bay_id)

        def _done(result: tuple[bool, bool] | None) -> None:
            if result is None:
                return
            _ok, create_snap = result
            try:
                preview = pb.apply_working(
                    self._working,
                    self.bay_id,
                    create_snapshot=create_snap,
                    patchbays_path=self._path,
                )
            except ConcurrentModificationError as exc:
                self.notify(str(exc), severity="error")
                self._reload_table(select_pair=self._selected_pair_key())
                return
            except StoreError as exc:
                self.notify(str(exc), severity="error")
                return
            self.notify(preview.message or "Applied")
            # Reload baseline from disk
            self._working = pb.open_working(self.bay_id, path=self._path)
            self._reload_table(select_pair=self._selected_pair_key())

        self.app.push_screen(ApplyPatchbayModal(summary), _done)

    def action_refresh(self) -> None:
        assert self._working is not None
        if self._working.is_dirty:

            def _done(ok: bool | None) -> None:
                if not ok:
                    return
                self._working = pb.open_working(self.bay_id, path=self._path)
                self._reload_table()
                self.notify("Reloaded")

            self.app.push_screen(
                DiscardModal(self._working.dirty_count),
                _done,
            )
            return
        self._working = pb.open_working(self.bay_id, path=self._path)
        self._reload_table(select_pair=self._selected_pair_key())
        self.notify("Reloaded")

    def action_back(self) -> None:
        assert self._working is not None
        if self._working.is_dirty:

            def _done(ok: bool | None) -> None:
                if ok:
                    self._working.discard()
                    self.app.pop_screen()

            self.app.push_screen(DiscardModal(self._working.dirty_count), _done)
            return
        self.app.pop_screen()

    def action_help(self) -> None:
        self.app.push_screen(
            HelpScreen(
                f"Patchbay {self.bay_id}\n\n"
                "e       edit mode for selected pair\n"
                "c       edit upper/lower connections\n"
                "m       edit hardware_model\n"
                "n       jump to next UNKNOWN mode\n"
                "Ctrl+S  apply staged changes (optional snapshot)\n"
                "o       open related OPEN question\n"
                "Ctrl+r  reload (discard if dirty)\n"
                "Esc/q   back (discard prompt if dirty)\n\n"
                "Enter does not apply. Bulk stage then Apply."
            )
        )
