# Inventory

`data/inventory.yaml` is the canonical ownership record. Stable item and unit IDs
connect inventory to CURRENT routing and acquired wishlist entries.

**Owned does not mean CURRENT.** A device can be owned and available without being
present in any active signal path. CURRENT topology remains canonical in
[Current Routing](current-routing.md) and [Pedal Chains](pedal-chains.md).

Wishlist entries are not inventory. Acquisition is the explicit boundary that
creates an inventory record and marks the wishlist entry `ACQUIRED`.

Patchbay hardware identity remains intentionally separate from PB-A/PB-B/PB-C/PB-D.
The model-to-letter mapping is UNKNOWN until the physical units are inspected
(Q-007); unit assignments must not be inferred.

<!-- rig:inventory:start -->
<!-- GENERATED FROM data/inventory.yaml BY `uv run rig render`. DO NOT EDIT THIS SECTION DIRECTLY. -->

## Interfaces Mixers

| ID | Name | Manufacturer | Model | Qty | Status | Condition | Notes |
|---|---|---|---|---:|---|---|---|
| tascam-us-16x08 | TASCAM US-16x08 | TASCAM | US-16x08 | 1 | OWNED | UNKNOWN | Main audio interface |
| alesis-mixer | Alesis mixer | Alesis | UNKNOWN | 1 | OWNED | UNKNOWN | Live routing and AUX SEND hub |

## Instruments

| ID | Name | Manufacturer | Model | Qty | Status | Condition | Notes |
|---|---|---|---|---:|---|---|---|
| bass | Bass | — | — | 1 | OWNED | UNKNOWN | — |
| electric-guitar | Electric guitar | — | — | 1 | OWNED | UNKNOWN | — |
| acoustic-instrument | Acoustic instrument | — | — | 1 | OWNED | UNKNOWN | — |
| electric-kazoo | Electric kazoo | — | — | 1 | OWNED | UNKNOWN | — |
| casio-privia | Casio Privia | Casio | Privia | 1 | OWNED | UNKNOWN | — |
| korg-minikorg | Korg miniKORG | Korg | miniKORG | 1 | OWNED | UNKNOWN | — |
| alesis-sr-18 | Alesis SR-18 | Alesis | SR-18 | 1 | OWNED | UNKNOWN | — |

## Preamps

| ID | Name | Manufacturer | Model | Qty | Status | Condition | Notes |
|---|---|---|---|---:|---|---|---|
| boss-acoustic-preamp | BOSS acoustic preamp | BOSS | — | 1 | OWNED | UNKNOWN | Acoustic front end before A/B/Y |
| bbox-preamp | BBox preamp | BBox | — | 1 | OWNED | UNKNOWN | Bass front end before A/B/Y |
| flamma-preamp | Flamma preamp | Flamma | — | 1 | OWNED | UNKNOWN | Electric guitar front end before A/B/Y |

## Utility

| ID | Name | Manufacturer | Model | Qty | Status | Condition | Notes |
|---|---|---|---|---:|---|---|---|
| aby-splitters | A/B/Y splitters | — | — | 1 | OWNED | UNKNOWN | Clean TASCAM legs confirmed; other legs UNKNOWN |
| mxr-trs-split-tap | MXR TRS split + tap | MXR | — | 1 | OWNED | UNKNOWN | — |
| radial-prormp | Radial ProRMP | Radial | ProRMP | 1 | OWNED | UNKNOWN | AUX SEND placement was too quiet; not default wet-loop device |
| pyle-pro-pdc22 | PYLE-PRO PDC22 dual DI | PYLE-PRO | PDC22 | 1 | OWNED | UNKNOWN | — |

## Loopers Samplers

| ID | Name | Manufacturer | Model | Qty | Status | Condition | Notes |
|---|---|---|---|---:|---|---|---|
| boss-rc-1 | BOSS RC-1 | BOSS | RC-1 | 1 | OWNED | UNKNOWN | — |
| kaoss-replay | KAOSS Replay | Korg | KAOSS Replay | 1 | OWNED | UNKNOWN | — |

## Patchbays

| ID | Name | Manufacturer | Model | Qty | Status | Condition | Notes |
|---|---|---|---|---:|---|---|---|
| art-p48 | ART Pro Audio P48 | ART | P48 | 2 | OWNED | UNKNOWN | Which physical units map to PB-A/B/C/D is UNKNOWN |
| behringer-px3000 | Behringer PX3000 | Behringer | PX3000 | 2 | OWNED | UNKNOWN | Which physical units map to PB-A/B/C/D is UNKNOWN |

## Routers

| ID | Name | Manufacturer | Model | Qty | Status | Condition | Notes |
|---|---|---|---|---:|---|---|---|
| joyo-ab-bypass | JOYO A/B/Bypass router | JOYO | — | 1 | OWNED | UNKNOWN | CURRENT A = DIRTY, B = SPACE |

## Pedals

| ID | Name | Manufacturer | Model | Qty | Status | Condition | Notes |
|---|---|---|---|---:|---|---|---|
| cry-baby | Cry Baby | — | — | 1 | OWNED | UNKNOWN | — |
| boss-od-1 | BOSS OD-1 | BOSS | OD-1 | 1 | OWNED | UNKNOWN | — |
| boss-bd-2 | BOSS BD-2 | BOSS | BD-2 | 1 | OWNED | UNKNOWN | — |
| boss-jb-2 | BOSS JB-2 | BOSS | JB-2 | 1 | OWNED | UNKNOWN | — |
| boss-mt-2w | BOSS MT-2w | BOSS | MT-2w | 1 | OWNED | UNKNOWN | — |
| boss-ds-1 | BOSS DS-1 | BOSS | DS-1 | 1 | OWNED | UNKNOWN | — |
| boss-sy-1 | BOSS SY-1 | BOSS | SY-1 | 1 | OWNED | UNKNOWN | — |
| boss-ph-3 | BOSS PH-3 | BOSS | PH-3 | 1 | OWNED | UNKNOWN | — |
| boss-tr-2 | BOSS TR-2 | BOSS | TR-2 | 1 | OWNED | UNKNOWN | — |
| boss-ls-2 | BOSS LS-2 | BOSS | LS-2 | 1 | OWNED | UNKNOWN | CURRENT SPACE after SY-1; mode A+B MIX ↔ BYPASS |
| boss-sl-2 | BOSS SL-2 | BOSS | SL-2 | 1 | OWNED | UNKNOWN | — |
| boss-dd-8 | BOSS DD-8 | BOSS | DD-8 | 1 | OWNED | UNKNOWN | — |
| boss-te-2 | BOSS TE-2 | BOSS | TE-2 | 1 | OWNED | UNKNOWN | — |
| boss-re-2 | BOSS RE-2 | BOSS | RE-2 | 1 | OWNED | UNKNOWN | Noise noted historically; gain/noise isolation pending |
| boss-ch-1 | BOSS CH-1 | BOSS | CH-1 | 1 | OWNED | UNKNOWN | Post-JOYO stereo stage |
| flamma-mod | Flamma Mod | Flamma | — | 1 | OWNED | UNKNOWN | OWNED but not in CURRENT SPACE topology |
| boss-ph-2 | BOSS PH-2 | BOSS | PH-2 | 1 | OWNED | UNKNOWN | OWNED but not in CURRENT SPACE topology |
| big-muff | Big Muff | — | — | 1 | OWNED | ISSUE | Failed/no audio; bench-test (RIG-020) |

## Controllers

| ID | Name | Manufacturer | Model | Qty | Status | Condition | Notes |
|---|---|---|---|---:|---|---|---|
| launchpad-x | Launchpad X | Novation | Launchpad X | 1 | OWNED | UNKNOWN | — |
| novation-launch-control-3 | Novation Launch Control 3 | Novation | Launch Control 3 | 1 | OWNED | UNKNOWN | — |
| korg-padkontrol | Korg padKONTROL | Korg | padKONTROL | 1 | OWNED | UNKNOWN | — |
| behringer-fcb1010 | Behringer FCB1010 | Behringer | FCB1010 | 1 | OWNED | UNKNOWN | — |
| novation-remote-zero-sl | Novation ReMOTE ZeRO SL | Novation | ReMOTE ZeRO SL | 1 | OWNED | ISSUE | Encoder #6 broken |
| elgato-stream-deck-plus | Elgato Stream Deck+ | Elgato | Stream Deck+ | 1 | OWNED | UNKNOWN | — |
| mosky-dual-switch | MOSKY Dual Switch | MOSKY | — | 1 | OWNED | UNKNOWN | — |
| boss-ev-30 | BOSS EV-30 | BOSS | EV-30 | 1 | OWNED | UNKNOWN | — |

## Midi Utilities

| ID | Name | Manufacturer | Model | Qty | Status | Condition | Notes |
|---|---|---|---|---:|---|---|---|
| cme-u6midi-pro | CME U6MIDI Pro | CME | U6MIDI Pro | 1 | OWNED | UNKNOWN | 3 in / 3 out; route / merge / filter |
| cme-midi-thru5-wc | CME MIDI Thru5 WC | CME | MIDI Thru5 WC | 1 | OWNED | UNKNOWN | Hardware thru distribution |
<!-- rig:inventory:end -->
