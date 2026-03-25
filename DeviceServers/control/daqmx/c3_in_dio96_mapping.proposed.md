# C3_IN_DIO96 Raw To Canonical Mapping

Raw-to-canonical mapping for C3_IN_DIO96 based on the full inventory screenshots. Raw labels are preserved; canonical names are internal Python DS names.

| Raw Name | Live Value | Canonical Name | Group | Direction |
|---|---:|---|---|---|
| `00 APA0 b47 Reffroidissement Canon marche` | `1.0` | `elyse/cooling/canon/running` | `cooling` | `read` |
| `01 APA1 b45 Reffroidissement Canon dÃ©faut` | `1.0` | `elyse/cooling/canon/fault` | `cooling` | `read` |
| `02 APA2 b43 Vanne Reffroidissement Canon fermÃ©e` | `1.0` | `elyse/cooling/canon/valve/closed` | `cooling` | `read` |
| `03 APA3 b41 Vanne Reffroidissement Canon ouverte` | `0.0` | `elyse/cooling/canon/valve/open` | `cooling` | `read` |
| `04 APA4 b39 DÃ©bit Reffroidissement Canon dÃ©faut` | `1.0` | `elyse/cooling/canon/flow/fault` | `cooling` | `read` |
| `05 APA5 b37 Local / Distance Canon (local=0V)` | `1.0` | `elyse/cooling/canon/local_distance` | `cooling` | `read` |
| `06 APA6 b35 Reffroidissement Section marche` | `1.0` | `elyse/cooling/section/running` | `cooling` | `read` |
| `07 APA7 b33 Reffroidissement Section dÃ©faut` | `1.0` | `elyse/cooling/section/fault` | `cooling` | `read` |
| `08 APB0 b31 Vanne Reffroidissement Section fermÃ©e` | `1.0` | `elyse/cooling/section/valve/closed` | `cooling` | `read` |
| `09 APB1 b29 Vanne Reffroidissement Section ouverte` | `0.0` | `elyse/cooling/section/valve/open` | `cooling` | `read` |
| `10 APB2 b27 DÃ©bit eau Reffroidissement Section` | `1.0` | `elyse/cooling/section/water_flow` | `cooling` | `read` |
| `11 APB3 b25 Loc/dist. Reffr. Section (local=0V)` | `1.0` | `elyse/cooling/section/local_distance` | `cooling` | `read` |
| `12 APB4 b23 Triplet 1-1 en marche` | `1.0` | `elyse/magnets/triplet1-1/running` | `magnets` | `read` |
| `13 APB5 b21 Triplet 1-1 en dÃ©faut` | `1.0` | `elyse/magnets/triplet1-1/fault` | `magnets` | `read` |
| `14 APB6 b19 Triplet 1-2 en marche` | `1.0` | `elyse/magnets/triplet1-2/running` | `magnets` | `read` |
| `15 APB7 b17 Triplet 1-2 en dÃ©faut` | `1.0` | `elyse/magnets/triplet1-2/fault` | `magnets` | `read` |
| `16 APC0 b15 RÃ©serve` | `1.0` | `` | `` | `read` |
| `17 APC1 b13 RÃ©serve` | `1.0` | `` | `` | `read` |
| `18 APC2 b11 Triplet 2-1 en marche` | `1.0` | `elyse/magnets/triplet2-1/running` | `magnets` | `read` |
| `19 APC3 b09 Triplet 2-1 en dÃ©faut` | `0.0` | `elyse/magnets/triplet2-1/fault` | `magnets` | `read` |
| `20 APC4 b07 Triplet 2-2 en marche` | `1.0` | `elyse/magnets/triplet2-2/running` | `magnets` | `read` |
| `21 APC5 b05 Triplet 2-2 en dÃ©faut` | `0.0` | `elyse/magnets/triplet2-2/fault` | `magnets` | `read` |
| `22 APC6 b03 RÃ©serve` | `1.0` | `` | `` | `read` |
| `23 APC7 b01 RÃ©serve` | `1.0` | `` | `` | `read` |
| `24 BPA0 b48 QuadripÃ´le 1 en marche` | `` | `` | `` | `read` |
| `25 BPA1 b46 QuadripÃ´le 1 en dÃ©faut` | `` | `` | `` | `read` |
| `26 BPA2 b44 QuadripÃ´le 2 en marche` | `` | `` | `` | `read` |
| `27 BPA3 b42 QuadripÃ´le 2 en dÃ©faut` | `` | `` | `` | `read` |
| `28 BPA4 b40 Focale injection en marche` | `1.0` | `elyse/magnets/focale/running` | `magnets` | `read` |
| `29 BPA5 b38 Focale injection en dÃ©faut` | `1.0` | `elyse/magnets/focale/fault` | `magnets` | `read` |
| `30 BPA6 b36 eau focale injection en dÃ©faut` | `1.0` | `elyse/magnets/focale/water_fault` | `magnets` | `read` |
| `31 BPA7 b34 DipÃ´le 1 en marche` | `1.0` | `elyse/magnets/dipole1/running` | `magnets` | `read` |
| `32 BPB0 b32 DipÃ´le 1 en dÃ©faut` | `1.0` | `elyse/magnets/dipole1/fault` | `magnets` | `read` |
| `33 BPB1 b30 DipÃ´le 2 en marche` | `1.0` | `elyse/magnets/dipole2/running` | `magnets` | `read` |
| `34 BPB2 b28 DipÃ´le 2 en dÃ©faut` | `1.0` | `elyse/magnets/dipole2/fault` | `magnets` | `read` |
| `35 BPB3 b26 Guidage H 1 en marche` | `1.0` | `elyse/magnets/Cor_H1/running` | `magnets` | `read` |
| `36 BPB4 b24 Guidage H 1 en dÃ©faut` | `1.0` | `elyse/magnets/Cor_H1/fault` | `magnets` | `read` |
| `37 BPB5 b22 Guidage V 1 en marche` | `1.0` | `elyse/magnets/Cor_V1/running` | `magnets` | `read` |
| `38 BPB6 b20 Guidage V 1 en dÃ©faut` | `1.0` | `elyse/magnets/Cor_V1/fault` | `magnets` | `read` |
| `39 BPB7 b18 Guidage H 2 en marche` | `1.0` | `elyse/magnets/Cor_H2/running` | `magnets` | `read` |
| `40 BPC0 b16 Guidage H 2 en dÃ©faut` | `0.0` | `elyse/magnets/Cor_H2/fault` | `magnets` | `read` |
| `41 BPC1 b14 Guidage V 2 en marche` | `1.0` | `elyse/magnets/Cor_V2/running` | `magnets` | `read` |
| `42 BPC2 b12 Guidage V 2 en dÃ©faut` | `0.0` | `elyse/magnets/Cor_V2/fault` | `magnets` | `read` |
| `43 BPC3 b10 Guidage H 3 en marche` | `1.0` | `elyse/magnets/Cor_H3/running` | `magnets` | `read` |
| `44 BPC4 b08 Guidage H 3 en dÃ©faut` | `1.0` | `elyse/magnets/Cor_H3/fault` | `magnets` | `read` |
| `45 BPC5 b06 Guidage V 3 en marche` | `1.0` | `elyse/magnets/Cor_V3/running` | `magnets` | `read` |
| `46 BPC6 b04 Guidage V 3 en dÃ©faut` | `0.0` | `elyse/magnets/Cor_V3/fault` | `magnets` | `read` |
| `47 BPC7 b02 Guidage H 4 en marche` | `1.0` | `elyse/magnets/Cor_H4/running` | `magnets` | `read` |
| `48 CPA0 b97 Guidage H 4 en dÃ©faut` | `1.0` | `elyse/magnets/Cor_H4/fault` | `magnets` | `read` |
| `49 CPA1 b95 Guidage V 4 en marche` | `1.0` | `elyse/magnets/Cor_V4/running` | `magnets` | `read` |
| `50 CPA2 b93 Guidage V 4 en dÃ©faut` | `0.0` | `elyse/magnets/Cor_V4/fault` | `magnets` | `read` |
| `51 CPA3 b91 RÃ©serve` | `1.0` | `` | `` | `read` |
| `52 CPA4 b89 RÃ©serve` | `1.0` | `` | `` | `read` |
| `53 CPA5 b87 Guidage V 5 en marche` | `1.0` | `elyse/magnets/Cor_V5/running` | `magnets` | `read` |
| `54 CPA6 b85 Guidage V 5 en dÃ©faut` | `0.0` | `elyse/magnets/Cor_V5/fault` | `magnets` | `read` |
| `55 CPA7 b83 RÃ©serve` | `1.0` | `` | `` | `read` |
