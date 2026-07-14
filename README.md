# Music Rig

Living documentation for a one-human, many-machines home studio routing system: Alesis mixer, TASCAM US-16x08, Ableton Live, KAOSS Replay, BOSS RC-1, miniKORG, Privia, pedal loops, DI/reamp utilities, MIDI sync, and troubleshooting notes.

Documentation site: https://sempervent.github.io/music-rig/

This repo is intended to be the authoritative source for:

- current signal flow
- channel maps
- pedal-chain inventory
- MIDI clock strategy
- Ableton track naming
- troubleshooting history
- planned upgrades and experiments

## Current high-level architecture

```mermaid
flowchart LR
  subgraph Sources
    Bass[Bass]
    Guitar[Guitar]
    Kazoo[Electric Kazoo]
    Privia[Privia Piano]
    MiniKORG[miniKORG]
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
    CryBaby[Cry Baby]
    RC1[BOSS RC-1]
    JOYO[JOYO A/B Router]
    Pedals[Pedal Chains A/B]
    CH1[BOSS CH-1 Stereo Out]
  end

  subgraph Recorder[TASCAM US-16x08]
    T12[1/2 Clean Mixer Out]
    T34[3/4 miniKORG]
    T5[5 Clean Guitar]
    T7[7 Clean Bass]
    T910[9/10 KAOSS Replay]
  end

  Bass --> A1
  Guitar --> A2
  Kazoo --> A4
  Privia --> A56
  MiniKORG --> T34
  A1 --> Aux
  A2 --> Aux
  A4 --> Aux
  A56 --> Aux
  Aux --> CryBaby --> RC1 --> JOYO --> Pedals --> CH1 --> Return
  Main --> T12
  Monitor --> KAOSS[KAOSS Replay] --> T910
```

## Docs

- [Current routing](docs/current-routing.md)
- [Inventory](docs/inventory.md)
- [TASCAM channel map](docs/tascam-channel-map.md)
- [Alesis mixer map](docs/alesis-mixer-map.md)
- [Pedal chains](docs/pedal-chains.md)
- [Ableton track map](docs/ableton-track-map.md)
- [MIDI clock and controller notes](docs/midi-clock.md)
- [Reamp and DI notes](docs/reamp-and-di.md)
- [Troubleshooting log](docs/troubleshooting.md)
- [Open questions](docs/open-questions.md)

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
