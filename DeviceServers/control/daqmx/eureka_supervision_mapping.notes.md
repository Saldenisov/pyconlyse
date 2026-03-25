# Eureka Supervision Mapping Draft

This document summarizes the draft extraction captured in `/Users/sad/dev/pyconlyse/DeviceServers/control/daqmx/eureka_supervision_mapping.draft.json`.

## Current coverage

- Total extracted channels: 115
- cooling: 2 channels
- ht_hf: 9 channels
- magnets: 40 channels
- modulator: 13 channels
- sync: 33 channels
- vacuum: 18 channels
- read: 61 channels
- write_candidate: 54 channels

## Write candidates visible in the screenshots

- elyse/HT/voltage/set_value
- elyse/preamplifier/set_value
- elyse/sync/NI6071E/delay
- elyse/sync/NI6071E/width
- elyse/sync/frequency/delay
- elyse/sync/frequency/width
- elyse/sync/WCM/delay
- elyse/sync/WCM/width
- elyse/sync/modulator/delay
- elyse/sync/modulator/width
- elyse/sync/HF/delay
- elyse/sync/HF/width
- elyse/sync/Faraday/delay
- elyse/sync/Faraday/width
- elyse/sync/Oscilloscope/delay
- elyse/sync/Oscilloscope/width
- elyse/sync/50Hz_20MHz/delay
- elyse/sync/50Hz_20MHz/width
- elyse/sync/laser_HF/delay
- elyse/sync/laser_HF/width
- elyse/sync/IMAC/delay
- elyse/sync/IMAC/width
- elyse/sync/laser/delay
- elyse/sync/laser/width
- elyse/sync/oscilloscope1/delay
- elyse/sync/oscilloscope1/width
- elyse/sync/oscilloscope2/delay
- elyse/sync/oscilloscope2/width
- elyse/sync/detection1/delay
- elyse/sync/detection1/width
- elyse/sync/detection2/delay
- elyse/sync/detection2/width
- elyse/sync/machine/delay
- elyse/sync/machine/width
- elyse/magnets/focale/set_value
- elyse/magnets/phase_HF_laser/set_value
- elyse/magnets/dipole1/set_value
- elyse/magnets/dipole2/set_value
- elyse/magnets/Cor_H1/set_value
- elyse/magnets/Cor_V1/set_value
- elyse/magnets/Cor_H2/set_value
- elyse/magnets/Cor_V2/set_value
- elyse/magnets/Cor_H3/set_value
- elyse/magnets/Cor_V3/set_value
- elyse/magnets/Cor_H4/set_value
- elyse/magnets/Cor_V4/set_value
- elyse/magnets/Cor_H5/set_value
- elyse/magnets/Cor_V5/set_value
- elyse/magnets/triplet1-1/set_value
- elyse/magnets/triplet1-2/set_value
- elyse/magnets/triplet2-1/set_value
- elyse/magnets/triplet2-2/set_value
- elyse/magnets/qudrupole1/set_value
- elyse/magnets/qudrupole2/set_value

## Groups extracted so far

### cooling
- `elyse/cooling/canon/temperature/measurement` <- `C1NI6071E` / `00 ACH00 b03 Mes temperature Canon` [read, high]
- `elyse/cooling/section/temperature/measurement` <- `C1NI6071E` / `08 ACH08 b04 Mes temperature Section` [read, high]

### ht_hf
- `elyse/HT/voltage/set_value` <- `C9NI6703` / `00 OUT00 b01 Cmd alimentation HT` [write_candidate, high]
- `elyse/preamplifier/set_value` <- `C8NI6703` / `06 OUT06 b25 Cmd amplitude HF preampli` [write_candidate, high]
- `elyse/HT/voltage/value` <- `C2NI6071E` / `07 ACH07 b17 Mes V alimentation HT` [read, high]
- `elyse/HT/current/value` <- `C2NI6071E` / `15 ACH15 b18 Mes I alimentation HT` [read, high]
- `elyse/HF/canon/value` <- `C2NI6071E` / `18 ACH18 b55 Mes HF directe Canon` [read, high]
- `elyse/HF/section/value` <- `C2NI6071E` / `26 ACH26 b56 Mes HF directe Section` [read, high]
- `elyse/HF/dephaser/value` <- `C1NI6071E` / `36 ACH36 b77 Mes position Dephaseur` [read, medium]
- `elyse/HF/dephaser/value_manuel` <- `C1NI6071E` / `37 ACH37 b79 Mes position Dephaseur ajust` [read, medium]
- `elyse/HF/attenuator/value` <- `C1NI6071E` / `44 ACH44 b78 Mesure Attenuateur` [read, medium]

### magnets
- `elyse/magnets/focale/set_value` <- `C7NI6703` / `05 OUT05 b21 Cmd I Solenoide` [write_candidate, high]
- `elyse/magnets/focale/value` <- `C1NI6071E` / `20 ACH20 b59 Mes I Solenoide` [read, high]
- `elyse/magnets/phase_HF_laser/set_value` <- `C8NI6703` / `05 OUT05 b21 Cmd dephasage HF/LASER` [write_candidate, high]
- `elyse/magnets/phase_HF_laser/value` <- `C1NI6071E` / `45 ACH45 b80 Mesure phase HF1` [read, high]
- `elyse/magnets/dipole1/set_value` <- `C7NI6703` / `08 OUT08 b33 Cmd I Dipole 1` [write_candidate, high]
- `elyse/magnets/dipole1/value` <- `C1NI6071E` / `28 ACH28 b60 Mes I Dipole 1` [read, high]
- `elyse/magnets/dipole2/set_value` <- `C7NI6703` / `09 OUT09 b37 Cmd I Dipole 2` [write_candidate, high]
- `elyse/magnets/dipole2/value` <- `C1NI6071E` / `21 ACH21 b61 Mes I Dipole 2` [read, high]
- `elyse/magnets/Cor_H1/set_value` <- `C6NI6703` / `00 OUT00 b01 Cmd Guidage H1` [write_candidate, high]
- `elyse/magnets/Cor_H1/value` <- `C1NI6071E` / `29 ACH29 b62 Mes I Guidage H1` [read, high]
- `elyse/magnets/Cor_V1/set_value` <- `C6NI6703` / `01 OUT01 b05 Cmd Guidage V1` [write_candidate, high]
- `elyse/magnets/Cor_V1/value` <- `C1NI6071E` / `22 ACH22 b63 Mes I Guidage V1` [read, high]
- `elyse/magnets/Cor_H2/set_value` <- `C6NI6703` / `02 OUT02 b09 Cmd Guidage H2` [write_candidate, high]
- `elyse/magnets/Cor_H2/value` <- `C1NI6071E` / `30 ACH30 b64 Mes I Guidage H2` [read, high]
- `elyse/magnets/Cor_V2/set_value` <- `C6NI6703` / `03 OUT03 b13 Cmd Guidage V2` [write_candidate, high]
- `elyse/magnets/Cor_V2/value` <- `C1NI6071E` / `23 ACH23 b65 Mes I Guidage V2` [read, high]
- `elyse/magnets/Cor_H3/set_value` <- `C6NI6703` / `04 OUT04 b17 Cmd Guidage H3` [write_candidate, high]
- `elyse/magnets/Cor_H3/value` <- `C1NI6071E` / `31 ACH31 b66 Mes I correcte Dipole 1 (H3)` [read, high]
- `elyse/magnets/Cor_V3/set_value` <- `C6NI6703` / `05 OUT05 b21 Cmd Guidage V3` [write_candidate, high]
- `elyse/magnets/Cor_V3/value` <- `C1NI6071E` / `32 ACH32 b67 Mes I Guidage V3` [read, high]
- `elyse/magnets/Cor_H4/set_value` <- `C6NI6703` / `06 OUT06 b25 Cmd Guidage H4` [write_candidate, high]
- `elyse/magnets/Cor_H4/value` <- `C1NI6071E` / `40 ACH40 b68 Mes I correcte Dipole 21 (H4)` [read, high]
- `elyse/magnets/Cor_V4/set_value` <- `C6NI6703` / `07 OUT07 b29 Cmd Guidage V4` [write_candidate, high]
- `elyse/magnets/Cor_V4/value` <- `C1NI6071E` / `33 ACH33 b69 Mes I Guidage V4` [read, high]
- `elyse/magnets/Cor_H5/set_value` <- `C6NI6703` / `08 OUT08 b33 Reserve` [write_candidate, medium]
- `elyse/magnets/Cor_H5/value` <- `C1NI6071E` / `34 ACH34 b71 Mes I Guidage V5` [read, medium]
- `elyse/magnets/Cor_V5/set_value` <- `C6NI6703` / `09 OUT09 b37 Cmd Guidage V5` [write_candidate, high]
- `elyse/magnets/Cor_V5/value` <- `C1NI6071E` / `34 ACH34 b71 Mes I Guidage V5` [read, high]
- `elyse/magnets/triplet1-1/set_value` <- `C7NI6703` / `00 OUT00 b01 Cmd I Triplet 1-1` [write_candidate, high]
- `elyse/magnets/triplet1-1/value` <- `C1NI6071E` / `16 ACH16 b51 Mes I Triplet 1-1` [read, high]
- `elyse/magnets/triplet1-2/set_value` <- `C7NI6703` / `01 OUT01 b05 Cmd I Triplet 1-2` [write_candidate, high]
- `elyse/magnets/triplet1-2/value` <- `C1NI6071E` / `24 ACH24 b52 Mes I Triplet 1-2` [read, high]
- `elyse/magnets/triplet2-1/set_value` <- `C7NI6703` / `03 OUT03 b13 Cmd I Triplet 2-1` [write_candidate, high]
- `elyse/magnets/triplet2-1/value` <- `C1NI6071E` / `25 ACH25 b54 Mes I Triplet 2-1` [read, high]
- `elyse/magnets/triplet2-2/set_value` <- `C7NI6703` / `04 OUT04 b17 Cmd I Triplet 2-2` [write_candidate, high]
- `elyse/magnets/triplet2-2/value` <- `C1NI6071E` / `18 ACH18 b55 Mes I Triplet 2-2` [read, high]
- `elyse/magnets/qudrupole1/set_value` <- `C7NI6703` / `06 OUT06 b25 Cmd I Quad 1` [write_candidate, high]
- `elyse/magnets/qudrupole1/value` <- `C1NI6071E` / `19 ACH19 b57 Mes I Quadripole 1` [read, high]
- `elyse/magnets/qudrupole2/set_value` <- `C7NI6703` / `07 OUT07 b29 Cmd I Quad 2` [write_candidate, high]
- `elyse/magnets/qudrupole2/value` <- `C1NI6071E` / `27 ACH27 b58 Mes I Quadripole 2` [read, high]

### modulator
- `elyse/modulator/focale1/current/value` <- `C2NI6071E` / `05 ACH05 b13 Mes I Focalisateur 1` [read, high]
- `elyse/modulator/focale2/current/value` <- `C2NI6071E` / `13 ACH13 b14 Mes I Focalisateur 2` [read, high]
- `elyse/modulator/focale3/current/value` <- `C2NI6071E` / `06 ACH06 b15 Mes I Focalisateur 3` [read, high]
- `elyse/modulator/LAR/voltage/value` <- `C2NI6071E` / `17 ACH17 b53 Mes V LAR` [read, high]
- `elyse/modulator/line_end/current/value` <- `C2NI6071E` / `12 ACH12 b12 Mes I fin de Ligne` [read, high]
- `elyse/modulator/thyratron/currents/power/value` <- `C2NI6071E` / `11 ACH11 b10 Mes I Thyratron` [read, medium]
- `elyse/modulator/thyratron_reservoir/current/value` <- `C2NI6071E` / `10 ACH10 b08 Mes I Reservoir Thyratron` [read, high]
- `elyse/modulator/paramagnetization/current/value` <- `C2NI6071E` / `04 ACH04 b11 Mes I Premagnetisation` [read, high]
- `elyse/modulator/thyratron/voltages/heating/value` <- `C2NI6071E` / `00 ACH00 b03 Mes V Chauffage Thyratron` [read, high]
- `elyse/modulator/thyratron/currents/heating/value` <- `C2NI6071E` / `08 ACH08 b04 Mes I Chauffage Thyratron` [read, high]
- `elyse/modulator/klystron/currents/power/value` <- `C2NI6071E` / `24 ACH24 b52 Mes I Klystron` [read, high]
- `elyse/modulator/klystron/voltages/power/value` <- `C2NI6071E` / `16 ACH16 b51 Mes V Klystron` [read, high]
- `elyse/modulator/klystron/currents/heating/value` <- `C2NI6071E` / `09 ACH09 b06 Mes I Chauffage Klystron` [read, high]

### sync
- `elyse/sync/NI6071E/delay` <- `C1011NI6602` / `00 OUT00 b05 C10 Delais` [write_candidate, high]
- `elyse/sync/NI6071E/width` <- `C1011NI6602` / `01 OUT00 b05 C10 Largeur` [write_candidate, high]
- `elyse/sync/frequency/delay` <- `C1011NI6602` / `02 OUT01 b09 C10 Delais` [write_candidate, high]
- `elyse/sync/frequency/width` <- `C1011NI6602` / `03 OUT01 b09 C10 Largeur` [write_candidate, high]
- `elyse/sync/WCM/delay` <- `C1011NI6602` / `04 OUT02 b32 C10 Delais` [write_candidate, high]
- `elyse/sync/WCM/width` <- `C1011NI6602` / `05 OUT02 b32 C10 Largeur` [write_candidate, high]
- `elyse/sync/modulator/delay` <- `C1011NI6602` / `06 OUT03 b29 C10 Delais` [write_candidate, high]
- `elyse/sync/modulator/width` <- `C1011NI6602` / `07 OUT03 b29 C10 Largeur` [write_candidate, high]
- `elyse/sync/HF/delay` <- `C1011NI6602` / `08 OUT04 b26 C10 Delais` [write_candidate, high]
- `elyse/sync/HF/width` <- `C1011NI6602` / `09 OUT04 b26 C10 Largeur` [write_candidate, high]
- `elyse/sync/Faraday/delay` <- `C1011NI6602` / `10 OUT05 b23 C10 Delais` [write_candidate, high]
- `elyse/sync/Faraday/width` <- `C1011NI6602` / `11 OUT05 b23 C10 Largeur` [write_candidate, high]
- `elyse/sync/Oscilloscope/delay` <- `C1011NI6602` / `12 OUT06 b53 C10 Delais` [write_candidate, high]
- `elyse/sync/Oscilloscope/width` <- `C1011NI6602` / `13 OUT06 b53 C10 Largeur` [write_candidate, high]
- `elyse/sync/50Hz_20MHz/delay` <- `C1011NI6602` / `14 OUT07 b16 C10 Delais` [write_candidate, high]
- `elyse/sync/50Hz_20MHz/width` <- `C1011NI6602` / `15 OUT07 b16 C10 Largeur` [write_candidate, high]
- `elyse/sync/laser_HF/delay` <- `C1011NI6602` / `16 OUT00 b05 C11 Delais` [write_candidate, high]
- `elyse/sync/laser_HF/width` <- `C1011NI6602` / `17 OUT00 b05 C11 Largeur` [write_candidate, high]
- `elyse/sync/IMAC/delay` <- `C1011NI6602` / `18 OUT01 b09 C11 Delais` [write_candidate, high]
- `elyse/sync/IMAC/width` <- `C1011NI6602` / `19 OUT01 b09 C11 Largeur` [write_candidate, high]
- `elyse/sync/laser/delay` <- `C1011NI6602` / `20 OUT02 b32 C11 Delais` [write_candidate, high]
- `elyse/sync/laser/width` <- `C1011NI6602` / `21 OUT02 b32 C11 Largeur` [write_candidate, high]
- `elyse/sync/oscilloscope1/delay` <- `C1011NI6602` / `22 OUT03 b29 C11 Delais` [write_candidate, high]
- `elyse/sync/oscilloscope1/width` <- `C1011NI6602` / `23 OUT03 b29 C11 Largeur` [write_candidate, high]
- `elyse/sync/oscilloscope2/delay` <- `C1011NI6602` / `24 OUT04 b26 C11 Delais` [write_candidate, high]
- `elyse/sync/oscilloscope2/width` <- `C1011NI6602` / `25 OUT04 b26 C11 Largeur` [write_candidate, high]
- `elyse/sync/detection1/delay` <- `C1011NI6602` / `26 OUT05 b23 C11 Delais` [write_candidate, high]
- `elyse/sync/detection1/width` <- `C1011NI6602` / `27 OUT05 b23 C11 Largeur` [write_candidate, high]
- `elyse/sync/detection2/delay` <- `C1011NI6602` / `28 OUT06 b53 C11 Delais` [write_candidate, medium]
- `elyse/sync/detection2/width` <- `C1011NI6602` / `29 OUT06 b53 C11 Largeur` [write_candidate, high]
- `elyse/sync/machine/delay` <- `C1011NI6602` / `30 OUT07 b16 C11 Delais` [write_candidate, high]
- `elyse/sync/machine/width` <- `C1011NI6602` / `31 OUT07 b16 C11 Largeur` [write_candidate, high]
- `elyse/sync/n_selection` <- `C1011NI6602` / `N du compteur` [read, medium]

### vacuum
- `elyse/vacuum/tpg300_section/measurement` <- `VAM-A` / `20 ACQ Vide TPG300 PIQ63` [read, high]
- `elyse/vacuum/preparation_chamber/measurement` <- `VAM-A` / `11 ACQ Vide Chambre` [read, high]
- `elyse/vacuum/HF/measurement` <- `VAM-A` / `12 ACQ Vide PI Guide HF` [read, high]
- `elyse/vacuum/canon/measurement` <- `VAM-A` / `13 ACQ Vide Canon PIQ12` [read, high]
- `elyse/vacuum/section/measurement` <- `VAM-A` / `14 ACQ Vide Section PIQ16` [read, high]
- `elyse/vacuum/mirror/measurement` <- `VAM-A` / `15 ACQ Vide Miroir PIQ21` [read, high]
- `elyse/vacuum/dipole1/measurement` <- `VAM-A` / `16 ACQ Vide Dip PIQ27/33` [read, high]
- `elyse/vacuum/screen1/measurement` <- `VAM-A` / `17 ACQ Vide Ecran PIQ53/63` [read, high]
- `elyse/vacuum/valves/cathode/state` <- `C5_IN_DIO96` / `15 APB7 b17 Vanne Cathode (VIC 01) fermee; 14 APB6 b19 Vanne Cathode (VIC 01) ouverte` [read, high derived]
- `elyse/vacuum/valves/injection/state` <- `C5_IN_DIO96` / `17 APC1 b13 Vanne Injection (VSC 17) fermee; 16 APC0 b15 Vanne Injection (VSC 17) ouverte` [read, high derived]
- `elyse/vacuum/preparation_chamber/state` <- `C5_IN_DIO96` / `00 APA0 b47 Vide chambre preparatoire en marche` [read, high derived]
- `elyse/vacuum/HF/state` <- `C5_IN_DIO96` / `02 APA2 b43 Vide sas guide HF en marche; 03 APA3 b41 Vide sas guide HF en defaut` [read, high derived]
- `elyse/vacuum/section/state` <- `C5_IN_DIO96` / `06 APA6 b35 Vide Section (PIQ 16) en marche; 07 APA7 b33 Vide Section (PIQ 16) en defaut` [read, high derived]
- `elyse/vacuum/dipole1/state` <- `C5_IN_DIO96` / `10 APB2 b27 Vide Dipole 1 (PIQ 27+33) en marche; 11 APB3 b25 Vide Dipole 1 (PIQ 27+33) en defaut` [read, high derived]
- `elyse/vacuum/screen1/state` <- `C5_IN_DIO96` / `12 APB4 b23 Vide Ecran 1 (PIQ 53+63) en marche; 13 APB5 b21 Vide Ecran 1 (PIQ 53+63) en defaut` [read, high derived]
- `elyse/vacuum/mirror/state` <- `C5_IN_DIO96` / `08 APB0 b31 Vide Miroir (PIQ 21) en marche; 09 APB1 b29 Vide Miroir (PIQ 21) en defaut` [read, high derived]
- `elyse/vacuum/tpg300_section/state` <- `C5_IN_DIO96` / `20 ACQ Vide TPG300 PIQ63` [read, low derived]
- `elyse/vacuum/canon/state` <- `C5_IN_DIO96` / `04 APA4 b39 Vide Canon (PIQ 12) en marche; 05 APA5 b37 Vide Canon (PIQ 12) en defaut` [read, high derived]

## Needs recheck in LabVIEW

- `elyse/HF/dephaser/value` from `C1NI6071E` / `36 ACH36 b77 Mes position Dephaseur` [medium] Passes through a formula block before the canonical output.
- `elyse/HF/dephaser/value_manuel` from `C1NI6071E` / `37 ACH37 b79 Mes position Dephaseur ajust` [medium] Passes through a formula block before the canonical output.
- `elyse/HF/attenuator/value` from `C1NI6071E` / `44 ACH44 b78 Mesure Attenuateur` [medium] Visual wiring suggests direct mapping, but the area includes formula nodes and should be rechecked.
- `elyse/modulator/thyratron/currents/power/value` from `C2NI6071E` / `11 ACH11 b10 Mes I Thyratron` [medium]
- `elyse/vacuum/tpg300_section/state` from `C5_IN_DIO96` / `20 ACQ Vide TPG300 PIQ63` [low] The state output is visible in the canonical list, but the exact discrete source for this state is not unambiguously legible in the screenshot.
- `elyse/sync/detection2/delay` from `C1011NI6602` / `28 OUT06 b53 C11 Delais` [medium] The screenshot strongly suggests detection2/delay, but the text should be rechecked in LabVIEW.
- `elyse/sync/n_selection` from `C1011NI6602` / `N du compteur` [medium] Visible as an exported channel in the VI, but the screenshot alone does not prove whether this should be writable.
- `elyse/magnets/Cor_H5/set_value` from `C6NI6703` / `08 OUT08 b33 Reserve` [medium] The VI canonical output is Cor_H5/set_value, but the raw output label is marked Reserve. The next case maps Guidage V5 explicitly to Cor_V5, so this Cor_H5 route should be treated as unresolved until rechecked in LabVIEW.
- `elyse/magnets/Cor_H5/value` from `C1NI6071E` / `34 ACH34 b71 Mes I Guidage V5` [medium] The VI canonical output is Cor_H5/value, but the raw readback label is Guidage V5. The next case maps the same raw label to Cor_V5/value, so this Cor_H5 route should be treated as unresolved until rechecked.

## Normalization note

- Vacuum channels appear in the VI as `vacuum.elyse/...`, while the normalized draft form stores them as `elyse/vacuum/...`.
- Sync channels appear in the VI as `sync.elyse/...`, while the normalized draft form stores them as `elyse/sync/...`.
- Cooling channels appear in the VI as `cooling.elyse/...`, while the normalized draft form stores them as `elyse/cooling/...`.
- Magnets channels appear in the VI as `magnets.elyse/...`, while the normalized draft form stores them as `elyse/magnets/...`.
- Before wiring this into `DS_PSP` or a future `DS_DAQmx`, we should confirm the exact channel names emitted by `psp_supervision.vi`.
