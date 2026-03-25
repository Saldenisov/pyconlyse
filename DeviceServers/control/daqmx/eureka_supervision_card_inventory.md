# Eureka Supervision Card Inventory

This file captures panel-level card inventories observed in `PSP_Supervision.vi`
screenshots. It complements the channel-level draft mapping in
`/Users/sad/dev/pyconlyse/DeviceServers/control/daqmx/eureka_supervision_mapping.draft.json`.

## C7NI6703

- `00 OUT00 b01` -> `Cmd I Triplet 1-1`
- `01 OUT01 b05` -> `Cmd I Triplet 1-2`
- `02 OUT02 b09` -> `Reserve`
- `03 OUT03 b13` -> `Cmd I Triplet 2-1`
- `04 OUT04 b17` -> `Cmd I Triplet 2-2`
- `05 OUT05 b21` -> `Cmd I Solenoide`
- `06 OUT06 b25` -> `Cmd I Quad 1`
- `07 OUT07 b29` -> `Cmd I Quad 2`
- `08 OUT08 b33` -> `Cmd I Dipole 1`
- `09 OUT09 b37` -> `Cmd I Dipole 2`

## C8NI6703

- `00 OUT00 b01` -> `Reserve`
- `01 OUT01 b05` -> `Cmd Temp. Canon`
- `02 OUT02 b09` -> `Cmd Temp. Section`
- `03 OUT03 b13` -> `Cmd Pos. Dephaseur`
- `04 OUT04 b17` -> `Cmd Pos. Attenuateur`
- `05 OUT05 b21` -> `Cmd dephasage HF/LASER`
- `06 OUT06 b25` -> `Cmd amplitude HF preampli`
- `07 OUT07 b29` -> `Reserve`
- `08 OUT08 b33` -> `Cmd position Miroir X`
- `09 OUT09 b37` -> `Cmd position Miroir Y`

## Current interpretation

- `C7NI6703 OUT05 Cmd I Solenoide` strongly supports the existing mapping
  `elyse/magnets/focale/set_value`.
- `C7NI6703 OUT02 Reserve` makes the currently inferred `Cor_H5` route highly
  suspicious and likely unresolved.
- `C8NI6703 OUT05 Cmd dephasage HF/LASER` confirms the existing mapping
  `elyse/magnets/phase_HF_laser/set_value`.
- `C8NI6703 OUT06 Cmd amplitude HF preampli` confirms the existing mapping
  `elyse/preamplifier/set_value`.
- `C8NI6703 OUT03/OUT04` suggest future write candidates for dephaser and
  attenuator control, but the canonical PSP channel names are not yet confirmed
  from the right-hand archive outputs.
- `C8NI6703 OUT01/OUT02` suggest future write candidates for cooling canon and
  section temperature control, but the canonical PSP channel names are not yet
  confirmed from the right-hand archive outputs.
- `C8NI6703 OUT08/OUT09` suggest future write candidates for mirror position
  control, but the canonical PSP channel names are not yet confirmed from the
  right-hand archive outputs.

## C9NI6703

- `00 OUT00 b01` -> `Cmd alimentation HT`
- `01 OUT01 b05` -> `Cmd DeQing`
- `02 OUT02 b09` -> `Cmd position fente HG`
- `03 OUT03 b13` -> `Cmd position fente HD`
- `04 OUT04 b17` -> `Cmd position translateur Ecran 1`
- `05 OUT05 b21` -> `Cmd position translateur Ecran 2`
- `06 OUT06 b25` -> `Cmd position translateur Ecran 3`
- `07 OUT07 b29` -> `Reserve`
- `08 OUT08 b33` -> `Reserve`
- `09 OUT09 b37` -> `Reserve`

## C9NI6703 current interpretation

- `C9NI6703 OUT00 Cmd alimentation HT` confirms the existing mapping
  `elyse/HT/voltage/set_value`.
- `C9NI6703 OUT01 Cmd DeQing` suggests a future write candidate, but the
  canonical PSP channel name is not yet confirmed from the right-hand archive
  outputs.
- `C9NI6703 OUT02/OUT03` suggest future write candidates for slit position
  control (`fente HG/HD`), but the canonical PSP channel names are not yet
  confirmed from the right-hand archive outputs.
- `C9NI6703 OUT04/OUT05/OUT06` suggest future write candidates for screen
  translator positioning, but the canonical PSP channel names are not yet
  confirmed from the right-hand archive outputs.

## C5_IN_DIO96

- `00 APA0 b47` -> `Vide chambre preparatoire en marche`
- `01 APA1 b45` -> `Reserve`
- `02 APA2 b43` -> `Vide sas guide HF en marche`
- `03 APA3 b41` -> `Vide sas guide HF en defaut`
- `04 APA4 b39` -> `Vide Canon (PIQ 12) en marche`
- `05 APA5 b37` -> `Vide Canon (PIQ 12) en defaut`
- `06 APA6 b35` -> `Vide Section (PIQ 16) en marche`
- `07 APA7 b33` -> `Vide Section (PIQ 16) en defaut`
- `08 APB0 b31` -> `Vide Miroir (PIQ 21) en marche`
- `09 APB1 b29` -> `Vide Miroir (PIQ 21) en defaut`
- `10 APB2 b27` -> `Vide Dipole 1 (PIQ 27+33) en marche`
- `11 APB3 b25` -> `Vide Dipole 1 (PIQ 27+33) en defaut`
- `12 APB4 b23` -> `Vide Ecran 1 (PIQ 53+63) en marche`
- `13 APB5 b21` -> `Vide Ecran 1 (PIQ 53+63) en defaut`
- `14 APB6 b19` -> `Vanne Cathode (VIC 01) ouverte`
- `15 APB7 b17` -> `Vanne Cathode (VIC 01) fermee`
- `16 APC0 b15` -> `Vanne Injection (VSC 17) ouverte`
- `17 APC1 b13` -> `Vanne Injection (VSC 17) fermee`
- `18 APC2 b11` -> `Vanne directe ouverte`
- `19 APC3 b09` -> `Vanne directe fermee`
- `20 APC4 b07` -> `Vanne Deviation 1 ouverte`
- `21 APC5 b05` -> `Vanne Deviation 1 fermee`
- `22 APC6 b03` -> `Vanne Deviation 2 ouverte`
- `23 APC7 b01` -> `Vanne Deviation 2 fermee`
- `24 BPA0 b48` -> `LASER en marche`
- `25 BPA1 b46` -> `LASER eb defaut`
- `26 BPA2 b44` -> `Reserve`
- `27 BPA3 b42` -> `Reserve`
- `28 BPA4 b40` -> `Reserve`
- `29 BPA5 b38` -> `Reserve`
- `30 BPA6 b36` -> `Reserve`
- `31 BPA7 b34` -> `Reserve`
- `32 BPB0 b32` -> `Reserve`
- `33 BPB1 b30` -> `Reserve`
- `34 BPB2 b28` -> `Reserve`
- `35 BPB3 b26` -> `Reserve`
- `36 BPB4 b24` -> `Reserve`
- `37 BPB5 b22` -> `Faraday 1 EN`
- `38 BPB6 b20` -> `Faraday 1 HORS`
- `39 BPB7 b18` -> `Faraday 2 EN`
- `40 BPC0 b16` -> `Faraday 2 HORS`
- `41 BPC1 b14` -> `Faraday 3 HORS`
- `42 BPC2 b12` -> `Faraday 3 EN`
- `43 BPC3 b10` -> `Position Miroir LASER EN`
- `44 BPC4 b08` -> `Position Miroir LASER HORS`
- `45 BPC5 b06` -> `Fente H butee MIN`
- `46 BPC6 b04` -> `Mors HG butee HORS`
- `47 BPC7 b02` -> `Mors HD butee HORS`
- `48 CPA0 b97` -> `Reserve`
- `49 CPA1 b95` -> `Reserve`
- `50 CPA2 b93` -> `Translateur ecran 1 en defaut`
- `51 CPA3 b91` -> `Translateur ecran 2 en defaut`
- `52 CPA4 b89` -> `Translateur ecran 3 en defaut`
- `53 CPA5 b87` -> `Reserve`
- `54 CPA6 b85` -> `Reserve`
- `55 CPA7 b83` -> `Reserve`

## C5_IN_DIO96 current interpretation

- The first vacuum-related part of `C5_IN_DIO96` matches the existing
  normalized `elyse/vacuum/.../state` draft mappings and strengthens confidence
  in those derived state channels.
- `Vanne directe`, `Vanne Deviation 1`, and `Vanne Deviation 2` appear on the
  card inventory but have not yet been matched to canonical PSP archive outputs
  in the screenshots we have.
- `LASER`, `Faraday`, mirror laser position, slit limits, jaw limits, and screen
  translator fault bits are visible on the card inventory but are not yet
  connected to canonical archive outputs in the mapping draft.
