# Controller Mappings

Canonical mapping intent and evidence from `data/controllers.yaml`. This is separate
from physical MIDI topology and channel/clock evidence in `data/midi.yaml`.

`INTENDED` is design intent, not physical or software verification. Empty contexts
and controls are left explicit instead of inventing assignments.

<!-- rig:controllers:start -->
<!-- GENERATED FROM data/controllers.yaml BY `uv run rig render`. DO NOT EDIT THIS SECTION DIRECTLY. -->

## Coverage

| Controller | Coverage | Contexts | Modeled controls | Evidence |
|---|---|---:|---:|---|
| behringer-fcb1010 | PARTIAL | 3 | 2 | INTENDED |
| novation-remote-zero-sl | PARTIAL | 8 | 2 | INTENDED, VERIFIED |
| novation-launch-control-3 | PARTIAL | 1 | 0 | INTENDED |
| korg-padkontrol | PARTIAL | 1 | 1 | INTENDED |
| launchpad-x | UNKNOWN | 0 | 0 | — |

## behringer-fcb1010

Channel 16 INTENDED. Q-016 HUMAN (bank 00): switches select/arm tracks 1–10 and their respective audio group control. Banks 01/02 still unobserved. EXP A/B CC numbers are documented intent; Ableton targets UNKNOWN.

| Context | Kind | Control | Type | Availability | Message | Target | Evidence | Notes |
|---|---|---|---|---|---|---|---|---|
| bank-00 | BANK | exp-a | EXPRESSION | AVAILABLE | CC 111 ch DEVICE (range) | UNKNOWN | INTENDED | — |
| bank-00 | BANK | exp-b | EXPRESSION | AVAILABLE | CC 112 ch DEVICE (range) | UNKNOWN | INTENDED | — |
| bank-01 | BANK | — | — | — | — | UNKNOWN | INTENDED | Bank role INTENDED; footswitch assignments not modeled until confirmed |
| bank-02 | BANK | — | — | — | — | UNKNOWN | INTENDED | Bank role INTENDED; footswitch assignments not modeled until confirmed |

## novation-remote-zero-sl

Templates listed as design direction (RIG-036). Stage 25 HUMAN observation for Q-017: templates have no names visible → UNKNOWN. Encoder #6 is physically broken — do not assign active mappings to it.

| Context | Kind | Control | Type | Availability | Message | Target | Evidence | Notes |
|---|---|---|---|---|---|---|---|---|
| pfl-send-c | TEMPLATE | pad-08 | PAD | AVAILABLE | — | ABLETON_ACTION: template-home | INTENDED | PAD 8 → HOME (RIG-036); MIDI message unknown |
| pfl-send-c | TEMPLATE | encoder-06 | ENCODER | BROKEN | — | UNASSIGNED | VERIFIED | Physically broken — no active mapping |
| reverb-fx | TEMPLATE | — | — | — | — | UNKNOWN | INTENDED | — |
| delay-send | TEMPLATE | — | — | — | — | UNKNOWN | INTENDED | — |
| midi-gen | TEMPLATE | — | — | — | — | UNKNOWN | INTENDED | — |
| mastering | TEMPLATE | — | — | — | — | UNKNOWN | INTENDED | — |
| quant | TEMPLATE | — | — | — | — | UNKNOWN | INTENDED | — |
| fx | TEMPLATE | — | — | — | — | UNKNOWN | INTENDED | — |
| chaos | TEMPLATE | — | — | — | — | UNKNOWN | INTENDED | — |

## novation-launch-control-3

Primary direction is Ableton Send D across active performance tracks (RIG-034). Exact knob/button assignments not invented — verify live set first (Q-018 / RIG-038).

| Context | Kind | Control | Type | Availability | Message | Target | Evidence | Notes |
|---|---|---|---|---|---|---|---|---|
| performance | MODE | — | — | — | — | UNKNOWN | INTENDED | Context intent only; individual controls unmodeled until RIG-034 completes |

## korg-padkontrol

MIDI ch10 for drums. Footswitch has been used for Ableton clip-record via Max for Live. Two-press stop issue not documented as solved (RIG-039) — mapping INTENDED, not VERIFIED success.

| Context | Kind | Control | Type | Availability | Message | Target | Evidence | Notes |
|---|---|---|---|---|---|---|---|---|
| global | GLOBAL | footswitch | FOOTSWITCH | AVAILABLE | — | ABLETON_ACTION: clip-record | INTENDED | Clip-record control via M4L. Prior workflow required two presses to stop; behavior imperfect until RIG-039. |

## launchpad-x

Owned and used with Ableton recording/control. No custom mapping documented in repo — do not invent pad/note maps.

| Context | Kind | Control | Type | Availability | Message | Target | Evidence | Notes |
|---|---|---|---|---|---|---|---|---|
| — | — | — | — | — | — | UNKNOWN | UNKNOWN | No contexts modeled |
<!-- rig:controllers:end -->
