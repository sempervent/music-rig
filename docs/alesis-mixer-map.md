# Alesis Mixer Map

Canonical CURRENT assignments: `data/channel-map.yaml`.

Edit with `uv run rig current channels set-source alesis …`.

<!-- rig:alesis:start -->
<!-- GENERATED FROM data/channel-map.yaml BY `uv run rig render`. DO NOT EDIT THIS SECTION DIRECTLY. -->

| Channel | Source | AUX SEND | Status |
|---|---|---|---|
| 1 | Bass | Yes | CURRENT |
| 2 | Acoustic | Yes | CURRENT |
| 3 | Electric | No | CURRENT |
| 4 | Electric kazoo | Yes | CURRENT |
| 5_6 | Privia | Yes | CURRENT |
| 7_8 | UNASSIGNED | No | UNASSIGNED |
<!-- rig:alesis:end -->

## Bus / send notes

| Path | Role |
|---|---|
| Main Out | Clean stereo capture → TASCAM 1/2 |
| Monitor Out | KAOSS Replay feed → TASCAM 9/10 |
| AUX SEND | Wet loop input → RC-1 → Cry Baby → JOYO → CH-1 |
| Stereo Return / Line Return | Wet loop return from CH-1 stereo out |

PB-B lower 31–34 connect toward Alesis CH 5–8; upper sources for 33–34 remain unassigned in CURRENT patchbay data.
