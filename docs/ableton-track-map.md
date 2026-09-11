# Ableton Track Map

<!-- rig:ableton:start -->
<!-- GENERATED FROM data/ableton.yaml BY `uv run rig render`. DO NOT EDIT THIS SECTION DIRECTLY. -->

## Tracks

| ID | Label | Evidence | Notes |
|---|---|---|---|
| drums | Drums | INTENDED | padKONTROL / Launchpad X MIDI ch10 — from docs/ableton-track-map.md |
| minikorg | miniKORG | INTENDED | TASCAM 3/4 |
| mixer | MIXER | INTENDED | Alesis main out → TASCAM 1/2 |
| kaoss | KAOSS | INTENDED | KAOSS Replay → TASCAM 9/10 |
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