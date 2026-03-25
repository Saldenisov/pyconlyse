# C9NI6703 Raw To Canonical Mapping

Both layers are kept: the raw LabVIEW name and the internal canonical name.

| raw_name | value | canonical_name | group | direction |
| --- | --- | --- | --- | --- |
| `00 OUT00 b01 Cmd alimentation HT` | `6.5` | `elyse/HT/voltage/set_value` | `ht_hf` | `write` |
| `01 OUT01 b05 Cmd DeQing` | `0.0` | `elyse/modulator/deqing/set_value` | `modulator` | `write` |
| `02 OUT02 b09 Cmd position fente HG` | `4.755` | `elyse/slit/jaw_hg/set_value` | `motion` | `write` |
| `03 OUT03 b13 Cmd position fente HD` | `4.755` | `elyse/slit/jaw_hd/set_value` | `motion` | `write` |
| `04 OUT04 b17 Cmd position translateur Ecran 1` | `2.126` | `elyse/screens/1/translator/set_value` | `motion` | `write` |
| `05 OUT05 b21 Cmd position translateur Ecran 2` | `2.126` | `elyse/screens/2/translator/set_value` | `motion` | `write` |
| `06 OUT06 b25 Cmd position translateur Ecran 3` | `2.126` | `elyse/screens/3/translator/set_value` | `motion` | `write` |
| `07 OUT07 b29 RÃ©serve` | `0.0` | `` | `placeholder` | `ignore` |
| `08 OUT08 b33 RÃ©serve` | `0.0` | `` | `placeholder` | `ignore` |
| `09 OUT09 b37 RÃ©serve` | `0.0` | `` | `placeholder` | `ignore` |
