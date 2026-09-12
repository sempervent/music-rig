"""RigApp — Textual application shell for music-rig."""

from __future__ import annotations

from textual.app import App
from textual.binding import Binding

from music_rig.tui.adapters import get_adapter
from music_rig.tui.editable_domains import registry as editable_registry
from music_rig.tui.navigation import normalize_route
from music_rig.tui.screens.editable import EditableListScreen
from music_rig.tui.screens.generic import ListDetailScreen
from music_rig.tui.screens.home import HomeScreen
from music_rig.tui.screens.patchbays import PatchbayEditorScreen, PatchbayListScreen
from music_rig.tui.screens.questions import QuestionsScreen
from music_rig.tui.screens.reconcile import ReconcileScreen
from music_rig.tui.screens.verify import VerifyScreen

APP_CSS = """
Screen {
    background: $surface;
}

#home-title, #screen-title {
    text-style: bold;
    padding: 1 1 0 1;
}

#home-subtitle, #filter-label, #dirty-label, #mode-banner {
    color: $text-muted;
    padding: 0 1 1 1;
}

#mode-banner {
    text-style: bold;
}

#split {
    height: 1fr;
}

#list-table {
    width: 3fr;
    height: 1fr;
}

#detail-pane {
    width: 2fr;
    height: 1fr;
    border-left: solid $primary;
    padding: 0 1;
}

#modal {
    width: 70;
    max-width: 90%;
    height: auto;
    max-height: 80%;
    padding: 1 2;
    background: $panel;
    border: thick $primary;
}

#modal-title {
    text-style: bold;
    margin-bottom: 1;
}

#modal-body {
    margin-bottom: 1;
}

#modal-buttons {
    height: auto;
    align: center middle;
}

#modal-buttons Button {
    margin: 0 1;
}

#mode-choices Button {
    width: 100%;
    margin: 0 0 1 0;
}
"""


class RigApp(App[None]):
    """Interactive presentation layer. Mutations go through shared services only."""

    CSS = APP_CSS
    TITLE = "music-rig"
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=False),
    ]

    def __init__(
        self,
        *,
        route: str | None = None,
        object_id: str | None = None,
        pair: str | None = None,
        debug: bool = False,
    ) -> None:
        super().__init__()
        self._route = normalize_route(route)
        self._object_id = object_id
        self._pair = pair
        if debug:
            from music_rig.tui.debug import set_debug

            set_debug(True)

    def on_mount(self) -> None:
        from music_rig.tui.debug import debug_log

        debug_log("app.mount", route=self._route, object_id=self._object_id)
        self.push_screen(HomeScreen())
        if self._route:
            self.open_domain(self._route, self._object_id, pair=self._pair)

    def push_screen(self, screen, *args, **kwargs):  # type: ignore[override]
        from music_rig.tui.debug import debug_log, is_debug

        if is_debug():
            name = type(screen).__name__ if not isinstance(screen, str) else screen
            debug_log("push_screen", screen=name, stack=len(self.screen_stack))
        return super().push_screen(screen, *args, **kwargs)

    def pop_screen(self):  # type: ignore[override]
        from music_rig.tui.debug import debug_log, is_debug

        if is_debug() and self.screen_stack:
            debug_log(
                "pop_screen",
                screen=type(self.screen).__name__,
                stack=len(self.screen_stack),
            )
        return super().pop_screen()

    def open_domain(
        self,
        domain: str,
        object_id: str | None = None,
        *,
        pair: str | None = None,
    ) -> None:
        key = normalize_route(domain)
        if key is None:
            self.notify(f"Unknown domain {domain!r}", severity="error")
            return
        if key == "question":
            self.push_screen(QuestionsScreen(initial_id=object_id))
            return
        if key == "verify":
            self.push_screen(VerifyScreen(initial_id=object_id))
            return
        if key == "reconcile":
            self.push_screen(ReconcileScreen(initial_id=object_id))
            return
        if key == "patchbay":
            if object_id:
                self.push_screen(PatchbayEditorScreen(object_id, initial_pair=pair))
            else:
                self.push_screen(PatchbayListScreen())
            return
        editable = editable_registry.get_adapter(key)
        if editable is not None:
            self.push_screen(EditableListScreen(editable, initial_id=object_id))
            return
        adapter = get_adapter(key)
        if adapter is None:
            self.notify(f"Domain {key!r} not available", severity="error")
            return
        self.push_screen(ListDetailScreen(adapter, initial_id=object_id))
