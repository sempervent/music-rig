"""Interactive Textual TUI for music-rig (presentation only)."""

from __future__ import annotations


def run_tui(
    route: str | None = None,
    object_id: str | None = None,
    *,
    pair: str | None = None,
    debug: bool = False,
) -> None:
    """Launch the interactive TUI. Optional route/object_id deep-link into a domain."""
    from music_rig.tui.app import RigApp
    from music_rig.tui.debug import set_debug

    if debug:
        set_debug(True)
    RigApp(route=route, object_id=object_id, pair=pair, debug=debug).run()
