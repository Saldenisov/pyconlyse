# C4_IN_DIO96 Raw To Canonical Mapping

Raw-to-canonical mapping for C4_IN_DIO96 based on the full inventory screenshots. Raw labels are preserved; canonical names are internal Python DS names.

| Raw Name | Live Value | Canonical Name | Group | Direction |
|---|---:|---|---|---|
| `00 APA0 b47 Eau corps Klystron` | `1.0` | `elyse/modulator/klystron/body_water` | `modulator` | `read` |
| `01 APA1 b45 Eau collecteur Klystron` | `1.0` | `elyse/modulator/klystron/collector_water` | `modulator` | `read` |
| `02 APA2 b43 Eau cuve Klystron` | `1.0` | `elyse/modulator/klystron/tank_water` | `modulator` | `read` |
| `03 APA3 b41 Vide Klystron` | `1.0` | `elyse/modulator/klystron/vacuum_ok` | `modulator` | `read` |
| `04 APA4 b39 Ventilation Thyratron` | `1.0` | `elyse/modulator/thyratron/ventilation` | `modulator` | `read` |
| `05 APA5 b37 Niveau d'huile cuve Klystron` | `1.0` | `elyse/modulator/klystron/tank_oil_level` | `modulator` | `read` |
| `06 APA6 b35 V chauffage Thyratron` | `1.0` | `elyse/modulator/thyratron/voltages/heating/status` | `modulator` | `read` |
| `07 APA7 b33 I chauffage Thyratron` | `1.0` | `elyse/modulator/thyratron/currents/heating/status` | `modulator` | `read` |
| `08 APB0 b31 V chauffage Klystron` | `1.0` | `elyse/modulator/klystron/voltages/heating/status` | `modulator` | `read` |
| `09 APB1 b29 I chauffage Klystron` | `1.0` | `elyse/modulator/klystron/currents/heating/status` | `modulator` | `read` |
| `10 APB2 b27 I De QING` | `1.0` | `elyse/modulator/deqing/current/status` | `modulator` | `read` |
| `11 APB3 b25 I rÃ©servoir Thyratron` | `1.0` | `elyse/modulator/thyratron_reservoir/current/status` | `modulator` | `read` |
| `12 APB4 b23 SÃ©curitÃ© Thyratron` | `1.0` | `elyse/modulator/thyratron/safety` | `safety` | `read` |
| `13 APB5 b21 Pression SF6` | `1.0` | `elyse/ht_hf/sf6_pressure` | `safety` | `read` |
| `14 APB6 b19 I prÃ©magnÃ©tisation` | `1.0` | `elyse/modulator/paramagnetization/current/status` | `modulator` | `read` |
| `15 APB7 b17 Contact porte` | `1.0` | `elyse/safety/door/contact` | `safety` | `read` |
| `16 APC0 b15 Contact perche` | `1.0` | `elyse/safety/probe/contact` | `safety` | `read` |
| `17 APC1 b13 Contact capot cuve` | `1.0` | `elyse/modulator/klystron/tank_cover/contact` | `safety` | `read` |
| `18 APC2 b11 Fin Tempo` | `1.0` | `elyse/modulator/timer/end` | `modulator` | `read` |
| `19 APC3 b09 DÃ©bit eau Canon` | `1.0` | `elyse/cooling/canon/water_flow` | `cooling` | `read` |
| `20 APC4 b07 Eau focale Klystron` | `1.0` | `elyse/modulator/klystron_focale/water` | `modulator` | `read` |
| `21 APC5 b05 I Focale 1` | `1.0` | `elyse/modulator/focale1/current/status` | `modulator` | `read` |
| `22 APC6 b03 I Focale 2` | `1.0` | `elyse/modulator/focale2/current/status` | `modulator` | `read` |
| `23 APC7 b01 I Focale 3` | `1.0` | `elyse/modulator/focale3/current/status` | `modulator` | `read` |
| `24 BPA0 b48 RÃ©serve` | `1.0` | `` | `` | `read` |
| `25 BPA1 b46 RÃ©serve` | `1.0` | `` | `` | `read` |
| `26 BPA2 b44 RÃ©serve` | `1.0` | `` | `` | `read` |
| `27 BPA3 b42 DÃ©phaseur butÃ©e MIN` | `1.0` | `elyse/HF/dephaser/min_limit` | `ht_hf` | `read` |
| `28 BPA4 b40 DÃ©phaseur butÃ©e MAX` | `1.0` | `elyse/HF/dephaser/max_limit` | `ht_hf` | `read` |
| `29 BPA5 b38 AttÃ©nuateur butÃ©e MIN` | `1.0` | `elyse/HF/attenuator/min_limit` | `ht_hf` | `read` |
| `30 BPA6 b36 AttÃ©nuateur butÃ©e MAX` | `1.0` | `elyse/HF/attenuator/max_limit` | `ht_hf` | `read` |
| `31 BPA7 b34 RÃ©serve` | `1.0` | `` | `` | `read` |
| `32 BPB0 b32 Relais 2 ouvert` | `1.0` | `elyse/HT/relay2/open` | `ht_hf` | `read` |
| `33 BPB1 b30 HF incident Canon` | `1.0` | `elyse/HF/canon/incident` | `ht_hf` | `read` |
| `34 BPB2 b28 HF incident Section` | `1.0` | `elyse/HF/section/incident` | `ht_hf` | `read` |
| `35 BPB3 b26 V alimentation HT` | `1.0` | `elyse/HT/voltage/status` | `ht_hf` | `read` |
| `36 BPB4 b24 I alimentation HT` | `1.0` | `elyse/HT/current/status` | `ht_hf` | `read` |
| `37 BPB5 b22 Relais 1 ouvert` | `1.0` | `elyse/HT/relay1/open` | `ht_hf` | `read` |
| `38 BPB6 b20 DÃ©bit eau Section` | `1.0` | `elyse/cooling/section/water_flow/status` | `cooling` | `read` |
| `39 BPB7 b18 RÃ©sistivitÃ©` | `1.0` | `elyse/cooling/water/resistivity` | `cooling` | `read` |
| `40 BPC0 b16 Vide Injection` | `1.0` | `elyse/vacuum/injection/status` | `vacuum` | `read` |
| `41 BPC1 b14 I Thyratron` | `1.0` | `elyse/modulator/thyratron/currents/power/status` | `modulator` | `read` |
| `42 BPC2 b12 I fin de ligne` | `1.0` | `elyse/modulator/line_end/current/status` | `modulator` | `read` |
| `43 BPC3 b10 V LAR` | `1.0` | `elyse/modulator/LAR/voltage/status` | `modulator` | `read` |
| `44 BPC4 b08 V Klystron` | `1.0` | `elyse/modulator/klystron/voltages/power/status` | `modulator` | `read` |
| `45 BPC5 b06 I Klystron` | `1.0` | `elyse/modulator/klystron/currents/power/status` | `modulator` | `read` |
| `46 BPC6 b04 Radioprotection 1, coupure HT` | `1.0` | `elyse/safety/radioprotection1/ht_cutoff` | `safety` | `read` |
| `47 BPC7 b02 Radioprotection 2, coupure HF` | `1.0` | `elyse/safety/radioprotection2/hf_cutoff` | `safety` | `read` |
| `48 CPA0 b97 Alimentation HT en marche` | `1.0` | `elyse/HT/power/running` | `ht_hf` | `read` |
| `49 CPA1 b95 Alimentation HT en dÃ©faut` | `1.0` | `elyse/HT/power/fault` | `ht_hf` | `read` |
| `50 CPA2 b93 RÃ©serve` | `1.0` | `` | `` | `read` |
| `51 CPA3 b91 RÃ©serve` | `1.0` | `` | `` | `read` |
| `52 CPA4 b89 Contact porte lÃ©gÃ¨re fermÃ©e` | `0.0` | `elyse/safety/door/light/closed` | `safety` | `read` |
| `53 CPA5 b87 Contact porte lourde fermÃ©e` | `0.0` | `elyse/safety/door/heavy/closed` | `safety` | `read` |
| `54 CPA6 b85 Contact porte secours fermÃ©e` | `1.0` | `elyse/safety/door/emergency/closed` | `safety` | `read` |
| `55 CPA7 b83 Contact porte laser fermÃ©e` | `1.0` | `elyse/safety/door/laser/closed` | `safety` | `read` |
| `56 CPB0 b81 Totalisation des AU` | `1.0` | `elyse/safety/emergency_stop/totalized` | `safety` | `read` |
| `57 CPB1 b79 Rondier 1` | `1.0` | `elyse/safety/roundier/1` | `safety` | `read` |
| `58 CPB2 b77 Rondier 2` | `1.0` | `elyse/safety/roundier/2` | `safety` | `read` |
| `59 CPB3 b75 Rondier 3` | `1.0` | `elyse/safety/roundier/3` | `safety` | `read` |
| `60 CPB4 b73 Totalisation des rondiers` | `1.0` | `elyse/safety/roundier/totalized` | `safety` | `read` |
| `61 CPB5 b71 Position BACO PA / MOD` | `0.0` | `elyse/motion/baco/pa_mod/position` | `motion` | `read` |
| `62 CPB6 b69 Position BACO de TIR` | `1.0` | `elyse/motion/baco/fire_position` | `motion` | `read` |
| `63 CPB7 b67 Position occulteur LASER` | `0.0` | `elyse/laser/occulter/position` | `motion` | `read` |
