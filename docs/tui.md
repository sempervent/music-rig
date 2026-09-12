# Interactive TUI

Stage 13 Textual UI for browsing and editing music-rig planning/CURRENT state.

## Rules

- Presentation only — mutations go through shared services (`question_service`,
  `todo_service`, `patchbay_state.propose_*` + `current_service.commit_*`, etc.).
- Never parse CLI output; never write YAML from Textual widgets.
- OBS / Ableton / MIDI / Stream Deck / macOS automation remain `NOT_IMPLEMENTED`.
- Apply lifecycle: Edit → dirty → **Ctrl+S** Review → Apply → validate → commit →
  render → refresh. **Enter does not apply.**

## Launch

```bash
uv run rig tui
uv run rig tui question Q-008
uv run rig tui patchbay PB-B
uv run rig tui todo
uv run rig tui gear
```

## Keyboard

| Key | Action |
|---|---|
| j/k or arrows | Navigate |
| Enter | Open / inspect (never apply) |
| e | Edit fields (FieldSpec form) |
| Ctrl+S | Review changes → Apply |
| a | Add (where supported) |
| / | Search |
| f | Cycle status filter |
| Ctrl+r | Refresh |
| Esc | Back / cancel |
| ? | Help |
| q | Quit on home; back on nested (discard prompt if dirty) |

### Questions

| Key | Action |
|---|---|
| **r** | **Resolve** (answer → confirm with Enter) |
| d | Defer |
| o | Reopen |
| t | Open typed target |
| Ctrl+r | Refresh |

After resolve under filter=OPEN the row disappears; notification explains how to
view RESOLVED/ALL.

### Patchbay editor

| Key | Action |
|---|---|
| e | Edit mode |
| c | Edit upper/lower connections |
| m | Hardware model |
| n | Next UNKNOWN mode |
| Ctrl+S / s | Apply staged (optional snapshot) |
| o | Related OPEN question |

## Editability matrix

| Domain | Editable | Notes |
|---|---|---|
| Questions | Yes | Full fields + semantic resolve/defer/reopen |
| TODO | Yes | Fields + Next Session + status actions |
| Wishlist | Yes | ACQUIRED requires inventory_ref |
| Inbox | Yes | Dismiss / edit; convert via CLI services |
| Changes | Yes | Mark Applied (confirm) / Dismiss |
| Patchbays | Yes | Mode, connections, model; bulk stage |
| Gear | Yes | Fields + retire; rename via `rig rename` |
| Channel map | Yes | Source via channel_state |
| Routing | Yes | Node mode via `node_token=mode`; structural CLI |
| MIDI | Yes | Channels/clock/ableton ports (no TX) |
| Controllers | Yes | Availability/evidence; BROKEN+mapped guarded |
| Ableton | Yes | Metadata (name/notes) |
| Performance | Partial | Binding evidence; no panic/record execution |
| Control surfaces | Browse | Prefer CLI / future nested editors |
| Backups | Yes | Plan fields only (no `.rig.local` secrets) |
| Sessions | Partial | ACTIVE notes via services; COMPLETED read-only |
| Snapshots | No | create/browse/verify/diff only |
| Doctor/Status/Reconcile/Automation | No | Derived / read-only |

## Architecture

```text
src/music_rig/tui/
  fields.py editors.py editable.py forms.py pickers.py
  editable_domains/   # FieldSpec adapters
  screens/            # home, questions, patchbays, editable, generic
```

`rig inspect schema <domain>` exposes the same FieldSpecs as the TUI.

## Agent inspection

See repository-root `SKILLS.md` (agent operating guide) and:

```bash
uv run rig inspect domains
uv run rig inspect cleanup --json
```
