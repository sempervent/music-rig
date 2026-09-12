# Interactive TUI

Stage 13–18 Textual UI for browsing and editing music-rig planning/CURRENT state.

## Rules

- Presentation only — mutations go through shared services (`question_service`,
  `todo_service`, `patchbay_state.propose_*` + `current_service.commit_*`, etc.).
- Never parse CLI output; never write YAML from Textual widgets.
- OBS / Ableton / MIDI / Stream Deck / macOS automation remain `NOT_IMPLEMENTED`.
- Apply lifecycle: Edit → dirty → **Ctrl+S** / **:w** Review → Apply → validate →
  commit → render → refresh. **Enter does not apply.**
- If the TUI says saved, canonical YAML has the value; reopen shows it; failed
  save retains edits (`SaveOutcome`: SUCCESS | FAILED | CANCELLED |
  CONCURRENT_MODIFICATION | VALIDATION_ERROR).
- Answering a question does **not** invent `verification_result` (Stage 17).

## Launch

```bash
uv run rig tui
uv run rig tui question Q-008
uv run rig tui patchbay PB-B
uv run rig tui todo
uv run rig tui --debug          # or RIG_DEBUG=1
```

## Vim-like modes

Footer / banner shows `-- NORMAL --` / `-- INSERT --` / `-- COMMAND --`.

| Mode | Behavior |
|---|---|
| NORMAL | j/k, gg/G, / n N, i edit, Enter inspect, u undo, **U** redo, : command |
| INSERT | Normal typing (j inserts j); Esc → NORMAL (keeps field value) |
| COMMAND | :w apply, :q quit (refuses if dirty), :wq apply+quit, :q! discard |

**Redo is U** (uppercase). Ctrl+r remains **Refresh** (not redo).

## Keyboard (global)

| Key | Action |
|---|---|
| j/k or arrows | Navigate |
| gg / G | Top / bottom |
| Enter | Open / inspect (**never** apply) |
| i / e | Edit fields (INSERT) |
| Ctrl+S / :w | Review changes → Apply |
| A | Add (where supported) |
| / n N | Search / next / previous |
| u / U | Undo / redo staged working-copy edits |
| : | COMMAND mode |
| Ctrl+r | Refresh |
| Esc | NORMAL / back / cancel |
| ? | Context-sensitive help |
| q | Quit on home; back on nested (discard prompt if dirty) |

### Questions

| Key | Action |
|---|---|
| **a** | **Answer** (question text stays visible; may keep OPEN) |
| **A** | **Add** question |
| **r** / **R** | **Resolve** (answer required; status→RESOLVED) |
| **V** | Verify (observation / `verification_result` flow) |
| **C** | Reconcile handoff |
| d | Defer |
| o | Reopen |
| t | Open typed target |
| Ctrl+r | Refresh |

Answer-only save uses `update_question_fields` and may leave status OPEN.
Resolve requires a non-empty answer and confirmation. Neither invents
`verification_result`.

After resolve under filter=OPEN the row disappears; notification explains how to
view RESOLVED/ALL.

### Patchbay editor

| Key | Action |
|---|---|
| e / i / Space | Stage MODE (Space cycles UNKNOWN→NORMAL→HALF-NORMAL→THRU) |
| c | Edit upper/lower connections |
| **m** | Hardware **model** (not mode) |
| n / N | Next / prev UNKNOWN mode |
| Ctrl+S / s / :w | Apply staged (optional snapshot) |
| u / U | Undo / redo staged |
| o | Related OPEN question (`Q-xxx: <question text>`) |
| :q / :q! | Quit / discard quit |

MODE is staged until Apply. SelectModeModal focuses primary; Enter confirms; 1–4 pick.

## Coverage matrix

| Domain | View | Edit | Add | Round-trip | Vim-modal | Notes |
|---|---|---|---|---|---|---|
| Questions | yes | yes | yes | yes | yes | Answer screen keeps question visible |
| Patchbays | yes | yes | no | yes | yes | Do not Add Pair |
| TODO | yes | yes | yes | yes | yes | |
| Wishlist | yes | yes | yes | yes | yes | |
| Inbox | yes | yes | yes | yes | yes | |
| Changes | yes | yes | yes | yes | yes | |
| Gear | yes | yes | yes | yes | yes | |
| Channel map | yes | yes | no | yes | yes | |
| Routing | yes | yes | no | yes | yes | Structural via CLI |
| MIDI | yes | yes | partial | yes | yes | No TX |
| Controllers | yes | yes | partial | yes | yes | |
| Ableton | yes | yes | no | yes | yes | Metadata |
| Performance | yes | partial | partial | yes | yes | Evidence; no execution |
| Backups | yes | yes | partial | yes | yes | Plan fields; no secrets |
| Sessions | yes | partial | — | — | — | ACTIVE notes |
| Snapshots | yes | no | — | — | — | create/browse only |
| Doctor/Status/Reconcile/Automation | yes | no | — | — | — | Derived / read-only |

## Architecture

```text
src/music_rig/tui/
  modes.py debug.py save_outcome.py
  fields.py editors.py editable.py forms.py pickers.py working.py
  editable_domains/   # FieldSpec adapters + coverage markers
  screens/            # home, questions, answer, create, patchbays, editable, …
```

`rig inspect schema <domain>` exposes the same FieldSpecs as the TUI.

## Agent inspection

See repository-root `SKILLS.md` (CLI-first; agents prefer CLI over TUI automation):

```bash
uv run rig inspect domains
uv run rig inspect cleanup --json
```
