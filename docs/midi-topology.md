# MIDI Topology

`data/midi.yaml` is the canonical structured source for MIDI endpoints, devices,
physical links, channels, clock, and Ableton port state.

Physical MIDI topology is currently **UNKNOWN**. No cable, USB port, DIN port, or
Ableton preference is implied by an intended design. A link appears below only
when it is explicitly represented in `connections`.

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
| cme-u6midi-pro | usb-midi-router | 3 in / 3 out; route / merge / filter / remap — OWNED |
| cme-midi-thru5-wc | midi-thru | Hardware thru distribution — OWNED; not a programmable remapper |
| tascam-us-16x08 | audio-interface-midi | May participate in MIDI paths; exact CURRENT use UNKNOWN |
| korg-minikorg | synth | — |
| kaoss-replay | sampler-effects | — |
| boss-sl-2 | pedal | — |
| casio-privia | instrument | — |
| korg-padkontrol | controller | — |
| behringer-fcb1010 | foot-controller | USB Uno recognition unresolved (RIG-022); switch maps out of Stage 8 scope |
| novation-remote-zero-sl | controller | — |
| launchpad-x | controller | — |
| novation-launch-control-3 | controller | — |

## Physical links

| ID | Source / port | Destination / port | Transport | Evidence | Notes |
|---|---|---|---|---|---|
| — | UNKNOWN | UNKNOWN | — | UNKNOWN | No verified physical links |
<!-- rig:midi-topology:end -->

## Evidence rules

- `VERIFIED` means directly confirmed.
- `INTENDED` describes a desired or planned setup, not current physical fact.
- `UNKNOWN` means the repository does not establish the fact.

Channel assignments, clock relationships, physical transport links, and Ableton
Track / Sync / Remote settings are separate facts and must be verified separately.
Controller switch and knob maps are outside this document.
