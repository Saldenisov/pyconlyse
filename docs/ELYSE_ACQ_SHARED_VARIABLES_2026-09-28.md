# ACQ: audit of the `VARIABLES PARTAGEES` panel

## Scope and evidence

Only `0_ACQ_ELYSE.vi` on `10.20.30.10` is in scope. The VI was stopped during this inspection; only panel-navigation tabs were selected. No command values, PSP values, DAQ outputs, or source files were changed. All 17 pages of its `VARIABLES PARTAGEES` panel were opened for inspection on 2026-09-28. The panel is a display of local LabVIEW controls/indicators; a displayed bank is **not by itself proof of who owns or writes the network variable**. Values and green lamps shown after the VI stopped are frozen UI values, not current hardware readbacks.

The exact field labels for every card-related bank are in `C:\dev\ELYSE-ACQ-analysis\offline\reports\channel_map.csv`; the connector-pane types, including non-card clusters, are in `C:\dev\ELYSE-ACQ-analysis\offline\lvkit_describe\0_ACQ_ELYSE.json`. Both derive from the byte-identical `ACQUISITION.llb` copy (SHA-256 `EB7C08800823D025F1B4F9E8EEA89ED9878F0CF00A02427871583B99989B2F8A`). The prior diagram evidence is under `C:\dev\ELYSE-ACQ-analysis\runs\20260922-085500-+0200\images`.

The consolidated [field inventory](ELYSE_ACQ_SHARED_VARIABLE_FIELDS_2026-09-28.csv) has 1,048 records across all 27 displayed banks, including one record for each of the 488 card fields and all non-card cluster fields. It is generated from the two copied/offline sources by [build_acq_shared_variable_fields.py](../tools/build_acq_shared_variable_fields.py). `visual_kind` is the displayed shape, **not** an independently validated deployed PSP data type.

## Every panel page

| Page | Displayed bank(s) | Composition from the copied VI | What is established |
|---|---|---|---|
| `DPS/C EPS/C` | `DPS`, `EPS`, `DPC`, `EPC` | 29 simple-procedure requests; 77 simple-procedure state/ED/OK fields; 5 combined-procedure requests; 12 combined-procedure state/ED/OK fields | Request and state clusters coexist on one page. `DPS[22]` (`Alimentation aimant = PT`, one-based selector arm 23) has no matching ACQ runtime event handler in the 26-case catalog. |
| `C1 NI6071E` | `C1NI6071E` | 64 named analog-input values, indices 0–63 | Hardware input path is in `1_ACQ_READ_NI6071E.vi`; displayed values can be stale after stop. |
| `C2 NI6071E` | `C2NI6071E` | 64 named analog-input values, indices 0–63 | Same read VI, separate 64-channel task. |
| `C3 DIO96 IN` | `C3_IN_DIO96` | 56 named digital inputs | Physical read path is in `1_ACQ_RW_DIO96.vi`. |
| `C3 DIO96 OUT` | `C3_OUT_DIO96` | 40 named digital outputs | Physical write path is in `1_ACQ_RW_DIO96.vi`; output bank includes cooling and magnet-supply commands. |
| `C4 DIO96 IN` | `C4_IN_DIO96` | 64 named digital inputs | Includes water-flow, modulator, HT, and radioprotection contacts. |
| `C4 DIO96 OUT` | `C4_OUT_DIO96` | 32 named digital outputs | Includes modulator, HT, and HF command pulses/latches. |
| `C5 DIO96 IN` | `C5_IN_DIO96` | 56 named digital inputs | Includes vacuum, valves, diagnostics, Faraday, and screen contacts. |
| `C5 DIO96 OUT` | `C5_OUT_DIO96` | 40 named digital outputs | Includes vacuum/diagnostic/screen/laser/Faraday commands. |
| `C6/9 NI6703` | `C6NI6703`–`C9NI6703` | Four clusters of 10 analog commands each, indices 0–9 | The page caption says “9 voies”, but the visible lists and `1_ACQ_INIT_NI6703.vi` each have **10**. `1_ACQ_WRITE_NI6703.vi` performs the physical writes. |
| `C10-11 NI6602` | `C10-11 NI6602` | 32 delay/width fields plus one `N° du compteur` display/selector | The bank contains two sets of eight timing pairs. The saved ACQ counter-update call indexes only C10 fields 0–15; integer selector values 1–16 pair onto `/10/ctr0..7`. C11 fields 16–31 have no path into **that call**. This does **not** prove two local NI6602 cards: the ACQ task initializer configures eight outputs on device `/10/ctr0..7`; local device 11 is NI6220. |
| `C12 NI1409` | `C12NI1409` | String/list area, visibly empty while stopped | No active ACQ camera task is established from this page. |
| `VDM-A/S` | `VDM-A`, `VDM-S` | 80 Boolean fields each; only `VDM-A[0]` is named `Pilote présent ?`, remaining labels are placeholders | Full producer/consumer semantics not established from the panel. |
| `VDD` | `VDD` | 80 Boolean fields with placeholder labels | No conclusion that the bank is unused. |
| `VAM-A/S` | `VAM-A`, `VAM-S` | 64 numeric fields each | `VAM-A` labels include ACQ loop metrics, vacuum/TPG300 values, WCM extrema, and `B_NI6220`; `VAM-S` names SUP video/variable/event metrics at indices 0–2. |
| `VAD` | `VAD` | 64 numeric fields with numeric-only labels | No conclusion that the bank is unused. |
| `VTA/S/L` | `VTA`, `VTS`, `VTL` | Three string arrays, empty in the stopped panel | Array length and runtime ownership require a live schema/diagram trace; empty display is not proof of no use. |

The card-field inventory has 488 rows: 128 AI, 176 DI, 112 DO, 40 AO, and 32 NI6602 delay/width fields. It excludes the non-card procedure, telemetry, Boolean, text, and counter-selector fields above. For `C4_IN_DIO96`, use the 64 `channel_map.csv` rows; a naïve comma split of the connector type produces 66 because two labels contain commas.

## Dataflow already visible in ACQ

1. Initialization discovers variables under `ni.var.psp://10.20.30.2/SUPERVISION` and opens PSP references (`EV-ACQ-0006`). Thus the network namespace is on the SVE host, even though ACQ displays its local mirrors.
2. At startup ACQ writes the four C6–C9 analog-command banks and three C3–C5 output banks to that PSP namespace (`EV-ACQ-0008`); it also writes `DPS`, `EPS`, and `VDM-A`, setting `Pilote présent ?` (`EV-ACQ-0011`). These writes are not passive telemetry.
3. The runtime timeout frame reads the PSP banks `C6NI6703`–`C9NI6703`, `C10-11 NI6602`, `C3_OUT_DIO96`–`C5_OUT_DIO96`, `DPS`, `DPC`, `EPS`, and `EPC` (`EV-ACQ-0018`). `DPS` requests are projected into local `Value (Signaling)` events (`EV-ACQ-0020`). ACQ also writes `DPS` after at least one completed procedure (`EV-ACQ-0012`). Therefore some banks are **bidirectional at the ACQ boundary**; an IN/OUT suffix describes the hardware card, not exclusive PSP write ownership.
4. ACQ directly reads C1/C2 analog and C3/C4/C5 digital inputs and directly writes DIO/AO hardware during startup (`EV-ACQ-0009`). The exact PSP publication point and writer for every input/telemetry bank still need an exhaustive diagram trace.

## What remains before the ACQ communication contract is complete

- Build a field-level read/write ledger for every PSP node and every local cluster update, with VI/frame path, trigger, guard, ordering, and recipient. The 17 panel pages identify schemas, not all writers.
- Resolve actual deployed PSP data types and access directions against the SVE-hosted namespace, including whether a bank can be overwritten by both applications and how conflicts/reconnects are handled.
- Trace `VAM-A/S`, `VDM-A/S`, `VDD`, `VAD`, `VTA/S/L`, `C12NI1409`, `DPC/EPC`, and all `EPS` transitions; blank/placeholder labels cannot justify removal.
- Trace startup defaults and shutdown/communication-loss behavior separately from steady-state loops. ACQ startup itself writes PSP and physical outputs; it is not only a publisher of measurements.
- Keep physical readback distinct from requested state, PSP mirror, last DAQ write, and a frozen front-panel indicator.

No SuperVision VI was opened or analyzed in this audit.
