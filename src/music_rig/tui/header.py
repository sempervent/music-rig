"""Lifecycle-safe Header for multi-screen push/pop.

Textual 8.2.8 ``Header._on_mount`` registers an *async* ``set_title`` watcher that
calls ``query_one(HeaderTitle)`` and only catches ``NoScreen``. During rapid
screen transitions (Questions → Reconcile → back, title churn, etc.):

1. The async coroutine may be created and never awaited → ``RuntimeWarning``
2. When awaited after children are gone → ``NoMatches: HeaderTitle``

See Textualize/textual#4258. Upstream ``main`` still only catches ``NoScreen``.
Subclassing ``Header`` is insufficient: Textual invokes ``Header._on_mount`` via
the MRO even when overridden.

``RigHeader`` is a lookalike Widget that never registers the fragile watcher.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.content import Content
from textual.dom import NoScreen
from textual.events import Mount
from textual.reactive import Reactive
from textual.widget import Widget
from textual.widgets._header import (
    HeaderClock,
    HeaderClockSpace,
    HeaderIcon,
    HeaderTitle,
)


class RigHeader(Widget):
    """Drop-in Header replacement that survives rapid multi-screen navigation."""

    DEFAULT_CSS = """
    RigHeader {
        dock: top;
        width: 100%;
        background: $panel;
        color: $foreground;
        height: 1;
    }
    """

    icon: Reactive[str] = Reactive("⭘")
    time_format: Reactive[str] = Reactive("%X")

    def __init__(
        self,
        show_clock: bool = False,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        icon: str | None = None,
        time_format: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._show_clock = show_clock
        if icon is not None:
            self.icon = icon
        if time_format is not None:
            self.time_format = time_format
        self._header_title = HeaderTitle()

    def compose(self) -> ComposeResult:
        yield HeaderIcon().data_bind(RigHeader.icon)
        yield self._header_title
        yield (
            HeaderClock().data_bind(RigHeader.time_format)
            if self._show_clock
            else HeaderClockSpace()
        )

    @property
    def screen_title(self) -> str:
        screen_title = self.screen.title
        return screen_title if screen_title is not None else self.app.title

    @property
    def screen_sub_title(self) -> str:
        screen_sub_title = self.screen.sub_title
        return screen_sub_title if screen_sub_title is not None else self.app.sub_title

    def format_title(self) -> Content:
        return self.app.format_title(self.screen_title, self.screen_sub_title)

    def _on_mount(self, _: Mount) -> None:
        def set_title() -> None:
            if not self.is_attached:
                return
            title = self._header_title
            if not title.is_attached:
                return
            try:
                title.update(self.format_title())
            except NoScreen:
                return

        self.watch(self.app, "title", set_title)
        self.watch(self.app, "sub_title", set_title)
        self.watch(self.screen, "title", set_title)
        self.watch(self.screen, "sub_title", set_title)
        set_title()
