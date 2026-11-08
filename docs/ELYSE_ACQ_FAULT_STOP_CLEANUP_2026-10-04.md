# Acquisition fault stop and resource cleanup

This review connects the saved runtime fault flags to the two outer-stop
loops and the final resource-close frame. The controller does not contain one
universal stop action. A publication fault can enter the outer frame without
requesting its staged shutdown. Conversely, an emergency-stop snapshot can
permit the outer loops to finish without entering that sequence. These are
software control-flow consequences under the explicitly supplied conditions
below, not observations of apparatus shutdown or emergency-stop reliability.

Scope is the original Acquisition source, not Supervision. No VI was run or
saved, no XP/NI system was controlled, and no PSP/VISA/serial command was sent.
The Python additions are inert supplied-order models, not a deployable server.

## Source and evidence

The saved root sequence `359` contains five ordered frames:

```text
135 declarations -> 188 initialization -> 367 runtime
                 -> 41058 outer stop -> 246 resource cleanup

runtime frame367 must join loops47483 /59483 /20601 /203 /102
  -> local45 TCP ED read7387
  -> selector43488
     False frame43496: empty
     True frame43502: I/O loop41705 and operator loop42592
  -> both entered outer loops must return
  -> cleanup frame246
```

The [lifecycle validator](../tools/validate_acq_lifecycle_envelopes.py) checks
the root frame order, exact outer operations/nets, both Stop-if-True loop
conditions and the I/O error chain. The [stop ownership validator](../tools/validate_acq_stop_state_memory.py)
checks all 20 stop-bank local references and all 11 literal writers. The
[controlled-stop validator](../tools/validate_acq_controlled_stop.py) checks
the seven-phase sequence and nested graphs. These existing proofs establish
the dependency boundaries used in the new composition; this continuation
does not add a previously missing diagram to the census.

The [cleanup validator](../tools/validate_acq_final_cleanup.py) now also pins
all three `Simple Error Handler.vi` identities and their complete ten-slot
connectors, including the previously unqualified PSP handler `88`. Exact
frame nets establish that handler modes are unwired and returned outputs
are unused. The PSP-close primitive input/output directions are separately
checked. The independent TPG Close source still directly connects public
VISA/error inputs to standard VISA Close; it has no custom command/retry case.

| Saved source | SHA256 |
|---|---|
|Original `0_ACQ_ELYSE.vi`|`6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF`|
|Original Acquisition LLB|`EB7C08800823D025F1B4F9E8EEA89ED9878F0CF00A02427871583B99989B2F8A`|
|Pinned root XML archive|`6A518B319B2D35B465DB9AAB557CCA751ACC8B58A600FBA0B8E13771B6EA1527`|
|Pinned TPG Close XML archive|`D0140C8A69938D3957566F5D8B5FD51021F445C6D5EE54CD0ABD878CB6688CDC`|

All 17 original member hashes still match their manifest. Shared lvkit was
not changed; its current source fingerprint is
`AF6B25B199C17DF8B0DB729965A727D66498083CE7FB72CA20EA51554E0C3BFB`.

## Faults do not select the same shutdown path

Two runtime publication error arms write local30 `stop=True` and local45
`TCP ED=True`. The Timeout receiving error arm writes both False instead.
Those pairs are independent local assignments, not atomic transactions.
Runtime loop conditions likewise capture local30 independently of body
completion. The outer TCP read cannot execute until all five runtime bodies
have returned with exit conditions.

After that join, the following table describes explicit captured inputs.
For the True TCP rows, cleanup still requires all entered body work to
return. No external completion, timing or physical output state is implied.

| TCP ED snapshot | General47 snapshot | Emergency46 snapshot | Saved controller consequence |
|---|---|---|---|
|False|Either|Either|Skip both outer loops and all seven staged phases; next root frame is resource cleanup.|
|True|False|False|Operator requests UI re-enabling, not staged shutdown. Both loops can continue; cleanup is not yet reachable.|
|True|False|True|No staged shutdown request. Both entered bodies can exit after their work returns; cleanup becomes reachable.|
|True|True|False|Enter all seven phases. Early False conditions remain captured; another iteration may be needed after completion writes Emergency=True.|
|True|True|True|Still enter all seven phases. True loop condition does not cancel that already selected work; body completion remains required.|

Seventeen explicitly completed idle iterations are tested for each
publication fault arm with General=False/Emergency=False. Neither fixture
invented a shutdown request or reached cleanup. A separate returning trace
lets the receive-error arm clear TCP, then supplies a later stop=True to
complete the runtime join: the outer frame skips its staged shutdown. These
finite witnesses distinguish controller dependency paths. They do not prove
that either schedule occurs on the installation or estimate its frequency.

The separately source-qualified outer I/O caller uses Emergency46, not
runtime stop30, as its loop condition. In a returning publication-fault
fixture with stop=True, General=False and Emergency=False, it still records
all 13 AI/DIO/AO/handler call nodes. A separately supplied C9 command12.7
still produces the requested6.35V at the fourth AO call. A returned AI error
is passed to the handler but does not insert an Emergency46 assignment.
Even an initially True emergency condition does not cancel the first
entered I/O body. These integration tests distinguish call-node requests
from physical writes and from eventual body return.

General47 is level-tested by selector `52981`; this is not a NewVal event
gate. An explicitly supplied indirect/UI reassertion can therefore request
the sequence again in a later operator iteration. The ordinary runtime PSP
receiver has already exited at the preceding join and is not that actor.
No indirect writer or source of such a reassertion is established here.

The seven-phase request remains distinct from the normal modulator-stop
event6 described in the [request pipeline](ELYSE_ACQ_STOP_TCP_ERROR_TRACE_2026-09-29.md#normal-request-versus-program-shutdown).
It also remains distinct from resource cleanup. The HT phase checks the
command against 6.6, not measured HT, and its returning ramp does not request
a zero voltage. See the [HT ownership proof](ELYSE_ACQ_HT_COMMAND_OWNERSHIP_2026-10-04.md).

## Final writes do not interrupt a captured loop condition

The last controlled-stop frame `64826` independently requests:

```text
node18163 -> local46 stop urgence=True
node43536 -> local47 Arrêt général=False
node63433 -> local50 ETAPES=0.0
Wait node67189 <- 1000ms
```

No wire orders these four effects within the frame. The operator condition
read `115330` sits in parent body `42610`; the sibling I/O condition read
`43367` sits in body `41713`. Neither condition depends on the completed
last frame. Reading Emergency=False before node18163 and returning a body
after node18163 are therefore compatible dependencies.

The new [outer replay](../DeviceServers/control/elyse_acq/vi_simulation/outer_stop_schedule.py)
keeps those captured values and the two-loop join. All 24 orders of the two
flag writes and the two emergency reads are checked after explicit entry
into the final frame. Eight orders capture `(False, False)`, eight capture
`(True, True)`, and four each capture the mixed pairs. These are permutation
counts for four independent operations, not probabilities or exhaustive
whole-program schedules. Only the all-True pair makes the outer join ready
in that supplied returning iteration.

A tested early-False trace completes the controlled sequence, then requires
one explicitly supplied next iteration in both outer loops. General=False
chooses UI re-enabling rather than a second sequence; Emergency=True then
permits exit. Separate tests retain a blocked I/O body despite a captured
True condition and a blocked controlled sequence despite an emergency
change. A condition value alone is never modeled as a completed body.

`ControlledFinalFrameEntered` explicitly asserts that the preceding six
phases returned; it does not execute them or establish hardware success.
`OperatorArmReturned` asserts the remaining entered work returned, including
the final wait/status effect. Both literal flag writes must already be
supplied before a True arm can return. Inner phase arithmetic/call arguments
remain in the independently qualified `controlled_stop` projections.

## Resource cleanup has three error branches and no NI output writes

Final frame246 contains a fixed 27-element PSP URI-tag array, two TPG session
reads, three error handlers and local30=False. It does not read the dynamic
PSP-open reference array. Whether these saved tags identify particular live
open resources is an external-boundary question; recording a close-node
request does not certify successful release.

```text
27 fixed URI tags -> For1176 auto-index -> Close primitive536
                        error shift register -> next iteration
                        final error -> handler88

local51 -> TPG Close61121 -> handler68680
local52 -> TPG Close66474 -> handler67965
False   -> local30 writer12978
```

Each close-node error feeds only its own wired successor. The PSP error
register has no initializer wire; the inert model therefore requires an
explicit first value. No implicit NO_ERROR or native retained-register
value is inferred. Handler88 output does not feed that register. The two
TPG error-in ports and all three handler-mode ports are unwired. Standard
call/handler behavior, including whether it blocks, clears an error or skips
an actual close, remains a supplied external return.

The new [cleanup replay](../DeviceServers/control/elyse_acq/vi_simulation/final_cleanup.py)
permits cross-branch interleaving but preserves the 27-call PSP error chain
and each close-to-handler edge. A completed fixture contains 32 external
call-node returns: 27 PSP closes, two TPG closes and three handlers. All 32
individual returned-error injections retain the saved call-site sequence;
none inserts a controller retry, a DAQ Stop/Clear call or output zeroing.
That statement concerns controller nodes, not whether a failing standard
primitive performs its requested action.

Local30 can be reset before another cleanup branch returns, because no
ordering wire connects that reset to the closes. A tested partial trace has
stop=False after one PSP close return while the final frame remains
incomplete. Final-frame completion requires all branch/handler returns,
not just the reset. After completion, TCP45, Emergency46 and General47 are
preserved by this frame. Native restart values and task/resource lifetime
across invocations remain unqualified.

A separate explicitly retained-memory fixture carries General=True through
the cleanup bypass and post-initialization resets. A later publication fault
then enters an operator arm with that supplied General=True and requests
the staged sequence. This does not contradict the General=False fault
fixture: its boundary conditions differ. It does not establish that native
LabVIEW restart retains that value or that saved defaults initialize it True.

## Verification and remaining boundaries

The first focused run passed64 tests and88 subtests in43.36s. The broader
source/model selection then passed438 tests and2007 subtests in230.45s.
Five later business integration tests exposed an imported test-helper type
identity conflict only in the full model selection. The new I/O fixture was
made self-contained; no controller behavior was changed to pass that test.
The final isolated model/register selection passed396 tests and1914 subtests
in7.14s. The final focused source/model selection passed70 tests and90 subtests
in36.01s; its source assignment test independently compares original local
banks, directions, literal values and wire peers. These are separate
selections, not summed test counts or whole-Acquisition coverage.
Each run denied outbound networking and reported one existing
assertion-rewriting warning. Six new/affected Python files pass scoped
Ruff lint/format checks.

Reproduce from `C:\dev\pyconlyse`:

```powershell
$env:PYTHONPATH='C:/dev/ELYSE-ACQ-analysis/converter/lvkit/src;C:/dev/ELYSE-ACQ-analysis/converter/test-deps;C:/dev/pyconlyse/tools;C:/dev/pyconlyse'
& 'C:/dev/pyconlyse/Supervision/analysis/lvkit_eval/.venv/Scripts/python.exe' -m pytest -q -x -o addopts= --deny-network tests/device_servers/control/test_elyse_acq_vi_outer_stop_schedule.py tests/device_servers/control/test_elyse_acq_vi_final_cleanup.py tests/scripts/test_elyse_acq_final_cleanup.py tests/scripts/test_elyse_acq_stop_state_memory.py tests/scripts/test_elyse_acq_controlled_stop.py
```

The local32-bit source window remains disabled and marked `*`. Its capture
returned another application; one refreshed activation attempt failed with
`failed to activate captured window`. No app input was sent. That capture is
not LabVIEW evidence and is not included as a VI figure. Source-matched
screenshots, omitted numeric Defaults, native Diagram Disable activation,
indirect writers, complete event/I/O fault schedules, native external
returns and restart remain open. All533 original diagrams have named
bounded facets, not full behavioral closure. No whole-Acquisition or
apparatus safety completion is claimed.

The [NI Array To Cluster reference](https://www.ni.com/docs/en-US/bundle/labview-api-ref/page/functions/array-to-cluster.html)
was rechecked while investigating the separate six-to-eight VAM conversion.
It specifies configured size and element order, but its inspected text does
not define the missing-entry value. No new zero-padding inference or model
change follows from that check; the existing supplied conversion boundary
remains explicit. That issue still needs a source-matched native/reference
check rather than a guess based on Index Array semantics.
