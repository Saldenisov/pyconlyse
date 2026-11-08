# ELYSE Acquisition: lifecycle and loop audit (2026-09-28)

## Verdict and scope

This is an audit of `0_ACQ_ELYSE.vi` in the copied `ACQUISITION.llb`, not a claim of complete behavioral equivalence. The five outer sequence frames and five top-level runtime loops are structurally identified. All 17 local LLB members have parsed static bodies and contracts; none has yet passed the stronger test of complete behavior under faults and real external devices. No VI was run, saved, or modified for this audit, and no hardware command was issued. The [completion matrix](ELYSE_ACQ_CLOSURE_MATRIX_2026-10-01.md) now separates software-logic closure from physical commissioning and keeps Acquisition ahead of Supervision.

The five outer frames are sequential. The five `While` loops inside frame 2 execute concurrently; their physical positions on the diagram do **not** establish execution order.

## Outer sequence

| Frame | Observed operation | Important limit |
|---:|---|---|
| 0 | `Variables`: local terminals/state references and labels; no hardware operation in the normalized body. | This is preparatory, not the complete initialization. |
| 1 | Six-frame initialization sequence, described below. | It configures tasks **and writes initial outputs**; it is not read-only discovery. |
| 2 | Five concurrent loops: event/command dispatch, NI6071E+DIO+AO exchange, shared-value aggregation, NI6220/WCM acquisition, TPG300 pressure polling. | Cross-loop freshness, arbitration, and shutdown timing are not fully proven. |
| 3 | `TCP ED`-selected controlled/general-stop branch: two concurrent loops; `Arrêt général` selects a seven-phase procedure versus re-enabling five UI controls. | Case selectors and normal-path sequence are natively checked; error paths and guarantee of completion are not. |
| 4 | Close connections for 27 fixed PSP URI-tag references and two TPG300 sessions; assign `stop=False` independently. | This is not the dynamically opened reference array. The PSP error shift register is uninitialized; branches are not mutually ordered. No DAQ Stop/Clear or output-zero call appears in this frame. See the [full cleanup trace](ELYSE_ACQ_FINAL_CLEANUP_TRACE_2026-10-01.md). |

### Initialization (outer frame 1)

| Inner frame | Observed operation |
|---:|---|
| 0 | Wait 200 ms; execute `net time \\10.20.30.2 /set /y`. This synchronizes the XP clock with the other computer; it is **not** the PSP connection. |
| 1 | Create/configure NI6602 counter tasks, two NI6071E analog-input tasks, DIO96 tasks, and four NI6703 analog-output tasks; propagate error clusters through conditional gates. |
| 2 | Test NI6071E acquisition. The read error cluster directly selects the fallback Case; `-200284` is a comment, not a code-equality guard. The error arm clears the read error, calls Clear Task for C1 then C2, and calls NI6071E INIT with `/1/20MHzTimebase`, `/2/20MHzTimebase`, 5000 Hz and 10 samples. Its returned error passes through another error-clearing Case. Successful fallback is not established by that final cluster. |
| 3 | An explicit per-variable PSP map is inside a disabled diagram branch and therefore is not the active connection path. |
| 4 | Discover/open shared-variable references dynamically under `ni.var.psp://10.20.30.2/SUPERVISION`. This is the actual visible PSP discovery step. |
| 5 | Five startup subframes: assign DIO/AO initial state (including nonzero AO values); publish C6–C9 and C3–C5 output clusters to PSP; perform initial NI6071E/DIO96/NI6703 exchange; initialize TPG300 sessions and NI6220, reset UI/procedure flags; publish `DPS`, `EPS`, and `VDM-A`. The last startup write has a visible 100 ms wait. |

The initial analog-output arrays contain nonzero constants; a Python server must not infer that “initialize” means “all outputs zero.” The physical meaning and safety of these constants still need terminal-level validation.

### Initialization error gates checked on 2026-10-01

The new [hash-pinned validator](../tools/validate_acq_initialization_error_gates.py)
traces outer frame 1, initialization sequence `201`, frame 1 diagram `227`.
Four root error Cases lie between the initializer calls. The no-error arm
of each Case passes its input cluster directly to its output tunnel;
the error arm contains only `Clear Errors.vi`, whose output reaches the
same output tunnel. The wiring is therefore not a root-level
abort-on-first-error policy.

| Initializer | Error output | Case | Case output destination | Task-reference local bank |
|---|---|---|---|---|
| NI6602 call 593 | 598 | 1242 | 374 → NI6071E input 436 | paramIdx 21 |
| NI6071E call 262 | 448 | 1503 | 1510 → DIO96 input 517 | paramIdx 23 and 24 |
| DIO96 call 500 | 505 | 1203 | 1220 → NI6703 input 637 | paramIdx 22 |
| NI6703 call 620 | 625 | 342 | 562 → sequence-local terminal 1131 | paramIdx 25 |

Sequence local `1063`, defined in initialization frame 1, forwards that
last gate result through frame-2 terminal `1195` to input `2639` of
`1_ACQ_READ_NI6071E.vi` (call `287`). All five task-reference local writes
are outside the four error Cases. Their placement does not establish
that the returned references are valid after a failed initializer.
No explicit task Stop/Clear, retry, or stop-flag local assignment exists
in frame `227`. Cleanup, error return, and partial-task behavior inside
the called initializers remain separate review items. The later frame-2
acquisition fallback is also a separate mechanism, not rollback of all
card initialization.

The validator passed against the saved source export; nine offline
tests passed in [the targeted test file](../tests/scripts/test_elyse_acq_init_error_gates.py).
They reject changed gate destinations, altered error-arm calls,
added top-level operations, nonempty pass-through arms, task-bank changes,
and changed sequence-local or reader mappings. This is static wire evidence. The four missing
native error-arm screenshots in the 2026-10-01 Word report are still
required; no VI was executed or saved for this check.

```powershell
python tools/validate_acq_initialization_error_gates.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
python tests/scripts/test_elyse_acq_init_error_gates.py
```

### NI6071E initialization fallback checked on 2026-10-01

The [fallback validator](../tools/validate_acq_initialization_ai_fallback.py)
checks initialization sequence `201`, frame 2 diagram `133`. READ call
`287` error output `1309` is wired directly to Case selector `2107`
(Case `2105`). No error-code comparison node intervenes. The comment
`Erreur :-200284 s'il manque le pilote 20MHz` explains the intended
fault scenario but does not restrict this branch to that code.
The no-error arm `2119` passes the error cluster through unchanged.

The error arm `2128` has this error-wire-ordered call chain:

```text
READ error -> Clear Errors.vi (2134)
           -> DAQmx Clear Task.vi (4034, C1 task bank 23)
           -> DAQmx Clear Task.vi (7931, C2 task bank 24)
           -> 1_ACQ_INIT_NI6071E.vi (1198)
           -> Case 2239 -> sequence local 306
```

This corrects the earlier description of the two operations as task
"stops": their saved call labels are **Clear Task**, not Stop Task.
The Clear Task error outputs feed the next call without an intervening
error-clear node. The internal initializer audit below now establishes
that its public error input is unused. This parent wire therefore does
not impose an initializer abort on a preceding Clear Task error; actual
task-clear and task-creation outcomes remain untested.

| Fallback initializer input | Constant terminal | Call terminal / slot | Saved value |
|---|---|---|---|
| C1 trigger source | 2402 | 1201 / 0 | `/1/20MHzTimebase` |
| C2 trigger source | 2415 | 1205 / 1 | `/2/20MHzTimebase` |
| Sampling frequency | 2428 | 1209 / 2 | DBL `40B3880000000000` = 5000 Hz |
| Samples per channel | 2390 | 1229 / 4 | I32 `0000000A` = 10 |

Initializer outputs `1232` and `1235` replace local task-reference
banks `23` and `24`, outside Case `2239`. That Case's no-error arm
passes through; its error arm calls only `Clear Errors.vi` (`2268`).
The result reaches sequence-local terminal `1320` (local `306`, defined
in frame 2). No second test READ or retry loop exists in this root
frame. These are controller-requested call arguments, not proof of
successful acquisition, a 20-MHz sampling rate, or recovered task
validity. The initializer's internal wiring, checked below, resolves
the distinction between sampling clock and start-trigger source.

Nine tests passed in [the fallback test file](../tests/scripts/test_elyse_acq_init_ai_fallback.py),
including mutations of task calls, error wires, bank destinations,
sample count, connector slots, final error clearing and sequence-local
mapping. The check parses the existing hash-pinned source export; no
native screenshot was added, and no VI was executed or saved.

```powershell
python tools/validate_acq_initialization_ai_fallback.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
python tests/scripts/test_elyse_acq_init_ai_fallback.py
```

The combined 2026-10-01 offline check ran **28 tests in 41.127 s: OK**
(three saved-source positive cases and 25 rejecting-mutation cases).
It covers these initialization gates, the AI fallback, and the eight
controlled-stop Wait tunnel paths, not full VI behavior:

```powershell
python -m unittest discover -s tests/scripts -p 'test_elyse_acq_*.py'
```

### NI6071E internal initializer checked on 2026-10-01

The [initializer validator](../tools/validate_acq_ni6071e_initializer.py)
checks the original archived `1_ACQ_INIT_NI6071E.vi`, not the converted
working main VI. A fresh read-only binary export produced
[`1_ACQ_INIT_NI6071E_XML_shafeb8.zip`](../legacy/xp_acq_agent/data/source_exports/1_ACQ_INIT_NI6071E_XML_shafeb8.zip).
Original VI SHA256:
`FEB881DB3A01B5402D5164C3B149195E83D8A0B089DDAEEA0D6A54D7C4E0F07C`.
Export ZIP SHA256:
`C150D3978BF6F27602EB5E7AF83E0EFAB1B4D162714F400F28A119E2314C2DD3`.
The validator additionally pins all three exported XML files. The
original VI hash remained unchanged; no VI was opened, run or saved
during this export and wire check.

Sequence `101` has terminal frame 0 (`1144`), C1 frame 1 (`2383`), and
C2 frame 2 (`944`). The three retained native diagrams were also
visually reviewed:

- [Frame 0 terminals](C:/dev/ELYSE-ACQ-analysis/runs/20261001-lifecycle-proof/images/INIT-NI6071E-frame0.png).
- [Frame 1 C1](C:/dev/ELYSE-ACQ-analysis/runs/20261001-lifecycle-proof/images/INIT-NI6071E-frame1-C1.png).
- [Frame 2 C2](C:/dev/ELYSE-ACQ-analysis/runs/20261001-lifecycle-proof/images/INIT-NI6071E-frame2-C2.png).

**Observed configuration requests.** Both tasks use a 64-iteration For
with auto-indexed physical-channel and Min/Max arrays, RSE, finite
Sample Clock with `OnboardClock` and rising edge, then a separate
rising-edge Start Digital Edge configuration. Frequency and sample
count feed Sample Clock; the two Trigger inputs feed Start Digital
Edge. Thus the parent fallback's `20MHzTimebase` paths are start-trigger
sources, not a 20-MHz sampling rate.

| Task | Complete physical array | Requested AI ranges |
|---|---|---|
| C1 | `1/ai0` through `1/ai63` | ai2: ±0.05 V; ai3/ai4: ±1 V; remaining 61: ±10 V |
| C2 | `2/ai0` through `2/ai63` | All 64: ±10 V |

These complete arrays come from raw constant bytes and their wires;
the native array widgets display only selected elements. Both
Create Task calls receive `auto cleanup=True`. Both Read property
nodes set RelativeTo to current read position (`0x28B9`) and
AutoStart to True. No explicit Start Task call exists in this subVI.
This proves configuration requests, not successful sampling or physical
cleanup.

**Observed error contract.** Public error-in terminal `583` (FP DCO
`580`) and error-out terminal `1282` (FP DCO `1280`) have no wires and
no matching local references. The internal chain is:

```text
C1 Create Task 2629 [error input 2665 unwired]
  -> C1 channel loop 2680 -> Timing 2393 -> Trigger 2454 -> Read property 2561
  -> sequence local 310: terminal 2390 -> frame-2 terminal 986
  -> C2 Create Task 2462 [error input 2568]
  -> C2 channel loop 2604 -> Timing 998 -> Trigger 2212 -> Read property 2380
  -> Simple Error Handler 134 [error input 2854; output 2814 unwired]
```

The externally supplied error does not enter this chain, and this
chain's result is not assigned to the public error output. Consequently,
the parent error wire cannot be treated as a successful-initialization
acknowledgement or as propagation of these internal DAQmx errors.
No assertion is made about an unwired output's value in every possible
runtime instance. Handler dialogue and DAQmx device outcomes remain
outside this static proof.

Each channel For has ordinary, non-indexed input/output error tunnels,
not an error shift register. Its nine internal wires feed the same
incoming error to each channel call. The output tunnel returns the
last iteration's error rather than an accumulated error history.
**Inference:** an earlier channel error need not appear in the final
error if subsequent calls produce a no-error result. No such device
failure was induced or observed.

The mapping is established for **this subVI only** by both its
connector pane and CPMp flags. Connector slots 0–7 map to local
reference indices `[1,0,6,3,4,7,5,2]`; the root VI has no equivalent
usable CPMp table in this export. Do not apply this recovered
permutation to the root's unresolved local bank identities.

Eighteen tests passed in
[the targeted test file](../tests/scripts/test_elyse_acq_ni6071e_initializer.py):
one original-source check and 17 rejecting mutations of connector/local
mapping, arrays, clock/trigger inputs, task properties, error tunnels,
shift registers, public error wires and polymorphic call slots.

```powershell
python tools/validate_acq_ni6071e_initializer.py legacy/xp_acq_agent/data/source_exports/1_ACQ_INIT_NI6071E_XML_shafeb8.zip
python tests/scripts/test_elyse_acq_ni6071e_initializer.py
```

The combined lifecycle evidence suite passed **46 tests in 41.111 s**:
four original-source checks and 42 rejecting mutations. It includes
the controlled-stop Wait tunnels, initialization error-clearing gates,
NI6071E fallback, and this initializer. Reproduction:

```powershell
python -m unittest discover -s tests/scripts -p 'test_elyse_acq_*.py'
```

The Word evidence document was updated without new native captures:
`ELYSE_ACQ_INITIALIZATION_SHUTDOWN_EVIDENCE_2026-10-01.docx` contains
38 pages and 48 figures. All 38 rendered pages were visually reviewed
at original resolution. Source hashes, test counts and render checks
are recorded in `ELYSE_ACQ_LIFECYCLE_EVIDENCE_CHECK_2026-10-01.json`.
This closes the initializer's array/clock/trigger/error-wire gaps,
not the still-missing 20 nested stop-frame screenshots or unresolved
fault/partial-stop behavior. No hardware or running VI was accessed.

### Runtime (outer frame 2)

| Top-level loop (normalized UID) | Identified role | Visible cadence / nested structure |
|---|---|---|
| `102` | Event dispatcher. Timeout reads PSP command/status banks, projects NI6703 values, dispatches `DPS` requests via `Value (Signaling)` into local event cases, updates NI6602, and checks water-flow safety. There are 26 event cases. | 20 ms event timeout; many command-specific waits and nested loops. |
| `203` | Seven-frame acquisition/exchange: read two NI6071E tasks; read/write DIO96; write four NI6703 AO groups; publish eight shared-value banks; update vacuum/pressure fields; evaluate direct/deviated setpoint–readback discrepancies when gated. | 80 ms loop wait; sequence frames 0–6. |
| `20601` | Assemble the `VAM-A`/shared-variable display cluster from card values, pressures, and status fields; publish the assembled value. | 80 ms loop wait; three sequence frames. |
| `47483` | Read NI6220, calculate means and WCM-related values, update `VAD`/`VAM-S` paths. A separate NI6259 structure is disabled. | 15 ms visible wait; two-frame sequence plus disabled structure. |
| `59483` | Poll TPG300 pressure/status for section and chamber gauges, updating vacuum fields. | Two ordered 500 ms waits in a two-frame sequence. |

The 2026-10-01 [NI6220 raw-wire check](ELYSE_ACQ_FINAL_CLEANUP_TRACE_2026-10-01.md#ni6220-error-contract-and-mean-loop-correction)
corrects the earlier reader summary: its mean For N is on the supplied
sample-count net. Output length is bounded by N and returned channel
count, not unconditionally 16. Its read receives timeout literal −1;
the loop stop flag is not a read-cancellation input. If an abstract
external read never returns, `stop=True` alone cannot complete the
iteration or reach final cleanup. This is a conditional scheduling
result, not an observed equipment hang.

The runtime dispatcher has a statically mapped catalog of all 26 event selectors and 1,566 terminal-level rows across nested event sequences. This establishes the visible *normal-path* commands and pulse ordering; it does not establish all races, stale-data behavior, device timeout semantics, or restart behavior. `DPS[22]` (`Alimentation aimant = PT`, one-based selector arm 23) has no registered event case; it is an unresolved/orphaned intent, not an implemented actuator procedure in the recovered top-level graph. See the [raw event-registration audit](ELYSE_ACQ_DPS_EVENT_REGISTRATION_AUDIT_2026-09-29.md).

### Controlled/general stop (outer frame 3)

Native wire inspection shows `TCP ED` selecting the outer Case (`False` is empty) and `Arrêt général` selecting the inner Case. The inner `False` arm sets the LabVIEW `Disabled` property to `Enabled` for five UI elements. The outer `True` arm contains two `While` loops: one continues final read/write exchange with NI6071E, DIO96, and NI6703 at a visible 50 ms wait; the other runs the inner Case and its seven-phase stop sequence. Both While stop terminals consume `stop urgence`, which phase 6 sets to `True`:

1. Ramp the logical C9[0] HT command down by 0.1 with 500 ms waits while the comparison with 6.6 is false. The caption says 6.5 kV; the [raw-wire recheck](ELYSE_ACQ_CONTROLLED_STOP_HT_RAMP_2026-09-30.md) confirms exit at command `< 6.6`, not measured voltage, and records two auxiliary local assignments with unresolved labels.
2. Wait for modulator pulse completion and stop NI6602 tasks.
3. Set the HT supply stop line `C4_OUT_DIO96[19]` `False` in the same nested frame as a 150 ms wait, then `True` in the next frame, then wait 1,000 ms. The [raw-wire recheck](ELYSE_ACQ_CONTROLLED_STOP_HT_RAMP_2026-09-30.md) places the 150 ms wait inside the first frame; it does not prove an exact 150 ms physical pulse because the wait and local write can execute concurrently.
4. Set C6/C7 magnet analog commands to zero.
5. Execute the ordered modulator-stop procedure.
6. Execute the ordered cooling-stop procedure.
7. In one final frame, reset stage/state flags, assign `stop urgence=True`
   and `Arrêt général=False`, and wait 1,000 ms. The assignments and wait
   are not wire-ordered relative to one another; see the
   [raw-wire recheck](ELYSE_ACQ_CONTROLLED_STOP_HT_RAMP_2026-09-30.md).

All seven stop phases and their nested 3-, 3-, 4-, 15-, and 8-frame sequences were navigated in native LabVIEW on 2026-09-28. The five top-level runtime loops all consume the Boolean `stop`; outer frame 3 begins only after they exit. These observations are **not** a validated safety procedure. The origins of `TCP ED`/`Arrêt général`, exact DIO bit/state mapping, fault interruption, and partial-stop recovery remain unproven. Do not replay this sequence against equipment based on this document alone. See `docs/ELYSE_ACQ_NATIVE_REVIEW_AND_PYTHON_TRANSFER_2026-09-28.md` for frame detail and parser caveats.

The 2026-10-01 [sequence-tunnel trace](ELYSE_ACQ_CONTROLLED_STOP_HT_RAMP_2026-09-30.md)
additionally resolves all eight previously undecoded short Wait inputs
in phases 4 and 5 to `150 ms`. Phase 4 uses this duration in frames
0,3,6,9,12; phase 5 in frames 0,3,4, including the C3[4]=True restore
frame. Ten mutation tests passed. These software Wait inputs do not
prove electrical pulse widths; 20 nested stop-frame screenshots remain
missing from the Word evidence set. Earlier navigation records and
retained per-frame screenshot coverage are distinct measures.

## Coverage and remaining proof

| Measure | Current evidence |
|---|---|
| Outer sequence | 5/5 frames visually inspected. |
| Initialization | 6/6 primary frames and 5/5 startup subframes visually inspected. |
| Runtime dispatcher | 26/26 event selectors inspected; normal-path static procedures mapped. |
| Top-level runtime loops | 5/5 identified and statically traversed; their external timing and cross-loop arbitration are not validated. |
| Local LLB members | 17/17 parsed and contracted; 15 statically reachable (root plus 14 subVIs), 2 NI6259 VIs not statically referenced. All 15 reachable members have now been opened in native 32-bit LabVIEW and their visible diagrams cross-checked. This is not frame-by-frame native coverage. |
| Original raw diagrams | The 2026-10-01 original-source census contains 533 diagrams including 17 roots: 516 non-root diagrams, 512 in statically reachable members. The older normalized 520-row inventory includes four focal-VI sequence rows absent from original source; it is retained as a search aid. Diagram-enable/reachability guards and complete behavioral coverage are separate checks. |
| Full behavioral understanding | 0/17 met the earlier strict criterion: trigger, guard, transition, side effect, error branch, and external contract all validated. This is a deliberately conservative metric, not “nothing is known.” |

For the **LabVIEW-control logic** task, the outstanding work is to trace each runtime loop's stop condition and cross-loop shared-state ownership; verify PSP field use and producer–consumer direction; inspect every selector guard, error branch, call argument, wait, and exit tunnel; and establish exactly when LabVIEW creates, reads, writes, stops, and clears external tasks. NI-DAQmx internals, serial framing, electrical polarity, and physical interlock behavior are outside this software-logic review. They matter only for a later live-hardware deployment claim.

## Evidence

- Source LLB: `C:\dev\ELYSE-ACQ-analysis\source\10.20.30.10\ACQUISITION.llb`; SHA-256 `EB7C08800823D025F1B4F9E8EEA89ED9878F0CF00A02427871583B99989B2F8A`.
- Static inventory: `C:\dev\ELYSE-ACQ-analysis\offline\reports\llb_inventory.md`.
- Local VI contracts: `C:\dev\ELYSE-ACQ-analysis\offline\reports\subvi_contracts.md`.
- Event procedures: `C:\dev\ELYSE-ACQ-analysis\offline\reports\procedure_steps.md` and `event_step_inventory.csv`.
- Prior run coverage: `C:\dev\ELYSE-ACQ-analysis\runs\20260922-085500-+0200\progress.json`.
- Native screenshots: `C:\dev\ELYSE-ACQ-analysis\runs\20260922-085500-+0200\images\EV-ACQ-0001` through `EV-ACQ-0014`, plus event/stop detail captures in the same directory.
- Shared-variable field inventory: `C:\dev\pyconlyse\docs\ELYSE_ACQ_SHARED_VARIABLES_2026-09-28.md` and `ELYSE_ACQ_SHARED_VARIABLE_FIELDS_2026-09-28.csv`.
