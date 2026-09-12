# Music Rig Repository Skill Guide

Operating guide for agentic coding agents working in this repository.

## Opening rule (CLI-first)

**Agents must use the `rig` CLI for ordinary operations.** Do not teach or perform
direct YAML edits for day-to-day mutations. Prefer:

```bash
uv run rig <domain> <verb> …
uv run rig reconcile …
uv run rig inspect …
uv run rig question answer … --json
uv run rig question target set … --yes --json
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
     uv run rig inspect domains
     uv run rig inspect cleanup --json

2. Work a factual uncertainty (human/observed answer — never invent)
     uv run rig question show Q-xxx
     uv run rig question answer Q-xxx --answer "<answer>" --json
     # optional dry-run:
     uv run rig question answer Q-xxx --answer "<answer>" --dry-run --json

3. Complete typed target if plan says NEEDS_AGENT_ACTION / missing_target_field
     uv run rig question target show Q-xxx --json
     uv run rig question target set Q-xxx --pair 1/25 --yes --json
     # candidates come from canonical patchbay data only — no guessing

4. Reconcile answer into CURRENT (separate from answer/resolve)
     uv run rig reconcile plan question Q-xxx --json
     uv run rig reconcile apply question Q-xxx --dry-run --json
     uv run rig reconcile apply question Q-xxx --yes --json
     uv run rig reconcile verify question Q-xxx --json
     uv run rig reconcile finalize question Q-xxx --yes \
       --complete-linked-todos --apply-linked-changes --confirm-dod --json

5. Validate
     uv run rig check
     uv run rig render --check
```

`answer` / `resolve` records an answer only. It does **not** set `reconciled_at`
or rewrite CURRENT. Human message: “Answer recorded. CURRENT reconciliation
still required.” Finalize sets `reconciled_at` after verify MATCH (or
`--no-current-change` with `--note`).

## Target completion workflow

Typed targets (`QuestionTarget`) drive adapters. Incomplete targets block apply:

```bash
uv run rig question target show Q-008 --json
uv run rig question target set Q-008 --domain patchbay.mode --bay PB-B --pair 1/25 --yes --json
uv run rig question target set Q-008 --pair 1/25 --dry-run --json   # before/after
uv run rig question target clear Q-008 --field pair --yes --json
uv run rig question target clear Q-008 --yes --json                 # entire target
```

Validation is exact (bay exists, pair exists in bay, gear/path IDs exist). No fuzzy match.

Structured NEEDS_AGENT_ACTION blockers look like:

```json
{
  "code": "missing_target_field",
  "field": "pair",
  "candidates": ["1/25", "2/26"],
  "suggested_commands": ["uv run rig question target set Q-xxx --pair 1/25 --yes"],
  "message": "target.pair missing — set pair before apply"
}
```

Candidates come from canonical data only. **Do not invent** production pairs
(e.g. production Q-008 pair stays null until inspected).

## VERIFY_ONLY domains

These adapters never promote INTENDED→VERIFIED via `reconcile apply`:

| Domain | Capability | Notes |
|---|---|---|
| `routing.verify` | VERIFY_ONLY | Inspect paths; finalize with `--no-current-change` |
| `midi.verify` | VERIFY_ONLY | Topology evidence; no auto-match freeform |
| `controls.verify` | VERIFY_ONLY | Controller evidence |
| `ableton.template` | VERIFY_ONLY | Live-set match is offline/manual |
| `midi.clock_master` | VERIFY_ONLY | Q-014 is physical practice (“in practice”); use `set-clock-master` then finalize — apply does not auto-write |
| `inventory.patchbay_mapping` | MANUAL | hardware_model only; no `gear_ref` / `set-gear` yet |

`patchbay.mode` is `APPLY_AND_VERIFY` when bay + pair + normalizable mode are known.

## Artifact lifecycle

| Artifact | Lifecycle | Never |
|---|---|---|
| Question `Q-*` | OPEN → RESOLVED (answer) → reconciled (`reconciled_at`) | Delete; invent answers |
| TODO `RIG-*` | … → DONE via `todo_service` / finalize | Delete records |
| Change `CHG-*` | OPEN → APPLIED via `change_service` / finalize | Delete records |
| Next Session | Max 3; remove on DONE | Leave DONE in next_session |

## Reconciliation states

`NEEDS_ANSWER` · `READY_TO_APPLY` · `NEEDS_AGENT_ACTION` · `CURRENT_MATCHES` ·
`READY_TO_FINALIZE` · `RECONCILED` · `BLOCKED`

Capabilities: `APPLY_AND_VERIFY` | `VERIFY_ONLY` | `MANUAL` | `UNSUPPORTED`

Adapters **normalize deterministically only** (e.g. `HALF_NORMAL` → `half-normal`).
They must not fuzzy-NLP guess answers.

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
```

Sweep `--dry-run --json` includes grouped counts:
`ready_to_finalize`, `needs_answer`, `needs_target_metadata`, `needs_agent_action`,
`blocked_by_dod`, `already_reconciled` plus `suggested_next_commands`.

JSON contract:

```json
{"ok": true, "operation": "...", "result": {}}
{"ok": false, "error": {"code": "...", "message": "...", "details": {}}}
```

No Rich/ANSI in `--json` mode. Exit 0 for successful inspect including
`NEEDS_AGENT_ACTION`. Verify returns `ok:true` with `verification=MISMATCH` and
**exit 1** on mismatch.

## Human verification (Stage 16)

Guides observation at the physical rig. The human supplies facts; **UNKNOWN is
valid**. Manuals describe capabilities — they do not invent CURRENT state.

```bash
uv run rig verify queue [--area] [--json]
uv run rig verify next [--json]
uv run rig verify show Q-008 [--json]
uv run rig verify run Q-008 [--answer-only]     # interactive
uv run rig verify answer Q-008 --value half-normal [--dry-run] [--yes] [--json] [--note]
uv run rig verify session [--area] [--todo RIG-002]
uv run rig verify summary [--json]
uv run rig verify area Patchbay
uv run rig tui verify
```

Workflow:

1. `verify queue` / `verify show` — see CURRENT hint + how to check
2. Ask the human / inspect the rig (do not invent from manuals)
3. `verify answer` or `verify run` — records via `question answer` only
4. `reconcile plan` → apply / verify / finalize as capability allows

Never invent answers to production OPEN questions during tests. Enriching
verification metadata (kind, prompt, answer schema, unambiguous targets) is OK.

## Question list flags

```bash
uv run rig question list                 # ACTIVE = OPEN + RESOLVED-unreconciled
uv run rig question list --open
uv run rig question list --unreconciled
uv run rig question list --all
```

TODO list hides terminal statuses (DONE / CANCELLED / DEFERRED) unless `--all`.

## Examples

### 1) Patchbay mode with incomplete target (fixture-style)

```bash
uv run rig question answer Q-008 --answer "half-normal" --json
uv run rig reconcile plan question Q-008 --json
# → NEEDS_AGENT_ACTION + missing_target_field pair + candidates
uv run rig question target set Q-008 --pair 1/25 --yes --json
uv run rig reconcile plan question Q-008 --json   # READY_TO_APPLY
uv run rig reconcile apply question Q-008 --yes --json
uv run rig reconcile verify question Q-008 --json
uv run rig reconcile finalize question Q-008 --yes \
  --complete-linked-todos --apply-linked-changes --confirm-dod --json
```

Production Q-008 has `bay: PB-B` and `pair: null` — do not invent the pair.

### 2) MANUAL inventory mapping

```bash
uv run rig reconcile plan question Q-007 --json
# MANUAL — set-model then finalize; no set-gear yet
```

## Inspection

```bash
uv run rig inspect domains               # Rich table (no tabs)
uv run rig inspect domains --json        # + mutable/derived/supports_reconcile
uv run rig inspect schema question
uv run rig inspect list question --json
uv run rig inspect cleanup --json        # missing targets, CURRENT_MATCHES, …
```

Human list output uses the shared presentation layer (`music_rig.presentation`).
Never rely on tab-separated columns.

## Architecture

```text
canonical YAML
  → Pydantic models
  → domain service / propose_*
  → validate
  → transactional write
  → render projections
  → TUI refresh / CLI output (presentation.py for human tables)
```

Reconciliation orchestrates existing CURRENT services; it does not duplicate editors.
Textual widgets never write YAML.

## TUI

- `rig tui verify`: guided queue + structured answer pickers; Skip / Next /
  Open Target / Edit Target / Reconcile. After answer shows READY_TO_APPLY or
  blockers.
- `rig tui reconcile`: plan/apply/verify/finalize; **e** Edit Target opens pair
  picker when `patchbay.mode` is missing `pair`.
- Questions: **t** Target — pair picker when pair missing; **r** Resolve.

## Things Agents Must Never Do

- Invent answers to OPEN questions or mark UNKNOWN as decided
- Invent production target pairs / gear mappings
- Direct-edit YAML for ordinary CURRENT/planning mutations
- Execute OBS / Ableton / MIDI TX / Stream Deck / macOS automation
- Promote INTENDED → VERIFIED without explicit verification (VERIFY_ONLY apply)
- Commit secrets from `.rig.local.yaml` into canonical data
- Blind-overwrite on concurrency conflicts
- Commit/push unless the human explicitly asks
- Mutate production data during tests — fixtures only

## Stage Boundaries / External Automation

Through Stage 16: documentation + local services + TUI editing + reconciliation
+ guided human verification (`rig verify`). External live automation remains
`NOT_IMPLEMENTED` / capability only. No OBS / Ableton / MIDI TX / Stream Deck
automation from verify flows.
