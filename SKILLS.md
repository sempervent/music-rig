# Music Rig Repository Skill Guide

Operating guide for agentic coding agents working in this repository.

## Mission

`music-rig` is the durable source of truth for the physical/logical music setup
(ChatGPT Project `jng - the music setup`). Canonical YAML under `data/` plus
shared Python services own CURRENT truth; Markdown under `docs/` and diagrams are
generated or human narrative. Agents must not invent equipment, channels, or
resolved decisions.

## Truth and Evidence Hierarchy

1. **CURRENT** — verified/documented physical or logical state in `data/*.yaml`
2. **INTENDED** — design direction; not yet verified as CURRENT
3. **UNKNOWN** — explicitly undocumented; do not invent
4. **Planning** — TODO / questions / wishlist / inbox / changes
5. **Projections** — rendered Markdown/diagrams from YAML (never edit as source)

Evidence labels (`VERIFIED` | `INTENDED` | `UNKNOWN`) matter more than prose tone.

## Canonical Data Sources

| File | Domain |
|---|---|
| `data/todo.yaml` | Accepted work queue + Next Session |
| `data/wishlist.yaml` | Acquisition ideas |
| `data/open-questions.yaml` | Open / resolved / deferred questions |
| `data/changes.yaml` | Structured change records |
| `data/inbox.yaml` | Low-friction captures |
| `data/inventory.yaml` | Owned gear |
| `data/patchbays.yaml` | Patchbay jacks / modes / connections |
| `data/channel-map.yaml` | TASCAM / Alesis channel sources |
| `data/routing.yaml` | Routes + `named_paths` |
| `data/midi.yaml` | MIDI topology (documented only; no TX) |
| `data/controllers.yaml` | Controller mappings |
| `data/ableton.yaml` | Ableton track/send/action registry |
| `data/performance.yaml` | PFL performance bindings |
| `data/control-surfaces.yaml` | Control surface profiles |
| `data/backups.yaml` | Backup plan (no secrets; paths via `.rig.local.yaml`) |
| `data/sessions/` | Studio session logs |
| `.rig/snapshots/` | Immutable YAML snapshots |

Local secrets/paths: gitignored `.rig.local.yaml` (see `.rig.local.example.yaml`).

## Architecture

```text
canonical YAML
  → Pydantic models (music_rig.models / domain loaders)
  → domain service / propose_* 
  → validate
  → transactional write (store.write_documents / commit_*)
  → render projections
  → TUI refresh / CLI output
```

Textual widgets **never** write YAML.

TUI editor stack:

- `tui/fields.py` — FieldSpec metadata
- `tui/editors.py` — reusable field widgets
- `tui/editable.py` — WorkingRecord + EditableDomainAdapter protocol
- `tui/forms.py` — RecordEditScreen (Ctrl+S review/apply)
- `tui/pickers.py` — reference / ordered-list pickers
- `tui/editable_domains/` — per-domain adapters
- Specialized: Questions screen, Patchbay editor

## CLI vs TUI

| Need | Prefer |
|---|---|
| Scripted / CI mutation | CLI (`rig …`) |
| Interactive browse/edit | `rig tui` / `rig tui <domain>` |
| Agent discovery | `rig inspect …` |
| Validation | `rig check`, `rig render --check`, `rig doctor` |

Both CLI and TUI call the same services.

## Domain Services

Planning: `question_service`, `todo_service`, `wishlist_service`, `inbox_service`,
`change_service`, `session_service`.

CURRENT: `patchbay_state` / `channel_state` / `routing_state` / `inventory_state` /
`midi_state` / `control_state` / `performance_state` + `current_service.commit_*`.

Ops: `snapshot_service`, `backup_state`, `automation` (capability only).

## Field Specs / Editor Metadata

`FieldSpec` (`tui/fields.py`) drives TUI forms and `rig inspect schema <domain>`.
Types: TEXT, MULTILINE, ENUM, BOOL, INT, REF, REF_LIST, ORDERED_LIST, TIMESTAMP,
NESTED, READONLY.

## Safe Mutation Contract

Do not directly mutate canonical YAML from UI code.

Prefer:

```text
model → service → proposed state → validate →
transactional write → render → check
```

Apply lifecycle in TUI:

```text
Open → e Edit → modify (dirty) → Ctrl+S Review → Apply →
concurrency check → validate → commit → render → reload
```

Enter inspects/opens; it must **not** apply staged mutations.

Concurrency: WorkingDocument / WorkingRecord source SHA-256. On conflict: refuse
overwrite; offer reload/discard (no blind merge).

## Stable IDs and References

IDs like `Q-008`, `RIG-001`, `CHG-003`, gear slugs are stable references.
Cross-links live in typed fields (`related_todos`, `gear_ref`, typed question
targets). Do not invent IDs.

## Adding or Renaming IDs

- Create via services (`add_question`, `add_todo`, …) so IDs allocate correctly.
- Rename: `rig rename preview|apply <domain> <old> <new>`
- Supported today: **gear** inventory IDs (updates wishlist refs + structured
  `gear_ref` fields). Deferred: question/todo/change/patchbay/MIDI/control IDs.

## Generated Documents

`docs/*.md` markers (`<!-- rig:…:start -->`) are filled by `rig render`.
Edit YAML, then render. Do not hand-edit generated blocks as source of truth.

## Inspection and Cleanup

```bash
uv run rig inspect domains
uv run rig inspect schema question
uv run rig inspect list question --json
uv run rig inspect show question Q-008 --json
uv run rig inspect refs Q-008 --json
uv run rig inspect cleanup --json
```

Cleanup reports dangling refs and BROKEN+mapped controls only. There is **no**
`cleanup --fix-all`.

## Textual Development

- Package: `src/music_rig/tui/`
- Headless tests: Textual Pilot in `tests/test_tui.py`
- Keybindings (Stage 13):
  - Questions: `r` Resolve, `Ctrl+r` Refresh
  - Editors: `e` Edit, `Ctrl+S` Review/Apply
  - Confirm modals: Enter confirms; Confirm focused by default
- After resolve under OPEN filter, notify that the row is hidden; use `f` for
  RESOLVED/ALL

### TUI extension recipe

1. Ensure typed model exists.
2. Ensure service supports mutation (`propose_*` / update helpers).
3. Add/update FieldSpecs.
4. Register editable adapter in `editable_domains/registry.py`.
5. Reuse generic form widgets; add domain widgets only when semantics demand it.
6. Add Pilot tests (tmp fixtures only).
7. Verify CLI parity for new CURRENT proposes.

## Testing

```bash
uv sync --extra dev --extra docs
uv run pytest
```

Never mutate production `data/*.yaml` in tests — use tmp fixtures + monkeypatch
store paths. Leave `assets/` alone.

## Validation Commands

```bash
uv run rig check
uv run rig render --check
uv run rig doctor
uv run rig status
```

## Common Failure Modes

- Pressing `r` on Questions expecting refresh (Stage 12) — now Resolve; use Ctrl+r
- Resolve under OPEN filter looks like failure — row hides; check RESOLVED/ALL
- Confirm Tab → Cancel then Enter — Stage 13 binds Enter → confirm
- Widget writing YAML directly — forbidden; use services
- Treating INTENDED MIDI/Ableton as VERIFIED CURRENT
- Collapsing clean TASCAM / AUX wet loop / KAOSS paths in docs/diagrams

## Things Agents Must Never Do

- Execute OBS / Ableton / MIDI TX / Stream Deck / macOS automation
- Invent CURRENT facts or mark UNKNOWN as decided
- Commit secrets from `.rig.local.yaml` into canonical data
- Blind-overwrite on concurrency conflicts
- Aesthetic-only cleanup rules
- Commit/push unless the human explicitly asks

## Stage Boundaries / External Automation

Through Stage 13: documentation + local services + TUI editing.
External live automation remains `NOT_IMPLEMENTED` / capability reporting only.
