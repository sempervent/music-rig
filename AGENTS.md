# AGENTS.md

**IMPORTANT: You are a bot.**

Every invocation of the music-rig CLI MUST include the global `--am-bot`
flag immediately after `rig`.

Correct:

```bash
uv run rig --am-bot question show Q-014 --json
```

Incorrect:

```bash
uv run rig question show Q-014 --json
```

Before running any `rig` command, verify it begins:

```text
rig --am-bot
```

If not, correct the command before execution.

Bots cannot supply HUMAN answer authority or HUMAN observation evidence.
Prefer `question draft` for suggestions; humans Answer & Resolve / verify.

Operational instructions for Codex sessions working in this repository.

## Role of this repository

This repository is the durable source of truth for the ChatGPT Project named `jng - the music setup`.
Use the repository itself as the source of remembered state, not chat memory or guessed context.

## Required workflow

1. Inspect the existing repository documentation before answering questions, proposing changes, or modifying files.
2. Treat the source-of-truth hierarchy below as authoritative for CURRENT physical state.
3. Cross-check routing, inventory, diagrams, and YAML data before stating that a connection, device role, or channel assignment is current.
4. **CLI-first for agents:** use `uv run rig --am-bot …` (especially `rig reconcile`) for ordinary mutations — do not teach direct YAML edits. See [SKILLS.md](SKILLS.md).

## Source-of-truth hierarchy

| Layer | File | Role |
|---|---|---|
| Overview | [docs/current-routing.md](docs/current-routing.md) | End-to-end physical CURRENT routing |
| Routes | [data/routing.yaml](data/routing.yaml) | Canonical structured CURRENT audio/pedal topology (`named_paths`) + high-level routes |
| Channels | [data/channel-map.yaml](data/channel-map.yaml) | Interface and mixer channel assignments |
| Patchbays | [data/patchbays.yaml](data/patchbays.yaml) | Physical patchbay jack assignments and normalization state |
| Patchbay ops | [docs/patchbays.md](docs/patchbays.md) | Human-readable patchbay reference at the rack |
| Pedals | [docs/pedal-chains.md](docs/pedal-chains.md) | Exact CURRENT active pedal topology |
| Inventory | [docs/inventory.md](docs/inventory.md) / [data/inventory.yaml](data/inventory.yaml) | Equipment ownership and role — not necessarily current signal-path membership |
| MIDI | [data/midi.yaml](data/midi.yaml) | Canonical MIDI devices, links, channels, clock, and Ableton port evidence |
| MIDI topology | [docs/midi-topology.md](docs/midi-topology.md) / [diagrams/midi-topology.mmd](diagrams/midi-topology.mmd) | Generated physical-link projections |
| MIDI clock | [docs/midi-clock.md](docs/midi-clock.md) | Generated clock/channel/Ableton overview plus controller notes |
| Controller maps | [data/controllers.yaml](data/controllers.yaml) / [docs/controller-mappings.md](docs/controller-mappings.md) | Canonical mapping evidence and generated tables |
| Ableton targets | [data/ableton.yaml](data/ableton.yaml) / [docs/ableton-track-map.md](docs/ableton-track-map.md) | Durable track/send/action targets; not a Live Set dump |
| Performance | [data/performance.yaml](data/performance.yaml) / [docs/performance.md](docs/performance.md) | PFL modes, actions, bindings, recovery contracts |
| Backups | [data/backups.yaml](data/backups.yaml) / [docs/backups.md](docs/backups.md) | Backup / archive plan (locators only; no absolute paths) |
| Automation | [docs/automation-readiness.md](docs/automation-readiness.md) | Honest capability registry; simulate never executes |
| Diagrams | [diagrams/](diagrams/) | Visual projections of the same authoritative state |
| Todo (canonical) | [data/todo.yaml](data/todo.yaml) | Structured accepted work — edit this, not generated Markdown sections |
| Todo (rendered) | [docs/todo.md](docs/todo.md) | Human-facing TODO view; generated section owned by `uv run rig --am-bot render` |
| Wishlist (canonical) | [data/wishlist.yaml](data/wishlist.yaml) | Structured speculative desires |
| Wishlist (rendered) | [docs/wishlist.md](docs/wishlist.md) | Human-facing wishlist view; generated section owned by `uv run rig --am-bot render` |
| Inbox | [data/inbox.yaml](data/inbox.yaml) | Uncategorized captures — observations only, not CURRENT truth |
| Changes | [data/changes.yaml](data/changes.yaml) | Structured “reality may have changed” records — not auto-CURRENT |
| Sessions | [data/sessions/](data/sessions/) | Studio session logs — operational history |
| Open questions (canonical) | [data/open-questions.yaml](data/open-questions.yaml) | Unresolved factual uncertainties (`Q-*`) |
| Open questions (rendered) | [docs/open-questions.md](docs/open-questions.md) | Human-facing questions; generated section owned by `uv run rig --am-bot render` |

### Planning CLI

```bash
uv sync --extra dev --extra docs
uv run rig --am-bot status
uv run rig --am-bot now
uv run rig --am-bot now --play
uv run rig --am-bot doctor
uv run rig --am-bot reconcile
uv run rig --am-bot reconcile queue --json
uv run rig --am-bot reconcile plan question Q-008 --json

# Questions
uv run rig --am-bot question list
uv run rig --am-bot question list --open
uv run rig --am-bot question list --unreconciled
uv run rig --am-bot question show Q-008
uv run rig --am-bot question draft Q-008 --answer "half-normal" --json
# Final HUMAN answers must be entered without --am-bot (or via TUI)
uv run rig --am-bot question target show Q-008 --json
uv run rig --am-bot question target set Q-008 --pair 1/25 --yes --json
uv run rig --am-bot question resolve Q-008
uv run rig --am-bot question todo Q-008

# Interactive TUI (HUMAN only — do not use --am-bot)
uv run rig tui
uv run rig tui question Q-008
uv run rig tui patchbay PB-B
uv run rig tui reconcile

# Inspection (agents)
uv run rig --am-bot inspect domains
uv run rig --am-bot inspect schema question
uv run rig --am-bot inspect cleanup --json

# Work
uv run rig --am-bot todo start RIG-001
uv run rig --am-bot todo done RIG-001

# Plan next studio session
uv run rig --am-bot todo next list
uv run rig --am-bot todo next set RIG-002 RIG-038 RIG-046

# Wishlist
uv run rig --am-bot wish list
uv run rig --am-bot wish promote "PFL Eurorack v1"

# Capture now, classify later
uv run rig --am-bot capture "RE-2 noisy after DD-8"
uv run rig --am-bot inbox list
uv run rig --am-bot inbox triage CAP-001

# Studio session
uv run rig --am-bot session start
uv run rig --am-bot session note "PH-3 confirmed before TR-2"
uv run rig --am-bot session discovery "RE-2 quiet on separate power"
uv run rig --am-bot session end

# Read CURRENT wiring at the rack
uv run rig --am-bot channels
uv run rig --am-bot gear list
uv run rig --am-bot gear show boss-rc-1
uv run rig --am-bot gear usage boss-rc-1
uv run rig --am-bot patchbay PB-B
uv run rig --am-bot path list
uv run rig --am-bot path show space
uv run rig --am-bot midi summary
uv run rig --am-bot midi links
uv run rig --am-bot midi channels
uv run rig --am-bot midi clock
uv run rig --am-bot controls summary
uv run rig --am-bot ableton targets
uv run rig --am-bot performance summary
uv run rig --am-bot performance preflight
uv run rig --am-bot automation capabilities
uv run rig --am-bot snapshot create
uv run rig --am-bot backup plan

# Physical reality changed (does not edit CURRENT docs)
uv run rig --am-bot change "Moved TR-2 after PH-3" --category PEDAL_CHAIN
uv run rig --am-bot changes list

# Supported CURRENT routing mutations (preview + confirm; inventory unchanged)
uv run rig --am-bot current path branches space
uv run rig --am-bot current path verify space
uv run rig --am-bot current path move space TR-2 --branch sy1-send --after PH-3 --dry-run
uv run rig --am-bot current path move space TR-2 --branch sy1-send --after PH-3
uv run rig --am-bot current gear set-condition big-muff ISSUE
uv run rig --am-bot current gear acquire "BOSS RC-600"
uv run rig --am-bot current midi verify
uv run rig --am-bot current controls verify behringer-fcb1010

uv run rig --am-bot render --check
uv run rig --am-bot check
```

- Canonical planning data: `data/todo.yaml`, `data/wishlist.yaml`, `data/inbox.yaml`, `data/open-questions.yaml`, `data/changes.yaml`.
- Session logs: `data/sessions/SES-*.yaml` (operational history, not CURRENT truth).
- Change captures: `data/changes.yaml` (`CHG-*`) — OPEN means the physical/logical rig may differ from documented CURRENT until reconciled.
- Questions: `data/open-questions.yaml` (`Q-*`) — unresolved facts. Resolving records an answer; it does **not** rewrite CURRENT.
- Do **not** hand-edit generated TODO/Wishlist/Questions Markdown sections.
- Do **not** hand-edit generated routing sections (`docs/current-routing.md`, `docs/pedal-chains.md`) or `diagrams/aux-send-loop.mmd`.
- `data/routing.yaml` is canonical for structured CURRENT audio/pedal topology (`named_paths`).
- Use `rig current path …` for supported structured routing mutations.
- `data/inventory.yaml` is canonical for owned equipment and stable gear IDs.
- Gear and unit IDs are exact references; do not fuzzy-match or casually rename them.
- Owned does not imply CURRENT routing membership. Inactive ownership states are
  forbidden while CURRENT routing still references an item or one of its units.
- Acquisition is an explicit transactional boundary: create inventory and mark the
  wishlist entry ACQUIRED together. Do not treat wishlist entries as owned beforehand.
- Do not invent inventory locations or infer patchbay unit-to-PB-letter mappings.
- Keep MIDI physical links, channel assignments, clock, and Ableton Track / Sync /
  Remote as separate evidence domains. `INTENDED` is not `VERIFIED`.
- Keep controller mappings in `data/controllers.yaml` and durable Ableton targets in
  `data/ableton.yaml`; neither overrides MIDI topology evidence.
- Separate physical control, emitted MIDI message, MIDI channel, target action, and
  evidence state. Do not infer targets from MIDI numbers. Do not fuzzy-match Ableton
  targets. Do not assign active mappings to BROKEN controls. Do not upgrade INTENDED
  mappings to VERIFIED without explicit verification.
- Do not invent MIDI ports, physical links, Ableton preference state, or controller
  switch/knob maps. Use `rig current midi ...` / `rig current controls ...` only from
  direct evidence.
- Keep `rig status` compact; inventory counts belong in `rig gear` / `rig doctor`.
- Do not infer a CURRENT route update from inbox observations, session discoveries, freeform OPEN changes, or unresolved questions.
- Use `rig change` when physical state may have changed but has not been reconciled.
- `next_session` is the authoritative Next Session queue; TODO status is lifecycle only (`READY`, `IN PROGRESS`, etc.). There is no `NEXT` status.
- `rig now` is deterministic: active session → IN PROGRESS → Next Session order → highest READY (P0–P3, YAML order) → Just Play. No LLM.
- Performance readiness is advisory and never gates `rig now --play`.
  - `NOT_READY`: a required action is missing, has zero bindings, or its sole binding uses a BROKEN control.
  - `PARTIAL`: required paths retain INTENDED/UNKNOWN evidence, imperfect bindings, unknown/true keyboard requirements for EMERGENCY recovery, or lack VERIFIED bindings.
  - `READY`: every required action has an AVAILABLE binding and all critical/emergency paths are VERIFIED.
- Do not bind BROKEN controls or upgrade INTENDED performance evidence to VERIFIED without direct verification.
- Preservation / Stage 11 rules:
  - Machine-local paths live only in gitignored `.rig.local.yaml` (see `.rig.local.example.yaml`).
  - Never commit `.rig.local.yaml`, `.rig/` snapshots/backups, or absolute user paths in canonical `data/*.yaml`.
  - `rig snapshot` copies top-level `data/*.yaml` only; it is not CURRENT physical truth and is not a git substitute.
  - `rig backup create` embeds a snapshot and copies configured FILE/DIRECTORY items; MANUAL_EXPORT stays operator-driven.
  - `rig performance simulate` / `preflight` must never connect to OBS, Ableton, MIDI, Stream Deck, send keys, or execute effects.
  - Do not invent fake automation adapters that return success for unimplemented families.
  - Broad `--snapshot-before` integration is deferred; use `uv run rig --am-bot snapshot create` manually.
  - Absence of local config is advisory, not a CI failure.
- Mutation commands write YAML and re-render docs unless `--no-render` is passed.
- No CLI mutation command commits or pushes Git.
- Prefer the CLI/service layer for planning mutations when practical.

### Interactive TUI (Stage 13+)

- `uv run rig tui` is a Textual presentation layer over the same services as the CLI.
  Do **not** launch `rig --am-bot tui` (rejected). Bots use noninteractive CLI only.
- TUI widgets must not parse CLI output and must not write YAML directly.
- Editable domains use FieldSpecs (`tui/fields.py`) + adapters under
  `tui/editable_domains/`; apply via Ctrl+S / :w review → service commit.
- Vim-like modes: NORMAL / INSERT / COMMAND (see [docs/tui.md](docs/tui.md)).
- Questions: **`a` = Answer**, **`A` = Add**, **`r`/`R` = Resolve**,
  **`V` = Verify**, **`C` = Reconcile**, **`Ctrl+r` = Refresh**.
  Answer may keep OPEN; Resolve requires answer. Neither invents
  `verification_result`.
- After resolve, CURRENT reconciliation is still required (`rig reconcile …`).
- Reconcile screen (`rig tui reconcile`): queue + plan/apply/verify/finalize via
  `music_rig.reconciliation.service` (same as CLI).
- Patchbays: mode (e/Space staged), connections, hardware_model (`m`); apply with
  Ctrl+S / :w. Related OPEN questions show `Q-xxx: <text>`.
- Also editable: TODO, wishlist, inbox, changes, gear, channels, routing, MIDI,
  controllers, Ableton metadata, performance evidence, backup plan fields.
- Snapshots / doctor / status / automation remain non-mutating views.
- Staged editors use source SHA-256 concurrency checks (no blind overwrite).
- Resolving a question still does **not** rewrite CURRENT or set `reconciled_at`.
- Screen/modal results are **single-shot**: one semantic completion per push;
  child screens return navigation intent (`AnswerResult`); the requester owns
  subsequent `push_screen` / `open_domain`. Never push a sibling then dismiss
  the child underneath it. See [docs/tui.md](docs/tui.md).
- Agent reconciliation: `uv run rig --am-bot agent packet|validate|apply` — agents propose
  allowlisted `RigOperation`s; the rig validates and dispatches. No YAML edits,
  no shell, no invented VERIFIED evidence. See root `SKILLS.md`.
- Agent guide: root `SKILLS.md` (CLI-first; do not automate TUI). Discovery:
  `uv run rig --am-bot inspect …`.
- Do not implement OBS/Ableton/MIDI/Stream Deck/macOS automation from the TUI;
  those families remain `NOT_IMPLEMENTED`.

### Evidence / truth hierarchy

```text
CURRENT
    reconciled authoritative repository state

OPEN CHANGE
    explicit report that physical/logical reality may differ from CURRENT

RESOLVED QUESTION
    answered factual uncertainty; may still require CURRENT reconciliation

SESSION DISCOVERY
    evidence observed during a session

INBOX
    untriaged observation

TODO
    accepted work, not factual truth

WISHLIST
    possible future capability, not factual truth
```

```text
Question = an unresolved factual uncertainty.
```

A resolved Question does not automatically alter CURRENT.
OPEN change records mean the physical rig may differ from documented CURRENT state.
Before treating CURRENT docs as unquestionably authoritative:
- inspect OPEN CHG records
- inspect OPEN questions for affected areas
- reconcile them if the task concerns those areas

Do not automatically apply captured changes.
Do not elevate discoveries to CURRENT facts without reconciliation.

Do not hand-edit generated CURRENT sections (`docs/patchbays.md`, channel maps, `docs/current-routing.md`, `docs/pedal-chains.md`, generated diagrams).

Canonical structured CURRENT sources include:
- `data/patchbays.yaml`
- `data/channel-map.yaml`
- `data/routing.yaml` (`named_paths` for pedal/audio topology)

For supported CURRENT mutations, prefer `uv run rig --am-bot current …` / the service layer.

OPEN Changes and Question answers are evidence.
They do not become CURRENT until reconciled.

Never infer a CURRENT update from freeform text.
Always preview; use `--dry-run` when unsure.

Do not infer a CURRENT route update from:
- inbox observations
- session discoveries
- freeform OPEN changes
- unresolved questions

Use `rig change` when physical state may have changed but has not been reconciled.

### Planning layers (do not collapse)

| Layer | Means | Does not mean |
|---|---|---|
| CURRENT docs | What is physically true now | What might be bought or tried later |
| Inventory | What is owned | That the device is in the active signal path |
| Open questions | Unknown facts | Approved work to resolve them |
| Wishlist | Ideas worth evaluating | Accepted tasks or purchase orders |
| Todo | Work accepted as worth doing | Speculative gear acquisition |
| Session log | What happened during a studio session | Automatic CURRENT updates |
| Change capture | Statement that reality may have changed | That CURRENT docs are already reconciled |
| Inbox | Unclassified observations | Confirmed routing facts |

```text
Session NOTE
    informal observation

Session DISCOVERY
    stronger evidence, but still not necessarily CURRENT

CHANGE (CHG-*)
    explicit statement that reality changed

CURRENT
    reconciled authoritative state
```

```text
Wishlist item
   ↓
evaluation
   ↓
accepted decision
   ↓
TODO item
```

Planned ideas, experiments, and wishlist entries must never override documented CURRENT physical state.

A device being **owned** does not mean it is currently in the signal chain.
A **proposed** or **experiment** route does not mean it is currently wired.

## Documentation discipline

- Keep [README.md](README.md), Markdown documentation in `docs/`, Mermaid diagrams in `diagrams/`, and YAML files in `data/` synchronized when the physical rig changes.
- Preserve historical troubleshooting information in [docs/troubleshooting.md](docs/troubleshooting.md); append or refine it rather than erasing useful failure history.
- Distinguish clearly between:
  - clean capture paths
  - the Alesis AUX SEND wet loop
  - the KAOSS Replay sampling and monitor path
  - patchbay connectivity
- Label state explicitly when needed: `CURRENT`, `AVAILABLE` / `OWNED`, `UNASSIGNED`, `UNKNOWN`, `PLANNED`, `EXPERIMENT`, `HISTORICAL`.
- Do not invent equipment, channels, connections, routing states, or resolved decisions.
- If the repository contains ambiguity or contradiction, call it out explicitly and resolve it only from repository evidence or new user-provided facts.
- When nothing in the repository confirms a fact, say that it is unknown.

## Routing guidance

- Treat the clean TASCAM captures, the AUX SEND creative loop, the KAOSS Replay path, and the patchbays as separate concepts in both prose and diagrams.
- Do not collapse wet and clean paths into a simplified diagram if that would hide an important distinction.
- Do not mark open questions as decided unless the repository has been updated to record the decision.
- Do not call dual mono "stereo." The JOYO path is mono until BOSS CH-1 provides the post-chain stereo output, unless device-specific docs prove otherwise.

## Change expectations

- When rig changes are documented, update every affected representation of that change instead of only one file.
- When nothing in the repository confirms a fact, say that it is unknown.
- When accepting work from the wishlist, create a TODO with Definition of Done; do not silently treat wishlist rows as commitments.

## Quality gates

- Install hooks once: `uv sync --extra dev` then `uv run pre-commit install`.
- Local / CI lint: `uv run pre-commit run --all-files` (ruff check --fix, ruff format, ryl check via system hooks).
- Ruff and ryl rule config live only in `pyproject.toml` — do not duplicate them in `.pre-commit-config.yaml`.
- Full pytest suite enforces **80%** coverage (`addopts` includes `--cov-fail-under=80`).
- Subset / debug runs: pass `--cov-fail-under=0` (and usually `-n0`), e.g. `uv run pytest path -n0 --cov-fail-under=0`.
