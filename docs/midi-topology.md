# MIDI Topology

`data/midi.yaml` is the canonical structured source for MIDI endpoints, devices,
physical links, channels, clock, and Ableton port state.

Two DIN links are **VERIFIED** (Q-015): FCB1010 → U6MIDI Pro IN 1, and
U6MIDI Pro OUT 1 → Thru5 WC IN 1. Stage 27 HUMAN: Thru5 provides
**device-level THRU fanout** to SL-2, SR-18, miniKORG, and KAOSS.
Individual physical THRU socket assignment is intentionally **not tracked**.

A link appears in the generated table only when it is explicitly represented
in `connections`. Device-level fanout uses port label `THRU` → `UNSPECIFIED`
when the exact socket is not tracked.

<!-- rig:midi-topology:start -->
<!-- GENERATED FROM data/midi.yaml BY `uv run rig render`. DO NOT EDIT THIS SECTION DIRECTLY. -->

## Endpoints

| ID | Kind | Name |
|---|---|---|
| ableton | software | Ableton Live |
| macbook | host | MacBook |

## MIDI devices

| Gear ref | Role | Notes |
|---|---|---|
| cme-u6midi-pro | usb-midi-router | 3 in / 3 out; route / merge / filter / remap — OWNED. Q-015: receives FCB1010 on MIDI IN 1; sends to Thru5 WC on MIDI OUT 1. |
| cme-midi-thru5-wc | midi-thru | Hardware thru distribution — OWNED; not a programmable remapper. Q-015: fed from U6MIDI Pro OUT 1 into Thru5 WC IN 1. HUMAN (Stage 27): device-level THRU fanout to SL-2, SR-18, miniKORG, KAOSS. Individual physical THRU socket assignment intentionally not tracked. |
| tascam-us-16x08 | audio-interface-midi | May participate in MIDI paths; exact CURRENT use UNKNOWN |
| korg-minikorg | synth | HUMAN — receives Thru5 WC THRU fanout (device-level; exact THRU socket not tracked). Destination role: miniKORG. |
| kaoss-replay | sampler-effects | HUMAN — receives Thru5 WC THRU fanout (device-level; exact THRU socket not tracked). Destination role: KAOSS Replay. |
| boss-sl-2 | pedal | HUMAN — receives Thru5 WC THRU fanout (device-level; exact THRU socket not tracked). Destination role: SL-2. |
| alesis-sr-18 | drum-machine | HUMAN — receives Thru5 WC THRU fanout (device-level; exact THRU socket not tracked). Destination role: SR-18. |
| casio-privia | instrument | — |
| korg-padkontrol | controller | — |
| behringer-fcb1010 | foot-controller | USB Uno recognition unresolved (RIG-022); bank-00 map partially attested (Q-016) |
| novation-remote-zero-sl | controller | — |
| launchpad-x | controller | — |
| novation-launch-control-3 | controller | — |

## Physical links

| ID | Source / port | Destination / port | Transport | Evidence | Notes |
|---|---|---|---|---|---|
| midi-link-001 | behringer-fcb1010 / MIDI OUT | cme-u6midi-pro / MIDI IN 1 | DIN | VERIFIED | — |
| midi-link-002 | cme-u6midi-pro / MIDI OUT 1 | cme-midi-thru5-wc / MIDI IN 1 | DIN | VERIFIED | — |
| midi-link-003 | cme-midi-thru5-wc / THRU | boss-sl-2 / UNSPECIFIED | DIN | VERIFIED | Device-level fanout (HUMAN). Exact physical THRU jack intentionally not tracked. |
| midi-link-004 | cme-midi-thru5-wc / THRU | alesis-sr-18 / UNSPECIFIED | DIN | VERIFIED | Device-level fanout (HUMAN). Exact physical THRU jack intentionally not tracked. |
| midi-link-005 | cme-midi-thru5-wc / THRU | korg-minikorg / UNSPECIFIED | DIN | VERIFIED | Device-level fanout (HUMAN). Exact physical THRU jack intentionally not tracked. |
| midi-link-006 | cme-midi-thru5-wc / THRU | kaoss-replay / UNSPECIFIED | DIN | VERIFIED | Device-level fanout (HUMAN). Exact physical THRU jack intentionally not tracked. |
<!-- rig:midi-topology:end -->

## Evidence rules

- `VERIFIED` means directly confirmed.
- `INTENDED` describes a desired or planned setup, not current physical fact.
- `UNKNOWN` means the repository does not establish the fact.

Channel assignments, clock relationships, physical transport links, and Ableton
Track / Sync / Remote settings are separate facts and must be verified separately.
Controller switch and knob maps are outside this document.
