# C6NI6703 Raw To Canonical Mapping

Both layers are kept: the raw LabVIEW name and the internal canonical name.

Important: `Cor_H5` remains unresolved. This full inventory confirms `08 OUT08 b33` is reserve and `09 OUT09 b37` is `Cmd Guidage V5`.

| raw_name | value | canonical_name | group | direction |
| --- | --- | --- | --- | --- |
| `00 OUT00 b01 Cmd Guidage H1` | `0.0` | `elyse/magnets/Cor_H1/set_value` | `magnets` | `write` |
| `01 OUT01 b05 Cmd Guidage V1` | `0.0` | `elyse/magnets/Cor_V1/set_value` | `magnets` | `write` |
| `02 OUT02 b09 Cmd Guidage H2` | `0.0` | `elyse/magnets/Cor_H2/set_value` | `magnets` | `write` |
| `03 OUT03 b13 Cmd Guidage V2` | `0.0` | `elyse/magnets/Cor_V2/set_value` | `magnets` | `write` |
| `04 OUT04 b17 Cmd Guidage H3` | `0.0` | `elyse/magnets/Cor_H3/set_value` | `magnets` | `write` |
| `05 OUT05 b21 Cmd Guidage V3` | `0.0` | `elyse/magnets/Cor_V3/set_value` | `magnets` | `write` |
| `06 OUT06 b25 Cmd Guidage H4` | `0.0` | `elyse/magnets/Cor_H4/set_value` | `magnets` | `write` |
| `07 OUT07 b29 Cmd Guidage V4` | `0.0` | `elyse/magnets/Cor_V4/set_value` | `magnets` | `write` |
| `08 OUT08 b33 RÃ©serve` | `0.0` | `` | `placeholder` | `ignore` |
| `09 OUT09 b37 Cmd Guidage V5` | `0.0` | `elyse/magnets/Cor_V5/set_value` | `magnets` | `write` |
