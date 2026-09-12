# Ableton Track Map

<!-- rig:ableton:start -->
<!-- GENERATED FROM data/ableton.yaml BY `uv run rig render`. DO NOT EDIT THIS SECTION DIRECTLY. -->

## Tracks

| ID | Label | Evidence | Notes |
|---|---|---|---|
| drums | Drums | INTENDED | padKONTROL / Launchpad X MIDI ch10 — from docs/ableton-track-map.md |
| minikorg | miniKORG | INTENDED | TASCAM 3/4 |
| mixer | MIXER | INTENDED | Alesis main out → TASCAM 1/2 |
| kaoss | KAOSS | INTENDED | TASCAM OUT 3/4 → KAOSS Replay → TASCAM IN 15/16 |
| acoustic-clean | ACOUSTIC CLEAN | INTENDED | TASCAM 5 |
| bass-clean | BASS CLEAN | INTENDED | TASCAM 6 |
| guitar-clean | GUITAR CLEAN | INTENDED | TASCAM 7 |
| sr18 | SR-18 | INTENDED | TASCAM 11/12 |
| kaoss-privia | KAOSS - Privia | INTENDED | — |
| kaoss-kazoo | KAOSS - Kazoo | INTENDED | — |
| kaoss-bass | KAOSS - Bass | INTENDED | — |
| kaoss-guitar | KAOSS - Guitar | INTENDED | — |

## Sends

| ID | Label | Evidence | Notes |
|---|---|---|---|
| send-a | Send A | INTENDED | — |
| send-b | Send B | INTENDED | — |
| send-c | Send C | INTENDED | ZeRO PFL SEND C design direction (RIG-036) |
| send-d | Send D | INTENDED | Launch Control 3 primary performance direction (RIG-034) |

## Actions

| ID | Label | Evidence | Notes |
|---|---|---|---|
| clip-record | Clip Record | INTENDED | padKONTROL footswitch / M4L target (RIG-039) |
| scene-launch | Scene Launch | INTENDED | FCB bank-02 design direction (RIG-035) |
| track-arm | Track Arm | INTENDED | FCB bank-00 design direction (RIG-035) |
| template-home | Template HOME | INTENDED | ZeRO PAD 8 → HOME (RIG-036) |

## Templates

| ID | Label | Tracks | Sends | Requirements | Evidence | Notes |
|---|---|---:|---:|---|---|---|
| pfl-jam | PFL JAM | 8 | 2 | hands-off-core, pfl-jam-record-ready | INTENDED | Structural expectations for a turn-on-and-play jam set. Exact live-set contents remain open (Q-018 / RIG-038). |

### PFL JAM tracks

| Track | Role | Active | Record ready |
|---|---|---|---|
| drums | midi-source | true | unknown |
| minikorg | audio-source | true | unknown |
| mixer | clean-bus | true | unknown |
| kaoss | wet-source | true | unknown |
| acoustic-clean | clean-source | true | unknown |
| bass-clean | clean-source | true | unknown |
| guitar-clean | clean-source | true | unknown |
| sr18 | audio-source | true | unknown |

| Send | Role | Notes |
|---|---|---|
| send-c | performance-send | ZeRO PFL SEND C direction |
| send-d | performance-send | Launch Control 3 direction |
<!-- rig:ableton:end -->

## Clip naming convention

Use this pattern:

```text
YYYY-MM-DD_source_device_bpm_key_take-description
```

Examples:

```text
2026-07-13_bass_kaoss_92bpm_Am_take01_swamp-pulse
2026-07-13_privia_rc1_110bpm_Dm_take03_half-lit-loop
```

## Performance mapping notes

Launch Control 3 Send D mapping and exact live-set track list are TODO RIG-034 / RIG-038. Do not invent track names here that conflict with the live Ableton set — verify the set first, then update this table.