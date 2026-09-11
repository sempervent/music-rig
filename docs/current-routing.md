# Current Routing

Authoritative end-to-end overview of the **CURRENT** physical studio. For jack-level patchbay detail see [Patchbays](patchbays.md). For exact pedal topology see [Pedal Chains](pedal-chains.md).

## Stable TASCAM inputs

| TASCAM Input | Source | Notes |
|---:|---|---|
| 1/2 | Alesis mixer MAIN OUT L/R | Clean stereo mixer capture |
| 3/4 | miniKORG L/R | Direct stereo synth capture (also documented on PB-B) |
| 5 | Acoustic instrument clean | After BOSS acoustic preamp → A/B/Y clean leg |
| 6 | Bass clean | After BBox preamp → A/B/Y clean leg |
| 7 | Electric guitar clean | After Flamma preamp → A/B/Y clean leg |
| 8 | UNASSIGNED | — |
| 9/10 | KAOSS Replay L/R | Stereo KAOSS capture |
| 11/12 | Alesis SR-18 MAIN L/R | Drum machine direct (also documented on PB-B) |
| 13–16 | UNASSIGNED | — |

## Clean instrument paths (preamp → split → TASCAM)

Confirmed clean destinations only. The other A/B/Y leg for each instrument is **UNKNOWN** unless documented elsewhere.

```text
Acoustic  -> BOSS acoustic preamp -> A/B/Y -> clean leg -> TASCAM 5
Bass      -> BBox preamp          -> A/B/Y -> clean leg -> TASCAM 6
Electric  -> Flamma preamp        -> A/B/Y -> clean leg -> TASCAM 7
```

## Alesis mixer inputs

| Alesis Channel | Source | Status | Notes |
|---:|---|---|---|
| 1 | Bass | CURRENT (prior docs) | Can feed AUX SEND wet loop |
| 2 | Guitar | CURRENT (prior docs) | Can feed AUX SEND wet loop |
| 3 | — | UNASSIGNED | — |
| 4 | Electric kazoo | CURRENT (prior docs) | Can feed AUX SEND wet loop |
| 5/6 | Privia piano | CURRENT | Stereo; rear patch documented on PB-B 7/8 → 31/32 |
| 7/8 | — | UNASSIGNED sources | PB-B lower 33/34 connect to these channels; no upper-row sources documented |

## AUX SEND wet-processing path (CURRENT)

Creative wet loop. RC-1 sits ahead of the wah and JOYO branches so a captured phrase can be manipulated by downstream pedals.

```text
Alesis AUX SEND
  -> BOSS RC-1
  -> Cry Baby wah
  -> JOYO A/B/Bypass
       A = DIRTY
       B = SPACE
  -> BOSS CH-1 chorus
  -> stereo L/R back to Alesis return / stereo line input
```

JOYO routing up to CH-1 is **mono**. CH-1 provides the post-chain stereo output. Do not call dual mono "stereo."

Exact DIRTY and SPACE topologies: [Pedal Chains](pedal-chains.md).

## KAOSS Replay path (CURRENT)

Separate from clean capture and from the AUX SEND wet loop.

```text
Alesis Monitor Out
  -> KAOSS Replay
  -> TASCAM US-16x08 inputs 9/10
```

Treat KAOSS like its own instrument once sampled.

## Patchbay connectivity

Four 48-point 1/4-inch TRS patchbays: **PB-A**, **PB-B**, **PB-C**, **PB-D**.

Hardware owned: 2× ART Pro Audio P48, 2× Behringer PX3000. Mapping of model → PB letter is **UNKNOWN**.

Only **PB-B** currently has documented jack assignments. PB-A, PB-C, and PB-D are undocumented/unassigned. See [Patchbays](patchbays.md) and repository file `data/patchbays.yaml`.
