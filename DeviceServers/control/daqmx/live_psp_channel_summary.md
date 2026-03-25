# Live PSP Channel Summary

- Source: `/Users/sad/dev/pyconlyse/DeviceServers/control/daqmx/live_psp_latest_raw.json`
- Tango host: `10.20.30.202:10000`
- Device: `manip/general/PSP`
- Total keys: `796`
- Raw-like keys: `611`
- Canonical-like keys: `119`
- Placeholders/index-only: `66`

## Important finding

- The current live stream is mixed: `DS_PSP` currently contains both raw card/channel labels and canonical `elyse/...`-style names.
- This means the rewritten `PSP_Supervision.vi` is not yet the only producer format, or historical/current senders are mixed.

## Canonical-like examples

- `elyse/HF/attenuator/value`
- `elyse/HF/canon/value`
- `elyse/HF/dephaser/value`
- `elyse/HF/dephaser/value_manuel`
- `elyse/HF/section/value`
- `elyse/HT/current/value`
- `elyse/HT/voltage/set_value`
- `elyse/HT/voltage/value`
- `elyse/cooling/canon/temperature/measurement`
- `elyse/cooling/canon/temperature/set_value`
- `elyse/cooling/section/temperature/measurement`
- `elyse/cooling/section/temperature/set_value`
- `elyse/magnets/Cor_H1/set_value`
- `elyse/magnets/Cor_H1/value`
- `elyse/magnets/Cor_H2/set_value`
- `elyse/magnets/Cor_H2/value`
- `elyse/magnets/Cor_H3/set_value`
- `elyse/magnets/Cor_H3/value`
- `elyse/magnets/Cor_H4/set_value`
- `elyse/magnets/Cor_H4/value`
- `elyse/magnets/Cor_H5/set_value`
- `elyse/magnets/Cor_H5/value`
- `elyse/magnets/Cor_V1/set_value`
- `elyse/magnets/Cor_V1/value`
- `elyse/magnets/Cor_V2/set_value`
- `elyse/magnets/Cor_V2/value`
- `elyse/magnets/Cor_V3/set_value`
- `elyse/magnets/Cor_V3/value`
- `elyse/magnets/Cor_V4/set_value`
- `elyse/magnets/Cor_V4/value`

## Raw-like examples

- `00 ACH00 b03 Mes V Chauffage Thyratron`
- `00 ACH00 b03 Mes tempÃ©rature Canon`
- `00 ACQ Auxiliare`
- `00 APA0 b47 Eau corps Klystron`
- `00 APA0 b47 Reffroidissement Canon marche`
- `00 APA0 b47 Vide chambre prÃ©paratoire en marche`
- `00 CPB0 b81 Marche Reffroidissement Canon`
- `00 CPB0 b81 RÃ©serve`
- `00 CPC0 b65 Marche modulateur Bas Niveau`
- `00 OUT00 b01 Cmd Guidage H1`
- `00 OUT00 b01 Cmd I Triplet 1-1`
- `00 OUT00 b01 Cmd alimentation HT`
- `00 OUT00 b01 RÃ©serve`
- `00 OUT00 b05 C10 DÃ©lais`
- `00 SUP VidÃ©o`
- `01 ACH01 b05 Mes V Chauffage Klystron`
- `01 ACH01 b05 Mes Vide Chambre de prÃ©paration`
- `01 ACQ Variables`
- `01 APA1 b45 Eau collecteur Klystron`
- `01 APA1 b45 Reffroidissement Canon dÃ©faut`
- `01 APA1 b45 RÃ©serve`
- `01 CPB1 b79 Alimentation moteur`
- `01 CPB1 b79 ArrÃªt Reffroidissement Canon`
- `01 CPC1 b63 ArrÃªt modulateur Bas Niveau`
- `01 OUT00 b05 C10 Largeur`
- `01 OUT01 b05 Cmd DeQing`
- `01 OUT01 b05 Cmd Guidage V1`
- `01 OUT01 b05 Cmd I Triplet 1-2`
- `01 OUT01 b05 Cmd Temp. Canon`
- `01 SUP Variables`
- `02 ACH02 b07 Mes I D'Qing`
- `02 ACH02 b07 Mes Vide Canon (PIQ 12)`
- `02 ACQ EvÃ©nement`
- `02 APA2 b43 Eau cuve Klystron`
- `02 APA2 b43 Vanne Reffroidissement Canon fermÃ©e`
- `02 APA2 b43 Vide sas guide HF en marche`
- `02 CPB2 b77 RAZ Reffroidissement Canon`
- `02 CPB2 b77 RÃ©serve`
- `02 CPC2 b61 RAZ modulateur Bas Niveau`
- `02 OUT01 b09 C10 DÃ©lais`
- `02 OUT02 b09 Cmd Guidage H2`
- `02 OUT02 b09 Cmd Temp. Section`
- `02 OUT02 b09 Cmd position fente HG`
- `02 OUT02 b09 RÃ©serve`
- `02 SUP Evenement`
- `03 ACH03 b09 Mes Vide Miroir (PIQ 21)`
- `03 ACH03 b09 RÃ©servÃ©`
- `03 APA3 b41 Vanne Reffroidissement Canon ouverte`
- `03 APA3 b41 Vide Klystron`
- `03 APA3 b41 Vide sas guide HF en dÃ©faut`
