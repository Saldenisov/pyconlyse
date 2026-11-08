# Acquisition controlled stop and lifecycle coverage

## Complete nested native20 review 2026-10-15

The [nested-stop observation record](ELYSE_ACQ_NATIVE_NESTED_STOP_2026-10-15.json)
adds33 frozen PNGs, one for each inner sequence frame. Together with three
earlier HT/completion images, these explicitly account for all45 diagrams
inside source sequence51954:7 stage diagrams,33 inner frames,3 While bodies
and2 HT comparison arms. The reproducible check is
`tools/validate_acq_native_nested_stop.py`; its source proof retains45 exact
graphs and152 nets. No VI was run or saved.

The modulator stage contains15 inner frames, not just five conceptual
operations. C4 fields8,17,6,4,1 are each assigned False then True in order.
Five150ms Wait arguments accompany the False frames; intervening waits
are1000,1000,1000,2000,1000ms. Same-frame writes and waits have no mutual
wire order. The cooling stage has8 frames, including the identical EPS/DPS
assignment frames5/6; it does not wait for a pump-state acknowledgment.
The counter guards are Done OR i>40: all-False supplied Done values permit
42 polls, not a guaranteed40ms deadline. Outer stop urgence46 does not
interrupt an entered inner sequence or HT loop.

This closes the specific static native-view queue for sequence51954.
It is not the separate event6 shutdown, proof of a completed hardware stop,
full concurrency/restart parity or original LabVIEW2012 runtime equivalence.
The nested/source/model regression passed33 tests and4 subtests in33.68s
with network denied; the existing pytest rewrite warning remains.

The original main Acquisition VI now has named source facets for all 475
saved diagrams. This batch checks the last 57 root diagrams and 204 direct
nets, and transfers the complete seven-phase controlled-stop plan into
non-actuating Python. That closes the unregistered root-graph queue, not
whole software behavior: omitted defaults, Diagram Disable activation,
native failure returns and global restart/concurrency remain open.

The source-facet register now accounts for all 533 original saved diagrams:
527 have named facets, including all 475 main-VI diagrams and 52 helper
diagrams. The other six belong to two NI6259 VIs with no inbound saved IUVI
call across the 17 original members. Those six are explicitly excluded from
the static reachable graph, not declared wire-complete or translated.
Facet presence is not a percentage of verified business behavior.

## Sources and verification boundaries

The [2026-10-15 native stop record](ELYSE_ACQ_NATIVE_STOP_OBSERVATIONS_2026-10-15.json)
binds twelve static LabVIEW20.0f1 images to the byte-exact original Main
review copy. It confirms the outer selector distinction, selected views of
all seven stages and final resource cleanup without Run or Save. Not every
nested stop diagram was newly visited. Original LabVIEW2012 runtime
equivalence and physical effects are not inferred from those imported views.

The main VI SHA256 is
`6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF`.
The pinned root export is
`legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip`.
The source identity and original XML hashes are enforced by `checked_vam`.
No VI, NI task, PSP command, serial/VISA request or physical write runs.

The independent wire proof checks 45 controlled-stop diagrams and 152 nets
against the Python plan. Another proof checks 12 lifecycle/cleanup
diagrams and 52 nets. Exact operation populations and complete direct net
fanouts reject unexplained graph content. Existing initializer,
NI6220 reader and deviation-helper proofs are cross-indexed for 37 previously
unregistered helper diagrams; their documented limits are retained.

The current shared lvkit fingerprint is
`7C33FBFE65696D162E7826588EA6692F833C0920ADF556061A3520AB43C80533`.
Four pure generated scalar fragments match 826 fixtures for the strict HT
threshold, subtraction and both counter-loop exit predicates. The fixture
SHA256 is
`1637573327704746DEC69DA69854C05A93A3028C6A51286F56829FAC64E29C9D`.
No lvkit modification was required for these fragments. This qualification
does not execute generated main-VI code or qualify property/driver failures.

## Root lifecycle and stop entry

The main stacked sequence has five frames in saved order:
`135`, `188`, `367`, `41058`, `246`.
Frame 135 contains 66 unwired terminal references and no executable assignment
wires. It does not establish initial global/local values. Initialization
is frame188; five runtime loops run in frame367. The subsequent frame41058
can begin only after that runtime frame completes. The existing
`stop_schedule.py` models supplied single-iteration condition-read and
body-completion order, not an actual scheduler or a liveness guarantee.

Observation: the Boolean local45, `TCP ED`, selects frame41058. False
executes an empty arm; True starts two independent While loops41705 and
42592. There are no inter-loop wires. Their bodies both sample local46,
`stop urgence`, with Stop-if-True semantics. Loop42592 reads local47,
`Arrêt général`: True executes all seven phases below; False requests five
source-bound `DisabledEnum=0` UI property writes. The sampled46 condition
does not cancel an entered sequence.

The runtime While59483 also writes its I32 iteration index into local55,
labelled `BVide`. This wire is not a VI-reference assignment. Both the
saved type and the loop-index DCO association are checked.

### UI availability is not a stop request

The original front-panel export independently identifies the five controls
behind the startup and controlled-stop `DisabledEnum` writes:

| Attached DDO | Original front-panel label |
| --- | --- |
| 79089 | ETAPES: |
| 40722 | Arrêt général |
| 70708 | Lecture alimentation HT: |
| 8957 | Cmd alimentation HT: |
| 11783 | TCP ED |

Startup frame33052 requests `DisabledEnum=2`, labelled Disabled and Grayed
Out. The False general-stop arm52989 requests `DisabledEnum=0`, labelled
Enabled. These requests do not assign the Boolean values of Arrêt général
or TCP ED. The directly attached property census finds precisely ten
DisabledEnum writes and no Value/Value(Signaling) writer for these five
controls or the separate stop and stop urgence controls. This does not
exclude UI actions, primary terminals or indirect VI Server writes.

Seven control/DDO/type/label bindings and all ten property bindings are
checked by `validate_acq_stop_ui_bindings.py`. The original FPHb SHA256 is
`000E82C66074929C7A9C7434B66629ADF6934C411AB85109E663BF0474F49E72`.
Neither front-panel labels nor unwired root terminals establish loaded
initial values. The three stop Booleans must not be collapsed into one
Python flag merely because their names include stop.

## Seven ordered stop phases

Indices below are LabVIEW local-bank/cluster indices, not physical pins.
Effects in one frame have no mutual order unless an explicit wire supplies
one. A Wait request in a write frame therefore does not prove physical
pulse width. Every cluster update uses its own supplied read snapshot;
concurrent updates are not silently merged.

| Phase | Saved diagram | Observed command and frame order |
| --- | --- | --- |
| 0 | 60323 | Repeatedly read C9/local12 field0. If command<6.6, exit without another C9 write. Otherwise subtract0.1 from that checked command, update field0 of a separately read C9 base and request Wait500ms. Mirror the checked command to local48; write marker6.0 to local50. |
| 1 | 51962 | Set ACTION/local35=True. For task-bank21 fields3 then4, poll Done==True OR i>40 with Wait1ms; then Stop Task and Clear Errors. First task frame writes marker5.0. Final frame requests Wait1000ms. |
| 2 | 43360 | Write marker4.0 and C4/local15 field19=False in the same frame as Wait150ms; restore True in the next frame; then Wait1000ms. |
| 3 | 129793 | Write marker3.0. Set C6/local9 fields0..7,9 and C7/local10 fields0,1,3..9 to0.0. C6 field8 and C7 field2 are retained. Wait1000ms; set the18 listed C3/local17 magnet fields False; Wait1000ms. |
| 4 | 1722 | Write marker2.0. For C4 fields8,17,6,4,1, perform False with Wait150ms, then True, then a separate interstage wait of1000,1000,1000,2000,1000ms respectively. |
| 5 | 52159 | Write marker1.0. C3 field1=False with Wait150ms, then True, Wait400ms; field4=False with Wait150ms, then True with another Wait150ms. Two separate consecutive frames both set DPS/local36 field1=False and EPS/local44 fields1,2,3=False, field5=True. Then Wait100ms. |
| 6 | 64826 | Independent same-frame effects write local50=0.0, local46=True, local47=False and request Wait1000ms. No ordering between the flag writes and Wait is claimed. |

The phase3 C3 field list is
`9,11,15,17,21,23,25,27,29,31,32,33,34,35,36,37,38,39`.

The [C9 ownership and phase proof](ELYSE_ACQ_HT_COMMAND_OWNERSHIP_2026-10-04.md)
now narrows the competing-writer boundary. All thirteen original C9 gRefs
have been accounted for; the only stop-phase direct C9 writer is the ramp.
The root's ordinary Supervision receiver belongs to the preceding runtime
phase and cannot continue after its five loops have joined. It is therefore
not a competing writer during this outer ramp in the same invocation.
Indirect/UI writes, additional invocations, finite external-call completion
and native scheduling remain separate boundaries. For the isolated supplied
binary64 command12.7, repeated subtraction requires62 decrement frames and
31000ms of requested Wait arguments before the strict exit test succeeds
near6.5, not zero. This is an inert fixture with returning frames and no
intervening writer, not an apparatus timing observation. Finiteness alone
does not guarantee progress: at supplied command1e200, subtracting0.1 rounds
back to the same binary64 value, creating a fixed point outside the usual
operating range. Reachability of that value in the deployed system is not
established. The new tests retain both cases without changing legacy logic.
The saved ramp contains no iteration limit or
direct emergency-flag check; no physical shutdown deadline is inferred.
The42 possible counter polls at indices0..41 are not a42ms deadline;
property calls and scheduling can block or take longer.

This outer stop contains neither a Focales OFF call nor direct PSP
publication. Event6 is a distinct procedure with those operations. The
outer stop must not be replaced with the event6 plan merely because both
are called shutdown.

## The sibling I/O loop continues during shutdown

Loop41705 executes the third source-checked AI-DIO-AO caller frame41713.
It requests1000 AI samples, then DIO exchange, then NI6703 output writing,
then Simple Error Handler. It reads the current C6..C9 AO and C3..C5 DO
locals separately. The saved error wire orders helper calls; it does not
gate data assignments or drive the sampled local46 exit condition.

The returned C2 analog cluster, local20, field7 is also copied to scalar49,
`Lecture alimentation HT:`. It is not C1 field7 and is not an output-card
voltage measurement. If this field is absent from a supplied short return,
the Python projection returns `UNSUPPLIED`, not zero or a retained value.
The body independently requests Wait50ms and samples local46.

Inference: this loop can consume local command changes produced by the
seven-phase sequence. The graph does not guarantee which writes it sees,
whether a short pulse is sampled, or a bounded emergency response.
`record_stop_io` records calls only to `ScriptedBoundary`; it is not a real
adapter or a safe shutdown implementation.

## Final cleanup is not hardware deinitialization

After frame41058 completes, frame246 closes27 fixed PSP URI-tag references
through an auto-indexed For loop with an uninitialized error shift register.
It separately requests two TPG300 closes with separate error handlers and
assigns stop/local30=False. These branches have no mutual order.

No DAQmx Stop/Clear and no output-zero operation occurs in this final frame.
The physical card state after cleanup therefore cannot be inferred as zero
or safe. Standard call returns, the uninitialized cleanup seed and retained
restart state remain explicit boundary inputs.

## Reproducing the checks

Use the existing Python3.11 environment and current shared lvkit checkout:

```powershell
$env:PYTHONPATH='C:/dev/ELYSE-ACQ-analysis/converter/lvkit/src;C:/dev/ELYSE-ACQ-analysis/converter/test-deps;C:/dev/pyconlyse/tools;C:/dev/pyconlyse'
& 'C:/dev/pyconlyse/Supervision/analysis/lvkit_eval/.venv/Scripts/python.exe' tools/validate_acq_controlled_stop.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
& 'C:/dev/pyconlyse/Supervision/analysis/lvkit_eval/.venv/Scripts/python.exe' tools/validate_acq_lifecycle_envelopes.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
& 'C:/dev/pyconlyse/Supervision/analysis/lvkit_eval/.venv/Scripts/python.exe' tools/qualify_acq_controlled_stop.py
& 'C:/dev/pyconlyse/Supervision/analysis/lvkit_eval/.venv/Scripts/python.exe' tools/validate_acq_helper_source_facets.py
& 'C:/dev/pyconlyse/Supervision/analysis/lvkit_eval/.venv/Scripts/python.exe' tools/validate_acq_stop_ui_bindings.py
& 'C:/dev/pyconlyse/Supervision/analysis/lvkit_eval/.venv/Scripts/python.exe' -m pytest -q tests/device_servers/control/test_elyse_acq_vi_controlled_stop.py tests/scripts/test_elyse_acq_controlled_stop.py tests/scripts/test_elyse_acq_source_facet_register.py
```

The initial targeted run passed21 tests with one warning in183.30s before
the helper/source-register additions. It includes all57 per-diagram
mutations, finite threshold boundaries, independent snapshots, retained AO
fields, duplicate status frames, all13 injected I/O faults and network/sleep
denial. The subsequent broad ACQ regression passed 747 tests with one
warning in1469.32s. It covers all `test_elyse_acq_vi_*.py` controller tests,
`test_elyse_acq*.py` script tests and `test_acq*.py` script tests. The later
front-panel/property proof passed a separate four-test run; it was not
included in the already collected 747-test run. Its final run passed4
tests with one warning in6.21s. Ruff lint and format checks pass for all13
Python files changed in this continuation. All17 original VI hashes and
the shared converter fingerprint still match after the checks.

## What prevents full business logic closure

1. Original native confirmation of omitted outer defaults in selectors
   `11557` and `63039` (beam-line masks), `81854` (NI6220 rising counter),
   and `8105` (Timeout DPS dispatch). Their unmatched values can change
   observable behavior. Both arms of numeric selector `74832` are empty;
   its omitted default is not treated as an additional actuator path.
   Diagram Disable nodes `76550` and `68772` have saved active/default=01;
   node `14478` omits both fields. Native activation semantics remain open.
2. Front-panel defaults, unwired public error seeds and native
   property/cast/Variant failure outputs that can change control flow.
3. Full multi-iteration stop/fault/restart traces with supplied scheduling
   and retained-state fixtures; single-iteration or per-frame parity cannot
   establish global behavior or finite emergency latency.
4. Short/empty/nonfinite array semantics and inactive NI6220 scaling
   arithmetic outside the qualified domain.
5. Source-matched native screenshots. The local computer-use attempt
   returned a different-app screenshot for the disabled LabVIEW window and
   then `failed to activate captured window`. No keyboard or mouse input,
   Run, Save or XP access was issued. That image is not LabVIEW evidence.

The computer-use safety workflow required withholding UI input after the
first mismatched capture. After the user freed the computer, the32-bit
LabVIEW start window and Open dialog became visible. Read-only open/path
navigation was attempted, but the only targetable window was the disabled
parent: typed text did not appear in the filename field. The original VI
was not opened, run or saved, and no new diagram evidence was claimed.
Completing the native checks requires the original Block Diagram to be
opened manually, not the modified review copy. None of these gaps is
closed by increasing a diagram count.
