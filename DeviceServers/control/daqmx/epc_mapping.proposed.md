# EPC Raw To Canonical Mapping

Raw-to-canonical mapping for EPC based on the visible state panel. Raw labels are preserved; canonical names are internal Python DS names.

| Raw Name | Live Value | Canonical Name | Group | Direction |
|---|---:|---|---|---|
| `TIR OK` | `0.0` | `elyse/epc/tir/ok` | `sequence` | `read` |
| `PRETIR OK` | `0.0` | `elyse/epc/pretir/ok` | `sequence` | `read` |
| `VEILLE OK` | `0.0` | `elyse/epc/veille/ok` | `sequence` | `read` |
| `ARRET OK` | `0.0` | `elyse/epc/arret/ok` | `sequence` | `read` |
| `ARRET <> VEILLE` | `0.0` | `elyse/epc/arret_to_veille` | `sequence` | `read` |
| `TIR ED` | `0.0` | `elyse/epc/tir/ed` | `sequence` | `read` |
| `PRETIR ED` | `0.0` | `elyse/epc/pretir/ed` | `sequence` | `read` |
| `VEILLE ED` | `0.0` | `elyse/epc/veille/ed` | `sequence` | `read` |
| `VEILLE ED 2` | `0.0` | `elyse/epc/veille/ed2` | `sequence` | `read` |
| `PRETIR <> VEILLE` | `0.0` | `elyse/epc/pretir_to_veille` | `sequence` | `read` |
| `TIR <> PRETIR` | `0.0` | `elyse/epc/tir_to_pretir` | `sequence` | `read` |
| `Procédure combiné EC` | `` | `` | `` | `read` |
