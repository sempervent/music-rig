# AGENTS.md

Operational instructions for Codex sessions working in this repository.

## Role of this repository

This repository is the durable source of truth for the ChatGPT Project named `jng - the music setup`.
Use the repository itself as the source of remembered state, not chat memory or guessed context.

## Required workflow

1. Inspect the existing repository documentation before answering questions, proposing changes, or modifying files.
2. Treat the source-of-truth hierarchy below as authoritative for CURRENT physical state.
3. Cross-check routing, inventory, diagrams, and YAML data before stating that a connection, device role, or channel assignment is current.

## Source-of-truth hierarchy

| Layer | File | Role |
|---|---|---|
| Overview | [docs/current-routing.md](docs/current-routing.md) | End-to-end physical CURRENT routing |
| Routes | [data/routing.yaml](data/routing.yaml) | Machine-readable high-level routes |
| Channels | [data/channel-map.yaml](data/channel-map.yaml) | Interface and mixer channel assignments |
| Patchbays | [data/patchbays.yaml](data/patchbays.yaml) | Physical patchbay jack assignments and normalization state |
| Patchbay ops | [docs/patchbays.md](docs/patchbays.md) | Human-readable patchbay reference at the rack |
| Pedals | [docs/pedal-chains.md](docs/pedal-chains.md) | Exact CURRENT active pedal topology |
| Inventory | [docs/inventory.md](docs/inventory.md) / [data/inventory.yaml](data/inventory.yaml) | Equipment ownership and role — not necessarily current signal-path membership |
| Diagrams | [diagrams/](diagrams/) | Visual projections of the same authoritative state |
| Todo (canonical) | [data/todo.yaml](data/todo.yaml) | Structured accepted work — edit this, not generated Markdown sections |
| Todo (rendered) | [docs/todo.md](docs/todo.md) | Human-facing TODO view; generated section owned by `uv run rig render` |
| Wishlist (canonical) | [data/wishlist.yaml](data/wishlist.yaml) | Structured speculative desires |
| Wishlist (rendered) | [docs/wishlist.md](docs/wishlist.md) | Human-facing wishlist view; generated section owned by `uv run rig render` |
| Inbox | [data/inbox.yaml](data/inbox.yaml) | Uncategorized captures — observations only, not CURRENT truth |
| Changes | [data/changes.yaml](data/changes.yaml) | Structured “reality may have changed” records — not auto-CURRENT |
| Sessions | [data/sessions/](data/sessions/) | Studio session logs — operational history |
| Open questions | [docs/open-questions.md](docs/open-questions.md) | Unresolved facts — not tasks (still Markdown-only) |

### Planning CLI

```bash
uv sync --extra dev --extra docs
uv run rig status
uv run rig doctor

# Work
uv run rig todo start RIG-001
uv run rig todo done RIG-001

# Plan next studio session
uv run rig todo next list
uv run rig todo next set RIG-002 RIG-038 RIG-046

# Wishlist
uv run rig wish list
uv run rig wish promote "PFL Eurorack v1"

# Capture now, classify later
uv run rig capture "RE-2 noisy after DD-8"
uv run rig inbox list
uv run rig inbox triage CAP-001

# Studio session
uv run rig session start
uv run rig session note "PH-3 confirmed before TR-2"
uv run rig session discovery "RE-2 quiet on separate power"
uv run rig session end

# Read CURRENT wiring at the rack
uv run rig channels
uv run rig patchbay PB-B
uv run rig path list
uv run rig path show space

# Physical reality changed (does not edit CURRENT docs)
uv run rig change "Moved TR-2 after PH-3" --category PEDAL_CHAIN
uv run rig changes list

uv run rig render --check
uv run rig check
```

- Canonical planning data: `data/todo.yaml`, `data/wishlist.yaml`, `data/inbox.yaml`.
- Session logs: `data/sessions/SES-*.yaml` (operational history, not CURRENT truth).
- Change captures: `data/changes.yaml` (`CHG-*`) — OPEN means the physical/logical rig may differ from documented CURRENT until reconciled.
- Do **not** hand-edit generated TODO/Wishlist Markdown sections.
- `next_session` is the authoritative Next Session queue; TODO status is lifecycle only (`READY`, `IN PROGRESS`, etc.). There is no `NEXT` status.
- Mutation commands write YAML and re-render docs unless `--no-render` is passed.
- No CLI mutation command commits or pushes Git.
- Inbox captures and session discoveries are observations, not confirmed CURRENT rig truth.
- Change records are not applied automatically; mark APPLIED only after CURRENT docs/data are reconciled.
- Open questions remain human-maintained Markdown for now.
- Prefer the CLI/service layer for planning mutations when practical.

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

Agents must preserve these distinctions.

OPEN change records mean the physical rig may differ from documented CURRENT state.
Before treating CURRENT docs as unquestionably authoritative:
- inspect OPEN CHG records
- reconcile them if the task concerns affected areas

Do not automatically apply captured changes.
Do not elevate discoveries to CURRENT facts without reconciliation.

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
