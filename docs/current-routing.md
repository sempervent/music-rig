# Current Routing

## Stable TASCAM inputs

| TASCAM Input | Source | Notes |
|---:|---|---|
| 1/2 | Alesis mixer main out | Clean stereo mixer capture |
| 3/4 | miniKORG | Direct stereo synth capture |
| 5 | Clean acoustic/electric guitar | Dry guitar capture |
| 7 | Clean bass | Dry bass capture |
| 9/10 | KAOSS Replay | Stereo KAOSS capture |

## Alesis mixer inputs

| Alesis Channel | Source | Notes |
|---:|---|---|
| 1 | Bass | Can feed AUX SEND wet loop |
| 2 | Guitar | Can feed AUX SEND wet loop |
| 3 | Open | Reserved |
| 4 | Electric kazoo | Can feed AUX SEND wet loop |
| 5/6 | Privia piano | Stereo piano input |
| 7/8 | Open | Reserved stereo pair |

## Aux send loop

Current creative wet path:

```text
Alesis AUX SEND
  -> Cry Baby
  -> BOSS RC-1
  -> JOYO A/B/Bypass input
     -> Chain A
     -> Chain B
  -> JOYO output
  -> BOSS CH-1 stereo out L/R
  -> Alesis stereo return or stereo line input
```

## KAOSS path

```text
Alesis Monitor Out
  -> KAOSS Replay
  -> TASCAM US-16x08 inputs 9/10
```

The KAOSS path is intentionally separate from the main clean capture. Treat it like its own instrument once sampled.
