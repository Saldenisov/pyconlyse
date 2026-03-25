# C8NI6703 Raw To Canonical Mapping

Both layers are kept: the raw LabVIEW name and the internal canonical name.

| raw_name | value | canonical_name | group | direction |
| --- | --- | --- | --- | --- |
| `00 OUT00 b01 RÃ©serve` | `0.0` | `` | `placeholder` | `ignore` |
| `01 OUT01 b05 Cmd Temp. Canon` | `21.0` | `elyse/cooling/canon/temperature/set_value` | `cooling` | `write` |
| `02 OUT02 b09 Cmd Temp. Section` | `27.9` | `elyse/cooling/section/temperature/set_value` | `cooling` | `write` |
| `03 OUT03 b13 Cmd Pos. DÃ©phaseur` | `0.0` | `elyse/HF/dephaser/set_value` | `ht_hf` | `write` |
| `04 OUT04 b17 Cmd Pos. AttÃ©nuateur` | `0.0` | `elyse/HF/attenuator/set_value` | `ht_hf` | `write` |
| `05 OUT05 b21 Cmd dÃ©phasage HF/LASER` | `0.0` | `elyse/magnets/phase_HF_laser/set_value` | `magnets` | `write` |
| `06 OUT06 b25 Cmd amplitude HF prÃ©ampli` | `360.0` | `elyse/preamplifier/set_value` | `ht_hf` | `write` |
| `07 OUT07 b29 RÃ©serve` | `0.0` | `` | `placeholder` | `ignore` |
| `08 OUT08 b33 Cmd position Miroir X` | `0.0` | `elyse/laser/mirror/x/set_value` | `laser` | `write` |
| `09 OUT09 b37 Cmd position Miroir Y` | `0.0` | `elyse/laser/mirror/y/set_value` | `laser` | `write` |
