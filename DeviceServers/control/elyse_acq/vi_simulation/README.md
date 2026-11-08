# Acquisition VI controller translations

Five source-identified VI helpers are translated into Python controller logic
with supplied external returns. The code records configuration requests,
task-reference flow and error flow. It does not create NI tasks, start
counters, write voltages or access XP. These helpers cover task specifications
for cards 1 through 11, but not the complete Acquisition initialization
sequence or runtime.

The original NI6703 writer is also translated as a requested-voltage
projection and in-memory four-call recorder. Its source/caller proof is
documented in the [writer trace](../../../../docs/ELYSE_ACQ_NI6703_WRITER_TRACE_2026-10-02.md).

The [runtime/counter/focal proof](../../../../docs/ELYSE_ACQ_RUNTIME_IO_TRACE_2026-10-02.md)
adds the NI6071E reader, DIO96 exchange, NI6602 reconfiguration, root
readback copies, eight-call publication and both focal command helpers.
Missing returned data remain `UNSUPPLIED`, not invented safe input states.
These remain isolated functions, not a complete Acquisition lifecycle.

The [dormant NI6259 proof](../../../../docs/ELYSE_ACQ_NI6259_DORMANT_TRACE_2026-10-04.md)
adds `ni6259_dormant.py`: an isolated12-call initializer and a reader with
one Read plus zero to8 supplied Mean calls. Neither saved VI is a static
callee of the17 original members. They are not integrated into root
initialization, CLI deployment or live hardware paths. All six saved
diagrams now have bounded facets; that does not establish full behavior.
Public initializer error output remains unassigned, while reader errors
do not gate supplied data. Inactive calibration is separately qualified
against shared lvkit; the saved reader selector remains False.

## VI to Python mapping

| Original VI | Python file | Normal trace calls | Task output slots | Error contract |
|---|---|---:|---:|---|
| `1_ACQ_INIT_DIO96.vi` | `init_dio96.py` | 12 | 6 | Continuous public input to output |
| `1_ACQ_INIT_NI6071E.vi` | `init_ni6071e.py` | 137 | 2 | Public input ignored; public output unassigned; internal C1 error feeds C2 and Simple Error Handler |
| `1_ACQ_INIT_NI6220.vi` | `init_ni6220.py` | 20 | 1 | Public input ignored; final internal error assigned to public output |
| `1_ACQ_INIT_NI6602.vi` | `init_ni6602.py` | 54 | 8 | Continuous chain across eight frames; Start Task requested only for counters 0, 1, 2, 5, 6, 7 |
| `1_ACQ_INIT_NI6703.vi` | `init_ni6703.py` | 44 | 4 | Create Task errors discarded; channel inputs unwired; only C9 final channel error returned |
| `1_ACQ_WRITE_NI6703.vi` | `write_ni6703.py` | 4 | 0 | Continuous public chain C6 → C7 → C8 → C9; returned task/count outputs unused |
| `1_ACQ_READ_NI6071E.vi` | `read_ni6071e.py` | 2 | 0 | Independent C1/C2 reads; first error/warning merge; data projection not error-gated |
| `1_ACQ_RW_DIO96.vi` | `rw_dio96.py` | 6 | 0 | Read C3/C4/C5 then Write C3/C4/C5; continuous error chain |
| `1_ACQ_WRITE_NI6602.vi` | `write_ni6602.py` | Variable, at most 26 recorded calls | 0 | Poll ordinary tunnels; Done=True OR i>20; Stop → Clear → configure → Start |
| `0_ACQ_ELYSE.vi`, frame 1 | `runtime_publication.py` | 8 | 0 | Eight PSP boundary requests; final true error assigns stop and TCP ED True |
| `0_ACQ_ELYSE.vi`, frames 2–5 | `line_readback.py` | 0 | 0 | 58 exact field copies using separate frame snapshots |
| `1_Focales ON/OFF.vi` | `focal_helpers.py` | 18 each | 0 | Three independent reset/configure/output/close chains; F3/F2/F1 final merge |

The 267 calls and 21 task slots are trace counts, not hardware operations
or a business-logic coverage percentage. Each call carries the original
node UID and enclosing diagram UID; each result carries the original VI
SHA256. Source validators independently check the original wire graph,
connector mapping, task-cluster order and loop indexing. Source correspondence
tests compare Python arguments directly with connected saved literals.
See the [initializer source and screenshot evidence](../../../../docs/ELYSE_ACQ_INITIALIZER_ERROR_CONTRACTS_2026-10-01.md).
The additional writer has four abstract calls, 40 connected slopes and
ten C8 offsets. These do not change the initializer trace counts.

## External returns and errors

`ScriptedBoundary` accepts data fixtures only, not a hardware adapter or
callback. Its default fixture generates synthetic task tokens, passes a wired
error/task through, and supplies `NO_ERROR` for an unwired error input.
These are simulation assumptions; they do not emulate DAQmx internals.
An injected return overrides that assumption at one original node and loop
iteration. Recording a call does not imply that a driver would perform its
requested action or that the task would be valid.

`UNWIRED` distinguishes an absent input wire from a successful error cluster.
`UNASSIGNED` distinguishes NI6071E's unwritten public output from its internal
error. Supplying `public_error_out_seed` retains that explicit value; leaving
it unspecified does not invent a LabVIEW indicator default. Warning clusters
with `status=False` and nonzero code/source remain intact.

`UNSUPPLIED` distinguishes missing external data from returned empty arrays.
`SampleMatrix` permits immutable rectangular channel-by-sample numeric
fixtures; flat scalar tuples represent Boolean reads and counter Done
returns. Only the exact `ScriptedBoundary` class is accepted by recorders,
not an executable adapter or subclass. Missing poll data can leave an
incomplete trace; no exit is guessed before the saved iteration bound.

NI6071E and NI6220 channel loops repeatedly receive the same Create Task
returns through ordinary tunnels. NI6703 repeatedly receives the created
task but has unwired channel error inputs. These loops are not changed into
error or task shift registers. The last channel's task/error returns feed
the next stage, matching non-indexed output tunnels. Errors must not be
silently accumulated or converted into a generic initialization success flag.

Example fault fixture:

```python
from DeviceServers.control.elyse_acq.vi_simulation import (
    NO_ERROR, CallKey, ErrorCluster, ScriptedBoundary, initialize_ni6703,
)

boundary = ScriptedBoundary(errors={
    CallKey("1_ACQ_INIT_NI6703.vi", "847", 0):
        ErrorCluster(True, -123, "supplied first-channel error"),
})
result = initialize_ni6703(boundary, error_in=NO_ERROR)
boundary.assert_all_fixtures_used()
assert result.calls[1].returned.error.status is True
assert result.error_out == NO_ERROR  # Later unwired-input fixtures mask it.
```

This reproduces the controller's selection of supplied returns, not a fault
observed on equipment. A future safety redesign must be specified separately
from literal legacy translation.

## Offline entry point

Run from the repository using modern local Python; no package beyond the
standard library is required for this simulator. The code uses Python 3.10+
syntax and is not an XP/Python 3.4 deployment package.

```powershell
python -m DeviceServers.control.elyse_acq.vi_simulation ni6602
python -m DeviceServers.control.elyse_acq.vi_simulation ni6220 --rate-hz 8123.5 --samples 17
python -m DeviceServers.control.elyse_acq.vi_simulation ni6071e --rate-hz 8123.5 --samples 17 --trigger-c1 /1/PFI3 --trigger-c2 /2/PFI7
python -m unittest discover -s tests/device_servers/control -p 'test_elyse_acq_vi_initializers.py'
python -m unittest discover -s tests/scripts -p 'test_elyse_acq_vi_translation_source.py'
```

The rate/count/trigger values above are deliberately explicit example inputs,
not established root startup defaults. CLI prints JSON for one helper only;
it does not start the Acquisition lifecycle, a server or a transport.

Python-only guards reject nonfinite rates, noninteger/negative sample counts,
wrong fixture types, duplicate call keys and unused fixtures. Finite zero or
negative rates are forwarded unchanged; validation by a driver is represented
only by a supplied external return. These guards are not inferred legacy
behavior.

## AO writer simulation

```python
from DeviceServers.control.elyse_acq.vi_simulation import (
    NO_ERROR, LogicalAoBanks, ScriptedBoundary, TaskReference,
    record_ni6703_writes,
)

logical = LogicalAoBanks(tuple((0.0,) * 10 for _ in range(4)))
tasks = tuple(TaskReference("supplied-C%d" % c) for c in range(6, 10))
result = record_ni6703_writes(
    ScriptedBoundary(), logical, tasks=tasks, error_in=NO_ERROR,
)
assert len(result.calls) == 4
assert result.requested_voltages[2][3:5] == (2.1775, 3.8587)
```

The example's zero logical banks are not the established startup banks.
No physical output or HT permission follows from these computed values.
Writer arguments accept scalar data and immutable scalar tuples only, never
an adapter. Writer input shape/finiteness, overflow and real-acos domain checks
are Python-only guards. Malformed-array, NaN/Inf and domain-fault behavior
in LabVIEW is not modeled. Supplied true errors do not remove downstream
graph call sites; real DAQmx action/skip behavior remains a boundary concern.
The root input/error edges are checked at all three caller sites, but those
parent frames are not declared fully translated.

## Readback, publication, counter and focal simulations

`record_ni6071e_reads` requests two supplied task reads, channel means and
saved calibration. All 256 coefficients have direct source correspondence.
`record_dio96_exchange` requests six calls; neither returned read errors nor
the AO chain suppress the saved data-assignment wires.

`record_runtime_io` composes runtime frame-0 AI, DI/DO, AO and abstract
error-handler requests. Saved input cluster sizes are AI 64/64 and DI
56/64/56; command clusters are DO 40/32/40 and AO 10/10/10/10. Thirteen
external requests consume supplied returns only. Short-array legacy
padding remains unproved: `ReadbackCluster` retains the known prefix but
does not expose a fabricated complete cluster. Snapshot order is one
admissible schedule, not an atomic read of LabVIEW local variables.

`copy_readback_frame` requires explicit source and target snapshots for
one saved frame. Deviated targets 91/103 both receive C1[34]; this duplicate
is not corrected. Whole-cluster read/modify/write remains non-atomic with
respect to sibling writers.

`record_runtime_publication` records eight immutable data snapshots to URI
strings only. It returns literal stop/TCP assignments, not a loop exit,
successful PSP delivery or a bounded emergency response. Its False arm
does not clear previous stop flags.

`record_ni6602_reconfiguration` polls Done at most 22 times, then requests
Stop, Clear Errors, timing properties and Start. The independent 1-ms Wait
is represented in the source proof, not slept. Delay/width ×20 conversion
rounds nearest/ties-even in the supported finite U32 domain. External
faults/tasks do not feed the next poll; only last poll returns feed Stop.

`record_focal_commands` requires explicit F3/F2/F1 resource snapshots.
Both ON and OFF reset and request voltage/slew/current before Set Output.
No baud argument is inferred from the three unconnected 9600 literals.
One permitted branch schedule is recorded, while error-merge priority stays
F3/F2/F1. No guarantee of output disable follows from a recorded OFF call.

## Remaining transfer

`record_startup_command_publication` records seven initial command banks
and their ordered PSP requests followed by the error-handler boundary.
`record_startup_status_publication` uses the original pilot-read error,
not a cleared fallback result: `VDM-A[0] = NOT error.status`. It preserves
the other 79 fields and publishes DPS/EPS/VDM-A through a separate error
chain. The independent 100-ms Wait is metadata only. These are three
bounded source facets, not a complete initialization implementation.
See the [startup proof](../../../../docs/ELYSE_ACQ_STARTUP_PUBLICATION_TRACE_2026-10-02.md).

`record_initial_io` adds the independently checked startup frame 25990.
`record_postinit` records one permitted 25-call NI6220/COM1/COM2 schedule
and the ungated software resets/UI disabling of frame 33052. Missing serial
sessions remain unknown. `tpg300_startup.transition` projects one of five
outer initializer states from explicit local snapshots and external returns;
it contains no serial protocol. See the
[startup integration proof](../../../../docs/ELYSE_ACQ_STARTUP_IO_TPG_TRACE_2026-10-02.md).

`tpg300_retry.retry_postprocess` projects the outer retry predicate and
error.status replacement from supplied phase-two flags. Retry=3 permits
four returning attempts; it does not bound latency or reconstruct the
inner ACK/NAK/ENQ protocol or suppress-warning helper.

`tpg300_protocol.byte_loop_step` now projects both polling-loop bodies from
explicit bytes, buffer/offset, elapsed-time and error snapshots. The fresh-byte
arms bypass the nominal timeout; the no-data arms use elapsed<timeout and
record a requested 50-ms wait. ACK uses the after substring, while response
collects bytes before CR. `tpg300_warning.suppress_warning` clears the whole
cluster only for code `0x3FFF0006`, independent of incoming status. These
remain pure projections, not a serial driver or complete initializer.
See the [protocol proof](../../../../docs/ELYSE_ACQ_TPG_PROTOCOL_TRACE_2026-10-02.md).

`tpg300_pressure` projects the saved period-to-comma loop, first-comma
split and the three caller assignments from explicitly supplied numeric
returns. It does not substitute Python `float()` for LabVIEW's localized
conversion. Sensor Status is discarded at those callers; a returned error
feeds its handler independently of the pressure assignment. The VAM-A
publication fault projection returns stop-bank assignments without sending
a publication or resetting stops on success. See the
[pressure trace](../../../../docs/ELYSE_ACQ_PRESSURE_READ_TRACE_2026-10-02.md).

`vam_status` adds all field copies of the first two VAM-A sequence frames:
the second frame preserves the preceding frame's pressure fields. Both
writers are ordered in the same loop, not racing independent writers.
Loop counter, 80-ms requested Wait and independently supplied stop snapshot
remain distinct from pressure quality and publication error. Direct cluster
fixtures are full-sized; short arrays require explicitly supplied conversions,
not silent padding. The two WCM conversions are supplied independently through
`second_frame_from_conversions`, without an atomic multi-bank sampling claim.

`ni6220_runtime` adds the relative WCM comparison, explicit counter cases,
six statistical-call arguments and independent stop/error snapshots.
NI Mean, Mean PtByPt and Increment returns remain supplied boundaries.
Bank59 contains six means; `vam_status.first_frame_from_conversion` requires
an explicit eight-element conversion return for the downstream cluster.
Missing True-counter default dispatch is marked unresolved. See the
[NI6220 runtime proof](../../../../docs/ELYSE_ACQ_NI6220_RUNTIME_TRACE_2026-10-03.md).

The subsequent typed-default proof closes the three 1D DBL Index Array
boundaries: missing reader entries and display indices outside0..5 yield
0.0. Supplied reader snapshots may now be empty/short without truncating
the four-entry WCM array or removing the six Mean calls. Their statistical
returns remain supplied; driver failure data and Array To Cluster padding
are not inferred. The shared-lvkit expanded-row correction agrees with
65734 fixture sets and does not change the hardware adapter.

`saved_measurement_data.saved_source_measurement_snapshot()` makes four empty
persisted measurement arrays and three zero scalars explicit, without applying
them automatically at startup/restart. `counter_frame` now accepts variable-length
prior WCM arrays: source-empty memory is not four invented DBL zeros. Native
Mean(empty), point-mean history and short cluster padding remain supplied
boundaries. The [saved measurement proof](../../../../docs/ELYSE_ACQ_SAVED_MEASUREMENT_STATE_2026-10-04.md)
checks seven control/data associations,26 original bytes and all21 root gRefs.

`timeout_reads` projects all twelve command/status reader arguments and
whole-cluster assignments in the first Timeout frame. The final returned
read error assigns False to stop/TCP ED, unlike publication errors.
Supplied data/errors are preserved; no transport or hold-last-value policy
is invented. See the
[Timeout receiving-frame proof](../../../../docs/ELYSE_ACQ_TIMEOUT_COMMAND_READ_TRACE_2026-10-03.md).

`timeout_setpoint_display` copies all20 commands into nested Consigne
fields of the direct/deviated device display banks, preserving their other
fields. It uses independently supplied source-bank snapshots and does not
turn displayed intent into measured voltage or permission. The source
proof resolves nested container/leaf indices explicitly.

`timeout_dispatch` projects the full29-bit DPS search, all24 property targets,
including the unregistered magnet-PT target, and bounded integer NI6602 caller
arguments. Counter reset/publication use separate snapshots and are not gated
by the returned helper error after frame completion. Numeric unmatched cases
and fractional index coercion stay explicitly unresolved. No event queue or
transport is connected. See the
[dispatch proof](../../../../docs/ELYSE_ACQ_TIMEOUT_DISPATCH_TRACE_2026-10-03.md).

`timeout_cooling` adds the raw guard and all seven trip frames, preserving
independent local snapshots, status fields and requested wait arguments.
Enabled-arm state must be supplied: the original XML lacks explicit active/
default arm fields, while the historical native screenshot is not a current
source-hash match. No actual pulse width or general-stop guarantee is inferred.

`stop_schedule` replays explicit single-iteration stop-local schedules from
the three verified error arms. It keeps both same-constant writes independent,
condition snapshots distinct from body completion and the five-loop join
ahead of outer TCP selection. It does not infer errors or complete calls,
measure latency, implement another iteration or actuate an emergency stop.
See the [stop trace](../../../../docs/ELYSE_ACQ_STOP_TCP_ERROR_TRACE_2026-09-29.md).

`stop_lifecycle` extends those supplied tokens across explicitly requested
iterations. An exited loop cannot restart when a sibling clears shared stop;
outer TCP selection still requires the five-loop join. All720 permutations
of six entered fault-arm writes preserve four distinct final flag pairs,
not a probability distribution or all whole-program interleavings. Three
completed-frame reset projections retain unknown starting values explicitly:
initialization writes45=False/46=False, controlled completion46=True/47=False,
cleanup30=False. The separate source proof checks all20 stop-bank gRefs and
11 literal writers. It does not infer loaded defaults, indirect/UI writers,
external-call completion, fairness, physical safe outputs or native restart.

`saved_stop_data.saved_source_stop_snapshot()` supplies the four independently
checked persisted False values for banks 30/45/46/47. This is an explicitly
selected source fixture, not a live read or an implicit initializer/reset.
Applying post-init writes to stale True memory still leaves banks 30/47 True.
The [saved-data proof](../../../../docs/ELYSE_ACQ_SAVED_STOP_DATA_2026-10-04.md)
checks 69 original DCO rows, their data links and the four control identities;
loaded controls and native restart remain separate unresolved boundaries.

The [HT ownership proof](../../../../docs/ELYSE_ACQ_HT_COMMAND_OWNERSHIP_2026-10-04.md)
joins all thirteen C9 gRefs to initialization, command reception, I/O sampling
and outer shutdown. Business-level tests compose these existing projections:
startup6.5 requests3.25V; supplied12.7 requests6.35V; a returning outer ramp
reaches command<6.6, not zero. The ordinary runtime PSP receiver cannot overlap
that later ramp after the five-loop join. Indirect/UI writes and native
completion remain unqualified. No new gate, clamp, scheduler or adapter exists.

The stop-request integration tests compose dispatch/NewVal/procedure facets
with explicitly supplied event delivery. DPS3 selects normal-stop event6,
not program stop30. Its17 frames and Focales OFF description remain distinct
from outer controlled shutdown. Lower asserted DPS fields can be selected
first, and a fresh publication payload need not equal an earlier local reset.
No event queue, remote acknowledgment or guaranteed completion is added.

`event_envelope` transcribes all23 supplied Boolean procedure-event entry
gates, including the magnet-zero NewVal wrapper missed by an older native
view. False arms are empty. The special event25 registration high bit is
retained without an invented locking/delivery interpretation. Entry is not
hardware permission. The separate `procedure_sequences` proof covers the
nested command-procedure graphs, not event delivery or hardware completion. See the
[envelope proof](../../../../docs/ELYSE_ACQ_EVENT_ENVELOPES_2026-10-03.md).

`procedure_sequences` records all23 ordered command paths and166 sequence/
focal-cell frames. Same-frame effects remain unordered; each projection
requires explicit local-read snapshots. Four conditioning ramps preserve
initialized DBL recurrence and retained C7 fields. Two pulse-stop predicates
retain Done OR i>40 without querying a task. Focal, counter and PSP requests
are returned as descriptions; no callback, sleep, adapter or network access
is performed. The caller/error graphs are checked against172 original
diagram identities and694 nets. See the
[procedure proof](../../../../docs/ELYSE_ACQ_PROCEDURE_SEQUENCES_2026-10-03.md).

`initialization_caller` projects frame227 and the AI-test error suffix using
explicit initializer and Clear Errors/Clear Task returned fixtures. All81
initializer-arm/clear-return status combinations preserve ordered error
dependencies and ungated task-bank assignments. Original pilot-read error
is retained even if the fallback error is cleared. No default success,
task validity or NI6071E public-error seed is invented. The test-read count
port is unwired; its default remains a separate proof obligation.

`psp_discovery` records explicit enumerated/property/open references and
returned errors. Auto-indexed supplied cardinality drives the trace, even
when returned errors have statusTrue. Returned type variants remain opaque
tokens; no successful-open filter or expected-name whitelist is added.
The final error is retained for inspection but has no saved exterior
consumer. Neither these tokens nor the trace can contact PSP.
Its separate named-open sibling trace requires explicit branch selection
and24 error fixtures. All bank anchors are reads feeding type terminals,
not publication data or local writes. Returned references/access and final
handler outputs are unused; native activation is not inferred from saved
selector fields.

`beamline_commands` projects event1/event2 frames1..3, not their frame0
difference detection, UI properties or adjustment cases. An explicit supplied
Boolean selects the emptyFalse or Consigne-copy arm. All20 copies retain
untargeted command fields. Publication uses fresh snapshots of C6 through C9
after either arm; four independent error handlers are not replaced by the
single chained topology used by other procedures. The100ms final Wait is a
request after the publication frame completes, not a physical settling
guarantee. Shared-lvkit pure cluster fragments agree with these mappings on
520 fixture sets; no generated whole VI, transport or adapter is executed.
See the [beam-line tail proof](../../../../docs/ELYSE_ACQ_BEAMLINE_COMMANDS_2026-10-03.md).

`beamline_adjustment` adds the separate event1/event2 frame0 projection.
Elementwise differences become masked field bits, followed by maximum-mask
selection and its first device index. The >=128 gate is not an interlock.
All24 scalar step/coercion chains and80 device/button rules are independently
checked against original XML. A separate current Value-read fixture supplies
the adjusted cell; four button fields reset after a requested70ms wait.
Combined outer masks remain explicitly refused pending independent native
default evidence; property failure returns and nonfinite values are outside
the fixture domain. Shared-lvkit scalar fragments match9600 finite fixtures.
No UI operation, sleep, network or hardware access is performed. See the
[adjustment proof](../../../../docs/ELYSE_ACQ_BEAMLINE_ADJUSTMENT_2026-10-03.md).

`controlled_stop` retains the complete seven-phase outer stop separately
from event6. HT uses a strict command<6.6 exit and separate check/bundle
snapshots; the two counter polls retain Done OR i>40. All staged AO/DO/status
writes, parent-tunnel waits and duplicate status frames have source proofs.
`record_stop_io` records the sibling AI-DIO-AO caller during shutdown and
mirrors C2/local20 field7 into scalar49. Explicit local46 snapshots are not
replaced by I/O error status. No sleep, hardware adapter or transport runs.
The proof adds57 root diagrams/204 nets; current shared lvkit matches826
pure scalar fixtures. See the
[controlled-stop proof](../../../../docs/ELYSE_ACQ_CONTROLLED_STOP_2026-10-04.md).

`outer_stop_schedule` requires a completed five-loop runtime trace and
captures General47 separately from each outer-loop Emergency46 read.
Entered True arms cannot be canceled by a later condition; both final flag
writes and all supplied body work must return before their owner can exit.
All24 local write/read orders retain four possible captured condition pairs.
TCP=False bypass and General=False/Emergency=True exit do not invent a
controlled sequence. A True condition still cannot complete a blocked call.

`final_cleanup` requires outer-join completion and explicit cleanup entry.
Its supplied schedule retains27 fixed PSP tag-close nodes, two independent
TPG-close branches, three unwired-mode handlers and the independent local30
reset. The uninitialized PSP error-register seed is explicit; handler output
does not reset it. No task deinitialization, voltage-zeroing, transport,
timer or hardware adapter exists here. See the
[fault and cleanup proof](../../../../docs/ELYSE_ACQ_FAULT_STOP_CLEANUP_2026-10-04.md).

All475 original main-VI diagrams and all533 original member diagram
identities now have named bounded source facets, not full behavioral/native
closure. The six NI6259 diagrams are translated as dormant helper facets,
not added to the reachable root call graph. Original numeric defaults,
Diagram Disable activation, native failures, complete concurrency and
native restart remain open.

`startup_integration` composes returning initializer/pilot/discovery fixtures
with command publication, initial I/O, post-init and status publication.
Task banks23/24 use replacement references when the pilot fallback assigns
them. The three error lanes remain distinct: final VDM-A[0] uses original
pilot error.status, not cleared fallback or aggregate startup success.
All49 suffix call sites remain descriptions, even with supplied faults.
Independent resets retain Stop30/General47 and are not readiness evidence.
The prefix is not executed; selected empty disable arm, returning handlers,
one allowed independent-branch order and no intervening local mutation are
explicit fixture conditions. See the
[startup error routing proof](../../../../docs/ELYSE_ACQ_STARTUP_ERROR_LANES_2026-10-04.md).

`saved_ni6071e_data` adds nine independently source-qualified persisted
parameters: the reader stores1000 samples, whereas its initializer stores
10 samples at5000Hz and the two PFI trigger strings. Saved error indicators
are False/0/empty; neither native loading nor the unwritten initializer
public-error return is inferred. `record_pilot_test` explicitly opts into
the saved reader count, preserves supplied initializer/read errors and
projects the existing fallback without executing task clear/reinitialization.
Pilot data gains no root readback assignment. A subsequent first-I/O phase
uses a separate inert recorder for repeated helper call sites. See the
[saved inputs and pilot composition proof](../../../../docs/ELYSE_ACQ_NI6071E_SAVED_INPUTS_2026-10-04.md).

Remaining native parent startup behavior and initialization integration, custom
external VISA behavior and CHROMA integration arguments, complete
short-array runtime defaults, complete concurrent publication/event/I/O
fault schedules, native cleanup returns and restart
remain separate modules or closure gates. Existing bounded stop/status/DPS
projections are not replaced or connected to these helpers. Neither the
Tango facade nor the adapter-capable procedure engine imports this package.
Supervision is not declared complete; its remaining gates follow Acquisition
closure in the [review matrix](../../../../docs/ELYSE_ACQ_CLOSURE_MATRIX_2026-10-01.md).
Physical output commissioning is separate from the closed software conversion
facet; it is not required to understand the controller's saved arithmetic.
