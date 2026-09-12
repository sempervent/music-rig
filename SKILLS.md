# Music Rig Repository Skill Guide

Operating guide for agentic coding agents working in this repository.

## Opening rule (CLI-first)

**Agents must use the `rig` CLI for ordinary operations.** Do not teach or perform
direct YAML edits for day-to-day mutations. Prefer:

```bash
uv run rig <domain> <verb> …
uv run rig reconcile …
uv run rig inspect …
```

If a needed mutation has no service/CLI yet: **add the service + CLI first**, then
use it. Never invent human answers to OPEN questions. Sweep never answers OPEN.

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

## Agent operating loop

```text
1. Inspect repository truth
     uv run rig status
     uv run rig doctor
     uv run rig reconcile queue --json
     uv run rig inspect cleanup --json

2. Work a factual uncertainty
     uv run rig question show Q-xxx
     # Human (or verified observation) provides answer — agents must NOT invent it
     uv run rig question resolve Q-xxx "<answer>"

3. Reconcile answer into CURRENT (separate from resolve)
     uv run rig reconcile plan question Q-xxx --json
     uv run rig reconcile apply question Q-xxx --dry-run --json
     uv run rig reconcile apply question Q-xxx --yes --json
     uv run rig reconcile verify question Q-xxx --json
     uv run rig reconcile finalize question Q-xxx --yes \
       --complete-linked-todos --apply-linked-changes --confirm-dod --json

4. Validate
     uv run rig check
     uv run rig render --check
```

Resolve records an answer only. It does **not** set `reconciled_at` or rewrite
CURRENT. Finalize sets `reconciled_at` after verify MATCH (or `--no-current-change`
with `--note`).

## Artifact lifecycle

| Artifact | Lifecycle | Never |
|---|---|---|
| Question `Q-*` | OPEN → RESOLVED (answer) → reconciled (`reconciled_at`) | Delete; invent answers |
| TODO `RIG-*` | … → DONE via `todo_service` / finalize | Delete records |
| Change `CHG-*` | OPEN → APPLIED via `change_service` / finalize | Delete records |
| Next Session | Max 3; remove on DONE | Leave DONE in next_session |

Completing TODOs = status DONE + remove from `next_session`. Completing Changes =
status APPLIED. Records stay in YAML forever.

## Reconciliation states

`NEEDS_ANSWER` · `READY_TO_APPLY` · `NEEDS_AGENT_ACTION` · `CURRENT_MATCHES` ·
`READY_TO_FINALIZE` · `RECONCILED` · `BLOCKED`

Capabilities: `APPLY_AND_VERIFY` | `VERIFY_ONLY` | `MANUAL` | `UNSUPPORTED`

Adapters **normalize deterministically only** (e.g. `HALF_NORMAL` → `half-normal`).
They must not fuzzy-NLP guess answers.

Audit: `reconciled_at` + Change/TODO status. No separate `reconciliation-log.yaml`.

## Reconcile CLI

```bash
uv run rig reconcile                    # advisory summary
uv run rig reconcile status
uv run rig reconcile queue [--type] [--state] [--ready] [--json]
uv run rig reconcile show question Q-008 [--json]
uv run rig reconcile plan question Q-008 [--json]
uv run rig reconcile apply question Q-008 [--dry-run] [--yes] [--snapshot-before] [--json]
uv run rig reconcile verify question Q-008 [--json]
uv run rig reconcile finalize question Q-008 [--dry-run] [--yes] [--json] \
  [--complete-linked-todos] [--apply-linked-changes] [--confirm-dod] \
  [--no-current-change] [--note "..."] [--snapshot-before]
uv run rig reconcile sweep [--dry-run|--write] [--yes] [--confirm-dod] [--json]
# legacy
uv run rig reconcile question Q-008
uv run rig reconcile change CHG-001
```

JSON contract:

```json
{"ok": true, "operation": "...", "result": {}}
{"ok": false, "error": {"code": "...", "message": "...", "details": {}}}
```

No Rich/ANSI in `--json` mode. Exit 0 for successful inspect including
`NEEDS_AGENT_ACTION`. Verify returns `ok:true` with `verification=MISMATCH` and
**exit 1** on mismatch.

## Examples

### 1) Patchbay mode (APPLY_AND_VERIFY)

```bash
# Fixture/target must include pair (e.g. 1/25). Production Q-008 is bay-wide → NEEDS_AGENT.
uv run rig question resolve Q-008 "half-normal"
uv run rig reconcile plan question Q-008 --json
# READY_TO_APPLY when pair known + mode normalizes + CURRENT differs
uv run rig reconcile apply question Q-008 --dry-run --json
uv run rig reconcile apply question Q-008 --yes --json
uv run rig reconcile verify question Q-008 --json   # MATCH
uv run rig reconcile finalize question Q-008 --yes \
  --complete-linked-todos --apply-linked-changes --confirm-dod --json
```

### 2) Freeform / NEEDS_AGENT_ACTION (no write)

```bash
uv run rig reconcile plan question Q-007 --json
# MANUAL inventory mapping — adapter suggests set-model commands; apply refuses
uv run rig reconcile apply question Q-007 --yes --json   # error / no CURRENT write
```

### 3) Q + TODO + Change finalize

```bash
uv run rig reconcile finalize question Q-xxx --yes \
  --complete-linked-todos --apply-linked-changes --confirm-dod \
  --note "CURRENT already matches" --no-current-change --json
# Linked OPEN changes → APPLIED; linked TODOs → DONE; cleared from next_session
```

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

Reconciliation (`music_rig.reconciliation`) **orchestrates** existing CURRENT
services; it does not duplicate editors.

Textual widgets **never** write YAML.

## CLI vs TUI

| Need | Prefer |
|---|---|
| Scripted / agent mutation | CLI (`rig …`) |
| Interactive browse/edit | `rig tui` / `rig tui <domain>` |
| Agent discovery | `rig inspect …` |
| Validation | `rig check`, `rig render --check`, `rig doctor` |

Both CLI and TUI call the same services.

## Safe Mutation Contract

Do not directly mutate canonical YAML for ordinary ops.

Prefer:

```text
model → service → proposed state → validate →
transactional write → render → check
```

## Inspection and Cleanup

```bash
uv run rig inspect domains
uv run rig inspect schema question
uv run rig inspect list question --json
uv run rig inspect show question Q-008 --json
uv run rig inspect refs Q-008 --json
uv run rig inspect cleanup --json
```

Cleanup reports dangling refs, BROKEN+mapped controls, RESOLVED-not-reconciled,
reconciled-with-OPEN-change, unfinished linked TODOs, DONE-in-next_session, etc.
There is **no** `cleanup --fix-all`.

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

## Things Agents Must Never Do

- Invent answers to OPEN questions or mark UNKNOWN as decided
- Direct-edit YAML for ordinary CURRENT/planning mutations
- Execute OBS / Ableton / MIDI TX / Stream Deck / macOS automation
- Promote INTENDED → VERIFIED without explicit verification
- Commit secrets from `.rig.local.yaml` into canonical data
- Blind-overwrite on concurrency conflicts
- Commit/push unless the human explicitly asks

## Stage Boundaries / External Automation

Through Stage 14: documentation + local services + TUI editing + reconciliation
workflow. External live automation remains `NOT_IMPLEMENTED` / capability only.
