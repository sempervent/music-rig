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
- [Todo](docs/todo.md) — accepted work only
- [Wishlist](docs/wishlist.md) — speculative / evaluative, not commitments
- [TASCAM channel map](docs/tascam-channel-map.md)
- [Alesis mixer map](docs/alesis-mixer-map.md)
- [Pedal chains](docs/pedal-chains.md)
- [Ableton track map](docs/ableton-track-map.md)
- [MIDI clock and controller notes](docs/midi-clock.md)
- [Reamp and DI notes](docs/reamp-and-di.md)
- [Troubleshooting log](docs/troubleshooting.md)
- [Open questions](docs/open-questions.md) — unresolved facts

## Documentation CI/CD

- Pull requests that change documentation-related files run `mkdocs build --strict`.
- Pushes to `main` and manual workflow runs build the site and deploy it to GitHub Pages.
- Local validation:

```bash
python -m pip install -r requirements-docs.txt
mkdocs build --strict
```

- Local preview:

```bash
mkdocs serve
```

## Local docs preview

This repo is MkDocs-ready:

```bash
python -m pip install -r requirements-docs.txt
mkdocs serve
```
