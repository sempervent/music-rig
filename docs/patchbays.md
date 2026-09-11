# Patchbays

Operational reference for standing at the rack with a patch cable.

Machine-readable map: repository file `data/patchbays.yaml`. Diagram: repository file `diagrams/patchbays.mmd`.

## Hardware

| Named bay | Points | Hardware model |
|---|---:|---|
| PB-A | 48 (1/4" TRS) | UNKNOWN |
| PB-B | 48 (1/4" TRS) | UNKNOWN |
| PB-C | 48 (1/4" TRS) | UNKNOWN |
| PB-D | 48 (1/4" TRS) | UNKNOWN |

Owned hardware (model → bay letter mapping **UNKNOWN**):

- 2× ART Pro Audio P48
- 2× Behringer PX3000

## Status by bay

| Bay | Status |
|---|---|
| PB-A | UNDOCUMENTED / UNASSIGNED |
| PB-B | PARTIALLY DOCUMENTED (see below) |
| PB-C | UNDOCUMENTED / UNASSIGNED |
| PB-D | UNDOCUMENTED / UNASSIGNED |

## Numbering convention (PB-B)

Spreadsheet / physical numbering:

- **Upper row:** jacks 1–24
- **Lower row:** jacks 25–48

Upper jack *N* pairs with lower jack *N+24* (e.g. 1↔25, 7↔31).

## Normalization mode

Whether each pair is **normal**, **half-normal**, or **thru** is **UNKNOWN**. Do not assume a pair is normalled merely because both rear jacks have connections.

Distinguish:

| Concept | Meaning |
|---|---|
| Rear-panel connection | What is physically wired to that jack on the back |
| Default normalled path | Internal bay behavior when no front patch is inserted (UNKNOWN here) |
| Front-panel patch destination | What you reach by plugging into the front |

## PB-B documented jack map (CURRENT)

| Upper | Upper connection | Lower | Lower connection | Mode |
|---:|---|---:|---|---|
| 1 | miniKORG L/MONO | 25 | TASCAM input 3 | UNKNOWN |
| 2 | miniKORG R | 26 | TASCAM input 4 | UNKNOWN |
| 3 | SR-18 MAIN L | 27 | TASCAM input 11 | UNKNOWN |
| 4 | SR-18 MAIN R | 28 | TASCAM input 12 | UNKNOWN |
| 5 | UNDOCUMENTED | 29 | UNDOCUMENTED | UNKNOWN |
| 6 | UNDOCUMENTED | 30 | UNDOCUMENTED | UNKNOWN |
| 7 | Privia L/MONO | 31 | Alesis CH 5/L | UNKNOWN |
| 8 | Privia R | 32 | Alesis CH 6/R | UNKNOWN |
| 9 | UNASSIGNED | 33 | Alesis CH 7/L | UNKNOWN |
| 10 | UNASSIGNED | 34 | Alesis CH 8/R | UNKNOWN |
| 11 | UNASSIGNED | 35 | miniKORG AUDIO IN 1 | UNKNOWN |
| 12 | UNASSIGNED | 36 | miniKORG AUDIO IN 2 | UNKNOWN |
| 13–24 | UNDOCUMENTED | 37–48 | UNDOCUMENTED | UNKNOWN |

### Notes for rack use

- Documented **source → destination** pairs with both ends known: 1↔25, 2↔26, 3↔27, 4↔28, 7↔31, 8↔32.
- Lower jacks **33–36** have destinations wired, but **no corresponding upper-row source** is currently documented. Do not invent one.
- Upper jacks **9–12** are explicitly unassigned in the current spreadsheet.
- All other PB-B positions are undocumented/unassigned until recorded.
