# Current Routing

Authoritative end-to-end overview of the **CURRENT** physical studio. For jack-level patchbay detail see [Patchbays](patchbays.md). For exact pedal topology see [Pedal Chains](pedal-chains.md).

## Stable TASCAM inputs

| TASCAM Input | Source | Notes |
|---:|---|---|
| 1/2 | Alesis mixer MAIN OUT L/R | Clean stereo mixer capture |
| 3/4 | miniKORG L/R | Direct stereo **input** capture (PB-B). Distinct from **TASCAM OUT 3/4**, which feeds KAOSS Replay. |
| 5 | Acoustic instrument clean | After BOSS acoustic preamp → A/B/Y clean leg |
| 6 | Bass clean | After BBox preamp → A/B/Y clean leg |
| 7 | Electric guitar clean | After Flamma preamp → A/B/Y clean leg |
| 8 | UNASSIGNED | — |
| 9/10 | UNASSIGNED | Formerly stale KAOSS return; cleared — KAOSS returns on 15/16 |
| 11/12 | Alesis SR-18 MAIN L/R | Drum machine direct (also documented on PB-B) |
| 13/14 | UNASSIGNED | — |
| 15/16 | KAOSS Replay L/R | Stereo KAOSS return (**TASCAM IN 15/16**), fed from **TASCAM OUT 3/4** |

## Alesis mixer inputs

| Alesis Channel | Source | Status | Notes |
|---:|---|---|---|
| 1 | Bass | CURRENT | Non-clean A/B/Y leg (Q-001); can feed AUX SEND wet loop |
| 2 | Acoustic | CURRENT | Non-clean A/B/Y leg (Q-001); can feed AUX SEND wet loop |
| 3 | Electric | CURRENT | Non-clean A/B/Y leg (Q-001) |
| 4 | Electric kazoo | CURRENT (prior docs) | Can feed AUX SEND wet loop |
| 5/6 | Privia piano | CURRENT | Stereo; rear patch documented on PB-B 7/8 → 31/32 |
| 7/8 | — | UNASSIGNED sources | PB-B lower 33/34 connect to these channels; no upper-row sources documented |

The sections below project structured CURRENT paths from `data/routing.yaml`. Conceptual distinctions between **clean capture**, the **AUX SEND wet loop**, and the **KAOSS path** remain intentional.

JOYO routing up to CH-1 is **mono**. CH-1 provides the post-chain stereo output. Do not call dual mono "stereo."

<!-- rig:routing:start -->
<!-- GENERATED FROM data/routing.yaml BY `uv run rig render`. DO NOT EDIT THIS SECTION DIRECTLY. -->

## Named CURRENT paths (from `data/routing.yaml`)

### Clean capture

**Clean mixer capture** (`clean_mixer`)

```text
Alesis Main Out
-> TASCAM 1/2
```

**Acoustic clean capture** (`acoustic`)

```text
Acoustic instrument
-> BOSS acoustic preamp
  -> A/B/Y clean leg
  -> TASCAM 5
  other A/B/Y leg
    -> Alesis 2
```

**Bass clean capture** (`bass`)

```text
Bass
-> BBox preamp
  -> A/B/Y clean leg
  -> TASCAM 6
  other A/B/Y leg
    -> Alesis 1
```

**Electric guitar clean capture** (`electric`)

```text
Electric guitar
-> Flamma preamp
  -> A/B/Y clean leg
  -> TASCAM 7
  other A/B/Y leg
    -> Alesis 3
```

**miniKORG direct capture** (`minikorg`)

```text
miniKORG stereo out
-> PB-B
-> TASCAM 3/4
```

**SR-18 direct capture** (`sr18`)

```text
Alesis SR-18 MAIN L/R
-> PB-B
-> TASCAM 11/12
```

### AUX SEND wet-processing path

```text
Alesis AUX SEND
-> BOSS RC-1
-> Cry Baby
-> JOYO A/B/Bypass
  A = DIRTY (see: rig path show dirty)
  B = SPACE (see: rig path show space)
  -> BOSS CH-1 stereo out
  -> Alesis Return 1 and 2
```

Exact DIRTY and SPACE topologies: [Pedal Chains](pedal-chains.md) or `rig path show dirty` / `rig path show space`.

### KAOSS Replay path

```text
TASCAM OUT 3/4
-> KAOSS Replay
-> TASCAM IN 15/16
```
<!-- rig:routing:end -->

## Patchbay connectivity

Four 48-point 1/4-inch TRS patchbays: **PB-A**, **PB-B**, **PB-C**, **PB-D**.

Hardware owned: 2× ART Pro Audio P48, 2× Behringer PX3000. Mapping of model → PB letter is **UNKNOWN**.

Only **PB-B** currently has documented jack assignments. PB-A, PB-C, and PB-D are undocumented/unassigned. See [Patchbays](patchbays.md) and repository file `data/patchbays.yaml`.
