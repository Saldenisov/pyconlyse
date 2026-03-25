# DPS Raw To Canonical Mapping

Raw-to-canonical mapping for DPS based on the visible companion-state panel. Raw labels are preserved exactly as they arrive from the live dump, including mojibake when present.

| Raw Name | Live Value | Canonical Name | Group | Direction |
|---|---:|---|---|---|
| `Marche refroidissement X` | `0.0` | `elyse/dps/cooling/start` | `sequence` | `read` |
| `Arret refroidissement X` | `0.0` | `elyse/dps/cooling/stop` | `sequence` | `read` |
| `X Marche GENERAL Mod.` | `0.0` | `elyse/dps/modulator_general/start` | `sequence` | `read` |
| `X ArrÃªt GENERAL Mod.` | `0.0` | `elyse/dps/modulator_general/stop` | `sequence` | `read` |
| `X Marche CHAUFFAGE Mod.` | `0.0` | `elyse/dps/modulator_heating/start` | `sequence` | `read` |
| `X ArrÃªt CHAUFFAGE Mod.` | `0.0` | `elyse/dps/modulator_heating/stop` | `sequence` | `read` |
| `X Marche PREMA Mod. ` | `0.0` | `elyse/dps/modulator_prema/start` | `sequence` | `read` |
| `X ArrÃªt PREMA Mod.` | `0.0` | `elyse/dps/modulator_prema/stop` | `sequence` | `read` |
| `X Marche RELAIS HT Mod.` | `0.0` | `elyse/dps/modulator_relay_ht/start` | `sequence` | `read` |
| `X ArrÃªt RELAIS HT Mod.` | `0.0` | `elyse/dps/modulator_relay_ht/stop` | `sequence` | `read` |
| `X Marche FOCALE Mod.` | `0.0` | `elyse/dps/modulator_focale/start` | `sequence` | `read` |
| `X ArrÃªt FOCALE Mod.` | `0.0` | `elyse/dps/modulator_focale/stop` | `sequence` | `read` |
| `X RESET Mod.` | `0.0` | `elyse/dps/modulator/reset` | `sequence` | `read` |
| `X Marche Att DÃ©ph` | `0.0` | `elyse/dps/hf_att_deph/start` | `sequence` | `read` |
| `X Arret Att DÃ©ph` | `0.0` | `elyse/dps/hf_att_deph/stop` | `sequence` | `read` |
| `X Marche alimentation HT` | `0.0` | `elyse/dps/ht_power/start` | `sequence` | `read` |
| `X Reset alimentation HT` | `0.0` | `elyse/dps/ht_power/reset` | `sequence` | `read` |
| `X ArrÃªt alimentation HT` | `0.0` | `elyse/dps/ht_power/stop` | `sequence` | `read` |
| `X Marche impulsion mod` | `0.0` | `elyse/dps/modulator_impulse/start` | `sequence` | `read` |
| `X Arret impulsion mod` | `0.0` | `elyse/dps/modulator_impulse/stop` | `sequence` | `read` |
| `X Marche alimentation aimant` | `0.0` | `elyse/dps/magnets_power/start` | `sequence` | `read` |
| `X Alimentation aimant = 0V` | `0.0` | `elyse/dps/magnets_power/zero_v` | `sequence` | `read` |
| `X Alimentation aimant = PT` | `0.0` | `elyse/dps/magnets_power/pt` | `sequence` | `read` |
| `X ArrÃªt alimentation aimant` | `0.0` | `elyse/dps/magnets_power/stop` | `sequence` | `read` |
| `X Tempo 1s` | `0.0` | `elyse/dps/timing/1s` | `sequence` | `read` |
| `X Tempo 5s` | `0.0` | `elyse/dps/timing/5s` | `sequence` | `read` |
| `X Tempo 30s` | `0.0` | `elyse/dps/timing/30s` | `sequence` | `read` |
| `X FREQ. ELYSE` | `0.0` | `elyse/dps/freq_elyse` | `sequence` | `read` |
| `Libre X` | `0.0` | `elyse/dps/free` | `sequence` | `read` |
