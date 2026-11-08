# ELYSE Acquisition VI review → Python transfer boundary (2026-09-28)

## Question and evidence boundary

The question is whether the nested logic of `0_ACQ_ELYSE.vi`, including the frames visible inside its stop loop, is sufficiently resolved to reproduce the **LabVIEW controller's behavior** in Python. This audit does **not** require explaining NI-DAQmx internals or proving physical card behavior. Treat each external call as a boundary with the arguments LabVIEW supplies, the value/error it consumes, and its order relative to other calls. The local call graph, five lifecycle phases, five concurrent runtime loops, 26 event selectors, and all selector frames are indexed. Normal-path procedures can be simulated. Some LabVIEW guards, state transitions, cross-loop data ownership, and failure branches are still not proven.

The source is the byte-identical copy `C:\dev\ELYSE-ACQ-analysis\source\10.20.30.10\ACQUISITION.llb` (SHA-256 `EB7C08800823D025F1B4F9E8EEA89ED9878F0CF00A02427871583B99989B2F8A`). Evidence combines normalized offline `lvkit describe` JSON, rendered diagrams, terminal-level event inventory, and passive inspection in native 32-bit LabVIEW through RDP. No VI was run or saved during this review; no DAQ, VISA, or serial command was issued.

`docs/ELYSE_ACQ_VI_FRAME_INVENTORY_2026-09-28.csv` records a stable path, selector label, directly contained calls/state names, and Diagram Disable status for every frame. `tools/build_acq_vi_frame_inventory.py` regenerates it from the offline JSON. It is an **index**, not a dataflow proof: branches with a true diagram-enable flag may still be unreachable at runtime, and names alone do not establish wire direction or error handling. Its `parser_selector_source_unverified` column is diagnostic only. In the nested stop graph, some parser-assigned selectors appear to be task-reference names where the native screenshot shows Boolean control wires; the exact guards must therefore be read in LabVIEW, not inferred from that column.

`docs/ELYSE_ACQ_NATIVE_FRAME_COVERAGE_LEDGER_2026-09-28.md` now records the separate native frame-by-frame pass, including exact NI6602 timing and the distinction between enabled and diagram-disabled initialization branches. It does not certify the 390 runtime frames.

| Coverage measure | Result | Meaning |
|---|---:|---|
| LLB members parsed | 17/17 | Complete local library inventory. |
| Statically reachable members | 15/17 | Root and 14 local subVIs; two NI6259 VIs have no static caller. |
| Original raw diagrams (2026-10-01) | 533 | 17 roots plus 516 non-root diagrams; fresh source-matching exports, including flat sequences and loop bodies. |
| Non-root diagrams in statically reachable members | 512 | New census has not yet been cross-indexed with every prior proof. Historical normalized count 520 includes four unsupported focal sequence rows. |
| Root runtime frames | 390 | 354 lie within dispatcher loop UID `102`; 26 top-level event selectors. |
| Native 32-bit VI openings | 15/15 reachable | Visible diagrams checked, **not** every selector frame manually visited. |
| Complete LabVIEW-control logic parity | Not yet demonstrated | Remaining proof is frame-level guards, wires, state transitions, concurrency, and error branches; DAQmx device internals are outside this criterion. |

## Execution model to preserve

The outer five-frame sequence is strictly ordered: preparatory state; task/PSP/serial initialization; concurrent operation; conditional controlled stop; PSP/serial cleanup. Frame 1 itself has six stages. It time-syncs against `10.20.30.2`, creates NI counter/AI/DIO/AO tasks, attempts a NI6071E trigger recovery when the returned error cluster selects the error arm, dynamically discovers `ni.var.psp://10.20.30.2/SUPERVISION`, then publishes initial states and starts the first I/O exchange. The `-200284` text is a comment, not an equality guard. Initialization is **not** a harmless read-only phase: it sets nonzero AO values and may start counters.

The five frame-2 `While` loops operate concurrently, not top-to-bottom:

The saved native overview shows each loop's stop terminal connected to the Boolean `stop` local. Thus `stop=True` requests termination of all five loops, but they can observe it on different iterations; the diagram does not impose simultaneous exit or a total order between their final I/O operations. The enclosing outer sequence cannot enter frame 3 until frame 2's loops have completed. The parser's separate `stop` label is ambiguous because it also attaches that name to an AO-array value; the native loop-terminal wiring is the evidence for this Boolean stop claim.

| Loop UID | LabVIEW responsibility | Python boundary needed |
|---:|---|---|
| `102` | 20 ms event timeout; PSP command/status read; `DPS` → `Value (Signaling)` dispatch; NI6602 updates; water-flow stop logic; 26 event cases. | Command inbox, deterministic procedure scheduler, event trace, interlock service. |
| `203` | NI6071E read, DIO96 read/write, NI6703 write, PSP bank publish, pressure/readback discrepancy; seven ordered subframes and 80 ms loop wait. | Acquirer and output-commit loop with versioned snapshots and readback. |
| `20601` | Assemble and publish `VAM-A`/display values; three subframes and 80 ms wait. | Projection/publisher from one coherent snapshot. |
| `47483` | NI6220 read, means, WCM-related projection, `VAD`/`VAM-S`; 15 ms visible wait. NI6259 alternative is diagram-disabled. | Independent 16-channel acquisition stream and derived values. |
| `59483` | TPG300 pressure/status for two sessions; ordered 500 ms waits. | Serial poller with explicit freshness and fault state. |

The 26 event cases are not all procedures. Case 0 is timeout/PSP dispatch; cases 1–2 reconstruct direct/deviated magnet setpoint rows and conditionally propagate `M/A=True` setpoints to AO; cases 3–25 are named procedures. A false `NewVal` does not execute a procedure. The `DPS` dispatcher exposes an `Alimentation aimant = PT` request without a matching visible event handler; Python must not invent that actuator action.

Frame 3 contains the nested structure highlighted in the user screenshot, not a single generic “stop” block. The native diagram shows that Boolean `TCP ED` selects `case:43488`: its `False` arm is empty; its `True` arm contains two concurrent `While` loops (`41705`, `42592`). The upper loop continues NI6071E/DIO96/NI6703 exchange. In the lower loop, Boolean `Arrêt général` selects `case:52981`. Its `False` arm writes the LabVIEW `Disabled` property with the enum value `Enabled` for `TCP ED`, `Cmd alimentation HT`, `Lecture alimentation HT`, `Arrêt général`, and `ETAPES`. Its `True` arm executes seven-phase sequence `51954`. Both loops have `stop urgence` wired to their stop terminals; phase 6 of the lower sequence writes `stop urgence=True`, so the loops need not terminate on the same iteration. This is a native wire-level reading of the shown branches, not a certified hardware shutdown or a proof of all failure paths.

The stop outer frame alone contributes **52 indexed selector-frame rows**. All seven top-level stop phases and the contained 3-, 3-, 4-, 15-, and 8-frame sequences were navigated in native 32-bit LabVIEW on 2026-09-28. An inner sequence is an ordering constraint, not one indivisible action. In phase 0, the caption says “descend HT to 6.5 kV,” but the actual comparison uses `6.6`: the `False` arm subtracts `0.1` from the command, waits `500 ms`, and feeds `False` to the While stop terminal; the `True` arm feeds `True` to that terminal without a further decrement. Thus the visible exit test is command `< 6.6`, not a proven physical readback of 6.5 kV. Floating-point/boundary behavior and indefinite waiting still need pure-code tests.

| `sequence:51954` phase | Nested selector scope | Static normal-path meaning |
|---:|---|---|
| 0 | `while:18613` plus `case:47558` | Decrement HT command by `0.1` per `500 ms` until command `< 6.6` (native comparator), despite the 6.5 kV caption. |
| 1 | `sequence:47655` (3 frames), `while:47748` and `while:48046` | Wait for two NI6602 pulse-complete states, stop each task, then wait `1000 ms`. |
| 2 | `sequence:49098` (3 frames) | `C4_OUT_DIO96` HT-supply stop line `False`, then `True`, then wait `1000 ms`. |
| 3 | `sequence:128434` (4 frames) | Set C6/C7 ten-channel magnet AO command banks to zero; wait `1000 ms`; update a `C3_OUT_DIO96` stop line; wait `1000 ms`. |
| 4 | `sequence:42397` (15 frames) | Five ordered `False`→`True` DIO pulses for klystron focus, HT relay, premagnetization, heating, and low-level modulator shutdown, with waits of `1000`, `1000`, `1000`, `2000`, and `1000 ms`. |
| 5 | `sequence:54275` (8 frames) | `C3_OUT_DIO96` cooling-stop pulse for canon, wait `400 ms`, cooling-stop pulse for section, two *local EPS/DPS status-assignment* frames, wait `100 ms`. No direct PSP writer exists within this sequence; a sibling loop may publish local state. |
| 6 | No nested selector | In the same frame, set `ETAPES=0`, write `stop urgence=True` and `Arrêt général=False`, and wait `1000 ms`; these nodes are not wire-ordered against the wait. |

These phase meanings were checked by navigating the native sequence selectors; the CSV supplies exact scope paths and counts. Later [raw-terminal checks](ELYSE_ACQ_CONTROLLED_STOP_HT_RAMP_2026-09-30.md) identify the phase-3–5 local DIO fields and phase-5 EPS/DPS assignments. Their PSP publication schedule and physical effects remain unverified. In particular, a “stop” Python method must not collapse phases 4–5 into one Boolean flip.

### Control-flow parser check (2026-09-28)

The offline parser indexes scope nesting reproducibly, but its selector-net assignments are **not reliable enough to specify guards** in the stop frame. It reports `DPS#5.DPS` for Case `43488`, `C1NI6071E` task-reference names for the two While selectors, and `C2NI6071E` for Case `52981`. Native wire inspection instead establishes Boolean `TCP ED` and `Arrêt général` as the outer and inner Case selectors, respectively, and `stop urgence` as the two While exit signals. The parser discrepancy could arise from misresolved scope tunnels or a source/version mismatch; the evidence does not yet distinguish them. The seven-phase ordering and phase-0 comparison behavior are now directly checked. Still open: who sets `TCP ED` and `Arrêt général`, the detailed DIO bit/state mapping, error/fault interruption, and how a partial stop recovers.

`tools/build_acq_control_instance_inventory.py` now indexes all 1,453 root-VI instance nodes with their parent frame and the parser's input/output nets, producing `docs/ELYSE_ACQ_CONTROL_INSTANCE_INVENTORY_2026-09-28.csv`. This is a search aid for cross-loop state, not a substitute for following native wires. Across the five runtime loops, 36 names occur in at least two loops; the set includes generic primitives and cannot be equated with 36 shared variables. A saved native screenshot of runtime frame 2 (`EV-ACQ-0012-runtime-parallel-loops-overview.png`) shows the `stop` local connected to the stop terminal of **all five** top-level loops. The parser inventory identifies `stop` instances in only loops `102` and `203`, so its apparent absence from another loop is not evidence of absence. The non-primitive candidates most relevant to controller behavior are:

| Named state in normalized graph | Loop UIDs where it occurs | Next wire-level question |
|---|---|---|
| `stop` | Parser finds `102`, `203`; native screenshot shows all five top-level loops consume it. | Which code path sets it, and when do the concurrent loops observe the change? |
| `BNI`, `BPRO`, `BAUX`, `DPC` | `102`, `203` | Are these command banks, readback banks, or local aliases at each occurrence? |
| `DPS` | `102`, `203`, `20601` | How does request acknowledgement propagate between dispatcher and publishers? |
| `Pression Section`, `Pression Chambre` | `102`/`203`, `203`/`20601` | Which snapshot is read and published when the pressure poller updates? |
| `VDD`, `VTL`, `VTS` | `20601`, `47483` | Which acquisition values are transferred to the shared-value assembly loop? |
| `Voie directe`, `Voie déviée` | `102`, `203` | Which loop owns setpoint changes versus discrepancy/readback projection? |

These are **candidate interactions**, not verified read/write directions. The next proof step is to follow the native local-variable terminals, Case selectors, and loop exit tunnels for these names, then turn each verified transition into a pure Python test with mocked external-call results.

## Local VI contracts checked against native diagrams

“Native check” means the member and visible diagram were opened in 32-bit LabVIEW. Scope counts come from the offline parser; this table does not claim that every scope frame was navigated manually.

| Reachable VI | Selector frames | Observed transformation / side effect | Python transfer |
|---|---:|---|---|
| `1_ACQ_INIT_DIO96.vi` | 0 | Creates C3/C4/C5 DI tasks (56/64/56 lines) and DO tasks (40/32/40 lines), serialized by error wire. | Task specification, no simulator actuation. |
| `1_ACQ_INIT_NI6071E.vi` | 5 | Two RSE 64-channel AI tasks on devices 1/2, 5 kHz × 10 samples, PFI0 trigger; C1 channel 2 ±0.05 V, 3–4 ±1 V, other ranges ±10 V. The earlier Python DIFFERENTIAL/RSE diagnostic split was not the native task configuration. | AI task specification and calibrated sample model. |
| `1_ACQ_INIT_NI6220.vi` | 1 | Device 11 `/11/ai0..15`, RSE; 0–3 and 8–15 ±0.2 V, 4–7 ±10 V. Rate/count are parent locals 58/57, not proven fixed at the displayed 5 kHz/10 defaults. Public error-in is unused; final internal error reaches public error-out through local 0. | 16-channel AI task specification; parent inputs remain explicit. |
| `1_ACQ_INIT_NI6602.vi` | 8 | Eight `/10/ctr0..7` retriggerable output tasks, 20 MHz timing; counters 0,1,2,5,6,7 start during init; 3,4 remain configured. Counter 7 has falling-edge trigger. | Counter state machine and exact timing table. |
| `1_ACQ_INIT_NI6703.vi` | 8 | Four ten-channel AO tasks C6–C9 on devices 6–9, ±10 V. Native outer sequence frames 0–3 have now all been selected and inspected; the count of eight includes nested selector rows. | AO task specification with safe startup plan. |
| `1_ACQ_READ_NI6071E.vi` | 4 | Reads both 64-channel tasks, averages sample axis, applies per-channel `mean×scale+offset` with calibration hardwired true; 1 s read timeout. | Deterministic calibration/projection. |
| `1_ACQ_READ_NI6220.vi` | 3 | Requests 2D DBL N-channel/N-sample data with literal timeout `-1`; calibration selector is False. Mean-For N shares the sample-count input net: for nonnegative integer N, mean count is `min(N, returned channel count)`, not unconditionally 16. Front-panel “8 voies” / connector `0:7` do not establish task size. | Bounded non-actuating mean projection; stop flag is not a read-cancellation argument. See the [original wire correction](ELYSE_ACQ_FINAL_CLEANUP_TRACE_2026-10-01.md#ni6220-error-contract-and-mean-loop-correction). |
| `1_ACQ_RW_DIO96.vi` | 2 | Reads C3/C4/C5 DI, then writes C3/C4/C5 DO in error-wire order, auto-start enabled. No interlock policy inside helper. | Read/commit adapter with explicit output ownership. |
| `1_ACQ_WRITE_NI6602.vi` | 1 | Polls pulse completion at 1 ms intervals until done or loop index exceeds 20, stops task, clears stop error, then writes three DAQmx properties before restart. For a 20 MHz task, `Délai` in µs × 20 (I32) feeds **both initial-delay and low-tick properties**; `Largeur` in µs × 20 feeds high ticks. | Counter reconfiguration state machine; preserve error semantics and check I32 conversion/overflow. |
| `1_ACQ_WRITE_NI6703.vi` | 2 | Scales C6–C9 arrays, including nonlinear C8[3]/[4], then executes four DAQ writes; prior cluster implementation is diagram-disabled. | Pure conversion functions plus separate write adapter. |
| `1_Focales ON.vi` | 2 | Three CHROMA sessions: initialize, set voltage/slew/current, enable output, close. | Serial-device state machine, only after production port/protocol validation. |
| `1_Focales OFF.vi` | 2 | Repeats configuration then disables outputs and closes; this is not merely “write off.” | Explicit off sequence and failure policy. |
| `2_SUP_Ecart_lu_ecr_VDirecte.vi` | 2 | `orange = abs(command-readback)>threshold` for eleven direct-path fields; Phase HF/Laser output forced false. | Pure cluster transform and exact-field tests. |
| `2_SUP_Ecart_lu_ecr_VDéviée.vi` | 2 | Same comparison for nine deviated-path fields. | Pure cluster transform and exact-field tests. |

Two NI6259 members have no static caller. The fresh original census contains one initializer non-root diagram and three reader non-root diagrams for these members. They are legacy-looking device-11 variants, not an additional active card path. Dynamic invocation has not been excluded by runtime observation, so “dormant” means **statically unreferenced**, not impossible to execute under every configuration.

The focal front panels currently show defaults COM10/COM11/COM12. The diagram separately annotates COM35/COM36/COM37 as development-PC resources. Neither the annotation nor defaults prove which production ports the root VI actually passes at the call site. Resolve the caller wires before coding serial resources.

## What existing Python does and does not reproduce

`DeviceServers/control/elyse_acq/plans.py` contains the 23 case-3..25 procedure plans, executed by `engine.py` against `simulator.py`. The Tango facade `DS_ElyseAcq.py` refuses production hardware mode. These plans capture many **ordered intent traces** but are not a port of the Acquisition server:

| Legacy behavior | Current Python status | Required next offline artifact |
|---|---|---|
| 23 procedure cases 3..25 | Declarative plans and simulator present. | Golden traces versus `event_step_inventory.csv`, including pulse restore, waits, state publications, and cancellation. |
| Timeout case 0 and setpoint cases 1–2 | Not represented by the procedure-plan contract. | Pure PSP dispatcher and direct/deviated setpoint routing tests. |
| Five concurrent runtime loops | Not represented. | Simulated multi-loop scheduler with timestamped card samples, PSP snapshots, stale-data and stop propagation. |
| DAQ task creation, startup AO values, counter startup | Not represented. | Pure configuration model and startup trace; do not create physical tasks yet. |
| Read/calibration/aggregation/discrepancy | Not represented as continuous acquisition. | Pure transformations using all channel and coefficient maps, with shape and threshold tests. |
| Controlled/general stop and final cleanup | Not represented as the seven-phase stop graph. | Fault-injectable stop state machine and resource-lifecycle tests. |
| TPG300/CHROMA actual protocol and hardware response | Not commissioned. | Serial framing evidence, production resources, timeout/failure injection. |

For Python, separate immutable sample and command snapshots from physical I/O. One component should own each DAQ task/output group; procedures should request state changes, not race the acquisition loop with direct writes. Each PSP publication should carry source timestamp/quality, since the LabVIEW loops run at different rates. Those are **design inferences** from concurrent LabVIEW wiring, not claims that the original guarantees atomic publication.

## XP-side code staged on 2026-09-28

The Python 3.4-compatible `legacy/xp_acq_agent` candidate was copied to
`C:\elyse_acq_candidate_20260928_source` on `10.20.30.10` through the redirected
RDP drive. Explorer properties on the acquisition computer showed **44 files,
3 directories, 206,066 bytes**, matching the local staging folder; the remote
`elyse_agent` listing displayed `hardware_plan.py` and `hardware_tasks.py`.
The live `C:\xp_elyse_deployment` installation was not overwritten or run.

`hardware_plan.py` describes all eleven cards and recovered startup images
without a driver import. `hardware_tasks.py` contains explicitly gated DAQmx
task constructors and manual read/write/start methods, with no TCP route to
create a hardware task. Python 3.4 local mocks and simulator tests passed
**40/40**. No NI tasks were created on the acquisition computer, no output
was written, and the new adapter was not executed there. This is transferred
code, not commissioned initialization: DIO96 task creation can change output
states, and physical pin mapping/polarity, interlocks, full event/stop logic,
and error/rollback behavior remain unverified.

## Software-only closure criterion

Understanding the controller means being able to predict, for each reachable LabVIEW frame and supplied external return value/error, which frame runs next, which local/PSP state changes, what command and arguments are sent to each external VI/DAQmx/VISA boundary, and when the loop exits. The same criterion applies to startup, all five concurrent runtime loops, event cases 0–25, controlled stop, and final cleanup. No claim about voltage at a terminal or NI-DAQmx's implementation is needed.

The remaining work is therefore **inside the LabVIEW graph**: trace selector input wires and exit tunnels for all indexed branches; distinguish control state from observations; map every read/write of locals and PSP values across loops; resolve ordering where an error wire or sequence frame imposes it, and record when loops have no defined relative order. For external nodes, record the exact call parameters and resulting branch on success/error without reverse-engineering the driver.

## Discriminating software tests before claiming parity

1. Trace writes to `TCP ED`, `Arrêt général`, and `stop urgence` before and during frame 3; extract exact bit indices and EPS/DPS field directions for stop phases 2–5. Test phase-0 boundary values, cancellation, and injected failure after every physical-side-effect phase in simulation.
2. For every event case, compare Python trace with terminal-level event inventory: output value, polarity, delay, restore, publication, and resulting DPS/EPS state. Treat the 23 plans as candidates, not certified parity.
3. Reproduce the calculations **performed by LabVIEW**: AI means/calibrations, AO linear and C8 nonlinear transforms, NI6602 tick conversion, DI/DO array dimensions, and discrepancy flags with fixed inputs and exact expected outputs.
4. Resolve PSP producer/consumer ownership and typedef field order against `docs/ELYSE_ACQ_SHARED_VARIABLE_FIELDS_2026-09-28.csv`; test delayed, absent, and contradictory updates.
5. Model external DAQmx/VISA/PSP calls with controlled return values and errors. Verify LabVIEW's subsequent branches, task-reference handling, timeout paths, and final cleanup. Physical polarity, serial framing, and card behavior are **not required to close this software-logic review**; they belong to a separate deployment/commissioning task.

The immediate implementation target is a simulator of the LabVIEW controller with abstract external calls, realistic timing/state, snapshots, and fault injection. This document does **not** authorize replay of observed startup or stop sequences on equipment.

## Supporting evidence

- `C:\dev\ELYSE-ACQ-analysis\offline\reports\llb_inventory.md`: member/call graph.
- `C:\dev\ELYSE-ACQ-analysis\offline\reports\subvi_contracts.md`: card and helper contracts.
- `C:\dev\ELYSE-ACQ-analysis\offline\reports\procedure_steps.md` and `event_step_inventory.csv`: event procedures and terminal-level rows.
- `C:\dev\ELYSE-ACQ-analysis\offline\reports\channel_map.csv`, `calibration_map.csv`, `ni6602_timing.csv`: card mappings and coefficients.
- `docs/ELYSE_ACQ_LIFECYCLE_LOOP_AUDIT_2026-09-28.md`: root lifecycle, stop, and loop audit.
- `docs/ELYSE_ACQ_SHARED_VARIABLES_2026-09-28.md`: PSP namespace and field mapping.
