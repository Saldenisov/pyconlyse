# Supervision radioprotection display and graph aggregate (2026-09-30)

## Question and boundary

Does a changed door, rondier, emergency-stop, or BACO input make the saved
Supervision controller send a stop command, or does it update the operator
display? This audit follows the relevant wires in the copied
`0_SUP_ELYSE.vi` (SHA-256
`2257C86FF6285E1E144BCC5039B4CA5455A34E0DB95B8A15D4DA8503C3A8686B`).
It does not test the installed programs, electrical polarity, or the
hardwired safety chain. No VI, PSP variable, or NI card was operated.

## Observation 1: all 12 Page Radioprotection fields copy C4 inputs

Sequence UID `36869`, frame 16 (diagram UID `2928`), reads local
`C4_IN_DIO96` (`gRef paramIdx=29`, UID `29714`). Its source unbundle UID
`29989` has 12 direct, non-inverted wires to bundle UID `43587`, which
updates the `Page Radioprotection` local cluster (`gRef paramIdx=2`, UIDs
`42797` and `43860`). The destination's VCTP schema has exactly 12 fields.
The copied label `Porte légére` contains that spelling; the Python reference
model retains it for source parity.

| Page index and copied label | C4 input index and copied label |
|---|---|
| 0 `Porte lourde` | 53 `Contact porte lourde fermée` |
| 1 `Porte légére` | 52 `Contact porte légére fermée` |
| 2 `Porte de Secours` | 54 `Contact porte secours fermée` |
| 3 `Porte Laser` | 55 `Contact porte laser fermée` |
| 4 `Rondiers` | 60 `Totalisation des rondiers` |
| 5 `Occulteur LASER` | 63 `Position occulteur LASER` |
| 6 `BACO-TIR EN/HORS` | 62 `Position BACO de TIR` |
| 7 `BACO PA/MOD` | 61 `Position BACO PA / MOD` |
| 8 `RONDIER 1` | 57 `Rondier 1` |
| 9 `RONDIER 2` | 58 `Rondier 2` |
| 10 `RONDIER 3` | 59 `Rondier 3` |
| 11 `ARRETS D'URGENCE` | 56 `Totalisation des AU` |

The frame contains only sequence bookkeeping, three local references, and
two bundle/unbundle nodes. It has no Case, procedure subVI, or PSP-write
node. Other root uses of `gRef paramIdx=29` comprise PSP setup/read, three
unbundles of lower-index C4 fields, and the separately audited HT display
projection. The 52–63 fields are unbundled only in this radioprotection
display frame in the saved root. That is a bounded root-level observation,
not a statement about other software or wiring.

## Observation 2: eight display bits form one graph input

Sequence UID `49452`, frame 5 (diagram UID `4090`), reads the same Page
cluster through `gRef paramIdx=2` and unbundle UID `4153`. Compound
Arithmetic UID `4284` has AND operation bits and inverted input flags on
two terminals. Its exact raw-Boolean expression is:

```text
G = Page[0] AND Page[1] AND Page[2] AND Page[3]
    AND NOT Page[4] AND Page[11] AND NOT Page[6] AND Page[7]
  = C4[53] AND C4[52] AND C4[54] AND C4[55]
    AND NOT C4[60] AND C4[56] AND NOT C4[62] AND C4[61]
```

`Occulteur LASER` and individual `RONDIER 1–3` fields (`Page[5,8,9,10]`)
do not enter this expression. The totalized rondier input `C4[60]` does,
inverted. The aggregate writes a local Boolean (`gRef paramIdx=58`). The
saved root has exactly two references to that local: this writer and a
reader wired to connector 9 of `2_SUP_Graph _Radioprot.vi`. The subVI's
saved connector description names connector 9 `Somme Radioprotection`.
No direct wire from this aggregate to a root stop selector or PSP command
was identified. The [parsed graph-VI description](../Supervision/analysis/lvkit_eval/batch_0_8_4_minimal_vilib/descriptions/2_SUP_Graph__Radioprot.json)
and saved [branch screenshots](../Supervision/analysis/screenshots/2_SUP_Graph_Radioprot_outer_true_state_0_default_lower_true_full.png)
show graph-cluster calculations and no PSP/NI command nodes in the reviewed
copy. This is a static side-effect screen, not a runtime guarantee.

There is a material source-version boundary: the graph-VI description's
[manifest](../Supervision/analysis/lvkit_eval/batch_0_8_4_minimal_vilib/manifest.json)
pins a **32,366-byte** VI with SHA-256
`25D72D2432462638F26E71F8E02614A02CA5174D7008E7E8116B8102C205718D`.
That byte-identical copy remains in `Supervision/analysis/print_batch_root_no_password`.
The present `Supervision/extracted/.../2_SUP_Graph _Radioprot.vi` is
**32,730 bytes**, SHA-256
`8C3FFAB277E9A2E5346B6B4F5A657BCC8105853F26ED658B33211790C773815F`.
The read-only `lvkit diff --format text --load-mode none --no-auto-vilib`
reports `No changes detected` for their parsed diagrams and interfaces.
It also reports `VICD` and `VITS` parse warnings on the 32,730-byte copy;
therefore byte differences outside the compared semantic model remain
unresolved. This is evidence of matching *parsed* logic, not binary or
deployed equivalence.

## Inference, alternative, and transfer

The saved Supervision root uses the listed radioprotection bits to update
the operator display and a graph input. The [saved Acquisition root
audit](ELYSE_ACQ_RADIOPROTECTION_REAUDIT_2026-09-29.md) likewise found no
direct C4[46–62]-to-general-stop branch. These two static negatives do not
establish what happens physically when a rondier changes: a hardwired
chain, another process, unparsed graph-VI differences, or changed deployed code
remain possible. A displayed green state must not be treated as an HT
enable condition.

The pure [Python reference model](../DeviceServers/control/elyse_acq/supervision_status.py)
copies the 12 raw display bits and calculates `G`; it sends no commands and
is not wired into authorization or hardware adapters. The
[tests](../tests/device_servers/control/test_elyse_supervision_status.py)
cover each one-hot display wire, all **4096** Boolean Page snapshots for
the aggregate, and malformed inputs. The
[read-only source validator](../tools/validate_sup_radioprotection_projection.py)
checks source hashes, node/terminal UIDs, field indices, inversion flags,
AND operation, and the local-to-graph connector wire.
Its pinned [source-export archive](../Supervision/analysis/source_exports/0_SUP_ELYSE_XML_sha2257.zip)
(SHA-256 `68920CD0C441D2F99037FBE60565AF12C80D2DC01EF421892F1D2D69AF9FE5D2`)
preserves the XML independently of the temporary `lvkit` cache.

```powershell
$supExtractRoot = 'C:\dev\pyconlyse\Supervision\extracted\PILOTAGE_ELYSE_SUP\SUPERVISION_VIs'
python tools/validate_sup_radioprotection_projection.py 'Supervision\analysis\source_exports\0_SUP_ELYSE_XML_sha2257.zip'
python -m unittest -v tests.device_servers.control.test_elyse_supervision_status
& 'C:\dev\pyconlyse\Supervision\analysis\lvkit_eval\.venv\Scripts\lvkit.exe' diff --format text --load-mode none --no-auto-vilib 'C:\dev\pyconlyse\Supervision\analysis\print_batch_root_no_password\2_SUP_Graph _Radioprot.vi' (Join-Path $supExtractRoot '2_SUP_Graph _Radioprot.vi')
```

## Unresolved discriminating checks

1. Resolve the two graph-VI versions beyond `lvkit`'s compared diagram and
   interface model. Its diff found no parsed changes, but `VICD`/`VITS`
   parse warnings prevent claiming full equivalence. The 32,366-byte
   version's parsed cases and saved screenshots show only graph-cluster
   calculations.
2. Compare copied VI/LLB hashes with deployed binaries. Static results
   apply to the copies, not automatically to current software.
3. Establish C4 input polarity, sampling/freshness, and the hardwired
   safety response from authorized documentation or a formal instrumented
   safety test. Do not infer them from indicator labels or this formula.
