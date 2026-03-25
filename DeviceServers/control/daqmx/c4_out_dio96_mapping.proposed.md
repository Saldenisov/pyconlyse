# C4_OUT_DIO96 Raw To Canonical Mapping

Raw-to-canonical mapping for the visible C4_OUT_DIO96 panel. Raw labels are preserved; canonical names are internal Python DS names.

| Raw Name | Live Value | Canonical Name | Group | Direction |
|---|---:|---|---|---|
| `00 CPC0 b65 Marche modulateur Bas Niveau` | `0.0` | `elyse/modulator/low_level/start` | `modulator` | `write` |
| `01 CPC1 b63 ArrÃªt modulateur Bas Niveau` | `1.0` | `elyse/modulator/low_level/stop` | `modulator` | `write` |
| `02 CPC2 b61 RAZ modulateur Bas Niveau` | `0.0` | `elyse/modulator/low_level/reset` | `modulator` | `write` |
| `03 CPC3 b59 Marche Chauffage` | `0.0` | `elyse/modulator/heating/start` | `modulator` | `write` |
| `04 CPC4 b57 ArrÃªt Chauffage` | `1.0` | `elyse/modulator/heating/stop` | `modulator` | `write` |
| `05 CPC5 b55 Marche prÃ©magnÃ©tisation` | `0.0` | `elyse/modulator/paramagnetization/start` | `modulator` | `write` |
| `06 CPC6 b53 ArrÃªt prÃ©magnÃ©tisation` | `1.0` | `elyse/modulator/paramagnetization/stop` | `modulator` | `write` |
| `07 CPC7 b51 Marche focale Klystron` | `0.0` | `elyse/modulator/klystron_focale/start` | `modulator` | `write` |
| `08 DPA0 b98 ArrÃªt focale Klystron` | `1.0` | `elyse/modulator/klystron_focale/stop` | `modulator` | `write` |
| `09 DPA1 b96 RÃ©serve` | `0.0` | `` | `` | `None` |
| `10 DPA2 b94 RÃ©serve` | `0.0` | `` | `` | `None` |
| `11 DPA3 b92 RÃ©serve` | `0.0` | `` | `` | `None` |
| `12 DPA4 b90 RÃ©serve` | `0.0` | `` | `` | `None` |
| `13 DPA5 b88 RÃ©serve` | `0.0` | `` | `` | `None` |
| `14 DPA6 b86 RÃ©serve` | `0.0` | `` | `` | `None` |
| `15 DPA7 b84 RÃ©serve` | `0.0` | `` | `` | `None` |
| `16 DPB0 b82 Marche relais HT 1` | `0.0` | `elyse/HT/relay1/start` | `ht_hf` | `write` |
| `17 DPB1 b80 ArrÃªt relais HT 1` | `1.0` | `elyse/HT/relay1/stop` | `ht_hf` | `write` |
| `18 DPB2 b78 Marche alimentation HT` | `0.0` | `elyse/HT/power/start` | `ht_hf` | `write` |
| `19 DPB3 b76 ArrÃªt alimentation HT` | `1.0` | `elyse/HT/power/stop` | `ht_hf` | `write` |
| `20 DPB4 b74 RAZ alimentation HT` | `0.0` | `elyse/HT/power/reset` | `ht_hf` | `write` |
| `21 DPB5 b72 RÃ©serve` | `0.0` | `` | `` | `None` |
| `22 DPB6 b70 RÃ©serve` | `0.0` | `` | `` | `None` |
| `23 DPB7 b68 RÃ©serve` | `0.0` | `` | `` | `None` |
| `24 DPC0 b66 RÃ©serve` | `0.0` | `` | `` | `None` |
| `25 DPC1 b64 RÃ©serve` | `0.0` | `` | `` | `None` |
| `26 DPC2 b62 RÃ©serve` | `0.0` | `` | `` | `None` |
| `27 DPC3 b60 RÃ©serve` | `0.0` | `` | `` | `None` |
| `28 DPC4 b58 RÃ©serve` | `0.0` | `` | `` | `None` |
| `29 DPC5 b56 M/A alimentation Att. et Deph.` | `0.0` | `elyse/HF/attenuator_dephaser/power_toggle` | `ht_hf` | `write` |
| `30 DPC6 b54 RÃ©serve` | `0.0` | `` | `` | `None` |
| `31 DPC7 b52 RÃ©serve` | `0.0` | `` | `` | `None` |
