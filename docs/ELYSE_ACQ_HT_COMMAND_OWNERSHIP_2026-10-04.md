# Acquisition HT command ownership and phase separation

## Business question and result

Which Acquisition paths create, replace and reduce the HT setpoint, and can
ordinary Supervision reception oppose the outer shutdown ramp? The original
root VI contains thirteen C9 local references and exactly three direct local
writers: initialization, runtime PSP reception, and the later stop ramp.
The receiver and ramp belong to different stacked lifecycle phases. After
the five runtime loops have joined, that receiver cannot resume or compete
with the outer ramp in the same VI invocation.

The command is not a measurement or permission. Initial C9[0]=6.5 requests
3.25 V through the saved conversion; a supplied 12.7 requests 6.35 V.
The shutdown ramp reduces the logical command until it is strictly below
6.6; it does not zero the command or wait for measured HT to reach that
threshold. These are saved controller contracts, not apparatus operations.

## Source and complete local ownership

Original root VI SHA256:
`6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF`.
Original LLB SHA256:
`EB7C08800823D025F1B4F9E8EEA89ED9878F0CF00A02427871583B99989B2F8A`.
The validator uses the unchanged pinned original BDHb/FPHb/type exports,
not a generated Python program or an uninspected loaded VI.

C9 is local bank 12, a ten-DBL cluster named `C9NI6703`. Its field 0 is
`00 OUT00 b01 Cmd alimentation HT`. Every reference below has independently
checked bank index, read/write flags, terminal, heap descriptor, containing
diagram and complete direct wire. Equivalent type labels at other local
indices are rejected. Similar `paramIdx=12` values on subVI connector ports
are not misclassified as C9 local memory.

| Local UID | Direct diagram | Direction | Business role |
|---|---|---|---|
| 1074 | 76558 | Read | Named PSP-open type anchor; activation remains separately qualified |
| 16414 | 14803 | Write | Entire initialization C9 literal, field 0=6.5 |
| 25050 | 24611 | Read | Initial C9 publication to Supervision |
| 19627 | 25990 | Read | Initial I/O command snapshot |
| 2494 | 7386 | Read | Normal runtime I/O command snapshot |
| 10472 | 10115 | Write | Entire supplied C9 PSP return |
| 10410 | 10115 | Read | C9 PSP reader default-data argument |
| 14748 | 14553 | Read | Direct-line event publication of C9 |
| 65137 | 64942 | Read | Deviated-line event publication of C9 |
| 55766 | 41713 | Read | Outer-stop sibling I/O snapshot |
| 11041 | 47573 | Write | Ramp read-modify-write, replacing field 0 only |
| 9781 | 47573 | Read | Ramp's separate whole-C9 bundle base |
| 538 | 42212 | Read | Ramp's comparison/subtraction value |

The source front-panel C9 identity is fPDCO 7032, DDO 6921, heap type 970.
No directly attached property node targets that display or any of its saved
descendants. This rules out that specific property-node mechanism in the
saved diagram. It does not rule out manual control edits, dynamically supplied
VI Server references or another invocation. All such actors remain outside
this direct local-reference proof.

## Reception to requested output

Timeout frame 10115 reads C9 from
`ni.var.psp://10.20.30.2/SUPERVISION/C9NI6703` at reader 10449. Its data
terminal 10466 directly feeds local writer terminal 10475. The current C9
snapshot at terminal 10413 feeds default-data terminal 10463. No caller Case
gates that data assignment on returned error status or EPS permission.
The reader's actual failure/default behavior remains a supplied boundary;
the simulator does not substitute zero or hold-last-value without evidence.

The separate I/O frame 7386 reads local C9 at 2494, converts it through
Cluster To Array 7611 and passes it to NI6703 writer call 278. The helper's
active C9 slope array is `(0.5, 0.25, 1, 1, 1, 1, 1, 1, 1, 1)`.
Its final Write site 1200 receives the converted C9 array and the fourth
task token. The saved request has autoStart=True and timeout=20.0 s.
No physical write success follows from visiting that call site.

The [receiving-frame proof](ELYSE_ACQ_TIMEOUT_COMMAND_READ_TRACE_2026-10-03.md)
and [NI6703 conversion proof](ELYSE_ACQ_NI6703_WRITER_TRACE_2026-10-02.md)
already qualify the full direct graphs and error dependencies at these
boundaries. The new ownership census connects them into one command path.
They do not supply an atomic handoff: an independently sampled I/O bank can
still contain the prior 6.5 command rather than a newly received 12.7.
The business tests retain both explicitly supplied read schedules.

## Command conditions versus supply state

The following are bounded negative results of the checked wiring, not claims
that hardware protection is absent:

- Changing the supplied EPS cluster alone does not suppress the C9 copy or
  its numeric conversion in this path.
- A supplied C9 reader error does not add a caller data-write gate. The final
  reader error, not C9's error alone, controls the separate stop/TCP flag
  assignments. If that final error is True, the legacy frame assigns False
  to banks 30/45 without clearing C9.
- A conditionally entered seven-frame cooling trip does not write C9. Its
  EPS cooling-status changes do not zero a previously supplied HT setpoint.
  Enabled-arm activation and physical input polarity remain explicit gaps.
- Events 20/21/22 start, stop and reset the HT supply through C4 Boolean
  command fields. Event 6 stops the normal modulator sequence. None of those
  saved procedures is another direct C9 writer. Switching a supply command
  is not equivalent to zeroing its analog setpoint.

Supervision gates and hardwired protection are not inferred from these
Acquisition-only results. The permission to energize equipment remains
separate from successful software assignment and command-status literals.

## Why ordinary reception cannot oppose the outer ramp

Root sequence 359 has exactly five saved frames in this order:
135, 188, 367, 41058 and 246. Frame 367 contains the five runtime loops
47483, 59483, 20601, 203 and 102. C9 receiver writer 10472 belongs to
dispatcher loop 102 in that frame. The outer controlled-stop ramp writer
11041 belongs to the following frame 41058.

Therefore the same invocation cannot execute its normal receiving frame
and its outer ramp concurrently. The stacked frame cannot advance until
all five runtime loops have finished, including any in-flight handler work.
The [existing stop-lifecycle replay](ELYSE_ACQ_STOP_TCP_ERROR_TRACE_2026-09-29.md)
retains exited loops as absorbing and rejects outer entry before the join.
This removes the ordinary PSP receiver from the ramp's competing-writer
hypothesis; indirect/UI actors, new invocations and external completion
remain separate questions.

Entry and sequence request also have different guards. At the outer frame,
`TCP ED=False` skips the controlled-stop branch; True enters the stop I/O
and operator loops. Within the latter, `Arrêt général=True` requests the
seven-phase sequence. With an explicitly False general-stop snapshot, even
a returning publication-fault trace that reaches the five-loop join does
not itself request the ramp. The independently sampled `stop urgence`
Boolean supplies loop termination, not an asynchronous cancellation wire
inside an already entered ramp/sequence. This is why a fault flag, general
stop request and emergency-label control must not be collapsed into one
Python stop action. Native UI/VI Server origins of those sampled controls
and physical emergency response are not inferred here.

During the ramp, the sibling I/O loop 41705 reads C9 but does not write it.
Each ramp iteration compares one C9[0] snapshot to 6.6. If not below that
value, it writes `checked_command - 0.1` into a separately read C9 base and
requests Wait=500 ms. Other nine fields come from that base. Once below
6.6, it exits without another C9 write. This is not a measured-voltage
feedback loop: the measured C2[7] readback is displayed separately.

In the returning no-indirect-change Python fixture, input 12.7 requires
62 subtractions and exits at approximately 6.5. Binary64 roundoff retains
the strict comparison near 6.6; the fixture is not a general iteration or
time bound. The remaining approximately 3.25-V analog request is distinct
from the subsequent Boolean HT-supply stop pulse. Actual deenergization,
external call latency, task lifetime and failure interruption are not proved
by this finite replay.

## Python acceptance checks and remaining coverage

[validate_acq_ht_command_ownership.py](../tools/validate_acq_ht_command_ownership.py)
pins the complete thirteen-reference census and lifecycle phase separation.
Source mutations exercise bank/direction/type/terminal identity, all direct
wire peers/owner diagrams, additional writers/aliases/properties, the HT field
label and front-panel identity, each lifecycle frame, joined-loop membership
and receiver relocation into the stop phase.

[Business-level tests](../tests/device_servers/control/test_elyse_acq_vi_ht_command_path.py)
compose existing in-memory initialization, PSP-return, runtime I/O, cooling,
procedure and stop projections. The thirteen tests cover the numeric examples,
independent sampling, returned read/write faults, EPS variations, all seven
conditional cooling frames, distinct HT supply commands, five-loop join,
separate stop-entry/operator guards and a finite returning ramp. No controller
behavior is silently repaired and no adapter, transport, clock, scheduler or
apparatus operation is introduced.

```powershell
$env:PYTHONPATH='C:\dev\ELYSE-ACQ-analysis\converter\lvkit\src;C:\dev\ELYSE-ACQ-analysis\converter\test-deps;C:\dev\pyconlyse\tools;C:\dev\pyconlyse'
& 'C:\dev\pyconlyse\Supervision\analysis\lvkit_eval\.venv\Scripts\python.exe' tools/validate_acq_ht_command_ownership.py
& 'C:\dev\pyconlyse\Supervision\analysis\lvkit_eval\.venv\Scripts\python.exe' -m pytest -q -x -o addopts= --deny-network tests/scripts/test_elyse_acq_ht_command_ownership.py tests/device_servers/control/test_elyse_acq_vi_ht_command_path.py
```

The final focused lane passed 24 tests and 100 subtests in 7.15 s, with external
network access denied and one assertion-rewriting warning. The six-file source
regression covering ownership, NI6703 conversion/callers, startup publication,
runtime I/O, command reads and controlled-stop/lifecycle graphs passed
55 tests and 204 subtests in 424.47 s, also with network denied and one
warning. All isolated VI-model/register tests passed 357 tests and 1826
subtests in 6.95 s with the same guard and warning. Four new/affected Python
files pass Ruff lint/format checks. All 17 original member hashes and the
LLB hash remain unchanged. No source-matched native
screenshot or Word revision was added. All original source bytes remain
unmodified; lvkit was not changed for this business-logic continuation. Its
verified shared-source fingerprint remains
`AF6B25B199C17DF8B0DB729965A727D66498083CE7FB72CA20EA51554E0C3BFB`.

This closes a named command-ownership and phase-separation contract, not
whole Acquisition behavior. Indirect control writes, native default/disabled
arm semantics, full external failure/restart contracts and all event/I/O
interleavings remain open. Further coverage must continue from those VI
branches rather than count converter tests as controller completeness.
