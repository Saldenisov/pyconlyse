# Acquisition local-reference mapping audit (2026-09-29)

## Question and boundary

The Python controller must reproduce the LabVIEW program's decisions, not merely list its case frames. That requires correct identities for every local-variable read and write. This audit tests the offline parser's assumed mapping from each raw `gRefDCO/paramIdx` to a front-panel control. It uses the saved `0_ACQ_ELYSE.vi` extracted from `ACQUISITION.llb` (SHA-256 of source LLB: `EB7C08800823D025F1B4F9E8EEA89ED9878F0CF00A02427871583B99989B2F8A`). It does not verify the current deployed LLB or operate the running system.

## Discriminating type test

The root BDHb XML contains 650 `gRef` nodes; 649 have a numeric `paramIdx`. Its FPHb XML has 69 front-panel DCOs. The installed `lvkit` graph builder maps each `paramIdx` to the control at that index in the FPHb XML order. For each of the 649 references, `tools/check_acq_local_ref_mapping.py` compared the broad raw LabVIEW type of the reference with the candidate control's type (Boolean, cluster, array, number, etc.).

| Candidate index sequence | Offset from `paramIdx` | Comparable references | Broad-type mismatches |
|---|---:|---:|---:|
| FPHb control order (current parser) | 0 | 649 | 420 |
| FPHb control order | −1 | 649 | 410 |
| FPHb control order | +1 | 641 | 531 |
| First BDHb `sRN` front-panel terminal order | −1 | 639 | 192 |
| First BDHb `sRN` front-panel terminal order | 0 | 636 | 274 |
| First BDHb `sRN` front-panel terminal order | +1 | 633 | 280 |

A type mismatch proves a proposed reference-to-control mapping false; a match does **not** establish identity because many controls share a type. The `sRN −1` candidate fits more types but still fails for 192 comparable references, so no single tested order/offset resolves the local-variable table. Some non-Boolean wrapper types may be represented differently, but the specific Boolean-to-cluster contradictions below do not depend on such subtleties.

Two raw selector wires illustrate the failure:

- Case structure `43488`, selector terminal `43512`: signal `45079` connects directly to local reference `7387`, terminal `7927`, `paramIdx=45`, raw type `TypeID(8141)` = Boolean. `lvkit`'s FPHb-order mapping instead names index 45 `DPS`, a cluster. The earlier native visual review identified this case as `TCP ED` (Boolean); that label remains a native observation, while the raw wire independently disproves `DPS`.
- Case structure `52981`, selector terminal `53005`: signal `555` connects to local reference `118957`, terminal `118967`, `paramIdx=47`, raw type `TypeID(7659)` = Boolean. The FPHb-order mapping names index 47 `C2NI6071E`, a cluster. The earlier native visual review identified the local Boolean as `Arrêt général`. Again, the raw wire disproves the parser name, without by itself recovering the correct parameter-table mapping.

`tools/trace_acq_raw_selectors.py` recorded the raw terminal peers for all 55 `select` structures in `docs/ELYSE_ACQ_RAW_SELECTOR_WIRES_2026-09-29.csv` (169 selector-peer rows). These are direct wire incidences, not inferred control names or complete execution paths. A signal may fan out to several peer terminals, so row count is not a count of independent selectors.

The cooling-flow and stop-path traces provide nine **local, manually checked anchors**, without resolving the remaining parameter table. Native screenshots identify the input clusters, output-bank names, and stop selectors; raw `nMux` field indices, VCTP cluster field order, and PSP URIs independently constrain the destinations:

| `paramIdx` | Checked identity in cooling-flow branch | Discriminating evidence |
|---:|---|---|
| 16 | `C4_IN_DIO96` | Unbundle fields 19/38 labelled water-flow inputs |
| 17 | `C3_OUT_DIO96` | Bundle fields 1/4 match Canon/Section stop outputs |
| 18 | `C3_IN_DIO96` | Unbundle fields 0/6 labelled pump-state inputs |
| 30 | `stop` | Error-branch constants labelled `stop` feed this reference; its reads feed all five runtime While-loop conditions |
| 36 | `DPS` | Status field 1 and dynamic write to `/SUPERVISION/DPS` |
| 44 | `EPS` | Bundle fields 1/2/3/5 match the EPS cooling-status cluster |
| 45 | `TCP ED` | Native outer-frame-3 selector label and the same signal as `stop` in two PSP-write error cases |
| 46 | `stop urgence` | Initialization/final-frame constants and Stop-if-True tests of both outer-frame-3 While loops |
| 47 | `Arrêt général` | Native inner selector label and frame-6 reset constant |

The exact guard and seven ordered actions are in `ELYSE_ACQ_COOLING_FLOW_SAFETY_TRACE_2026-09-29.md`. The anchors are specific to these verified references; do not extrapolate a linear offset to other `paramIdx` values.

## Direct PSP-wire crosswalk

`tools/map_acq_locals_from_psp_wires.py` pairs a local-reference terminal and a literal PSP URI **only when both connect to the same `sharedVariableDynamicOpen`/`Read`/`Write` node and each side is unique**. It found 96 such call sites, spanning **23 distinct `paramIdx` values**, with zero conflicting URIs for any index. Thirteen nodes with multiple or incomplete candidates were excluded rather than guessed. The exact node, signal, diagram, local UID, and URI are recorded in `ELYSE_ACQ_LOCAL_PSP_WIRE_MAP_2026-09-29.csv`.

This independently fixes the identities of the PSP-backed bank/status locals, including `paramIdx=16` → `/C4_IN_DIO96`, `17` → `/C3_OUT_DIO96`, `18` → `/C3_IN_DIO96`, `36` → `/DPS`, and `44` → `/EPS`. It does **not** identify non-PSP UI/stop locals or prove that every value at a call site is subsequently accepted by the remote PSP server. Together with the four manually checked non-PSP stop controls (`30`, `45`, `46`, `47`), this yields 27 of the 60 distinct numeric local-reference indices with a grounded identity, while the remaining 33 require further tracing.

## Consequence

Do not use `lvkit`-assigned **local-variable names** as proof of Acquisition behavior until `paramIdx` is mapped from the VI's actual parameter table or each safety-critical reference is traced in native LabVIEW. Raw structure/frame/case counts remain useful as a coverage inventory, but local-variable naming can misidentify the condition and destination. In particular, the existing candidate-wire CSV and any statements about radioprotection or general stop that rely on these normalized names are provisional. No complete interlock truth table or Python-equivalent controller can be certified from the current inventory.

The next discriminating step is to recover the saved VI's local-reference parameter table (or natively verify each affected `gRef`) and then regenerate the wire graph with a type-checked mapping. Re-run the audit on the current XP LLB after its hash is confirmed. Live hardware tests are not required for this static mapping task.
