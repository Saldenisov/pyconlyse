# ELYSE business logic migration status

## Current boundary

The original Acquisition, original Supervision, source-derived Python models,
LabVIEW telemetry bridge and prepared Python NI server are separate systems.
Neither complete Supervision coverage nor complete Python replacement is proven.
The machine-readable boundary is
[`business_logic_contract()`](../DeviceServers/control/elyse_acq/business_logic_contract.py).
It describes reviewed source, not a running deployment or permission to operate equipment.

This consolidation does not deploy software, restart processes, initialize cards
or issue NI, serial, PSP or Tango commands.

| Layer | Implemented behavior | Limit |
| --- | --- | --- |
| Original Acquisition | Saved VI evidence traces initialization, read/write loops, requests, stage sequences and selected fault/stop paths | Native execution, cross-loop timing and electrical safety are not certified by a static trace |
| Original Supervision | Saved-source models, display mappings, event fragments and focused lifecycle traces | 39 original VI/XML identities accounted; complete semantic coverage remains false |
| Pure Python models | Explicit supplied inputs/returns; 16 modulator procedures and 120 frames including nested frames | No stage actuators or native error-handler replacement |
| Copied LabVIEW telemetry | Latest 27 shared-variable banks through Python 3.4 to Everest | Sequential/non-atomic; transport does not qualify the source data or replace Acquisition |
| XP GUI server, default port 8771 | Cold IDLE, explicit local initialization, six AI/DI banks, local General Marche/Arrêt, resource release | Not the 27-bank schema; no runtime Chauffage/PREMA/Focales start controls or cooling-trip evaluation |
| Simulator, port 8765 | Signed named procedures, replay and durable intent state | Logical simulation only, not the GUI NI server |
| Everest Tango/web | Separate read-only views of LabVIEW telemetry and Python runtime; replay/business simulation | No remote NI control route; replay values are not measurements |

Initialization is not read-only: the NI backend configures 21 tasks across 11
cards, starts selected counters and writes reviewed AO/DO startup images.
Deinitialization releases resources; it is not electrical shutdown. EPS completion
assignments are software state, not independent physical acknowledgement.

## Control logic and unresolved parity

The reviewed Acquisition stage handlers receive DPS requests through EPS
`Value(Signaling)` events. Chauffage, PREMA and Focales start paths pulse C4 output
bits 3, 5 and 7 respectively. Their software completion flags do not establish
that cooling, power or current is physically available. No EPS OK/ED admission
predicate was found in those reviewed handlers. This is not permission to bypass
external cabinet interlocks.

The separately reviewed cooling timeout condition is
`(C4_IN[19] OR C4_IN[38]) AND ((NOT C3_IN[0]) OR (NOT C3_IN[6]))`.
Its true arm pulses C3 outputs and changes cooling EPS/DPS state. It is not a
demonstrated automatic klystron-stage shutdown, and the prepared Python NI
runtime does not execute it. Raw input polarity and physical interlock authority
remain unqualified. See [admission evidence](ELYSE_ACQ_STAGE_ADMISSION_2026-10-19.json)
and [running-fault evidence](ELYSE_ACQ_RUNNING_FAULT_RESPONSE_2026-10-19.json).

General Arrêt event 6 is distinct from the original outer seven-phase controlled
stop. The full event-6 implementation includes Focales OFF and C4 stop pulses
8, 17, 6, 4 and 1. The `general_only_test` profile deliberately implements only
frames 13–16. `extended_ht_stop` adds a Python-specific HT preamble; it is not
literal event-6 equivalence and remains gated by unqualified feedback/resources.

The GUI's default `legacy_full` profile preflights its Chroma stop adapter before
General Marche. With `resources_verified=false`, that preflight blocks a start
even when only General is requested. This additional Python gate is not literal
equivalence to the original General start handler. The partial
`general_only_test` profile avoids that Chroma dependency but must not be used
as a claim of full shutdown. No verification flag was relaxed in this audit.

| Discrepancy | Original/source model | Prepared NI runtime | Required closure |
| --- | --- | --- | --- |
| NI6071E requested samples/channel | 1000 in three explicit I/O callers | 10, with finite task configuration | Review task timing, trigger, read count and timeout together; 100× is a count ratio, not measured averaging time or precision |
| Snapshot schema | 27 LabVIEW shared-variable banks | Six input banks, 144 AI + 176 DI | Explicit schema adapter and validation; no guessed missing banks |
| Read scheduling | Parallel VI loops with asynchronous output writers | Single NI owner; normal reads pause during General procedures and FAULT | Qualify timing and continued fault observation before replacement |
| Stage/fault logic | Source traces and inert models | No live runtime transfer of remaining stages/cooling guard | Separate reviewed implementation and tests before any activation |

## Supervision corrections and remaining work

M/A action 1 passes seven retained values unchanged in the reviewed beam-line
handlers. It does not demonstrate a supply Marche/Arrêt command or a new
setpoint transfer; whole numeric-bank republication attempts remain. The web
description now states that behavior and leaves hardware buttons disabled.

X1/X10 selects small/large literal steps for later arrows; switching it alone
does not change a setpoint or transmit a Boolean to Acquisition. False selects
the smaller step and true the larger across 24 traced paths. Phase HF/Laser
fine adjustment uses 1/5, not a universal factor of ten. H1 routes to C6.OUT00
and Triplet 1-1 to C7.OUT00 according to saved labelled types, without physical
pin/ABI qualification. Phase running/fault flags are retained UI state in the
reviewed writers, not demonstrated hardware producers.

The additive source references below supersede older summaries only within
their explicit scope. Their historical JSON contents are unchanged:

- [M/A and X1/X10](../Supervision/integration_analysis/beam_switch_trace_20261016/RESULT.json)
- [H1 and Triplet 1-1](../Supervision/integration_analysis/h1_triplet_source_20261017/RESULT.json)
- [Phase retained status](../Supervision/integration_analysis/phase_status_20261017/RESULT.json)
- [Completion audit and outstanding dependencies](../Supervision/integration_analysis/completion_audit_20261017/RESULT.json)

Remaining source work includes Radioprot framing/coercion/retained state,
Search and Replace Pattern byte grammar and termination, Validate path/encoding,
and complete Event/property/camera/motor dependency closure. Frozen historical
reports and source-hash references do not imply those dependencies are bundled
or reproducible without the external VI/XML/screenshot evidence archive.

## Data freshness

The web now rejects retained bank values when the receiver explicitly reports
OFF, FAULT or not-ready, and rejects invalid elapsed times. A fault or missing
value in another bank does not invalidate an independently fresh, valid bank.

The Python-runtime Tango view distinguishes authenticated bridge freshness from
NI-source freshness. A recently polled signed response cannot make stale NI
measurements RUNNING. EXECUTING reports a procedure in progress without claiming
current acquisition data. No last-good measurement becomes a fresh zero.

## Deployment evidence

The saved v4 General-only A/B test matched 176 DI, 112 commanded DO and 40 logical
AO fields at baseline/start/stop, with 29 matching C4 input transitions.
Commanded outputs are not electrical output readback. The test did not qualify
analog sampling, pulse widths, other stages or full shutdown. See
[A/B evidence](ELYSE_PYTHON_LABVIEW_GENERAL_AB_2026-10-19.json).

The v6 extended-stop candidate was not deployed or hardware-commissioned.
Feedback and Chroma-resource verification remain false. Source code in Git,
saved package manifests, autostart settings and currently running code must not
be treated as interchangeable. HMAC proves response authentication, not an
immutable deployed build identity. See [HT readiness evidence](ELYSE_PYTHON_HT_READINESS_2026-10-19.json).

## Software verification

Verification on 19 October 2026 used the isolated review worktree, not the
running lab services:

| Gate | Result |
| --- | --- |
| Python 3.12.14 offline software gate, actual Python 3.4 process lane enabled | 3295 passed, no skips, 7300 warnings, 203.87 s |
| Actual Python 3.4.4 runtime/General/HT/model suites, fake drivers and loopback | 124 passed, 2.392 s; native DLL loading denied; no NI/VISA driver modules loaded |
| Affected frontend selections | 12 suites, 172 tests passed |
| Production frontend bundle, `CI=false` | Compiled with warnings |
| Strict frontend bundle, `CI=true` | Fails on existing React Hook warnings outside ELYSE: AndorSpectrographClient, CameraClient, DSNetioPDUClient, DSStandaMotorsClient, DeviceControl |

The targeted Python runtime suites are subsets of the 3295-test gate; the
frontend result is separate. Repeated targeted runs are not additional
independent coverage. Python warnings
include legacy `datetime.utcnow()` deprecations and the existing pytest
module-isolation rewrite warning. No full-project warning-free or hardware
acceptance result is claimed. Pinned catalogs and saved helper modules retain
byte identities in Git rather than acquiring platform-dependent line endings.

Use Python 3.12 with project development dependencies. The repository network
guard permits fake loopback services but blocks external DNS/TCP/UDP:

```powershell
& ./tools/test_elyse_offline.ps1 -Python python
```

The runner uses explicit package paths and pytest importlib mode to avoid the
three unrelated packages named `tests`. It restores the caller's environment.
The three ambiguous XP fixture imports are now fully qualified.
Process tests skip explicitly when actual Python 3.4 is absent; provide an
existing interpreter with `-Python34 <absolute-path>` to enable that optional
simulation lane. The interpreter is not bundled, and modern Python must not
be substituted for that compatibility check.

Tests using source XML, original VI binaries, NI installation libraries or
external screenshot paths belong to a separate evidence-reproduction lane.
They must not be reported as clean-checkout software tests. Hardware qualification
requires its own authorized session; it is not part of this consolidation.

Deployment configuration, private keys, telemetry histories, SQLite databases,
vendor DLLs, installers and extracted Python runtimes are not release sources.
