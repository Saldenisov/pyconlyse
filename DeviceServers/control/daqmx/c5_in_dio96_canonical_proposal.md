# C5_IN_DIO96 Canonical Proposal

Proposed canonical names for the full `C5_IN_DIO96` inventory, based on the new raw-name-first architecture.

These are proposals, not final truth. The goal is to keep the raw LabVIEW labels untouched and define the internal naming layer in Python.

## Proposed Mappings

- `00 APA0 b47 Vide chambre prÃ©paratoire en marche` -> `elyse/vacuum/preparation_chamber/running`
- `02 APA2 b43 Vide sas guide HF en marche` -> `elyse/vacuum/hf_guide/running`
- `03 APA3 b41 Vide sas guide HF en dÃ©faut` -> `elyse/vacuum/hf_guide/fault`
- `04 APA4 b39 Vide Canon (PIQ 12) en marche` -> `elyse/vacuum/canon/running`
- `05 APA5 b37 Vide Canon (PIQ 12) en dÃ©faut` -> `elyse/vacuum/canon/fault`
- `06 APA6 b35 Vide Section (PIQ 16) en marche` -> `elyse/vacuum/section/running`
- `07 APA7 b33 Vide Section (PIQ 16) en dÃ©faut` -> `elyse/vacuum/section/fault`
- `08 APB0 b31 Vide Miroir (PIQ 21) en marche` -> `elyse/vacuum/mirror/running`
- `09 APB1 b29 Vide Miroir (PIQ 21) en dÃ©faut` -> `elyse/vacuum/mirror/fault`
- `10 APB2 b27 Vide DipÃ´le 1 (PIQ 27+33) en marche` -> `elyse/vacuum/dipole1/running`
- `11 APB3 b25 Vide DipÃ´le 1 (PIQ 27+33) en dÃ©faut` -> `elyse/vacuum/dipole1/fault`
- `12 APB4 b23 Vide Ecran 1 (PIQ 53+63) en marche` -> `elyse/vacuum/screen1/running`
- `13 APB5 b21 Vide Ecran 1 (PIQ 53+63) en dÃ©faut` -> `elyse/vacuum/screen1/fault`
- `14 APB6 b19 Vanne Cathode (VIC 01) ouverte` -> `elyse/vacuum/valves/cathode/open`
- `15 APB7 b17 Vanne Cathode (VIC 01) fermÃ©e` -> `elyse/vacuum/valves/cathode/closed`
- `16 APC0 b15 Vanne Injection (VSC 17) ouverte` -> `elyse/vacuum/valves/injection/open`
- `17 APC1 b13 Vanne Injection (VSC 17) fermÃ©e` -> `elyse/vacuum/valves/injection/closed`
- `18 APC2 b11 Vanne directe ouverte` -> `elyse/vacuum/valves/direct/open`
- `19 APC3 b09 Vanne directe fermÃ©e` -> `elyse/vacuum/valves/direct/closed`
- `20 APC4 b07 Vanne DÃ©viation 1 ouverte` -> `elyse/vacuum/valves/deviation1/open`
- `21 APC5 b05 Vanne DÃ©viation 1 fermÃ©e` -> `elyse/vacuum/valves/deviation1/closed`
- `22 APC6 b03 Vanne DÃ©viation 2 ouverte` -> `elyse/vacuum/valves/deviation2/open`
- `23 APC7 b01 Vanne DÃ©viation 2 fermÃ©e` -> `elyse/vacuum/valves/deviation2/closed`
- `24 BPA0 b48 LASER en marche` -> `elyse/laser/running`
- `25 BPA1 b46 LASER eb dÃ©faut` -> `elyse/laser/eb_fault`
- `37 BPB5 b22 Faraday 1 EN` -> `elyse/faraday/1/in`
- `38 BPB6 b20 Faraday 1 HORS` -> `elyse/faraday/1/out`
- `39 BPB7 b18 Faraday 2 EN` -> `elyse/faraday/2/in`
- `40 BPC0 b16 Faraday 2 HORS` -> `elyse/faraday/2/out`
- `41 BPC1 b14 Faraday 3 HORS` -> `elyse/faraday/3/out`
- `42 BPC2 b12 Faraday 3 EN` -> `elyse/faraday/3/in`
- `43 BPC3 b10 Position Miroir LASER EN` -> `elyse/laser/mirror/in`
- `44 BPC4 b08 Position Miroir LASER HORS` -> `elyse/laser/mirror/out`
- `45 BPC5 b06 Fente H butÃ©e MIN` -> `elyse/slit/h/min_limit`
- `46 BPC6 b04 Mors HG butÃ©e HORS` -> `elyse/slit/jaw_hg/out_limit`
- `47 BPC7 b02 Mors HD butÃ©e HORS` -> `elyse/slit/jaw_hd/out_limit`
- `50 CPA2 b93 Translateur Ã©cran 1 en dÃ©faut` -> `elyse/screens/1/translator/fault`
- `51 CPA3 b91 Translateur Ã©cran 2 en dÃ©faut` -> `elyse/screens/2/translator/fault`
- `52 CPA4 b89 Translateur Ã©cran 3 en dÃ©faut` -> `elyse/screens/3/translator/fault`

## Reserve / Unused Entries

- `01 APA1 b45 Reserve`
- `26 BPA2 b44 Reserve`
- `27 BPA3 b42 Reserve`
- `28 BPA4 b40 Reserve`
- `29 BPA5 b38 Reserve`
- `30 BPA6 b36 Reserve`
- `31 BPA7 b34 Reserve`
- `32 BPB0 b32 Reserve`
- `33 BPB1 b30 Reserve`
- `34 BPB2 b28 Reserve`
- `35 BPB3 b26 Reserve`
- `36 BPB4 b24 Reserve`
- `48 CPA0 b97 Reserve`
- `49 CPA1 b95 Reserve`
- `53 CPA5 b87 Reserve`
- `54 CPA6 b85 Reserve`
- `55 CPA7 b83 Reserve`

## Notes

- `running` / `fault` / `open` / `closed` are proposed as direct raw-bit names.
- For vacuum items that used to collapse into one LabVIEW state channel, we now keep the individual raw bits and can derive the higher-level state later in Python.
- `laser`, `faraday`, and motion-limit names are also proposed directly from the bit labels.
- If you want, the next normalization pass can rename any of these segments, for example `running -> on`, `fault -> error`, or `screens/1 -> screen1`.
