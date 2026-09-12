"""Vim-like modal editing modes for the music-rig TUI.

Modes: NORMAL | INSERT | COMMAND
Always show ``-- NORMAL --`` / ``-- INSERT --`` / ``-- COMMAND --`` in the footer.

Redo binding: **U** (uppercase u). Ctrl+r remains Refresh to avoid collision.
"""

from __future__ import annotations

from enum import Enum
from typing import Callable

from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Input, Static


class EditorMode(str, Enum):
    NORMAL = "NORMAL"
    INSERT = "INSERT"
    COMMAND = "COMMAND"

    def banner(self) -> str:
        return f"-- {self.value} --"


# Shared NORMAL-mode navigation bindings (screens merge these carefully).
NORMAL_NAV_BINDINGS = [
    Binding("j", "cursor_down", "Down", show=False),
    Binding("k", "cursor_up", "Up", show=False),
    Binding("g", "go_top_pending", "gg", show=False),
    Binding("G", "go_bottom", "Bottom", show=False),
    Binding("slash", "search", "Search", show=False),
    Binding("n", "search_next", "Next hit", show=False),
    Binding("N", "search_prev", "Prev hit", show=False),
    Binding("colon", "command_mode", "Command", show=False),
    Binding("question_mark", "help", "Help", show=False),
    Binding("u", "undo_staged", "Undo", show=False),
    Binding("U", "redo_staged", "Redo", show=False),
]

VIM_HELP_COMMON = """\
Vim-like modes (footer shows -- NORMAL -- / -- INSERT -- / -- COMMAND --)

NORMAL
  j/k     move down/up
  gg / G  top / bottom
  / n N   search / next / previous hit
  i       enter INSERT (edit focused field)
  Enter   open / inspect (never apply)
  Esc     stay NORMAL / clear pending
  u / U   undo / redo staged working-copy edits
  :       COMMAND mode
  ?       this help

INSERT
  type normally (j inserts j)
  Esc     back to NORMAL (keeps field value)

COMMAND
  :w / :write     review/apply staged changes
  :q / :quit      quit (refuses if dirty)
  :wq             apply then quit
  :q!             discard and quit
  Esc             cancel command → NORMAL

Redo is **U** (not Ctrl+r — Ctrl+r is Refresh).
"""


class ModeController:
    """Mixin-style helper attached to screens that support modal editing."""

    def __init__(self) -> None:
        self.mode: EditorMode = EditorMode.NORMAL
        self._pending_g = False
        self.search_needle: str = ""
        self._command_buf: str = ""

    def set_mode(self, mode: EditorMode) -> None:
        self.mode = mode
        self._pending_g = False

    def banner(self) -> str:
        return self.mode.banner()

    def handle_g(self, go_top: Callable[[], None]) -> bool:
        """Return True if the key was consumed (gg sequence)."""
        if self.mode is not EditorMode.NORMAL:
            return False
        if self._pending_g:
            self._pending_g = False
            go_top()
            return True
        self._pending_g = True
        return True

    def clear_pending(self) -> None:
        self._pending_g = False


class CommandInputModal:
    """Factory helpers — actual modal lives in dialogs.CommandLineModal."""

    pass


def update_mode_banner(screen: Screen, controller: ModeController, widget_id: str = "mode-banner") -> None:
    try:
        screen.query_one(f"#{widget_id}", Static).update(controller.banner())
    except Exception:
        pass


def parse_command(raw: str) -> tuple[str, list[str]]:
    text = raw.strip()
    if text.startswith(":"):
        text = text[1:]
    parts = text.split()
    if not parts:
        return "", []
    cmd = parts[0].lower()
    aliases = {
        "w": "write",
        "write": "write",
        "q": "quit",
        "quit": "quit",
        "wq": "wq",
        "q!": "quit!",
        "quit!": "quit!",
    }
    return aliases.get(cmd, cmd), parts[1:]
