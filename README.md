# Music Rig

Living documentation for a one-human, many-machines home studio routing system: Alesis mixer, TASCAM US-16x08, Ableton Live, KAOSS Replay, BOSS RC-1, miniKORG, Privia, SR-18, pedal loops, patchbays, DI/reamp utilities, MIDI sync, and troubleshooting notes.

Documentation site: https://sempervent.github.io/music-rig/

This repo is intended to be the authoritative source for:

- current signal flow
- channel maps
- patchbay jack maps
- pedal-chain inventory vs active topology
- accepted TODO work vs speculative wishlist
- MIDI clock strategy
- Ableton track naming
- troubleshooting history
- planned upgrades and experiments (wishlist only until accepted into TODO)

## Current high-level architecture

```mermaid
flowchart LR
  subgraph Sources
    Acoustic[Acoustic]
    Bass[Bass]
    Electric[Electric Guitar]
    Kazoo[Electric Kazoo]
    Privia[Privia Piano]
    MiniKORG[miniKORG]
    SR18[Alesis SR-18]
  end

  subgraph Mixer[Alesis Mixer]
    A1[Ch 1 Bass]
    A2[Ch 2 Guitar]
    A4[Ch 4 Electric Kazoo]
    A56[Ch 5/6 Privia]
    Aux[AUX SEND]
    Main[Main Out]
    Monitor[Monitor Out]
    Return[Stereo Return / Line Return]
  end

  subgraph WetLoop[Aux Send Wet Loop]
    RC1[BOSS RC-1]
    CryBaby[Cry Baby]
    JOYO[JOYO A/B Router]
    Pedals[DIRTY / SPACE]
    CH1[BOSS CH-1 Stereo Out]
  end

  subgraph Recorder[TASCAM US-16x08]
    T12[1/2 Clean Mixer Out]
    T34[3/4 miniKORG]
    T5[5 Acoustic Clean]
    T6[6 Bass Clean]
    T7[7 Electric Clean]
    T910[9/10 KAOSS Replay]
    T1112[11/12 SR-18]
  end

  Bass --> A1
  Electric --> A2
  Kazoo --> A4
  Privia --> A56
  MiniKORG --> T34
  SR18 --> T1112
  Acoustic --> T5
  Bass --> T6
  Electric --> T7
  A1 --> Aux
  A2 --> Aux
  A4 --> Aux
  A56 --> Aux
  Aux --> RC1 --> CryBaby --> JOYO --> Pedals --> CH1 --> Return
  Main --> T12
  Monitor --> KAOSS[KAOSS Replay] --> T910
```

Clean paths use preamp → A/B/Y before the confirmed TASCAM clean legs (5/6/7). AUX SEND order is RC-1 → Cry Baby → JOYO. Patchbay detail: [docs/patchbays.md](docs/patchbays.md).

## Docs

- [Current routing](docs/current-routing.md)
- [Inventory](docs/inventory.md)
- [Patchbays](docs/patchbays.md)
- [Todo](docs/todo.md) — accepted work only (canonical: `data/todo.yaml`)
- [Wishlist](docs/wishlist.md) — speculative / evaluative, not commitments (canonical: `data/wishlist.yaml`)
- [TASCAM channel map](docs/tascam-channel-map.md)
- [Alesis mixer map](docs/alesis-mixer-map.md)
- [Pedal chains](docs/pedal-chains.md)
- [Ableton track map](docs/ableton-track-map.md)
- [Controller mappings](docs/controller-mappings.md)
- [Performance](docs/performance.md)
- [Live recovery](docs/live-recovery.md)
- [Backups](docs/backups.md)
- [Automation readiness](docs/automation-readiness.md)
- [MIDI topology](docs/midi-topology.md)
- [MIDI clock and controller notes](docs/midi-clock.md)
- [Reamp and DI notes](docs/reamp-and-di.md)
- [Troubleshooting log](docs/troubleshooting.md)
- [Open questions](docs/open-questions.md) — unresolved facts

## Planning CLI (`rig`)

Canonical planning and studio-ops data:

```text
data/todo.yaml            = canonical TODO data
data/inventory.yaml       = canonical owned-equipment identities
data/wishlist.yaml        = canonical wishlist data
data/inbox.yaml           = uncategorized capture inbox
data/changes.yaml         = physical/logical change captures (not auto-CURRENT)
data/open-questions.yaml  = unresolved factual questions (canonical)
data/controllers.yaml     = canonical controller mapping evidence
data/ableton.yaml         = durable Ableton mapping targets
data/performance.yaml     = PFL performance modes, actions, bindings, and recovery
data/control-surfaces.yaml = non-MIDI performance control surfaces
data/backups.yaml         = canonical backup / archive plan (no absolute paths)
data/sessions/            = studio session logs (one YAML file per session)
.rig.local.example.yaml   = template for machine-local path locators (copy to `.rig.local.yaml`)
docs/todo.md              = human-facing rendered representation
docs/wishlist.md          = human-facing rendered representation
docs/open-questions.md    = human-facing questions (generated section)
docs/backups.md           = generated backup plan
docs/automation-readiness.md = generated automation capability honesty
```

Do not manually edit the generated marker sections in the Markdown files.
Inbox captures, session discoveries, OPEN changes, and OPEN questions are not CURRENT routing truth until reconciled into docs/data.
Never commit `.rig.local.yaml`, `.rig/` snapshots, or absolute user paths in canonical YAML.

```bash
uv sync --extra dev --extra docs
uv run rig --help
uv run rig status

# What should I do?
uv run rig now
uv run rig now --play

# Unknown facts
uv run rig question list
uv run rig question show Q-008
uv run rig question resolve Q-008
uv run rig question todo Q-008

# What still needs reconciliation?
uv run rig reconcile
uv run rig reconcile change CHG-001
uv run rig reconcile question Q-008

# Begin working
uv run rig session start
uv run rig session status

# See current wiring
uv run rig channels
uv run rig gear list
uv run rig gear show boss-rc-1
uv run rig gear usage boss-rc-1
uv run rig patchbay list
uv run rig patchbay PB-B
uv run rig path list
uv run rig path show space
uv run rig midi summary
uv run rig midi devices
uv run rig midi links
uv run rig midi channels
uv run rig midi clock
uv run rig midi ableton
uv run rig controls summary
uv run rig controls show behringer-fcb1010
uv run rig controls context behringer-fcb1010 bank-00
uv run rig controls gaps
uv run rig controls conflicts
uv run rig ableton targets

# Evidence vs CURRENT truth
# I noticed something:        rig capture / rig change
# I verified CURRENT truth:   rig current ...
# What is unresolved:         rig reconcile
# Maintenance advice:         rig doctor

# Verify PB-B physically (transactional)
uv run rig current patchbay verify PB-B

# Record one exact mode (preview first)
uv run rig current patchbay set-mode PB-B 1 half-normal --dry-run
uv run rig current patchbay set-mode PB-B 1 half-normal --question Q-008

# Channel source assignment
uv run rig current channels set-source tascam 8 "Spare DI"
uv run rig current channels clear-source tascam 8

# CURRENT routing / pedal topology
uv run rig path show space
uv run rig current path branches space
uv run rig current path verify space
uv run rig current path move space TR-2 --branch sy1-send --after PH-3 --dry-run
uv run rig current path move space TR-2 --branch sy1-send --after PH-3
uv run rig change "TR-2 may have moved" --category PEDAL_CHAIN

# Maintain owned gear (preview + confirmation)
uv run rig current gear add
uv run rig current gear set-condition big-muff ISSUE
uv run rig current gear set-location boss-rc-1 "<verified location>"
uv run rig current gear retire flamma-mod

# Cross the explicit wishlist → inventory acquisition boundary
uv run rig current gear acquire "BOSS RC-600"
# `rig current gear acquire` does not purchase equipment.
# It records that equipment has already been acquired and updates repository state.

# Verify and maintain MIDI facts independently
uv run rig current midi set-channel casio-privia 1 --dry-run
uv run rig current midi add-link --source <ref> --source-port <port> \
  --destination <ref> --destination-port <port> --transport DIN --dry-run
uv run rig current midi set-clock-master ableton --question Q-014
uv run rig current midi set-clock korg-minikorg unknown
uv run rig current midi ableton-set <port-id> --track on --remote on
uv run rig current midi verify
uv run rig current controls verify behringer-fcb1010

uv run rig performance readiness
uv run rig performance plan panic
uv run rig performance simulate panic
uv run rig performance preflight --mode pfl-jam
uv run rig automation capabilities

# Snapshots vs git vs backup packages
# - git: version history for the repo
# - rig snapshot: dated copy of data/*.yaml under .rig/snapshots (gitignored)
# - rig backup: archive package with embedded snapshot + configured file copies
uv run rig snapshot create
uv run rig snapshot list
uv run rig snapshot show SNAP-YYYYMMDD-HHMMSS
uv run rig snapshot diff SNAP-A current
uv run rig snapshot verify SNAP-YYYYMMDD-HHMMSS
uv run rig backup plan
uv run rig backup status
uv run rig backup create --output /path/to/archive

# Broad `--snapshot-before` on mutation commands is deferred; run
# `uv run rig snapshot create` manually before risky changes.

# While working
uv run rig session note "PH-3 confirmed before TR-2"
uv run rig session discovery "RE-2 quiet on separate power"
uv run rig session capture "Maybe try Privia into miniKORG"

# Physical rig changed
uv run rig change "Moved pedal X after pedal Y" --category PEDAL_CHAIN
uv run rig changes list

# End
uv run rig session end

# Maintenance overview
uv run rig doctor

uv run rig todo list
uv run rig wish list
uv run rig capture "Something weird happened"

uv run rig render
uv run rig render --check
uv run rig check
```

Mutation commands write YAML and re-render Markdown unless `--no-render` is passed.
`rig change` / `rig question resolve` record evidence; they do not rewrite CURRENT routing.
`rig current …` modifies authoritative CURRENT state (typed, previewed, confirm by default).
Inventory IDs are stable exact references. Owned gear is not necessarily in CURRENT
routing; routed gear cannot be retired, sold, or loaned out until those references
are removed. Wishlist items become owned only through the acquisition workflow,
which writes inventory and wishlist state transactionally.
`rig now` is deterministic and explainable (no LLM).
`rig doctor` is advisory; `rig check` remains the CI gate.
No CLI command commits or pushes Git.

Performance readiness is also advisory and never blocks `rig now --play`:
`NOT_READY` means a required action is missing/unbound or solely bound to a BROKEN
control; `PARTIAL` means evidence or hands-off recovery remains incomplete; `READY`
requires AVAILABLE bindings and VERIFIED critical/emergency paths. INTENDED evidence
must not be promoted to VERIFIED without direct verification.

`rig performance simulate` always prints
`SIMULATION — NO EXTERNAL ACTIONS WILL BE EXECUTED` and never connects to OBS,
Ableton, MIDI, Stream Deck, or sends keys. `rig performance preflight` is optional
setup advice only.

Snapshots preserve canonical YAML; they are not CURRENT physical truth and are not a
git substitute. Backup packages embed a snapshot and copy only FILE_COPY /
DIRECTORY_COPY items whose local paths are configured; MANUAL_EXPORT items stay
operator-driven.

MIDI physical links, channel assignments, clock state, and Ableton Track / Sync /
Remote settings are separate evidence domains. `INTENDED` records design intent;
it must never be read or promoted as `VERIFIED` without direct evidence.

## Documentation CI/CD

- CI runs pytest, `rig check`, `rig render --check`, channel-map print, and `mkdocs build --strict`.
- Pushes to `main` also deploy the MkDocs site to GitHub Pages.
- Local validation:

```bash
uv sync --locked --extra dev --extra docs
uv run pytest
uv run rig check
uv run rig render --check
uv run python scripts/print_channel_map.py
uv run mkdocs build --strict
```

- Local preview:

```bash
uv run mkdocs serve
```
