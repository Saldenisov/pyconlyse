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
| XP GUI server, default port 8771 | Cold IDLE or recovery-blocked; explicit initialization; six AI/DI banks; General; sixteen additional stage paths; C9 voltage and C10 timing transfers; seven-phase outer stop; conditional cooling trip, all on the same owner | New paths default uncommissioned; no new HTTP/Tango commands; native error semantics, live PSP ingress and full 27-bank parity remain incomplete |
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
| Stage/fault logic | Source traces and inert models | Sixteen additional stage paths, HT command and C10 timing transfers, forty outer-stop frames and seven cooling-trip frames integrated, default uncommissioned | Remaining native error semantics, live shared-variable transport, scheduling and separate hardware qualification |

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
semantics, live shared-variable ingress/publication and recovery semantics,
and original parallel resource/error scheduling. The six-bank and sample-count
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

The package builder includes the reviewed execution modules and builds its
configuration from the committed example, not an ignored site configuration.
Stage, cooling, standalone HT, Focales, impulsion, HT-voltage, counter-timing, outer-stop,
feedback and Chroma permissions are forced false in generated candidates.
All three package profiles are checked for complete dependency/file closure,
manifest hashes, unchanged catalog bytes and absence of keys, telemetry history,
native drivers or an interpreter. A packaged cold runtime was also imported and
started in IDLE on actual Python 3.4 with native-library loading denied.

## Impulsion HT voltage and outer stop transfer

Two additional local paths implement the four frames of event 23 and five
frames of event 24. `modulator_impulse.start` starts retained ctr3 then ctr4;
stop polls and stops each counter. The channel property is `CO.PulseDone`,
not whole-task `Task.is_task_done()`. Stop polling retains the source condition
`Done OR i > 40`: at most 42 reads, with a requested 1 ms wait including the
last iteration. This is not a wall-clock deadline or physical pulse measurement.
The stop assigns EPS42 true and EPS52 false; it does not substitute EPS55.
Both paths retain the error-wired DPS to EPS publication chain as bounded RAM
snapshots. `counter_controls_verified=false` is an additional commissioning gate.

`AcquisitionRuntime.set_ht_voltage()` transfers a finite supplied logical
command into C9[0], preserving fields 1 through 9. Source PSP reader UID10449
feeds local12 and the independent AO writer UID7386; the NI6703 helper applies
gain 0.5, so logical 12.7 maps to 6.35 V. This local adapter neither opens PSP
nor invents its event producer, clamp, ramp or EPS admission predicate.
Its +/-20 logical validation follows the +/-10 V driver domain, not an
operating permit. `ht_voltage_controls_verified=false` remains independent of
the supply start/reset/stop gate and of feedback qualification.

The seven-phase `outer_controlled_stop()` executes the reviewed forty-frame
plan: command ramp, ctr3/4 stop, HT supply stop, selected analog/digital output
clearing, five C4 stop pulses, cooling pulses/software status, then final local
flags. Its strict ramp exit is command `<6.6`, not measured zero, not the
Python 8 kV preamble, and not General event 6. C6[8] and C7[2] are preserved.
Fixed requested waits total 12.85 s, excluding ramp and counter-poll waits. The
executor does not invent Chroma OFF, PSP publications, automatic root-loop
dispatch, NI resource release or electrical-OFF acknowledgement.
`outer_stop_verified=false` separately gates this local entry point.

These executors serialize nominal effects on the existing owner. Source
Clear Errors boundaries continue the counter chain; Python retains their
exceptions and reports aggregate failure. A failed/cancelled start attempts
counter cleanup, and an interrupted outer stop attempts remaining dedicated
counter/HT-stop cleanup without continuing to cooling OFF or final flags.
The 200-decrement bound and failure/cancellation policy are Python additions.
Failed counter stops and pulse restorations retain ownership. Held General or
RAZ commands block ordinary stage requests; only the dedicated General/outer
recovery path may release those fields before further whole-bank stop writes.

An AO callback can apply a command and then raise. The last successful image
then remains diagnostic history, not the current C9 command. An owner-lifetime
uncertainty latch blocks new energy/start commands, another C9 write and the
source outer ramp's use of that stale image. Outer cleanup still attempts
dedicated counter/HT stops; it cannot claim completion. Qualified independent
reconciliation or a new initialization after explicit electrical OFF is
required. Successful source stop callbacks alone do not clear HT release
requirements. Legacy General event 6 cannot clear an outstanding impulsion
stop requirement, because that event does not stop those counters.

NI6071E input streams now explicitly set the recovered current-read-position
and AutoStart properties. Timing remains finite ten samples; Python reads ten
with its explicit start/read/stop lifecycle. The original three callers request
1000 with a 1 s timeout from that finite ten-sample task, and their helper can
process returned partial rows along an error path. The Python SDK raises a
negative driver error before returning such rows. Blindly changing ten to 1000
would not reproduce that behavior. Startup fallback trigger selection and
native partial-error semantics remain open.

Original VI/XML/screenshot reproduction requires the external evidence archive.
`acquisition_outer_stop.SOURCE_ARCHIVE` names its actual external location;
that archive is not bundled in a clean checkout. Committed software tests
compare the forty-frame executable plan with the independently retained inert
plan, including source identities and ramp projections. They are not a fresh
LabVIEW wire inspection or hardware qualification. Frozen source catalogs and
historical evidence remain unchanged.

## Source counter timing transfer

`AcquisitionRuntime.configure_counter_timing()` now accepts an explicit immutable
33-DBL C1011NI6602 command image and executes its source-derived path on the
existing NI owner. `counter_timing_controls_verified=false` independently gates
this path, in addition to stage commissioning. No GUI button, automatic PSP
reader, HTTP/Tango mutation route or additional task owner is introduced. The
runtime does not invent a startup local39 image or report requested timings as
measured pulse widths.

The reviewed Acquisition guard is `0 < n < 17` for selector field32. Source
DBL arithmetic computes `q=floor((n-1.0)/2.0)` before the Index Array I32 inputs.
Finite selectors `1 <= n < 17`, including fractions, select C10 ctr0 through ctr7:
`1.5` and `2.9` select ctr0; `3.1` selects ctr1; `16.9` selects ctr7.
Delay and width come from fields `2*q` and `2*q+1`; fields16 through31 belong
to the other half of the combined image and do not address C11 here. Values
outside the guard have no counter/reset/publication effect. The source also
admits `0 < n < 1`, which produces task index -1 and timing indices -2/-1.
Python rejects that request before callbacks rather than treating negative
indices as valid array accesses. The native default task and ensuing driver
error remain unqualified. Requiring a finite exact-float tuple is additional
Python policy. The source types, wires and artifact hashes are recorded in
[`counter_selector_error_evidence.json`](../legacy/xp_acq_agent/data/counter_selector_error_evidence.json).

The original writer converts each finite timing as follows:

```text
product = microseconds * 20.0
signed = clamp(round_ties_to_even(product), -2147483648, 2147483647)
ticks = signed & 0xFFFFFFFF
```

The new executor preserves that representation, including negative and
saturated inputs. It does not reuse the manual `update_counter_microseconds()`
policy, which rejects negative or non-integral ticks. Zero and large U32 bit
patterns are source representations, not proof of driver acceptance or an
operating permit.

The helper polls channel `CO.PulseDone`, requesting 1 ms in every iteration,
including the last. `Done OR i>20` permits at most 22 reads, not a hard 22 ms
deadline. The nominal chain is Stop2976, Clear Errors309, Property3083, then
Start3032 on the same counter. The properties are initial delay664, low4465
and high4457; initial delay and low use the same converted delay. The low-level
adapter validates all three exact U32 values before any setter and writes them
in that order. It never starts, stops or recreates a task itself.

The caller then rereads local39, changes only selector32 to `-1.0`, writes that
complete image, and rereads local39 again for publication. These three reads
are deliberately distinct. The saved reset can consume a newer selector; it
is not a compare/exchange or an atomic cross-loop snapshot. Python serializes
its own modifications and retains only the latest publication in RAM, with
`psp_delivered=false`. No shared-variable server is contacted.

A property setter may apply and then raise. The backend marks that counter's
configuration uncertain before entering the three-property callback, retains
its last fully acknowledged image separately, and blocks new energy/start
commands after an ambiguous write. No property retry, rollback, modal dialog
or automatic Continue is implemented. The source can mask Stop errors at Clear
Errors and can proceed to reset/publication after a returned helper error and
completed handler. Python exceptions instead abort ordinary continuation and
retain the exact failing stage; native error-cluster/dialog equivalence remains
open. Failed or uncertain Stop/Start calls retain their counter handles and
pending-stop diagnostics.

Runtime release requirements cover every counter whose timing backend was
entered, not just ctr3/ctr4. Legacy General event6 acknowledges none of these
stops; qualified extended General, outer stop and impulsion stop acknowledge
only ctr3/ctr4. Retimed counters0/1/2/5/6/7 still require explicit local
electrical-OFF confirmation before resource release. A queued request invalidated
before backend entry introduces no new counter-stop requirement and preserves
any earlier requirement and the original read fault. Stop/confirmed-close
requests supersede an unexecuted timing request; no callback runs concurrently
with NI cleanup.

### Native error and dialog inspection

`acquisition_counter_error_flow.py` transfers the helper's task/error wires into
a supplied-return model compatible with Python 3.4. Each poll receives the
original task/error through ordinary tunnels, not the previous poll's result.
The last poll feeds Stop2976. Stop's task feeds Property3083, while its error
passes through Clear Errors309; Property's task/error then feed Start3032.
The final Start error is the helper output. Native error status alone is not
a polling exit condition or a source-proven driver short circuit.

Clear Errors has only connector slots0/4 connected. The unwired specific-error
code defaults to0; the documented transform returns `(False, 0, "")` for any
incoming cluster. `clear_all_errors()` implements that explicit value transform.
It does not clear a task, undo a write, catch a Python exception or establish
that Stop succeeded. Every native boundary in the replay still requires a
supplied return; partially applied property effects remain outside its scope.

The caller wires only the helper error into Simple Error Handler22439; the
dialog-mode input and all outputs are unwired. A normal handler return permits
selector reset and independent publication even if its returned error remains
set. A pending modal handler prevents ordinary frame completion. The inspected
local LabVIEW 2020 wrapper defaults to public mode1, with one Continue button,
not Continue/Stop. Continue does not clear or retry the failed operation.
Public modes0..4 map to CORE modes0/1/2/4/5; only public2/4 expose Stop. Their
Stop primitive aborts the calling top-level hierarchy without guaranteeing
normal cleanup. CORE3 is separate automatic error handling, not public3.
The deployed XP LabVIEW 2012 library has not been matched to this local binary.

`AcquisitionRuntime.inspect_counter_error_flow()` exposes a local data-only
replay: explicit error clusters, opaque task tokens and bounded return fixtures
produce a report and RAM-only fixture reset/publication. It cannot accept a
driver callback, mutate runtime state, open a dialog or stop the server. The
saved-default profile rejects a fabricated Stop response and a pending response
when that profile would show no dialog. Hypothetical hierarchy abort remains
available only in the lower-level supplied-return model, with explicit labels.
Neither API is installed on GUI/HTTP/Tango control routes. Actual backend
exceptions continue to fail closed and retain configuration/ownership latches;
native masking is not silently substituted for this Python safety policy.

Source reproduction uses the read-only validator below. It requires the pinned
external XML archives, metadata and saved NI help; these are not clean-checkout
test inputs or a deployment receipt.

```powershell
& C:/Users/elyse/miniconda3/envs/pyconlyse312/python.exe tools/validate_acq_counter_selector_errors.py
```

Clean-checkout tests compare all sixteen selector mappings, the nominal helper
trace, independent reset/publication images and 4301 deterministic finite
conversion fixtures against the retained inert source models. Callback tests
exercise failure/cancellation at each boundary; fake property setters exercise
partial writes at each of the three setters. Original helper identity remains
`4DB9022F837C5629DE670347D00C39285ACEAA61FE7CCA592D99D6F67713E211`.
Original VI/XML/screenshot reproduction still requires the external evidence
archive; these software tests are not a new LabVIEW or hardware run.

## Cold recovery and Python runtime observation on 20 October 2026

The prepared server now reports protocol version 2, a new 32-hex boot session,
a 64-hex source/data fingerprint and a lifecycle revision. The fingerprint
covers the packaged source files present at boot, not loaded bytecode, site
configuration, a Git commit, firmware or commissioning. It must not be used as
remote deployment attestation. The revision changes on accepted lifecycle
requests and completions/faults, not on every telemetry read.

Production GUI initialization exclusively creates a small ownership marker next
to its configuration before invoking the NI backend factory. A cold window
with an unreleased, malformed or unqualified marker enters `RECOVERY_REQUIRED`;
it does not initialize cards. Successful cleanup can remove only the current
session's exact marker, after backend resources and retained native workers
have been released. Stopping an uninitialized blocked window preserves a prior
owner's marker. The marker protects cooperating instances using the same
configuration path, not independent copies, other configurations or LabVIEW.

Recovery requires local electrical-OFF confirmation and a separately qualified
checker proving absence of the prior parent, native children and competing NI
owners. Parent PID absence alone is insufficient. No production checker is
shipped, so an ambiguous prior owner remains blocked; the local recovery button
does not bypass this condition. The small ownership and child journals contain
control-process identities, not measurements or private keys. Telemetry remains
RAM-latest without SQLite or history.

The cold supervisor holds a config-scoped OS file lock and writes a separate
pre-spawn child journal. Only a confirmed nonzero child exit permits another
cold GUI launch, with a default budget of three delayed retries. Exit zero is
intentional termination and is not respawned. A live or unresponsive owner is
never killed, replaced or abandoned. An unconfirmed child journal after
supervisor failure blocks a duplicate launch. The GUI entrypoint now propagates
its return code, so a failed startup is not silently reported as exit zero.
The explicit Windows Startup installer generates a supervisor launcher; no
installed Startup file was changed by this source update. Automatic recovery
of an initialized NI state or replay of a prior command remains forbidden.

The explicit local `ColdAcquisitionSupervisor.recover_prior_child()` acquires
the same config lock and can clear only its exact prior child journal. It
requires electrical-OFF confirmation and a trusted checker returning typed
evidence bound to that record's token, full controlled argument list and SHA256.
The evidence must establish absence of the matching GUI, native children and
competing NI owners; JSON flags or PID-only inspection are not accepted. A
changed record or lost lock aborts recovery. Success leaves the supervisor cold
and does not clear the separate NI ownership marker or launch a process.

Operational recovery is therefore still a commissioning prerequisite, not an
unattended-deployment feature: keep the candidate's autostart unqualified until
a Windows process/native-worker/NI-owner checker has been independently tested.
After an ambiguous crash, establish electrical OFF through the installation's
qualified local procedure, preserve both journals, and use those local recovery
APIs only with that checker. Do not delete files merely because a PID is absent.
If no qualified checker is available, retain the blocked state. A new cold
window must separately recover prior NI ownership before explicit initialization;
neither step resumes a saved stage sequence.

The Everest reader replaces each complete snapshot rather than merging banks.
It clears measurements after transport failure, incompatible identity,
revision rollback or in-session build changes, and suppresses otherwise valid
but stale measurements in its exported view. A changed
boot session requires another consistent poll before data are marked fresh.
Only one read is in flight, retries use bounded backoff, and a late reply after
stop cannot repopulate the cache. A still-live reader prevents overlapping
replacement. Socket inactivity timeouts do not by themselves certify a hard
end-to-end deadline against a peer that continuously drip-feeds bytes.

The separate authenticated web path `/api/elyse/acquisition/runtime` reads
`runtime_json` from the fixed Tango device
`tango://10.20.30.202:10000/elyse/acquisition/runtime`. Its Python Acquisition
tab distinguishes bridge age, NI age, lifecycle/recovery and boot/source
identity, then shows the six typed input banks only when fresh. Missing or
invalid values are not zero. Stale values are removed rather than left as
green live indicators. This view does not fall back to the 27-bank LabVIEW
bridge, PSP, a simulator or direct browser/Flask access to XP. Loss of telemetry
does not establish electrical OFF.

The web application owns one retained Tango-read worker covering proxy
construction and the complete direct read. Concurrent callers share only the
current unexpired flight; callers wait at most two seconds. An unresolved live
worker blocks replacement, and its late response is discarded rather than
cached. This bounds Flask request waits without claiming that a stuck PyTango
call was killed. The browser also includes the entire HTTP/JSON round-trip
duration in its conservative source/bridge ages before showing measurements;
a delayed response cannot reset an already old image to fresh.

An unwired named-command admission module provides session/revision fencing
and at-most-once dispatch attempts against explicitly supplied local callbacks.
It is disabled by default and is not instantiated by GUI, HTTP, Tango or web.
Its bounded RAM ledger never evicts old IDs to make them executable again;
failed or indeterminate attempts are not automatically replayed. It neither
authenticates a transport nor qualifies a hardware command. All network
mutations remain unavailable and all web hardware controls remain disabled.

These changes prepare source and fake-test infrastructure. They do not deploy
the candidate, exercise a real Windows restart, prove absence of native orphans
after a crash, or close the remaining VI/sample-count/27-bank parity gaps.

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

The native-error and fractional-selector extension passed **3873 offline tests**,
no skips, 7300 existing warnings, in **164.26 s** on Python 3.12.14, including
the actual Python 3.4 cold-package process lane. The selected additions include
27 native wire-flow tests, 13 data-only dialog/caller tests, 17 differential
tests against the retained inert helper and two committed-evidence checks.
Fractional backend selection and runtime release-latch tests cover ctr0/1/7;
source-admitted negative task indices are rejected before callbacks. These
selections overlap the full gate and are not additive coverage totals.

The guarded actual Python 3.4.4 suite ran **563 tests: 562 passed, one skipped**,
in **7.627 s** with the extracted interpreter; a second existing 3.4 environment
repeated the result in **9.763 s**. The skipped modern-model comparison runs in
the Python 3.12 gate. External networking, real child processes and native
library loading are denied in the focused harness; no NI/VISA module remains
loaded. The package now contains **29 Python modules**, both new inspection
modules are fingerprinted, and every commissioning permission remains false.
After import/layout formatting, the affected modern selection repeated
**146 passed in 6.62 s**, including the actual Python 3.4 cold-package lane;
the focused Python 3.4 result above was repeated on that final source layout.

The separate read-only source validator passed against **13 pinned artifacts,
three archive members, 15 terminal types, 11 selector nets, 14 helper error nets,
four ordinary loop tunnels and 12 selector examples**. It also checked the
caller's sole wired handler slot9 and the inspected local-2020 saved mode1.
This external-source reproduction is not a clean-checkout test or XP acceptance
test. Independent review found no remaining blocker in this bounded transfer.
Full Ruff checks pass for the seven new Python files; the critical Ruff subset
and `git diff --check` pass for the entire change. Frozen catalog SHA256 remains
`A9D821E7519EA50F6B35593E58C78129EC7D8A7BFEDCC06098E247BEF011A0B0`.
No screen, lab endpoint, VI execution, hardware, deployment or lab process was
operated. The documented XP-library/native-side-effect gaps remain open.

The source counter-timing integration passed **3807 offline tests**, no skips,
7300 warnings, in **173.56 s** on Python 3.12.14 with the actual Python 3.4
cold-package process lane enabled. This includes 35 callback-executor tests,
14 backend/runtime integration tests, 17 fake low-level task tests and 21
source-model comparisons. The 4301 numeric fixtures are comparisons within a
test, not 4301 separately counted test cases. These suites overlap the complete
gate. Frozen catalogs and original helper/evidence identities are unchanged.

The focused actual Python 3.4.4 gate ran **518 tests: 517 passed, one skipped**,
in **9.303 s** with the extracted interpreter and repeated the result in
7.824 s in a second existing 3.4 environment. The skipped modern-source-model
comparison runs in the Python 3.12 gate. All counter-timing callback/integration
and fake property-write tests run on 3.4. Native-library loading, real child
processes and external networking are denied; low-level tests use only the
scoped enum fixture and fake task descriptors. No NI/VISA module remains loaded.

The cold candidate now contains **27 Python modules**; package/fingerprint
closure, byte changes in the new timing module, default-disabled permissions
and all three profiles are checked. Independent source/lifecycle review found
no remaining blocker after rejecting a queued timing request invalidated by
an in-flight read fault. That rejection preserves the original fault and any
prior stop requirement without invoking a timing callback. Critical Ruff and
`git diff --check` passed. No frontend source changed or lab software was
deployed/restarted. Local tests use fake loopback services and cold interpreter
processes; no device, VI, lab network endpoint or hardware state was operated.

The impulsion/HT-voltage/outer-stop integration passed **3729 offline tests**,
no skips, 7300 warnings, in **209.16 s** on Python 3.12.14, with the actual
Python 3.4 cold-package process lane enabled. A final 32-test control/contract
selection also passed after tightening oversized-integer validation. The
catalog SHA256 remains
`A9D821E7519EA50F6B35593E58C78129EC7D8A7BFEDCC06098E247BEF011A0B0`.

The expanded focused gate ran **464 tests on actual Python 3.4.4: 463 passed,
one skipped**, in **7.425 s** using the extracted interpreter; a second existing
3.4 environment repeated the result in 7.358 s. The skipped modern-source-model
cross-check runs in the Python 3.12 gate. Twelve low-level task tests use fake
tasks and a scoped six-enum fixture transcribed from reviewed SDK constants;
they do not import a vendor driver. Real child processes, external networking
and native-library loading are denied, and no NI/VISA module remains loaded.
These overlapping totals are not additive. That earlier candidate contained 26
Python modules with complete package/fingerprint closure; every new permission
is forced false. Critical Ruff checks, `git diff --check` and independent
source/lifecycle review passed. No frontend source changed or was rebuilt in
this batch. No XP deployment or hardware execution was performed.

The final cold-recovery/runtime-web integration on 20 October 2026 passed
**3617 offline tests**, no skips, 7300 warnings, in **231.94 s** on Python
3.12.14 with the actual Python 3.4 package/process lane enabled. The independent
fake-NI pipeline exercises real server snapshot construction, signed loopback
HTTP, the Everest reader and web projection, including removal of old inputs
after deinitialization. It does not contact the lab computers or a real Tango
device. This count supersedes the overlapping earlier Python totals below.

The focused gate `tools/test_acquisition_python34.py` passed **360 tests in
7.918 s on actual Python 3.4.4**. It blocks real child-process creation, external
connections and ctypes driver loading; tests inject fake NI/native processes,
and no NI/VISA driver module was loaded. This focused result overlaps the
offline gate rather than adding 360 independent tests. Package checks separately
start only a cold IDLE interpreter process, with native loading denied. The
earlier candidate contained 22 Python modules; the fingerprint and package source/data
closures agree, and catalog bytes remain unchanged.

The final frontend selection passed **11 suites / 200 tests in 38.412 s**.
The exact-source production bundle passed with
`CI=false GENERATE_SOURCEMAP=false`; pre-existing Hook warnings remain in
AndorSpectrographClient, CameraClient, DSNetioPDUClient, DSStandaMotorsClient and
DeviceControl, alongside bundle-size/Browserslist advisories. New runtime
frontend files passed ESLint. Critical Python syntax/undefined-name checks,
`git diff --check` and independent source/lifecycle review passed. These are
software gates, not XP deployment, Windows restart, hardware, or full-VI
acceptance tests.

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
