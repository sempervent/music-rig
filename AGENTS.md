# AGENTS.md

Operational instructions for Codex sessions working in this repository.

## Role of this repository

This repository is the durable source of truth for the ChatGPT Project named `jng - the music setup`.
Use the repository itself as the source of remembered state, not chat memory or guessed context.

## Required workflow

1. Inspect the existing repository documentation before answering questions, proposing changes, or modifying files.
2. Treat [docs/current-routing.md](docs/current-routing.md) as the current wiring truth unless newer repository documentation explicitly supersedes it.
3. Cross-check routing, inventory, diagrams, and YAML data before stating that a connection, device role, or channel assignment is current.

## Documentation discipline

- Keep [README.md](README.md), Markdown documentation in `docs/`, Mermaid diagrams in `diagrams/`, and YAML files in `data/` synchronized when the physical rig changes.
- Preserve historical troubleshooting information in [docs/troubleshooting.md](docs/troubleshooting.md); append or refine it rather than erasing useful failure history.
- Distinguish clearly between:
  - clean capture paths
  - the Alesis AUX SEND wet loop
  - the KAOSS Replay sampling and monitor path
- Do not invent equipment, channels, connections, routing states, or resolved decisions.
- If the repository contains ambiguity or contradiction, call it out explicitly and resolve it only from repository evidence or new user-provided facts.

## Routing guidance

- Treat the clean TASCAM captures, the AUX SEND creative loop, and the KAOSS Replay path as separate concepts in both prose and diagrams.
- Do not collapse wet and clean paths into a simplified diagram if that would hide an important distinction.
- Do not mark open questions as decided unless the repository has been updated to record the decision.

## Change expectations

- When rig changes are documented, update every affected representation of that change instead of only one file.
- When nothing in the repository confirms a fact, say that it is unknown.
