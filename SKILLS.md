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
     # Provisional:
     uv run rig question draft Q-xxx --answer "<draft>" --json
     # Final (RESOLVED; reconciled_at still null):
     uv run rig question answer Q-xxx --answer "<answer>" --json
     # Promote existing draft:
     uv run rig question resolve Q-xxx
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
     # Adapter MATCH path:
     uv run rig reconcile finalize question Q-xxx --yes \
       --complete-linked-todos --apply-linked-changes --confirm-dod --json
     # Agent-interpreted / MANUAL path (after supported `rig current` updates):
     uv run rig reconcile finalize question Q-xxx --yes \
       --confirm-current-reconciled \
       --note "Updated CURRENT from final human answer via supported CLI" \
       --complete-linked-todos --confirm-dod --json

5. Validate
     uv run rig check
     uv run rig render --check
```

`draft` keeps status OPEN (`answer_state=DRAFT`). `answer` / `resolve` create
FINAL (`RESOLVED` + `resolved_at`). None of these set `reconciled_at` or rewrite
CURRENT. Do not invent `verification_result` from answering alone. Finalize sets
`reconciled_at` after verify MATCH, `--no-current-change` with `--note`, or
`--confirm-current-reconciled` with `--note` (manual/agent-interpreted).

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

## VERIFY_ONLY / human-verify-then-apply domains

These adapters never invent VERIFIED from metadata alone. After an explicit
human `verification_result` (CONFIRMED/CORRECTED), `reconcile apply` may set
scoped CURRENT evidence/value via shared services:

| Domain | Capability | After observation |
|---|---|---|
| `routing.verify` | VERIFY_ONLY | YES+CONFIRMED → NamedPath.evidence VERIFIED |
| `midi.verify` | VERIFY_ONLY | link-scoped only; never whole topology |
| `controls.verify` | VERIFY_ONLY | context-scoped evidence; not whole controller |
| `ableton.template` | VERIFY_ONLY | template evidence VERIFIED |
| `midi.clock_master` | VERIFY_ONLY | set master if needed + status VERIFIED |
| `inventory.patchbay_mapping` | MANUAL | set-model then finalize |

`patchbay.mode` is `APPLY_AND_VERIFY` when bay + pair + normalizable mode are known.

## Observation vs answer (Stage 17)

```text
ANSWER          recorded fact on the Question
OBSERVATION     verification_result — human performed the check
CURRENT         canonical documented configuration
EVIDENCE        VERIFIED | INTENDED | UNKNOWN on CURRENT entities
```

Complete YAML ≠ VERIFIED. Only explicit human observation may promote evidence.

```bash
# Answer without claiming physical verification (evidence stays INTENDED)
uv run rig verify answer Q-014 --value ableton --yes --json

# Explicit human observation (sets verification_result)
uv run rig verify record Q-014 --outcome confirmed --value ableton --yes --json
uv run rig verify record Q-014 --outcome corrected --value kaoss --yes --json
uv run rig verify record Q-016 --outcome failed_test --note "…" --create-change --yes --json
uv run rig verify record Q-014 --outcome unknown --yes --json

# Then reconcile evidence/value
uv run rig reconcile plan question Q-014 --json
uv run rig reconcile apply question Q-014 --dry-run --json
uv run rig reconcile apply question Q-014 --yes --json
```

**CONFIRMED flow:** observation matches documented → SET_EVIDENCE_VERIFIED (no value change if already correct) → verify MATCH → finalize.

**FAILED_TEST flow:** record observation; do **not** mark VERIFIED; optional Change; Question stays active; sweep must not finalize as success.

Never invent `verification_result` from inference or manuals. Agents may only call
`verify record` after the human explicitly reports performing the check.

Aliases: `rig verify confirm|correct|fail`.

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
uv run rig verify run Q-008 [--answer-only]     # interactive (+ observation prompt)
uv run rig verify record Q-014 --outcome confirmed --value ableton [--dry-run] [--yes] [--json]
uv run rig verify answer Q-008 --value half-normal [--dry-run] [--yes] [--json] [--note]
uv run rig verify session [--area] [--todo RIG-002]
uv run rig verify summary [--json]
uv run rig verify area Patchbay
uv run rig tui verify
```

Workflow:

1. `verify queue` / `verify show` — see CURRENT, evidence, last observation, how to check
2. Ask the human / inspect the rig (do not invent from manuals)
3. `verify record` (preferred when human performed the check) or `verify answer`
4. `reconcile plan` → apply evidence/value / verify / finalize as capability allows

Never invent answers or observations for production OPEN questions during tests.
Enriching verification metadata (kind, prompt, answer schema, unambiguous targets) is OK.

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

The TUI is a **human editor** over the same services as the CLI. Agents should prefer
`uv run rig …` (CLI-first) and must **not** automate the TUI.

- `rig tui verify`: guided queue + structured answer pickers; Skip / Next /
  Open Target / Edit Target / Reconcile. After answer shows READY_TO_APPLY or
  blockers.
- `rig tui reconcile`: plan/apply/verify/finalize; **e** Edit Target opens pair
  picker when `patchbay.mode` is missing `pair`.
- Questions: **a** Answer (Save Draft / Answer & Resolve), **A** Add,
  **R** Resolve draft, **V** Verify, **C** Reconcile. Ctrl+r = Refresh.
  Labels: OPEN/UNANSWERED · OPEN/DRAFT · RESOLVED/UNRECONCILED ·
  RESOLVED/RECONCILED. Default filter ACTIVE.
- Vim-like modes for extenders: NORMAL / INSERT / COMMAND (`:w` apply, `:q` /
  `:q!`). See [docs/tui.md](docs/tui.md). Do not teach agents to drive Pilot/TUI.
- Result-bearing screens/modals complete **once**; children return intent, parents
  navigate (never push a sibling then dismiss the child). See `docs/tui.md`.
- `rig tui --debug` / `RIG_DEBUG=1` for pipeline diagnostics only.

## Live Rig Data Changes During Development

When the human provides real rig facts while you are working on a feature branch:

1. Treat those facts as intentional production-state changes.
2. Do not discard them as test pollution.
3. Keep code fixes and real-data reconciliation distinguishable.
4. Use `rig` CLI entrypoints for the data mutation.
5. Run `rig check` / `rig render` / tests.
6. Review `git diff` carefully.
7. Do not silently mix unrelated implementation and data changes.

## Blocking code bug during reconciliation workflow

If a shared service bug blocks a legitimate reconciliation:

1. Stop the reconciliation.
2. Reproduce the bug.
3. Add a regression test.
4. Fix the service invariant.
5. Validate (`pytest`, `rig check`, `rig render --check`).
6. Resume reconciliation using the fixed CLI.
7. Report the code fix separately from the factual rig update.

## Do not ask redundant "preserve these?" after human asked to reconcile

If the human explicitly asked to reconcile answers they entered, the real rig
state changes from that reconciliation are intentional. Report them. Do **not**
finish by asking whether to preserve them. Git commit/push remains a separate
concern unless the human also requested repository delivery.

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
