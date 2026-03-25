# C3_OUT_DIO96 Raw To Canonical Mapping

Partial raw-to-canonical mapping for C3_OUT_DIO96 based on the visible upper portion of the panel. Raw labels are preserved; canonical names are internal Python DS names.

Visible range: `00..10`

| Raw Name | Live Value | Canonical Name | Group | Direction |
|---|---:|---|---|---|
| `00 CPB0 b81 Marche Reffroidissement Canon` | `0.0` | `elyse/cooling/canon/start` | `cooling` | `write` |
| `01 CPB1 b79 ArrÃªt Reffroidissement Canon` | `1.0` | `` | `cooling` | `read` |
| `02 CPB2 b77 RAZ Reffroidissement Canon` | `0.0` | `elyse/cooling/canon/reset` | `cooling` | `write` |
| `03 CPB3 b75 Marche Reffroidissement Section` | `0.0` | `elyse/cooling/section/start` | `cooling` | `write` |
| `04 CPB4 b73 ArrÃªt Reffroidissement Section` | `1.0` | `` | `cooling` | `read` |
| `05 CPB5 b71 RAZ Reffroidissement Section` | `0.0` | `elyse/cooling/section/reset` | `cooling` | `write` |
| `06 CPB6 b69 RÃ©serve` | `0.0` | `` | `` | `read` |
| `07 CPB7 b67 RÃ©serve` | `0.0` | `` | `` | `read` |
| `08 CPC0 b65 RÃ©serve` | `0.0` | `` | `` | `read` |
| `09 CPC1 b63 Marche Triplet 1-1` | `0.0` | `elyse/magnets/triplet1-1/start` | `magnets` | `write` |
| `10 CPC2 b61 RÃ©serve` | `0.0` | `` | `` | `read` |
