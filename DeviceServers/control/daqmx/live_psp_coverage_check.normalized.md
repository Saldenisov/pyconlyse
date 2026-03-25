# Normalized Live Coverage Check

Live channels now: `677`
Exact raw-name matches: `536`
Recovered by normalization: `20`
Effective covered total: `556`
Actionable uncovered: `36`
Ignored uncovered (`Libre` / `Réserve` / numeric placeholders): `85`
Effective coverage: `82.13%`

## Sample Normalized Rescues

- `00 OUT00 b05 C10 DÃ©lais` -> `00 OUT00 b05 C10 Delais`
- `02 OUT01 b09 C10 DÃ©lais` -> `02 OUT01 b09 C10 Delais`
- `03 ` -> `03`
- `04 OUT02 b32 C10 DÃ©lais` -> `04 OUT02 b32 C10 Delais`
- `06 OUT03 b29 C10 DÃ©lais` -> `06 OUT03 b29 C10 Delais`
- `08 OUT04 b26 C10 DÃ©lais` -> `08 OUT04 b26 C10 Delais`
- `10 OUT05 b23 C10 DÃ©lais` -> `10 OUT05 b23 C10 Delais`
- `12 OUT06 b53 C10 DÃ©lais` -> `12 OUT06 b53 C10 Delais`
- `14 OUT07 b16 C10 DÃ©lais` -> `14 OUT07 b16 C10 Delais`
- `16 ACQ Vide Dip PIQ27/33 ` -> `16 ACQ Vide Dip PIQ27/33`
- `16 OUT00 b05 C11 DÃ©lais` -> `16 OUT00 b05 C11 Delais`
- `18 OUT01 b09 C11 DÃ©lais` -> `18 OUT01 b09 C11 Delais`
- `20 OUT02 b32 C11 DÃ©lais` -> `20 OUT02 b32 C11 Delais`
- `22 OUT03 b29 C11 DÃ©lais` -> `22 OUT03 b29 C11 Delais`
- `24 OUT04 b26 C11 DÃ©lais` -> `24 OUT04 b26 C11 Delais`
- `26 OUT05 b23 C11 DÃ©lais` -> `26 OUT05 b23 C11 Delais`
- `28 OUT06 b53 C11 DÃ©lais` -> `28 OUT06 b53 C11 Delais`
- `30 OUT07 b16 C11 DÃ©lais` -> `30 OUT07 b16 C11 Delais`
- `NÂ° du compteur` -> `N du compteur`
- `ProcÃ©dure combinÃ© EC` -> `Procédure combiné EC`

## Sample Actionable Uncovered

- `00 ACQ Auxiliare`
- `01 ACQ Variables`
- `02 ACQ EvÃ©nement`
- `10 ACQ Vide Section`
- `11 CPC3 b59 Marche Triplet 1-2`
- `15 CPC7 b51 Marche Triplet 2-1`
- `17 DPA1 b96 Marche Triplet 2-2`
- `21 DPA5 b88 M/A QuadripÃ´ple 1`
- `23 DPA7 b84 M/A QuadripÃ´ple 2`
- `24 BPA0 b48 QuadripÃ´ple 1 en marche`
- `25 BPA1 b46 QuadripÃ´ple 1 en dÃ©faut`
- `25 DPB1 b80 M/A Focale Injection`
- `26 BPA2 b44 QuadripÃ´ple 2 en marche`
- `27 BPA3 b42 QuadripÃ´ple 2 en dÃ©faut`
- `27 DPB3 b76 M/A DipÃ´le 1`
- `29 DPB5 b72 M/A DipÃ´le 2`
- `31 DPB7 b68 M/A Guidage H1`
- `32 DPC0 b66 M/A Guidage V1`
- `32 WCM2HMax`
- `33 DPC1 b64 M/A Guidage H2`
- `33 WCM2BMax`
- `34 DPC2 b62 M/A Guidage V2`
- `34 WCM2GMax`
- `35 DPC3 b60 M/A Guidage H3`
- `35 WCM2DMax`
- `36 DPC4 b58 M/A Guidage V3`
- `36 WCM2HMin`
- `37 DPC5 b56 M/A Guidage H4`
- `37 WCM2BMin`
- `38 DPC6 b54 M/A Guidage V4`
- `38 WCM2GMin`
- `39 DPC7 b52 M/A Guidage V5`
- `39 WCM2DMin`
- `63 B_NI6220`
- `Arret refroidissement OK`
- `Pilote prÃ©sent ?`
