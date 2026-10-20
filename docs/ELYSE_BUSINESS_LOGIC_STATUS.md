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
| XP GUI server, default port 8771 | Cold IDLE, explicit local initialization, six AI/DI banks, General, fourteen additional source-stage paths and conditional cooling-trip evaluation on the same owner | New paths default uncommissioned; no new HTTP/Tango commands; native error semantics, HT-voltage/counter and full 27-bank parity remain incomplete |
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
runtime now has a separately gated executor for it. Raw input polarity and physical interlock authority
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
| Stage/fault logic | Source traces and inert models | Fourteen additional stage paths and seven cooling-trip frames integrated, default uncommissioned | Remaining native error semantics/HT-voltage/counter/ingress/lifecycle paths and separate hardware qualification |

## Executable stage transfer on 20 October 2026

`AcquisitionRuntime.stage_request()` dispatches the following additional paths
to `CardBackend.execute_stage()` on the existing NI owner thread. The executor
consumes the hash-pinned source catalog rather than duplicating its nominal
constants:

| Paths | Source event indices | Ordered frames |
| --- | --- | --- |
| cooling.start / cooling.stop | 3 / 4 | 12 / 7 |
| chauffage.start / chauffage.stop | 12 / 7 | 7 / 4 |
| prema.start / prema.stop | 13 / 8 | 8 / 4 |
| relays_ht.start / relays_ht.stop | 14 / 9 | 8 / 4 |
| modulator.reset | 11 | 4 |
| alimentation_ht.start / alimentation_ht.stop / alimentation_ht.reset | 20 / 21 / 22 | 5 / 5 / 5 |
| focales.start / focales.stop | 15 / 10 | 11 / 7 including nested frames |

These are 91 executable nominal frames, not another projection-only catalog.
Backend callbacks commit complete C3/C4 output banks through the existing owner,
preserving untouched fields; EPS/DPS are typed local software memory. The saved
False `NewVal` arms are empty. Source waits, including the extra 150 ms restore
wait in `cooling.stop`, are retained. Publications retain only the latest RAM
snapshot per name and explicitly do not acknowledge PSP delivery.

After a successful raw NI read, the same worker can evaluate the source cooling
condition and execute its seven frames without another NI read. This requires
both `stage_controls_verified` and `cooling_trip_verified`; both default to
false in constructors and example configuration. The general-only profile and
synthetic Demo input source cannot activate this background branch. The deployed
LV2012 enabled-arm selection still requires independent qualification.

This implementation uses an explicit deterministic writes/nested-helper/publication/wait
schedule within each native unordered frame. It does not reproduce independent
VI-loop timing or prove electrical pulse widths. EPS literals never authorize a
start, and the cooling trip does not invent automatic Chauffage/PREMA/Focales
shutdown. No remote mutation route or new GUI command button was enabled.

The three standalone HT supply paths require the additional exact-Boolean
`ht_controls_verified=false` gate. This is independent of `ht_feedback_verified`
for the extended General-stop profile. Each has five nominal frames, a 150 ms
pulse and a final 100 ms wait. They publish the source error-wired chain
`DPS -> EPS -> C4_OUT_DIO96`; a failed publication skips the rest of that chain.
Reset clears DPS16 without changing EPS. None changes an analog setpoint,
implements a voltage ramp, checks an input permit or stops a counter. HT start
can energize the voltage already commanded before that procedure.

Any accepted standalone HT command conservatively retains a separate release
requirement. Source HT-stop completion and EPS literals are not zero/OFF
acknowledgements; successful legacy General Arrêt cannot clear that requirement.
NI ownership remains protected until a successful separately qualified extended
shutdown or explicit confirmation of local electrical OFF. Failed commands keep
the requirement. This is additional Python release policy, not inferred VI logic.

Failure handling is explicit Python policy: starts/reset abort further effects;
stops attempt remaining source effects and retain every failure. Unfinished
output pulses are restored to known preprocedure values, including when a
write may have applied before raising. Failed restorations survive in backend
memory. Before any later output procedure, those exact fields must be recovered;
failed recovery blocks subsequent whole-bank writes instead of echoing a held
start bit. This policy is not claimed as native VI error-path equivalence.

Stage failures keep NI ownership in FAULT. Accepted stop procedures cannot be
cancelled by close/deinit; General Arrêt can interrupt a start on the same owner.
Previously set cancellation is cleared only by that owner for an accepted
recovery, without overwriting a newly queued stop/close. Precommand measurements
remain stale until a postcommand read. Resource release still requires General
Arrêt or explicit confirmation that the cabinet was switched off locally.

Remaining transfer is real implementation work: native helper/error-handler
semantics, HT-voltage/counter procedures, full shared-variable ingress/publication semantics,
and original outer-stop/resource/error scheduling. The six-bank and sample-count
discrepancies remain open. No code was deployed or executed on hardware.

Focales helper callbacks are now executed, not assumed successful opaque
boundaries. The reviewed source first pulses C4[7], waits 29 s, runs three independent
serial branches, waits 1.5 s and later pulses reset. Each Chroma ON/OFF branch
initializes with reset enabled and writes nonzero voltage/current before the
output command; OFF is not merely a zero-write operation. The separate
`focal_controls_verified=false` gate and verified serial resources are required
before the first cabinet/NI write. Native workers must be confirmed joined before
any later ON/OFF, NI output or resource release, including after cancellation or
timeout. Unkillable or unconfirmed children remain owned and block those actions.
General OFF uses that same owned command adapter, rather than an independent
legacy process owner that could forget a failed join. Three branches execute in
parallel; their 1–30 s execution deadline has separate bounded safety-reaping
waits. Process termination is never physical-OFF acknowledgement.

`run_branch()` keeps its original OFF default and now accepts an exact Boolean
for the saved ON/OFF difference. The x86 DLL hash, resources and source setpoints
remain unchanged. A separate worker entry point validates its ON/OFF flag.
Focales stop serializes the independent native 500 ms nested and 150 ms outer
waits as 650 ms; this is an explicit scheduling deviation, not electrical timing
equivalence. The original Simple Error Handler Continue/Stop behavior, vendor
incoming-error and positive-warning conversion remain unproven. Python uses
explicit fail-start/best-effort-stop, warning-as-failure, close-in-finally and
owned-worker deadlines. Actual serial mapping and physical mains/interlock
authority remain separate from nominal source-frame knowledge. Normal NI reads
pause during the long owner procedure; retained precommand telemetry stays stale.
An OFF-branch error does not terminate independent OFF branches prematurely;
they continue until completion or their execution deadline/cancellation. The
error still makes the helper fail. ON uses the separate conservative fail-fast
policy. Neither policy is claimed as the vendor's native error semantics.

The package builder now includes both execution modules and builds its
configuration from the committed example, not an ignored site configuration.
Stage, cooling, standalone HT, Focales, feedback and Chroma permissions are forced false in generated candidates.
All three package profiles are checked for complete dependency/file closure,
manifest hashes, unchanged catalog bytes and absence of keys, telemetry history,
native drivers or an interpreter. A packaged cold runtime was also imported and
started in IDLE on actual Python 3.4 with native-library loading denied.

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

The 20 October 2026 nine-stage/cooling integration passed the offline software
gate on Python 3.12.14: **3384 passed, no skips, 7300 warnings, 207.46 s**, with
the actual Python 3.4 process lane enabled. Its focused runtime/General/HT/stage
suites passed **208 tests on actual Python 3.4.4 in 3.307 s**, with external
connections and native-library loading denied and no NI/VISA module loaded.
These suites overlap the offline gate; their counts must not be added together.
Four package/profile checks, including a packaged Python 3.4 cold start, passed;
after strengthening the feedback reset across all package profiles, those four
checks were repeated successfully (1.29 s). No frontend source changed in this
integration, and no new frontend or hardware acceptance result is claimed.

The subsequent three-path HT extension passed **3406 offline tests**, no skips,
7300 warnings, in 203.69 s. The focused actual Python 3.4 suites passed **230
tests in 3.996 s** under the same external-network/native-driver denial, with
no NI/VISA driver module loaded. This supersedes the earlier nine-path count;
the overlapping counts are not cumulative. The HT release-latch, interrupted
start, failed extended stop and physical-OFF prompt tests use fake owners only.

The final fourteen-path/Focales integration, including the OFF-branch
best-effort correction, passed **3465 offline tests**, no skips, 7300 warnings,
in **216.84 s**. Focused actual Python 3.4 suites passed **289 tests in 5.134 s**
with external connections and ctypes driver loading denied; no NI/VISA driver
module was loaded. These are final overlapping totals, not additions to the
earlier counts. All native-driver and process-lifecycle tests use fake DLLs and
fake worker processes. The actual Python 3.4 subprocess package lane starts
only a cold IDLE runtime. The package contains 18 Python modules with complete
relative-import closure and no native driver, private key or telemetry history.
The critical syntax/undefined-name Ruff selection and `git diff --check` passed.
Independent source/lifecycle review found no remaining blocker in these selected
paths after the shared General-OFF worker-ownership correction. None of these
checks establishes complete VI equivalence or hardware commissioning.

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
