# Patchbays

Operational reference for standing at the rack with a patch cable.

Machine-readable map: repository file `data/patchbays.yaml`. Diagram: repository file `diagrams/patchbays.mmd`.

Canonical CURRENT patchbay state is edited with `uv run rig current patchbay …`.

Owned hardware (model → bay letter mapping may still be UNKNOWN in structured data):

- 2× ART Pro Audio P48
- 2× Behringer PX3000

<!-- rig:patchbays:start -->
<!-- GENERATED FROM data/patchbays.yaml BY `uv run rig render`. DO NOT EDIT THIS SECTION DIRECTLY. -->

## Hardware

| Named bay | Hardware model | Status |
|---|---|---|
| PB-A | ART P48 | UNDOCUMENTED |
| PB-B | ART P48 | PARTIALLY DOCUMENTED |
| PB-C | Behringer PX3000 | UNDOCUMENTED |
| PB-D | Behringer PX3000 | UNDOCUMENTED |

## Represented jack pairs

Only pairs present in `data/patchbays.yaml` are listed. UNKNOWN modes are shown explicitly.

### PB-A

_No jack pairs represented._

### PB-B

| Upper | Upper connection | Lower | Lower connection | Mode |
|---:|---|---:|---|---|
| 1 | miniKORG L/MONO | 25 | TASCAM input 3 | NORMAL |
| 2 | miniKORG R | 26 | TASCAM input 4 | NORMAL |
| 3 | SR-18 MAIN L | 27 | TASCAM input 11 | NORMAL |
| 4 | SR-18 MAIN R | 28 | TASCAM input 12 | NORMAL |
| 7 | Privia L/MONO | 31 | Alesis CH 5/L | NORMAL |
| 8 | Privia R | 32 | Alesis CH 6/R | NORMAL |
| 9 | UNASSIGNED | 33 | Alesis CH 7/L | NORMAL |
| 10 | UNASSIGNED | 34 | Alesis CH 8/R | NORMAL |
| 11 | UNASSIGNED | 35 | miniKORG AUDIO IN 1 | NORMAL |
| 12 | UNASSIGNED | 36 | miniKORG AUDIO IN 2 | NORMAL |

### PB-C

_No jack pairs represented._

### PB-D

_No jack pairs represented._
<!-- rig:patchbays:end -->

## Numbering convention (PB-B)

Spreadsheet / physical numbering:

- **Upper row:** jacks 1–24
- **Lower row:** jacks 25–48

Upper jack *N* pairs with lower jack *N+24* (e.g. 1↔25, 7↔31).

## Normalization mode

Whether each pair is **normal**, **half-normal**, or **thru** may be **UNKNOWN** until verified. Do not assume a pair is normalled merely because both rear jacks have connections.

Distinguish:

| Concept | Meaning |
|---|---|
| Rear-panel connection | What is physically wired to that jack on the back |
| Default normalled path | Internal bay behavior when no front patch is inserted (UNKNOWN until recorded) |
| Front-panel patch destination | What you reach by plugging into the front |

### Notes for rack use

- Use `uv run rig patchbay PB-B` or `uv run rig current patchbay verify PB-B` at the rack.
- Only pairs present in `data/patchbays.yaml` are CURRENT. Do not invent undocumented jacks.
- Lower destinations without upper sources remain UNKNOWN/unassigned until recorded.
