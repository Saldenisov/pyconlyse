# Acquisition cooling-flow safety: raw wire trace (2026-09-29)

## Question and boundary

This note resolves the Boolean guard and commanded output sequence in the saved Acquisition VI's `Timeout` event, ordered subframe 3. The evidence is the extracted LabVIEW 2012 BDHb/FPHb XML plus the native screenshot `C:\dev\ELYSE-ACQ-analysis\runs\20260922-085500-+0200\images\EV-ACQ-0021-timeout3-water-flow-safety.png`. The source LLB SHA-256 is `EB7C08800823D025F1B4F9E8EEA89ED9878F0CF00A02427871583B99989B2F8A`. This is saved-program logic, not a measured electrical truth table or a test of today's deployed executable. No VI or card was operated.

## Observed guard

**Static native-import continuation, 2026-10-15:** the byte-exact Main copy
was loaded as a subVI and inspected without Run/Save in 32-bit LabVIEW2020
(executable file version20.0f1). The Diagram Disable selector marks the
nonempty guard arm Enabled; its alternate Disabled arm is empty. Both
Boolean Case arms and all seven trip frames were photographed. The
[source/image record](ELYSE_ACQ_NATIVE_STATIC_OBSERVATIONS_2026-10-15.json)
pins the source and18 PNGs, with a reproducible validator. This qualifies
the specific native20 static interpretation, not original LV2012 execution
or generic omitted activeDiag/defaultDiag semantics. The following older
activation limitation remains applicable to unrestricted original-runtime
equivalence, but no longer describes an absence of source-matched native20
static evidence.

The historical native screenshot shows the `Enabled` arm of Diagram
Disable14478. The original hash-pinned XML has `commentMode=True`, arms
21070/21403 and no explicit `activeDiag`/`defaultDiag` fields. The screenshot
does not establish hash equality with that source. Thus the arm's activation
in the pinned original remains a separate native/format-semantics gate;
the following guard is conditional on executing its nonempty arm.
Its Boolean Case `11044` has an empty False arm and a seven-frame sequence
(`8256`) in the True arm. The selector signal `53644` is fed by AND primitive
`52228` (`primResID=1061`). Its two inputs are:

- OR primitive `12948` (`primResID=1062`) of `C4_IN_DIO96[19]` (`Débit EAU CANON`) and `C4_IN_DIO96[38]` (`Débit EAU SECTION`). Raw cluster unbundle `39336` has field indices 19 and 38 and is fed by local reference `paramIdx=16`.
- Compound-arithmetic OR `47240` (`objFlags=720896`, operation bits 16–18 = 3) of `C3_IN_DIO96[0]` (`Refroidissement Canon marche`) and `C3_IN_DIO96[6]` (`Refroidissement Section marche`). Both input DCOs have `objFlags=327680` (`0x50000`), which sets the Compound Arithmetic input-inversion bit. Raw unbundle `42277` has field indices 0 and 6 and is fed by local reference `paramIdx=18`.

Therefore the saved diagram's Boolean guard is:

`trip = (C4_IN_DIO96[19] OR C4_IN_DIO96[38]) AND ((NOT C3_IN_DIO96[0]) OR (NOT C3_IN_DIO96[6]))`

The terms are **raw LabVIEW Boolean values**. The labels alone do not establish whether a physical contact or DIO read is active-high or active-low. In particular, do not translate this formula into “flow present/absent” or “pump running/stopped” without confirming the NI-card input polarity and field construction. This is a software guard, not evidence that it is the only physical interlock.

The [hash-pinned selector-wire validator](../tools/validate_acq_cooling_flow_guard.py)
checks all four raw input wires, the inversion flags, OR/AND nodes, and the
direct Case-selector wire. Neither `ACTION` nor an EPS status bit lies on
that selector path. Therefore, each execution of Timeout subframe 3 with
the same four raw values would select the same arm; whether and how often
the Timeout event executes again is a separate scheduling question. The
Event Structure timeout terminal is wired to a **20 ms** literal, but
event-handler work, including the stop sequence, can exceed that interval.
This trace does not establish repeat pulse behavior in the running system.

## True-arm command sequence

| Frame | Saved-program action | Raw evidence |
|---:|---|---|
| 0 | Set logical `C3_OUT_DIO96[1]` to `False`, set local `ACTION=True`, wait **150 ms** | `nMux 10308`, `paramIdx=17`, `ConstValue=0000` and `01`, wait `0x96` |
| 1 | Restore `C3_OUT_DIO96[1]` to `True` | `nMux 13262`, `ConstValue=01` |
| 2 | Wait **400 ms** | wait `0x190` |
| 3 | Set logical `C3_OUT_DIO96[4]` to `False`, wait **150 ms** | `nMux 20645`, `ConstValue=0000`, wait `0x96` |
| 4 | Restore `C3_OUT_DIO96[4]` to `True` | `nMux 30840`, `ConstValue=01` |
| 5 | Update EPS and DPS flags | EPS local reference `paramIdx=44`: fields 1=True (`Marche refroidissement ED`), 2=False (`Marche refroidissement OK`), 3=False (`Arrêt refroidissement`), 5=True (`Arret refroidissement OK`). DPS `paramIdx=36`: field 1=False (`Arret refroidissement X`). Field identities are from the FPHb/VCTP cluster type order, not the constants' captions. |
| 6 | Publish DPS through `ni.var.psp://10.20.30.2/SUPERVISION/DPS`, then wait **100 ms** | `sharedVariableDynamicWrite 39450`, DPS local reference `paramIdx=36`, wait `0x64` |

The FPHb control field labels identify `C3_OUT_DIO96[1]` as `01 CPB1 b79 Arrêt Reffroidissement Canon` and `[4]` as `04 CPB4 b73 Arrêt Reffroidissement Section`. The literal Boolean constants in frames 0, 1, 3, and 4 all carry the copied label `00 CPB0 b81 Marche Reffroidissement Canon`; that label is **stale for the selected fields**. In frame 5, the constant captions for EPS field 3 and DPS field 1 are likewise inconsistent with their cluster field identities (`Arrêt refroidissement` and `Arret refroidissement X`). The `nMux` field indices and the control's own ordered type labels, not the constants' captions, determine the target. Thus this branch commands two stop lines in sequence; it does not directly call a general-stop event.

The 150 ms intervals describe how long the local command values are held before restoration in this LabVIEW sequence. The actual card write occurs in another running loop; its scheduling, output polarity, relay response, and pulse width at the terminals are not established here. The branch writes fault/status flags after both pulses; whether the `ACTION` local value is consumed elsewhere and whether the condition retriggers on each `Timeout` remain to be traced.

`DeviceServers/control/elyse_acq/interlocks.py` now contains a pure, non-actuating transcription of the Boolean guard. Its standard-library tests cover all **16** combinations of the four raw inputs and require the saved **64-field C4** and **56-field C3** Boolean bank shapes. This strict Python input validation is not a claim about LabVIEW runtime coercion; the tests verify the expression's Python truth table, not physical meaning or completeness of the interlock.

A further [raw-wire validator](../tools/validate_acq_cooling_flow_trip_status.py)
pins the True arm's frame-5 status assignments. The pure
`project_cooling_flow_trip_local_completion` function in
`DeviceServers/control/elyse_acq/acq_status_projection.py` models EPS[1]
True, EPS[2] False, EPS[3] False, EPS[5] True, and DPS[1] False, without
executing stop commands or publishing PSP. This frame does **not** assign
EPS[8] (`Marche GENERAL Mod. OK`). Consequently, a pure
[cooling-start](ELYSE_ACQ_COOLING_START_COMPLETION_2026-09-30.md) → flow-trip
status replay leaves EPS[8] True while cooling OK becomes False; that is a
bounded property of these two saved assignment frames, not proof that no
other writer or hardware interlock changes the running system. In fact,
the [whole-cluster EPS writer audit](ELYSE_ACQ_EPS_WHOLE_CLUSTER_INGEST_2026-09-30.md)
finds that the Timeout event reads remote EPS into the local cluster in
its earlier frame 0. A returned snapshot may alter EPS[8] before this
flow-trip frame executes; remote freshness and ordering remain unmeasured.

## Complete frame proof added 2026-10-03

The [complete sequence validator](../tools/validate_acq_timeout_cooling_sequence.py)
now pins all12 direct graphs and38 nets, both Diagram Disable arms, both
Boolean arms, all7 trip frames, all16 local reference sites including the
special DPS reader flags5, every pulse/restoration field, Wait input,
status bundle, PSP URI and error-handler connector. The additional flag
bit on the DPS local is retained without inventing a runtime interpretation.
The [inert frame projection](../DeviceServers/control/elyse_acq/vi_simulation/timeout_cooling.py)
requires explicit enabled-arm state and each frame's own full-sized read
snapshots. Unknown activation returns UNSUPPLIED; disabled returns no guard.

Within frame0, ACTION=True, the C3 command assignment and150-ms Wait have
no wire ordering relative to one another. The sequence must complete all
nodes before frame1; it does not require the Wait to start after the
command write. Therefore150ms cannot be asserted even as the exact local
False-hold duration, and independent card-write sampling may miss a pulse.
The same caveat applies to frame3. The earlier table lists requested Wait
arguments, not measured or guaranteed local/physical intervals. A fresh
local snapshot in each restoration frame may preserve unrelated intervening
changes or overwrite another writer's intervening update.

Frame5 preserves EPS[8] and does not write stop30/TCP ED45. Frame6 publishes
a separate DPS snapshot; it is not necessarily identical to frame5's reset
result. The publication error reaches Simple Error Handler39603, whose
outputs are unwired. No error arm here writes a general stop. A possible
fault or blocking modal handler is not equivalent to proven cancellation.

Verification:13 focused source/projection tests passed in19.40s, including
all16 raw guard combinations, full field preservation, all7 requested
frame effects and rejection of added default metadata, removed inversion,
shifted restore field, altered waits, extra gates and changed local flags.

```powershell
python tools/validate_acq_cooling_flow_trip_status.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
python tools/validate_acq_cooling_flow_guard.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
python -m unittest tests.device_servers.control.test_elyse_acq_status_projection
```
