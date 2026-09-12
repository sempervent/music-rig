# Interactive TUI

Stage 12 Textual UI for browsing and editing music-rig planning/CURRENT state.

## Rules

- Presentation only — mutations go through shared services (`question_service`,
  `patchbay_state.propose_*` + `current_service.commit_patchbay`,
  `snapshot_service.create_snapshot`).
- Never parse CLI output; never write YAML from Textual widgets.
- OBS / Ableton / MIDI / Stream Deck / macOS automation remain `NOT_IMPLEMENTED`.
- Patchbay endpoint (connection) editing is **deferred**; mode + `hardware_model` only.

## Launch

```bash
uv run rig tui
uv run rig tui question Q-008
uv run rig tui patchbay PB-B
```

## Keyboard

| Key | Action |
|---|---|
| j/k or arrows | Navigate |
| Enter | Open / inspect |
| Esc | Back |
| / | Search |
| e | Edit (where editable) |
| s | Save / apply staged |
| r | Refresh |
| ? | Help |
| q | Quit on home; back on nested (discard prompt if dirty) |

Questions also: `f` filter, `a` add, `R` resolve, `d` defer, `o` reopen, `t` open target.  
Patchbay editor: `e` mode, `m` model, `n` next UNKNOWN, `s` apply, `o` related question.

## Architecture

Code lives under `src/music_rig/tui/` (`app`, `navigation`, `working`, `dialogs`,
`adapters`, `screens`). Staged patchbay edits use `WorkingDocument` with source-file
SHA-256 concurrency checks before apply.
