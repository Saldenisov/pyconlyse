# C5_IN_DIO96 Raw To Canonical Mapping

Both layers are kept: the raw LabVIEW name and the internal canonical name.

| idx | raw_name | canonical_name | group | direction |
| --- | --- | --- | --- | --- |
| 0 | `00 APA0 b47 Vide chambre prÃ©paratoire en marche` | `elyse/vacuum/preparation_chamber/running` | `vacuum` | `read` |
| 1 | `01 APA1 b45 RÃ©serve` | `` | `` | `read` |
| 2 | `02 APA2 b43 Vide sas guide HF en marche` | `elyse/vacuum/hf_guide/running` | `vacuum` | `read` |
| 3 | `03 APA3 b41 Vide sas guide HF en dÃ©faut` | `elyse/vacuum/hf_guide/fault` | `vacuum` | `read` |
| 4 | `04 APA4 b39 Vide Canon (PIQ 12) en marche` | `elyse/vacuum/canon/running` | `vacuum` | `read` |
| 5 | `05 APA5 b37 Vide Canon (PIQ 12) en dÃ©faut` | `elyse/vacuum/canon/fault` | `vacuum` | `read` |
| 6 | `06 APA6 b35 Vide Section (PIQ 16) en marche` | `elyse/vacuum/section/running` | `vacuum` | `read` |
| 7 | `07 APA7 b33 Vide Section (PIQ 16) en dÃ©faut` | `elyse/vacuum/section/fault` | `vacuum` | `read` |
| 8 | `08 APB0 b31 Vide Miroir (PIQ 21) en marche` | `elyse/vacuum/mirror/running` | `vacuum` | `read` |
| 9 | `09 APB1 b29 Vide Miroir (PIQ 21) en dÃ©faut` | `elyse/vacuum/mirror/fault` | `vacuum` | `read` |
| 10 | `10 APB2 b27 Vide DipÃ´le 1 (PIQ 27+33) en marche` | `elyse/vacuum/dipole1/running` | `vacuum` | `read` |
| 11 | `11 APB3 b25 Vide DipÃ´le 1 (PIQ 27+33) en dÃ©faut` | `elyse/vacuum/dipole1/fault` | `vacuum` | `read` |
| 12 | `12 APB4 b23 Vide Ecran 1 (PIQ 53+63) en marche` | `elyse/vacuum/screen1/running` | `vacuum` | `read` |
| 13 | `13 APB5 b21 Vide Ecran 1 (PIQ 53+63) en dÃ©faut` | `elyse/vacuum/screen1/fault` | `vacuum` | `read` |
| 14 | `14 APB6 b19 Vanne Cathode (VIC 01) ouverte` | `elyse/vacuum/valves/cathode/open` | `vacuum` | `read` |
| 15 | `15 APB7 b17 Vanne Cathode (VIC 01) fermÃ©e` | `elyse/vacuum/valves/cathode/closed` | `vacuum` | `read` |
| 16 | `16 APC0 b15 Vanne Injection (VSC 17) ouverte` | `elyse/vacuum/valves/injection/open` | `vacuum` | `read` |
| 17 | `17 APC1 b13 Vanne Injection (VSC 17) fermÃ©e` | `elyse/vacuum/valves/injection/closed` | `vacuum` | `read` |
| 18 | `18 APC2 b11 Vanne directe ouverte` | `elyse/vacuum/valves/direct/open` | `vacuum` | `read` |
| 19 | `19 APC3 b09 Vanne directe fermÃ©e` | `elyse/vacuum/valves/direct/closed` | `vacuum` | `read` |
| 20 | `20 APC4 b07 Vanne DÃ©viation 1 ouverte` | `elyse/vacuum/valves/deviation1/open` | `vacuum` | `read` |
| 21 | `21 APC5 b05 Vanne DÃ©viation 1 fermÃ©e` | `elyse/vacuum/valves/deviation1/closed` | `vacuum` | `read` |
| 22 | `22 APC6 b03 Vanne DÃ©viation 2 ouverte` | `elyse/vacuum/valves/deviation2/open` | `vacuum` | `read` |
| 23 | `23 APC7 b01 Vanne DÃ©viation 2 fermÃ©e` | `elyse/vacuum/valves/deviation2/closed` | `vacuum` | `read` |
| 24 | `24 BPA0 b48 LASER en marche` | `elyse/laser/running` | `laser` | `read` |
| 25 | `25 BPA1 b46 LASER eb dÃ©faut` | `elyse/laser/eb_fault` | `laser` | `read` |
| 26 | `26 BPA2 b44 RÃ©serve` | `` | `` | `read` |
| 27 | `27 BPA3 b42 RÃ©serve` | `` | `` | `read` |
| 28 | `28 BPA4 b40 RÃ©serve` | `` | `` | `read` |
| 29 | `29 BPA5 b38 RÃ©serve` | `` | `` | `read` |
| 30 | `30 BPA6 b36 RÃ©serve` | `` | `` | `read` |
| 31 | `31 BPA7 b34 RÃ©serve` | `` | `` | `read` |
| 32 | `32 BPB0 b32 RÃ©serve` | `` | `` | `read` |
| 33 | `33 BPB1 b30 RÃ©serve` | `` | `` | `read` |
| 34 | `34 BPB2 b28 RÃ©serve` | `` | `` | `read` |
| 35 | `35 BPB3 b26 RÃ©serve` | `` | `` | `read` |
| 36 | `36 BPB4 b24 RÃ©serve` | `` | `` | `read` |
| 37 | `37 BPB5 b22 Faraday 1 EN` | `elyse/faraday/1/in` | `diagnostics` | `read` |
| 38 | `38 BPB6 b20 Faraday 1 HORS` | `elyse/faraday/1/out` | `diagnostics` | `read` |
| 39 | `39 BPB7 b18 Faraday 2 EN` | `elyse/faraday/2/in` | `diagnostics` | `read` |
| 40 | `40 BPC0 b16 Faraday 2 HORS` | `elyse/faraday/2/out` | `diagnostics` | `read` |
| 41 | `41 BPC1 b14 Faraday 3 HORS` | `elyse/faraday/3/out` | `diagnostics` | `read` |
| 42 | `42 BPC2 b12 Faraday 3 EN` | `elyse/faraday/3/in` | `diagnostics` | `read` |
| 43 | `43 BPC3 b10 Position Miroir LASER EN` | `elyse/laser/mirror/in` | `laser` | `read` |
| 44 | `44 BPC4 b08 Position Miroir LASER HORS` | `elyse/laser/mirror/out` | `laser` | `read` |
| 45 | `45 BPC5 b06 Fente H butÃ©e MIN` | `elyse/slit/h/min_limit` | `motion` | `read` |
| 46 | `46 BPC6 b04 Mors HG butÃ©e HORS` | `elyse/slit/jaw_hg/out_limit` | `motion` | `read` |
| 47 | `47 BPC7 b02 Mors HD butÃ©e HORS` | `elyse/slit/jaw_hd/out_limit` | `motion` | `read` |
| 48 | `48 CPA0 b97 RÃ©serve` | `` | `` | `read` |
| 49 | `49 CPA1 b95 RÃ©serve` | `` | `` | `read` |
| 50 | `50 CPA2 b93 Translateur Ã©cran 1 en dÃ©faut` | `elyse/screens/1/translator/fault` | `motion` | `read` |
| 51 | `51 CPA3 b91 Translateur Ã©cran 2 en dÃ©faut` | `elyse/screens/2/translator/fault` | `motion` | `read` |
| 52 | `52 CPA4 b89 Translateur Ã©cran 3 en dÃ©faut` | `elyse/screens/3/translator/fault` | `motion` | `read` |
| 53 | `53 CPA5 b87 RÃ©serve` | `` | `` | `read` |
| 54 | `54 CPA6 b85 RÃ©serve` | `` | `` | `read` |
| 55 | `55 CPA7 b83 RÃ©serve` | `` | `` | `read` |
