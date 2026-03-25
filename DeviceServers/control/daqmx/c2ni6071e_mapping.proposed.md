# C2NI6071E Raw To Canonical Mapping

Both layers are kept: the raw LabVIEW name and the internal canonical name.

Note: the trailing `2` in the panel title `C2NI6071E 2` is treated as an accidental panel label, not part of the card name.

| raw_name | value | canonical_name | group | direction |
| --- | --- | --- | --- | --- |
| `00 ACH00 b03 Mes V Chauffage Thyratron` | `0.0160546875` | `elyse/modulator/thyratron/voltages/heating/value` | `modulator` | `read` |
| `01 ACH01 b05 Mes V Chauffage Klystron` | `0.00703125` | `elyse/modulator/klystron/voltages/heating/value` | `modulator` | `read` |
| `02 ACH02 b07 Mes I D'Qing` | `0.0009765625` | `elyse/modulator/deqing/current/value` | `modulator` | `read` |
| `04 ACH04 b11 Mes I PrÃ©magnÃ©tisation` | `-0.02830078125` | `elyse/modulator/paramagnetization/current/value` | `modulator` | `read` |
| `05 ACH05 b13 Mes I Focalisateur 1` | `-0.00591796875` | `elyse/modulator/focale1/current/value` | `modulator` | `read` |
| `06 ACH06 b15 Mes I Focalisateur 3` | `-0.019873046875` | `elyse/modulator/focale3/current/value` | `modulator` | `read` |
| `07 ACH07 b17 Mes V alimentation HT` | `0.00357421875` | `elyse/HT/voltage/value` | `ht_hf` | `read` |
| `08 ACH08 b04 Mes I Chauffage Thyratron` | `0.082421875` | `elyse/modulator/thyratron/currents/heating/value` | `modulator` | `read` |
| `09 ACH09 b06 Mes I  Chauffage Klystron` | `0.0462890625` | `elyse/modulator/klystron/currents/heating/value` | `modulator` | `read` |
| `10 ACH10 b08 Mes I RÃ©servoir Thyratron` | `-0.019140625` | `elyse/modulator/thyratron_reservoir/current/value` | `modulator` | `read` |
| `11 ACH11 b10 Mes I Thyratron` | `-0.00078125` | `elyse/modulator/thyratron/currents/power/value` | `modulator` | `read` |
| `12 ACH12 b12 Mes I fin de Ligne` | `-0.078125` | `elyse/modulator/line_end/current/value` | `modulator` | `read` |
| `13 ACH13 b14 Mes I Focalisateur 2` | `-0.010791015625` | `elyse/modulator/focale2/current/value` | `modulator` | `read` |
| `15 ACH15 b18 Mes I alimentation HT` | `-0.00021484375` | `elyse/HT/current/value` | `ht_hf` | `read` |
| `16 ACH16 b51 Mes V Klystron` | `-3.486328125` | `elyse/modulator/klystron/voltages/power/value` | `modulator` | `read` |
| `17 ACH17 b53 Mes V LAR` | `-0.067075195313` | `elyse/modulator/LAR/voltage/value` | `modulator` | `read` |
| `18 ACH18 b55 Mes HF directe Canon` | `-0.01171875` | `elyse/HF/canon/value` | `ht_hf` | `read` |
| `19 ACH19 b57 Mes I Faraday 1` | `0.02197265625` | `elyse/faraday/1/current/value` | `diagnostics` | `read` |
| `20 ACH20 b59 Mes I Faraday 3` | `-0.01025390625` | `elyse/faraday/3/current/value` | `diagnostics` | `read` |
| `21 ACH21 b61 Mes WCM 1B` | `0.0146484375` | `elyse/wcm/1b/value` | `diagnostics` | `read` |
| `22 ACH22 b63 Mes WCM 1D` | `0.00439453125` | `elyse/wcm/1d/value` | `diagnostics` | `read` |
| `23 ACH23 b65 Mes WCM 2B` | `0.130055573574` | `elyse/wcm/2b/value` | `diagnostics` | `read` |
| `24 ACH24 b52 Mes I Klystron` | `-0.322265625` | `elyse/modulator/klystron/currents/power/value` | `modulator` | `read` |
| `26 ACH26 b56 Mes HF directe Section` | `0.025` | `elyse/HF/section/value` | `ht_hf` | `read` |
| `27 ACH27 b58 Mes I Faraday 2` | `0.09375` | `elyse/faraday/2/current/value` | `diagnostics` | `read` |
| `28 ACH28 b60 Mes WCM 1H` | `0.01806640625` | `elyse/wcm/1h/value` | `diagnostics` | `read` |
| `29 ACH29 b62 Mes WCM 1G` | `0.03515625` | `elyse/wcm/1g/value` | `diagnostics` | `read` |
| `30 ACH30 b64 Mes WCM 2H` | `0.130994575977` | `elyse/wcm/2h/value` | `diagnostics` | `read` |
| `31 ACH31 b66 Mes WCM 2G` | `0.130055573574` | `elyse/wcm/2g/value` | `diagnostics` | `read` |
| `32 ACH32 b67 Mes WCM 2D` | `0.130994575977` | `elyse/wcm/2d/value` | `diagnostics` | `read` |
| `33 ACH33 b69 Mes WCM 4` | `0.130330978877` | `elyse/wcm/4/value` | `diagnostics` | `read` |
| `34 ACH34 b71 Mes Fente H position mors D` | `2.4734609375` | `elyse/slit/h/jaw_d/position/value` | `motion` | `read` |
| `35 ACH35 b73 Mes Fente V position mors H` | `26.268676757812` | `elyse/slit/v/jaw_h/position/value` | `motion` | `read` |
| `36 ACH36 b77 Mes position Ecran 1` | `21.009457519531` | `elyse/screens/1/position/value` | `motion` | `read` |
| `37 ACH37 b79 Mes position Ecran 3` | `21.323626953125` | `elyse/screens/3/position/value` | `motion` | `read` |
| `38 ACH38 b81 Mes I obcs Faraday 2` | `4.15234375` | `elyse/faraday/2/obcs_current/value` | `diagnostics` | `read` |
| `40 ACH40 b68 Mes WCM 3` | `-15.71316043293` | `elyse/wcm/3/value` | `diagnostics` | `read` |
| `41 ACH41 b70 Mes WCM 5` | `0.390330966074` | `elyse/wcm/5/value` | `diagnostics` | `read` |
| `42 ACH42 b72 Mes Fente H position mors G` | `-2.548263183594` | `elyse/slit/h/jaw_g/position/value` | `motion` | `read` |
| `43 ACH43 b74 Mes Fente V position mors B` | `1.091674804687` | `elyse/slit/v/jaw_b/position/value` | `motion` | `read` |
| `44 ACH44 b78 Mes position Ecran 2` | `21.338587402344` | `elyse/screens/2/position/value` | `motion` | `read` |
| `45 ACH45 b80 Mes I obcs Faraday 1` | `4.2060546875` | `elyse/faraday/1/obcs_current/value` | `diagnostics` | `read` |
| `46 ACH46 b82 Mes I obcs Faraday 3` | `4.1884765625` | `elyse/faraday/3/obcs_current/value` | `diagnostics` | `read` |
| `47 ACH47 b84 Mes position Miroir X` | `19.2392578125` | `elyse/laser/mirror/x/position/value` | `laser` | `read` |
| `48 ACH48 b85 Mes position Miroir Y` | `18.67236328125` | `elyse/laser/mirror/y/position/value` | `laser` | `read` |
| `49 ACH49 b87 Signal laser 2` | `41.81640625` | `elyse/laser/signal2/value` | `laser` | `read` |
| `56 ACH56 b86 Signal laser 1` | `41.865234375` | `elyse/laser/signal1/value` | `laser` | `read` |
