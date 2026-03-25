# C1NI6071E Raw To Canonical Mapping

Both layers are kept: the raw LabVIEW name and the internal canonical name.

Important: `Cor_H5` now has a proposed readback channel (`41 ACH41 b70 Mes H5`), but its write channel is still unresolved.

| raw_name | value | canonical_name | group | direction |
| --- | --- | --- | --- | --- |
| `00 ACH00 b03 Mes tempÃ©rature Canon` | `9.970703125` | `elyse/cooling/canon/temperature/measurement` | `cooling` | `read` |
| `01 ACH01 b05 Mes Vide Chambre de prÃ©paration` | `0.015625` | `elyse/vacuum/preparation_chamber/measurement` | `vacuum` | `read` |
| `02 ACH02 b07 Mes Vide Canon (PIQ 12)` | `0.007170410156` | `elyse/vacuum/canon/measurement` | `vacuum` | `read` |
| `03 ACH03 b09 Mes Vide Miroir (PIQ 21)` | `0.018115234375` | `elyse/vacuum/mirror/measurement` | `vacuum` | `read` |
| `04 ACH04 b11 Mes Vide Ecran 1 (PIQ 53-63)` | `0.033154296875` | `elyse/vacuum/screen1/measurement` | `vacuum` | `read` |
| `08 ACH08 b04 Mes tempÃ©rature Section` | `9.87548828125` | `elyse/cooling/section/temperature/measurement` | `cooling` | `read` |
| `09 ACH09 b06 Mes Vide SAS guide HF` | `-0.00048828125` | `elyse/vacuum/HF/measurement` | `vacuum` | `read` |
| `10 ACH10 b08 Mes Vide Section (PIQ 16)` | `-0.01025390625` | `elyse/vacuum/section/measurement` | `vacuum` | `read` |
| `11 ACH11 b10 Mes Vide DIP 1 (PIQ27 + 33)` | `0.01025390625` | `elyse/vacuum/dipole1/measurement` | `vacuum` | `read` |
| `12 ACH12 b12 Mes Vide jauge canon` | `1.41357421875` | `elyse/vacuum/canon_gauge/measurement` | `vacuum` | `read` |
| `16 ACH16 b51 Mes I Triplet 1-1` | `1.201171875` | `elyse/magnets/triplet1-1/value` | `magnets` | `read` |
| `18 ACH18 b55 Mes I Triplet 2-2` | `0.23046875` | `elyse/magnets/triplet2-2/value` | `magnets` | `read` |
| `19 ACH19 b57 Mes I Faraday 1` | `0.02197265625` | `elyse/faraday/1/current/value` | `diagnostics` | `read` |
| `19 ACH19 b57 Mes I QuadripÃ´le 1` | `0.18359375` | `elyse/magnets/qudrupole1/value` | `magnets` | `read` |
| `20 ACH20 b59 Mes I Faraday 3` | `-0.01025390625` | `elyse/faraday/3/current/value` | `diagnostics` | `read` |
| `20 ACH20 b59 Mes I SolÃ©noÃ¯de` | `18.76171875` | `elyse/magnets/focale/value` | `magnets` | `read` |
| `21 ACH21 b61 Mes I DipÃ´le 2` | `3.22265625` | `elyse/magnets/dipole2/value` | `magnets` | `read` |
| `21 ACH21 b61 Mes WCM 1B` | `0.0146484375` | `elyse/wcm/1b/value` | `diagnostics` | `read` |
| `22 ACH22 b63 Mes I Guidage V1` | `0.77685546875` | `elyse/magnets/Cor_V1/value` | `magnets` | `read` |
| `22 ACH22 b63 Mes WCM 1D` | `0.00439453125` | `elyse/wcm/1d/value` | `diagnostics` | `read` |
| `23 ACH23 b65 Mes I Guidage V2` | `0.0595703125` | `elyse/magnets/Cor_V2/value` | `magnets` | `read` |
| `23 ACH23 b65 Mes WCM 2B` | `0.130055573574` | `elyse/wcm/2b/value` | `diagnostics` | `read` |
| `24 ACH24 b52 Mes I Triplet 1-2` | `2.09375` | `elyse/magnets/triplet1-2/value` | `magnets` | `read` |
| `25 ACH25 b54 Mes I Triplet 2-1` | `0.044921875` | `elyse/magnets/triplet2-1/value` | `magnets` | `read` |
| `27 ACH27 b58 Mes I Faraday 2` | `0.09375` | `elyse/faraday/2/current/value` | `diagnostics` | `read` |
| `27 ACH27 b58 Mes I QuadripÃ´le 2` | `-0.099609375` | `elyse/magnets/qudrupole2/value` | `magnets` | `read` |
| `28 ACH28 b60 Mes I DipÃ´le 1` | `-0.140625` | `elyse/magnets/dipole1/value` | `magnets` | `read` |
| `28 ACH28 b60 Mes WCM 1H` | `0.01806640625` | `elyse/wcm/1h/value` | `diagnostics` | `read` |
| `29 ACH29 b62 Mes I Guidage H1` | `-0.0107421875` | `elyse/magnets/Cor_H1/value` | `magnets` | `read` |
| `29 ACH29 b62 Mes WCM 1G` | `0.03515625` | `elyse/wcm/1g/value` | `diagnostics` | `read` |
| `30 ACH30 b64 Mes I Guidage H2` | `-0.0703125` | `elyse/magnets/Cor_H2/value` | `magnets` | `read` |
| `30 ACH30 b64 Mes WCM 2H` | `0.130994575977` | `elyse/wcm/2h/value` | `diagnostics` | `read` |
| `31 ACH31 b66 Mes I correcte DipÃ´le 1 (H3)` | `-0.01318359375` | `elyse/magnets/Cor_H3/value` | `magnets` | `read` |
| `31 ACH31 b66 Mes WCM 2G` | `0.130055573574` | `elyse/wcm/2g/value` | `diagnostics` | `read` |
| `32 ACH32 b67 Mes I Guidage V3` | `0.064453125` | `elyse/magnets/Cor_V3/value` | `magnets` | `read` |
| `32 ACH32 b67 Mes WCM 2D` | `0.130994575977` | `elyse/wcm/2d/value` | `diagnostics` | `read` |
| `33 ACH33 b69 Mes I Guidage V4` | `0.0166015625` | `elyse/magnets/Cor_V4/value` | `magnets` | `read` |
| `33 ACH33 b69 Mes WCM 4` | `0.130330978877` | `elyse/wcm/4/value` | `diagnostics` | `read` |
| `34 ACH34 b71 Mes Fente H position mors D` | `2.4734609375` | `elyse/slit/h/jaw_d/position/value` | `motion` | `read` |
| `34 ACH34 b71 Mes I Guidage V5` | `0.037109375` | `elyse/magnets/Cor_V5/value` | `magnets` | `read` |
| `35 ACH35 b73 Mes Fente V position mors H` | `26.268676757812` | `elyse/slit/v/jaw_h/position/value` | `motion` | `read` |
| `35 ACH35 b73 Mes champ DipÃ´le 2` | `4.296875` | `elyse/magnets/dipole2/field/value` | `magnets` | `read` |
| `36 ACH36 b77 Mes position DÃ©phaseur` | `2.54150390625` | `elyse/HF/dephaser/value` | `ht_hf` | `read` |
| `36 ACH36 b77 Mes position Ecran 1` | `21.009457519531` | `elyse/screens/1/position/value` | `motion` | `read` |
| `37 ACH37 b79 Mes position DÃ©phaseur ajust` | `3.9853515625` | `elyse/HF/dephaser/value_manuel` | `ht_hf` | `read` |
| `37 ACH37 b79 Mes position Ecran 3` | `21.323626953125` | `elyse/screens/3/position/value` | `motion` | `read` |
| `38 ACH38 b81 Mes I obcs Faraday 2` | `4.15234375` | `elyse/faraday/2/obcs_current/value` | `diagnostics` | `read` |
| `38 ACH38 b81 Mesure phase HF2` | `71.4814453125` | `elyse/HF/phase_hf2/value` | `ht_hf` | `read` |
| `40 ACH40 b68 Mes I correcte DipÃ´le 21 (H4)` | `2.2744140625` | `elyse/magnets/Cor_H4/value` | `magnets` | `read` |
| `40 ACH40 b68 Mes WCM 3` | `-15.71316043293` | `elyse/wcm/3/value` | `diagnostics` | `read` |
| `41 ACH41 b70 Mes H5` | `2.234375` | `elyse/magnets/Cor_H5/value` | `magnets` | `read` |
| `41 ACH41 b70 Mes WCM 5` | `0.390330966074` | `elyse/wcm/5/value` | `diagnostics` | `read` |
| `42 ACH42 b72 Mes Fente H position mors G` | `-2.548263183594` | `elyse/slit/h/jaw_g/position/value` | `motion` | `read` |
| `42 ACH42 b72 Mes champ DipÃ´le 2` | `221.58203125` | `elyse/magnets/dipole2/field/value_raw2` | `magnets` | `read` |
| `43 ACH43 b74 Mes Fente V position mors B` | `1.091674804687` | `elyse/slit/v/jaw_b/position/value` | `motion` | `read` |
| `44 ACH44 b78 Mes position Ecran 2` | `21.338587402344` | `elyse/screens/2/position/value` | `motion` | `read` |
| `44 ACH44 b78 Mesure AttÃ©nuateur` | `3.63525390625` | `elyse/HF/attenuator/value` | `ht_hf` | `read` |
| `45 ACH45 b80 Mes I obcs Faraday 1` | `4.2060546875` | `elyse/faraday/1/obcs_current/value` | `diagnostics` | `read` |
| `45 ACH45 b80 Mesure phase HF1` | `66.041015625` | `elyse/magnets/phase_HF_laser/value` | `magnets` | `read` |
