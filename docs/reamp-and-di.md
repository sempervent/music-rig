# Reamp and DI Notes

## Radial ProRMP

Observed behavior:

- Putting the ProRMP directly on the Alesis AUX SEND reduced the signal too much.
- It required all sends near maximum, which is undesirable.

Current recommendation:

- Do not make the ProRMP part of the default AUX SEND loop.
- Treat it as a DAW/TASCAM reamp utility unless a line-level gain staging solution is added.

Better candidate uses:

```text
TASCAM line output -> ProRMP -> guitar pedal input -> amp/pedal return/capture path
```

## PYLE-PRO PDC22 dual DI

Useful because it can process two channels, not merely one mono signal.

Candidate uses:

- stereo L/R tap
- A/B chain tap
- Privia direct-to-TASCAM tap
- bass/guitar direct split where isolation is useful

## General rule

Use DI boxes to convert instrument/unbalanced sources into interface/mixer-friendly signals. Use reamp boxes in the opposite direction: interface/line-level output back down to pedal/instrument-level expectations.
