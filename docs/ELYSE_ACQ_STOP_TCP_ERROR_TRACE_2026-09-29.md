# Acquisition `stop` / `TCP ED` control trace (2026-09-29)

## Question and boundary

This trace asks which saved LabVIEW paths terminate the five concurrent Acquisition loops and what the separate `TCP ED` flag selects afterward. It uses the offline root VI from `ACQUISITION.llb` (source SHA-256 `EB7C08800823D025F1B4F9E8EEA89ED9878F0CF00A02427871583B99989B2F8A`), raw BDHb wires, and the native screenshots `EV-ACQ-0018-timeout0-command-psp-reads.png` and `EV-ACQ-0013-outer3-emergency-stop-overview.png`. Current deployment equality and live behavior are unverified. No hardware command was issued.

## Local identities and loop polarity

The manually checked local-reference identities are `paramIdx=30` → front-panel `stop`, `paramIdx=45` → `TCP ED`, and `paramIdx=47` → `Arrêt général`. The first is supported by literals labelled `stop` and by its fanout to all five runtime While-loop conditional terminals. The others are displayed on the two native Case selectors. This mapping does **not** assume `paramIdx` equals FPHb control order, which is false for many references.

Runtime While loops `47483`, `59483`, `20601`, `203`, and `102` each read local `stop` at their loop-test terminal. All five raw `lTst` DCOs have `objFlags=65537`, the LabVIEW Stop-if-True polarity; thus `stop=True` requests termination of each loop on its next condition evaluation. The front-panel `stop` control also exists and can change this value externally; these diagram-local writers are not the whole set of possible runtime causes.

| Saved path | Wire-level assignment |
|---|---|
| Initialization, outer frame 1, inner frame 5/3 | `TCP ED=False`; this frame also initializes EPS/DPS and vacuum inputs. |
| Runtime loop `20601`, `AMA-A` PSP-write `Erreur` arm (`select 28682[1]`) | Same `True` constant drives `stop=True` and `TCP ED=True`. |
| Runtime loop `203`, main PSP-write `Erreur` arm (`select 40346[1]`) | Same `True` constant drives `stop=True` and `TCP ED=True`. |
| Runtime dispatcher loop `102`, `Timeout` PSP-read `Erreur` arm (`select 40205[1]`) | Same `False` constant drives `stop=False` and `TCP ED=False`; native screenshot confirms the `F` literal. |
| Cleanup, outer frame 4 | `stop=False`. |

Outer frame 3's Case `43488` reads `TCP ED`: its `False` arm is empty, while its `True` arm contains two While loops (`41705` and `42592`). Both loop tests read `stop urgence` (local `paramIdx=46`) and have Stop-if-True polarity (`lTst objFlags=65537`). Within loop `42592`, Case `52981` reads `Arrêt général`; its `True` arm contains the staged stop sequence. At that sequence's final frame, the saved diagram assigns `Arrêt général=False` and `stop urgence=True` and performs a 1000-ms wait. These independent same-frame nodes do not enforce a wait-before-flag order. These are control-flow facts, not a claim that every device has safely stopped.

## Consequence and unresolved asymmetry

The [hash-pinned raw-wire validator](../tools/validate_acq_stop_ingress.py)
checks all `paramIdx=30/45/46/47` root-local references, the two
PSP-write and one PSP-read Case selectors, their actual source-node
classes and Boolean literals, and all five runtime While stop terminals.
The pure `project_acq_psp_error_stop_assignment` helper records the
contrasting assignments for offline tests only; it neither reads PSP
nor changes any running stop flag.

The two PSP-**write** error paths directly request termination of all five runtime loops and select outer-frame-3 `TCP ED=True` logic. The inspected PSP-**read** error path does the opposite: it writes `False` to both locals. Therefore **that assignment alone cannot stop a Stop-if-True loop or select outer-frame-3's True arm**. This is a real asymmetry in the saved code, not a proven hang or unsafe physical state: other simultaneous loop/UI events might subsequently set `stop=True`, error handling may have effects outside these two assignments, and the deployed VI may differ.

A further raw-local census bounds the frame-3 exit path. `Arrêt général`
(`paramIdx=47`) has two root local references: the Case-selector read and a
`False` reset in the last stop-sequence frame; the root diagram contains no
local `True` assignment to that control. `stop urgence` (`paramIdx=46`) has
four references: initialization, the two loop-test reads, and the final
stop-sequence `True` assignment. With `TCP ED=True` but `Arrêt général=False`
and no separate front-panel input, Case `52981` takes its `False` arm, which
re-enables five UI controls, while the two frame-3 loops still read
`stop urgence=False`. In that state the saved graph has no automatic
in-diagram exit from those loops; the upper loop continues NI6071E/DIO96/AO
exchange. A user may change the front-panel controls, and hidden external
effects or a different deployed source remain possible. This is a
**conditional liveness concern**, not proof of a physical failure or an
unbounded real-time wait.

Before complete Python parity can be specified, retain the PSP read-error
source/returned-data boundary, all outer-frame-3 loop exits/outputs and the
manual-stop event path. The [complete read-frame proof](ELYSE_ACQ_TIMEOUT_COMMAND_READ_TRACE_2026-10-03.md)
now covers the twelve caller reads, default-data inputs, error dependency
chain and final False assignment, but does not invent NI recovery semantics.
Do not silently “correct” this asymmetry; faithful emulation and an approved
safety redesign are separate outcomes.

## Supplied stop-local schedules, 2026-10-03

The [inert replay model](../DeviceServers/control/elyse_acq/vi_simulation/stop_schedule.py)
integrates the already verified two publication-error True pairs and
Timeout-read-error False pair with all five loop stop snapshots. A same
constant feeds two independent local writes; the pair is not an atomic
transaction. Stop-local reads are independent body nodes, not a wired
read-after-error operation. The loop condition can therefore consume a
snapshot captured before a subsequent assignment, after its other body
work completes. A laterFalse write does not retroactively change an earlier
True condition snapshot.

Every error-arm entry and body completion is a supplied fixture token.
Replay requires both writes of an entered arm to complete before that
arm's owner body completes. Outer TCP selection is permitted only after
all five runtime loop bodies have completed with True condition snapshots.
No next iteration, call completion, scheduler fairness or latency is assumed.

Seven golden tests retain the following bounded partial-order outcomes:

| Supplied ordering | Result |
|---|---|
|All five conditions readFalse; publication writesTrue; Timeout writesFalse; bodies complete|All five conditions remainFalse; the fixture does not exit runtime|
|One condition readsTrue between publication and Timeout writes|That loop's completed condition remainsTrue although stop is nowFalse|
|All five conditions readTrue; Timeout subsequently clears stop/TCP; all bodies complete|All five can exit this fixture, but the outer TCP snapshot isFalse|
|Publication writes stopTrue before its TCP write|Transient local stopTrue/TCPFalse; assignment pair is non-atomic|

These are permitted by the checked data dependencies and supplied
completions, not observations of the deployed scheduler or claims of a
physical failure. The last complete-runtime fixture selects outerCase43488
False, not its staged True stop arm. This makes the fault-selection race
explicit without implementing any apparatus stop or changing saved logic.

## Repeated runtime faults and reset ownership, 2026-10-04

The [completed-frame memory validator](../tools/validate_acq_stop_state_memory.py)
checks all20 root gRef sites for banks30/45/46/47, all11 literal Boolean
writers, their bank/port/diagram bindings, and all five runtime condition
wires. The initializer's two writes are local45=False and local46=False;
it has no root gRef reset of local30 or local47. The final controlled-stop
frame writes local46=True and local47=False. Final cleanup writes only
local30=False among these four banks. This population does not exclude
primary terminals, UI input, properties or indirect external writers, and
does not establish loaded initial values.

The [repeated-runtime projection](../DeviceServers/control/elyse_acq/vi_simulation/stop_lifecycle.py)
extends the single-iteration fixture without introducing a scheduler. A
completed False condition permits an explicitly supplied next iteration;
a completed True condition permanently exits that loop for this runtime
frame. Later shared stop=False does not resurrect an exited loop. Each
entered fault arm's two independent writes must complete before its owner
body completes. A captured stop value remains distinct from the current
shared value. Outer TCP selection requires all five loops to have exited.
Every body completion, next iteration and external stop change is a
fixture assertion, not a driver result or an observed UI operation.

An exhaustive bounded test enumerates all720 permutations of the six
independent local writes from three already-entered error arms, followed
by five stop reads and five completed bodies:

| Final stop | Final TCP ED | Write orders | Runtime-frame consequence in this fixture |
|---|---|---|---|
|True|True|320|All five exit; outer TCP selects the controlled-stop arm|
|True|False|160|All five exit; outer TCP skips the controlled-stop arm|
|False|True|160|All five continue; outer TCP read is not yet reachable|
|False|False|80|All five continue; outer TCP read is not yet reachable|

These are counts of permitted orderings, not probabilities or an enumeration
of all whole-program schedules. Condition reads between writes introduce
additional mixed-exit outcomes. One discriminating fixture lets four loops
capture True and exit, while dispatcher102 captures False after its read
fault. That dispatcher then completes32 explicitly supplied further
read-fault iterations with False conditions. The runtime-frame join remains
unreachable throughout this finite trace. A later supplied stop=True can
exit the remaining loop, but does not set TCP ED=True: outer TCP then skips
the controlled-stop arm. This demonstrates a conditional partial-shutdown
path in the saved controller dependencies, not a measured hang or a claim
about physical outputs.

Completed-frame flag ownership is separately tested for all16 supplied
four-Boolean input states at each of three stages, giving48 postconditions:

| Completed stage | Saved gRef assignments | Other supplied flag snapshots retained by this projection |
|---|---|---|
|Post-initialization|TCP ED=False; stop urgence=False|stop; Arrêt général|
|Controlled-stop final frame|stop urgence=True; Arrêt général=False|stop; TCP ED|
|Final cleanup|stop=False|TCP ED; stop urgence; Arrêt général|

Same-frame assignments remain unordered; these are completed-frame
postconditions, not atomic reset transactions. If a supplied prior stop=True
survives initialization and all five first bodies return with True stop
snapshots, the initialized TCP ED=False selects the empty outer arm. The
fixture therefore reaches cleanup without the staged controlled stop.
Whether an actual native restart supplies that initial stop value remains
unknown; no loaded default or automatic startup reset is invented.

Verification: the complete current VI-projection test selection plus the
stop-memory, stop-UI-binding and facet-register source tests passed321 tests
with one warning in20.52s. The new memory lane contributes5 source/mutation
tests and15 pure lifecycle tests. This is not the earlier747-test full
source regression rerun. No VI execution/save, PSP command, NI operation,
sleep or hardware write was performed.

Reproduce the new source proof and focused tests from the repository root:

```powershell
$env:PYTHONPATH='C:/dev/ELYSE-ACQ-analysis/converter/lvkit/src;C:/dev/ELYSE-ACQ-analysis/converter/test-deps;C:/dev/pyconlyse/tools;C:/dev/pyconlyse'
& 'C:/dev/pyconlyse/Supervision/analysis/lvkit_eval/.venv/Scripts/python.exe' tools/validate_acq_stop_state_memory.py
& 'C:/dev/pyconlyse/Supervision/analysis/lvkit_eval/.venv/Scripts/python.exe' -m pytest tests/scripts/test_elyse_acq_stop_state_memory.py tests/device_servers/control/test_elyse_acq_vi_stop_lifecycle.py tests/device_servers/control/test_elyse_acq_vi_stop_request_pipeline.py --deny-network -q
```

Remaining boundaries include native loaded values, indirect stop writers,
all interleavings with complete event/I/O bodies, fault-return data and
restart semantics. The finite fixture proof narrows these gaps but does not
close whole Acquisition or qualify an apparatus emergency stop.

## Normal request versus program shutdown

The [request-pipeline tests](../tests/device_servers/control/test_elyse_acq_vi_stop_request_pipeline.py)
compose the separately proved Timeout dispatch, NewVal envelope and
procedure plans. This adds integration fixtures, not new source diagrams
or an event queue. All23 registered procedure requests agree with their
saved event indices; DPS22 targets a control with no registered event here,
and the five tail fields retain their unresolved dispatch boundary.

For a supplied DPS snapshot containing only field3=True, the path is:

```text
DPS[3] -> first-True index3 -> selector4
       -> DDO59378 Value=True / Val(Sgnl)=True requests
       -> separately supplied event6 / NewVal=True
       -> 17-frame general-modulator-stop procedure
       -> local DPS[3]=False -> separately read DPS publication payload
```

The normal procedure describes Focales OFF followed by logical C4 fields
8,17,6,4,1 False-to-True pairs, EPS completion and DPS publication. Its
local-write banks are15/35/36/44, not stop30/TCP45/emergency46/general47.
It therefore must not be replaced by a Python function that merely sets
program stop=True. Conversely, the outer seven-phase controlled stop is
not this event: it ramps the HT command, stops the counter tasks and
changes other banks, but does not directly call Focales OFF or publish
PSP. The [two-path source proof](../tools/validate_acq_two_stop_paths.py)
and the complete procedure/controlled-stop graph proofs retain this
distinction. These are software requests; physical acknowledgments and
safe output states are not established by either branch.

Timeout selects the first True DPS field, not a priority queue. A supplied
snapshot with both DPS0 and DPS3 True requests cooling-start event3 first.
The event3 completion frame clears DPS0 and retains DPS3. A later snapshot
containing that reset permits event6; re-supplying the original remote
snapshot requests event3 again. This is an explicit ordering consequence,
not a proof of starvation or eventual event delivery. The normal-stop
publication likewise reads DPS anew: another supplied snapshot can contain
DPS3=True even after the preceding completion projection cleared it.
Local reset and publication are not an atomic acknowledgment transaction.

The shared converter was requalified after its parallel changes, at
fingerprint `FA1E6520BFBC81C4EB841B94F7B1D22749D5FCF17516073F092BC20D291D75C8`.
Its four stop arithmetic fragments match all826 fixtures and retain
fixture SHA256 `1637573327704746DEC69DA69854C05A93A3028C6A51286F56829FAC64E29C9D`.
The [new receipt](../legacy/xp_acq_agent/data/converter_qualification/20261004_stop_memory_shared/receipt.json)
is separate from the earlier fingerprint's receipt. Whole-VI execution
and deployment remainFalse; no converter change was required in this lane.

At that earlier checkpoint, native control exposed only a disabled parent
and no original-source diagram view was produced. The then-failing DFDS
extraction is superseded by the [DFDS recovery](ELYSE_ACQ_DFDS_RECOVERY_2026-10-04.md)
and [saved stop-data proof](ELYSE_ACQ_SAVED_STOP_DATA_2026-10-04.md): all four
persisted stop Boolean bytes are00. Those saved values are not automatically
applied as live startup/restart values. Native loaded/retained values and
indirect writers remain separate evidence gaps.

Final verification after the request-pipeline addition:328 tests passed
with one warning in20.40s, with network denied. All five scoped Python
files pass Ruff lint/format checks. All17 original VI hashes still match,
and the new receipt's converter fingerprint equals the checkout's final
fingerprint. Neither these tests nor the named facet register establishes
whole Acquisition completion. The report retains separate source facts,
conditional fixture consequences and unverified native behavior.

The later [fault-to-cleanup continuation](ELYSE_ACQ_FAULT_STOP_CLEANUP_2026-10-04.md)
composes the five-loop join, outer operator/I/O condition snapshots and
final resource-close branches. It distinguishes automatic fault flags from
an Arrêt général sequence request, retains all24 local final-write/read
orders, and never substitutes resource cleanup for NI output zeroing.
