# EPS Raw To Canonical Mapping

Raw-to-canonical mapping for EPS based on the visible state panel. Raw labels are preserved; canonical names are internal Python DS names. X-prefixed companion states seen in the live dump are intentionally excluded from this first-pass panel mapping.

| Raw Name | Live Value | Canonical Name | Group | Direction |
|---|---:|---|---|---|
| `Alimentation aimant = 0V` | `0.0` | `elyse/eps/magnets_power/zero_v` | `sequence` | `read` |
| `Alimentation aimant = 0V ED` | `0.0` | `elyse/eps/magnets_power/zero_v_ed` | `sequence` | `read` |
| `Alimentation aimant = 0V OK` | `0.0` | `elyse/eps/magnets_power/zero_v_ok` | `sequence` | `read` |
| `Alimentation aimant = PT` | `0.0` | `elyse/eps/magnets_power/pt` | `sequence` | `read` |
| `Alimentation aimant = PT ED` | `0.0` | `elyse/eps/magnets_power/pt_ed` | `sequence` | `read` |
| `Alimentation aimant = PT OK` | `0.0` | `elyse/eps/magnets_power/pt_ok` | `sequence` | `read` |
| `Arret Att DÃ©ph ED` | `0.0` | `elyse/eps/hf_att_deph/stop_ed` | `sequence` | `read` |
| `Arret Att DÃ©ph OK` | `0.0` | `elyse/eps/hf_att_deph/stop_ok` | `sequence` | `read` |
| `Arret alimentation HT ED` | `0.0` | `elyse/eps/ht_power/stop_ed` | `sequence` | `read` |
| `Arret alimentation HT OK` | `0.0` | `elyse/eps/ht_power/stop_ok` | `sequence` | `read` |
| `Arret alimentation aimant ED` | `0.0` | `elyse/eps/magnets_power/stop_ed` | `sequence` | `read` |
| `Arret alimentation aimant OK` | `0.0` | `elyse/eps/magnets_power/stop_ok` | `sequence` | `read` |
| `Arret impulsion mod ED` | `0.0` | `elyse/eps/modulator_impulse/stop_ed` | `sequence` | `read` |
| `Arret impulsion mod OK` | `0.0` | `elyse/eps/modulator_impulse/stop_ok` | `sequence` | `read` |
| `Arret refroidissement ED` | `0.0` | `elyse/eps/cooling/stop_ed` | `sequence` | `read` |
| `ArrÃªt Att et DÃ©ph HF` | `0.0` | `elyse/eps/hf_att_deph/stop` | `sequence` | `read` |
| `ArrÃªt CHAUFFAGE Mod.` | `0.0` | `elyse/eps/modulator_heating/stop` | `sequence` | `read` |
| `ArrÃªt CHAUFFAGE Mod. ED` | `0.0` | `elyse/eps/modulator_heating/stop_ed` | `sequence` | `read` |
| `ArrÃªt CHAUFFAGE Mod. OK` | `0.0` | `elyse/eps/modulator_heating/stop_ok` | `sequence` | `read` |
| `ArrÃªt FOCALE Mod.` | `0.0` | `elyse/eps/modulator_focale/stop` | `sequence` | `read` |
| `ArrÃªt FOCALE Mod. ED` | `0.0` | `elyse/eps/modulator_focale/stop_ed` | `sequence` | `read` |
| `ArrÃªt FOCALE Mod. OK` | `0.0` | `elyse/eps/modulator_focale/stop_ok` | `sequence` | `read` |
| `ArrÃªt GENERAL Mod.` | `0.0` | `elyse/eps/modulator_general/stop` | `sequence` | `read` |
| `ArrÃªt GENERAL Mod. ED` | `0.0` | `elyse/eps/modulator_general/stop_ed` | `sequence` | `read` |
| `ArrÃªt GENERAL Mod. OK` | `0.0` | `elyse/eps/modulator_general/stop_ok` | `sequence` | `read` |
| `ArrÃªt PREMA Mod.` | `0.0` | `elyse/eps/modulator_prema/stop` | `sequence` | `read` |
| `ArrÃªt PREMA Mod. ED` | `0.0` | `elyse/eps/modulator_prema/stop_ed` | `sequence` | `read` |
| `ArrÃªt PREMA Mod. OK` | `0.0` | `elyse/eps/modulator_prema/stop_ok` | `sequence` | `read` |
| `ArrÃªt RELAIS HT Mod.` | `0.0` | `elyse/eps/modulator_relay_ht/stop` | `sequence` | `read` |
| `ArrÃªt RELAIS HT Mod. ED` | `0.0` | `elyse/eps/modulator_relay_ht/stop_ed` | `sequence` | `read` |
| `ArrÃªt RELAIS HT Mod. OK` | `0.0` | `elyse/eps/modulator_relay_ht/stop_ok` | `sequence` | `read` |
| `ArrÃªt alimentation HT` | `0.0` | `elyse/eps/ht_power/stop` | `sequence` | `read` |
| `ArrÃªt alimentation aimants` | `0.0` | `elyse/eps/magnets_power/stop` | `sequence` | `read` |
| `ArrÃªt impulsion modulateur` | `0.0` | `elyse/eps/modulator_impulse/stop` | `sequence` | `read` |
| `ArrÃªt refroidissement` | `0.0` | `elyse/eps/cooling/stop` | `sequence` | `read` |
| `FREQ. ELYSE` | `0.0` | `elyse/eps/freq_elyse` | `sequence` | `read` |
| `FREQ. ELYSE ED` | `0.0` | `elyse/eps/freq_elyse_ed` | `sequence` | `read` |
| `FREQ. ELYSE OK` | `0.0` | `elyse/eps/freq_elyse_ok` | `sequence` | `read` |
| `Libre` | `0.0` | `elyse/eps/free` | `sequence` | `read` |
| `Libre ED` | `0.0` | `elyse/eps/free_ed` | `sequence` | `read` |
| `Libre OK` | `0.0` | `elyse/eps/free_ok` | `sequence` | `read` |
| `Marche Att DÃ©ph ED` | `0.0` | `elyse/eps/hf_att_deph/start_ed` | `sequence` | `read` |
| `Marche Att DÃ©ph OK` | `0.0` | `elyse/eps/hf_att_deph/start_ok` | `sequence` | `read` |
| `Marche Att et DÃ©ph HF` | `0.0` | `elyse/eps/hf_att_deph/start` | `sequence` | `read` |
| `Marche CHAUFFAGE Mod.` | `0.0` | `elyse/eps/modulator_heating/start` | `sequence` | `read` |
| `Marche CHAUFFAGE Mod. ED` | `0.0` | `elyse/eps/modulator_heating/start_ed` | `sequence` | `read` |
| `Marche CHAUFFAGE Mod. OK` | `0.0` | `elyse/eps/modulator_heating/start_ok` | `sequence` | `read` |
| `Marche FOCALE Mod.` | `0.0` | `elyse/eps/modulator_focale/start` | `sequence` | `read` |
| `Marche FOCALE Mod. ED` | `0.0` | `elyse/eps/modulator_focale/start_ed` | `sequence` | `read` |
| `Marche FOCALE Mod. OK` | `0.0` | `elyse/eps/modulator_focale/start_ok` | `sequence` | `read` |
| `Marche GENERAL Mod.` | `0.0` | `elyse/eps/modulator_general/start` | `sequence` | `read` |
| `Marche GENERAL Mod. ED` | `0.0` | `elyse/eps/modulator_general/start_ed` | `sequence` | `read` |
| `Marche GENERAL Mod. OK` | `0.0` | `elyse/eps/modulator_general/start_ok` | `sequence` | `read` |
| `Marche PREMA Mod.` | `0.0` | `elyse/eps/modulator_prema/start` | `sequence` | `read` |
| `Marche PREMA Mod. ED` | `0.0` | `elyse/eps/modulator_prema/start_ed` | `sequence` | `read` |
| `Marche PREMA Mod. OK` | `0.0` | `elyse/eps/modulator_prema/start_ok` | `sequence` | `read` |
| `Marche RELAIS HT Mod.` | `0.0` | `elyse/eps/modulator_relay_ht/start` | `sequence` | `read` |
| `Marche RELAIS HT Mod. ED` | `0.0` | `elyse/eps/modulator_relay_ht/start_ed` | `sequence` | `read` |
| `Marche RELAIS HT Mod. OK` | `0.0` | `elyse/eps/modulator_relay_ht/start_ok` | `sequence` | `read` |
| `Marche alimentation HT` | `0.0` | `elyse/eps/ht_power/start` | `sequence` | `read` |
| `Marche alimentation HT ED` | `0.0` | `elyse/eps/ht_power/start_ed` | `sequence` | `read` |
| `Marche alimentation HT OK` | `0.0` | `elyse/eps/ht_power/start_ok` | `sequence` | `read` |
| `Marche alimentation aimant ED` | `0.0` | `elyse/eps/magnets_power/start_ed` | `sequence` | `read` |
| `Marche alimentation aimant OK` | `0.0` | `elyse/eps/magnets_power/start_ok` | `sequence` | `read` |
| `Marche alimentation aimants` | `0.0` | `elyse/eps/magnets_power/start` | `sequence` | `read` |
| `Marche impulsion mod ED` | `0.0` | `elyse/eps/modulator_impulse/start_ed` | `sequence` | `read` |
| `Marche impulsion mod OK` | `0.0` | `elyse/eps/modulator_impulse/start_ok` | `sequence` | `read` |
| `Marche impulsion modulateur` | `0.0` | `elyse/eps/modulator_impulse/start` | `sequence` | `read` |
| `Marche refroidissement` | `0.0` | `elyse/eps/cooling/start` | `sequence` | `read` |
| `Marche refroidissement ED` | `0.0` | `elyse/eps/cooling/start_ed` | `sequence` | `read` |
| `Marche refroidissement OK` | `0.0` | `elyse/eps/cooling/start_ok` | `sequence` | `read` |
| `RESET Mod.` | `0.0` | `elyse/eps/modulator/reset` | `sequence` | `read` |
| `Reset alimentation HT` | `0.0` | `elyse/eps/ht_power/reset` | `sequence` | `read` |
| `Tempo 1s` | `0.0` | `elyse/eps/timing/1s` | `sequence` | `read` |
| `Tempo 30s` | `0.0` | `elyse/eps/timing/30s` | `sequence` | `read` |
| `Tempo 5s` | `0.0` | `elyse/eps/timing/5s` | `sequence` | `read` |
