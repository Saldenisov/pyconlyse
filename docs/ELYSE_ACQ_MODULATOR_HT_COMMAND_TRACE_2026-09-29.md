# Acquisition modulator-HT commands: events 20–22 (2026-09-29)

## Scope

The saved root VI's three modulator-HT command events were traced from ordered-frame constants through `C4_OUT_DIO96` bundle indices and the EPS/DPS cluster field order. Source LLB SHA-256: `EB7C08800823D025F1B4F9E8EEA89ED9878F0CF00A02427871583B99989B2F8A`. This analysis does not operate a card, measure output polarity, or establish whether the deployed executable matches the copy.

| Event | Logical C4 output, frame 0 → frame 1 | Frame-2 state update | PSP publication |
|---|---|---|---|
| 20, `Marche alimentation HT` | index **18**, `18 DPB2 b78 Marche alimentation HT`: **True → False**, 150 ms requested hold | EPS `[45] Marche alimentation HT OK=True`, `[49] Arret alimentation HT OK=False`; DPS `[15] X Marche alimentation HT=False` | DPS, EPS, C4 output bank; then 100 ms wait |
| 21, `Arrêt alimentation HT` | index **19**, `19 DPB3 b76 Arrêt alimentation HT`: **False → True**, 150 ms requested hold | EPS `[45] Marche alimentation HT OK=False`, `[49] Arret alimentation HT OK=True`; DPS `[17] X Arrêt alimentation HT=False` | DPS, EPS, C4 output bank; then 100 ms wait |
| 22, `Reset alimentation HT` | index **20**, `20 DPB4 b74 RAZ alimentation HT`: **True → False**, 150 ms requested hold | DPS `[16] X Reset alimentation HT=False`; no EPS field update visible in frame 2 | DPS, EPS, C4 output bank; then 100 ms wait |

The input events' `NewVal=False` arms are empty; the five-frame sequences are in their `NewVal=True` arms. The raw `nMux` field indices and C4/EPS/DPS VCTP type descriptions identify the targets. The literal constants' captions in these frames were copied from `00 CPB0 b81 Marche Reffroidissement Canon` and `Marche refroidissement`; those captions are **not** the selected field names. Earlier notes had event 21's pulse direction wrong; its raw constants are `False` then `True`.

The 150 ms interval is a LabVIEW sequence delay between local command-value assignments, not measured terminal pulse width. A concurrent DIO write loop performs card updates. No interlock guard is visible inside these three event sequences; that does not prove that Supervision or hardwired protection allows every command. `OK` flags here are set by the command sequence, not demonstrated hardware acknowledgment. A Python implementation must keep command intent, readback, and verified interlock state distinct until the remaining paths are traced.
