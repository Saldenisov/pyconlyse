# Acquisition controller review completion criteria

## Complete nested controlled-stop native review 2026-10-15

The [nested-stop record](ELYSE_ACQ_NATIVE_NESTED_STOP_2026-10-15.json) now
cross-indexes every one of the45 source diagrams inside sequence51954 to a
manually inspected static native20 image. Thirty-three new PNGs cover all
inner sequence frames:3 counter-stop,3 HT-supply,4 magnet,15 modulator and8
cooling frames. The counter frames also display both poll While bodies.
Three already-frozen images supply the HT loop's two comparison arms and
the final completion frame. The exact source-diagram set, not an image-count
percentage, determines this specific visit completion.

This supersedes the missing-nested-image gate for sequence51954, not the
historical selected-view record's narrower claims. Both records remain
retained. It does not close the separate event6 stop, the controller's
complete fault/restart behavior, concurrent whole-cluster updates, native
execution or original LV2012 equivalence. The five-line modulator sequence
has no embedded emergency-cancellation test; outer46 is sampled by its
containing While. Its fixed waits are not hardware acknowledgments.

The new nested-image/source/model regression passed33 tests and4 subtests
in33.68s with network denied and one inherited rewrite warning. All33 new
image hashes and all17 original/review member identities passed. The fixed
Wait arguments outside the HT iterations and counter polls sum to12850ms;
that sum is metadata, not a shutdown-time or electrical-pulse guarantee.

The final combined ten-file regression passed140 tests and367 subtests in
38.63s with network denied. It includes native records, initializer source
and injected-return models, startup composition, controlled stop and
byte-copy checks. One existing rewrite warning remains. The ten scoped
Python files pass Ruff; the five native/stop files pass format checks.

## Native initializer continuation 2026-10-15

The [initializer observation record](ELYSE_ACQ_NATIVE_INITIALIZER_OBSERVATIONS_2026-10-15.json)
adds seventeen frozen PNGs. Both arms of the four Main initialization error
Cases and both pilot/reinitialization error Cases were visited. All four
NI6703 configuration frames and the complete DIO96 diagram were inspected.
NI6703 Properties reports the byte-exact review-copy path and source12.0;
the DIO96 loaded-path readback is still pending and is not silently inferred
from a matching filename. No native Run or Save was issued.

The same continuation visits dynamic PSP discovery and all five frames of
the final startup sequence24603. The first establishes seven logical command
banks; the second publishes those seven banks; the third calls AI Read,
DIO read/write and AO Write in the error-wire order. The fourth starts three
independent NI6220/TPG initialization/handler branches and independently
resets software status/UI. The fifth publishes DPS, EPS and VDM-A. The
Pilote présent field derives from the original pilot-read error, not an
aggregate card/instrument readiness result or a cleared fallback error.

Native views corroborate, rather than replace, the existing exact-source
proofs. NI6703 +/-10 V is a channel range, not an initial voltage write;
its visible scale arrays are unwired. Pilot error annotation-200284 is not
an equality guard. Discovery has no expected-name whitelist or successful-
open filter, and its final error is unused. Tall status constants are not
fully visible in the imported startup image; their complete saved values
remain covered by the source validator rather than claimed pixel coverage.

The initializer/source/model/copy regression passed84 tests and363 subtests
in21.35s. After adding the six discovery/startup images and their existing
error-lane proofs, the native/startup regression passed45 tests in22.64s.
Both runs denied network and reported the existing rewrite warning. Whole
initialization, original LV2012 runtime equivalence and whole Acquisition
remain explicitly unclosed.

## Native stop continuation 2026-10-15

The [frozen stop observation record](ELYSE_ACQ_NATIVE_STOP_OBSERVATIONS_2026-10-15.json)
adds twelve source-matched PNGs of the two outer TCP arms, the General=False
arm, seven top-level stop stages, both HT comparison arms and final cleanup.
These are selected inner views, not a claim that every nested stop diagram
was visited. The validator retains that distinction explicitly.

TCP=False is empty. General=False is not empty: it requests five UI
DisabledEnum=0 property writes, without issuing the staged card commands.
Both outer While conditions read stop urgence46; that condition does not
interrupt an already-entered HT ramp. Final resource frame246 closes27 PSP
URI tags and two TPG sessions. It contains no explicit DAQ Stop/Clear or
output-zero request. This absence does not determine driver auto-cleanup or
the physical state after VI termination.

Two new finite ramp fixtures delimit convergence. With identical fresh
checked/base binary64 reads, initial12.7, no other writer and returning
frames,62 decrements reach below the actual strict6.6 comparison, requesting
31000ms of Wait arguments. This is not a measured shutdown latency. The
finite seed1e200 instead satisfies1e200-0.1==1e200 and makes no progress;
its reachability in the installation is not established. Finiteness alone
therefore cannot prove ramp termination.

The combined native-record, stop-model, cooling-model and byte-copy
regression passed33 tests and4 subtests in15.22s with network denied. One
inherited pytest rewrite warning remains. Scoped Ruff checks passed.
No original VI, XP process, NI task or PSP output was operated or changed.

## Source-matched native-import observations 2026-10-15

The byte-exact original Main was loaded as a subVI of a new blank caller,
then inspected without Run or Save in local 32-bit LabVIEW 2020. The
executable reports file version20.0f1. Eight load warnings concerned moved
dependencies; the detailed warning list was not captured. The in-memory
modification asterisk was already present before diagram inspection. These
are static import observations, not original LabVIEW2012 runtime equivalence.

The [frozen observation record](ELYSE_ACQ_NATIVE_STATIC_OBSERVATIONS_2026-10-15.json)
binds all three Main Diagram Disable structures and their six arms to the
original source. Named PSP-open initialization76550 selects its empty arm1;
the legacy counter fragment68772 also selects empty arm1. The Timeout
cooling-flow structure14478 selects nonempty arm0. In this last structure,
activeDiag/defaultDiag are absent in the original XML: the native20 selector
marks the guard Enabled, whereas its alternate Disabled arm is empty. This
specific observation does not establish a universal omitted-field decoder
or the behavior of a different LabVIEW version.

Both Boolean flow-trip arms and all seven True sequence frames were reviewed
and photographed. The False arm is empty. The True arm requests C3 output
fields1/4 False then True, waits150/400/150/100ms in the respective frames,
updates EPS[1,2,3,5] and DPS[1], and publishes DPS. Those Wait arguments are
not guaranteed local or electrical pulse widths. This branch does not
directly write an HT command or general-stop flag. The source-qualified
distinction between cooling OK and General Modulator OK remains unchanged.

Eighteen PNGs have frozen SHA256 values. The native Timeout read-error arm
also visibly assigns False to both stop30 and TCP45, corroborating the
source premise of the returning-fault counterexample below. No concurrent
fault schedule was executed. The new record validator checks all17 original
and review-copy hashes, the complete three-structure census, source metadata,
existing guard/frame proofs and image hashes. Its inert model fixtures use
the observed arm selection explicitly; generic projections still require
an explicit enabled-arm value and are not silently promoted to LV2012.

The new native-record/flow/model/copy selection passed18 tests and22 subtests
with network denied. The separate stop/cleanup/source selection passed51
tests and156 subtests. One inherited pytest rewrite warning occurred in
each run. The earlier broad run was interrupted by the user's reboot and
has no passing final result. Full Acquisition coverage remains open.

## Returning runtime-fault window continuation 2026-10-15

The original register still accounts for 17 members and 533 saved diagrams;
this is not a whole-VI semantic or native-visit completion claim. The newer
whole-VI evidence under `Supervision/integration_analysis/CURRENT_EVIDENCE.json`
likewise retains unrestricted native equivalence as unqualified. Historical
unresolved-default descriptions below must be read with those later,
version-specific proofs; they are not all new missing work.

The new inert `vi_simulation/fault_window.py` exhaustively merges all
39,916,800 orders of six saved runtime assignments and five independent stop
condition reads. The checked source population is the existing 20 stop-bank
references and 11 literal writers; the finite window contains only the six
writes in entered error arms 28682, 40346 and 40205. It has 128 joint outcomes.
Every recorded witness is independently replayed against literal writer UIDs.
Counts are not probabilities, and body/call/handler completion is assumed.

All five runtime conditions can capture True while the later outer TCP
selector sees False. For example, both publication-fault arms write their
True flags; dispatcher writer68231 resets TCP45=False; all five conditions
read stop30=True; dispatcher writer85095 then resets stop30=False. Under
returning body completion, all five loops exit and the empty TCP False arm
executes. Neither a publication fault nor the final stop30 value alone proves
entry into the staged shutdown. TCP=True itself still requires a separate
General47 selection before the seven-phase stop. This is a controller
counterexample, not an observation or certification of physical shutdown.

Reproduce with `tools/audit_acq_fault_window.py`. The generated receipt at
`C:/dev/ELYSE-ACQ-analysis/review_20261015/fault_window_receipt_v2.json` retains
all outcomes, exact witnesses, assumptions and source identity, with source
checks for the outer TCP/General selectors, five-loop phase join and resource
cleanup. Eleven finite-window tests include replay of all128 witnesses
through the existing body/arm dependency model and a composed witness that
reaches the32 resource-close/handler boundaries without staged card shutdown.
Neither that supplied returning trace nor the post-initializer flag-reset
projection proves a native restart. The focused regression passed67 tests
and108 subtests with network denied. Native scheduling, additional
writers, repeated event/I/O epochs, blocked external calls, complete restart,
short-array conversion and source-matched native inspection remain open.

Original Main has saved RunOnOpen=True. A rejected review artifact changes
exactly one bit at byte42 (mask0x40), with every other byte unchanged and all
16 helper copies unchanged. This is byte-preservation evidence, NOT a valid
native review clone: after the user rebooted, LabVIEW 2020 refused to load it
with `(Hex 0x59) Another user tampered with the VI password` and load code3,
`Could not load front panel`. The artifact under `original_safeopen` must
not be used as a loading workflow or source of native evidence. No checksum,
password or protection bypass was attempted; the original remains unchanged.

The replacement `review_20261015/native_subvi_originals` contains byte-exact
copies of all17 original members. Following NI's documented Run when opened
editing workflow, Main is selected as a subVI onto a new blank VI diagram,
never opened directly as a top-level program. It reached dependency loading
without the previous integrity error. Neither the blank caller nor Main is
run or saved. Subsequent diagram observations are recorded above.

The broad test attempt also exposed four recently added pure facade imports
missing from the package boundary test's exact allowlist. The new entries
name only their actual exported functions and still subject all four shared
cores to the existing stdlib-only AST checks; no network/driver exemption is
added. The corrected boundary test passes. Original VIs, telemetry release,
XP, NI, PSP, instrument interfaces and shared lvkit remain unchanged.

## NI6071E saved inputs continuation 2026-10-04

The [saved-input and pilot-read proof](ELYSE_ACQ_NI6071E_SAVED_INPUTS_2026-10-04.md)
qualifies nine parameters in two original helpers by independent raw decoding
and current shared lvkit: all15 DCO rows /480 fields, nine control/connector
bindings and74 selected value bytes. Reader count1000 is distinct from
initializer count10 at5000Hz. Root pilot count2642/slot9 remains unwired;
the initializer's ten-sample literal is not its source. Native loading is
still separate from established persisted values.

The inert pilot wrapper retains supplied incoming/read errors, not the
stored False/0/empty indicators, and projects the existing fallback. A
returning pilot-to-startup fixture uses replacement AI references but retains
the original pilot error for VDM-A[0]. The initializer's unwritten public
output remains UNASSIGNED unless explicitly seeded; a source-qualified zero
seed is a conditional fixture, not evidence of a native success return.

Focused source/model tests passed33 tests in6.06s. Full isolated VI-model /
register tests passed445 tests and1942 subtests in8.32s; the ten-file affected
regression passed210 tests and363 subtests in87.85s. All denied network and
reported one existing rewrite warning. Four scoped files pass Ruff lint /
format; standalone source validation passed. All17 original member hashes
and the original LLB still match. Shared lvkit remains unchanged at
`AF6B25B199C17DF8B0DB729965A727D66498083CE7FB72CA20EA51554E0C3BFB`.

No new diagram identity, VI Run/Save, hardware/XP action or native screenshot
was added. Saved-value ownership is closed for these nine parameters, not
actual native default loading, output returns, concurrent actors or restart.
Whole Acquisition coverage remains open; Supervision is not extended.

## Startup error routing continuation 2026-10-04

The [startup composition proof](ELYSE_ACQ_STARTUP_ERROR_LANES_2026-10-04.md)
adds a whole-source census of three typed sequence locals,18 ports and six
exact signal occurrences. Original pilot error, cleared fallback error and
final initializer error remain distinct. The cleared fallback lane does not
become a later readiness guard. Final VDM-A[0] uses the original pilot status,
not aggregate card/instrument success.

The inert returning composition transfers task-bank ownership into first
I/O, including replacement AI references, and retains the seven startup
command banks. Its49 suffix call nodes are not successful physical writes.
All81 initializer/selected-clear status patterns, all eight initial fallback
clear-return status patterns and each of49 suffix fault sites retain the
proved contracts. DPS/EPS zeros and TCP45/Emergency46 resets
do not establish hardware readiness; supplied Stop30/General47 are retained.

The initial new source/model selection passed50 tests in20.07s, followed by
a136-test nine-file startup regression in171.79s. After one added fallback
acceptance test, the full isolated model/register suite passed429 tests and
1942 subtests in8.11s. Final new-source/model rerun passed51 tests in36.91s.
These runs denied network access and reported one
existing rewrite warning. Four scoped files
pass Ruff lint/format. All17 original member hashes and the LLB still match;
shared lvkit remains unchanged at fingerprint
`AF6B25B199C17DF8B0DB729965A727D66498083CE7FB72CA20EA51554E0C3BFB`.

No new diagram identity, native figure, VI Run/Save or apparatus command was
added. Returning calls, the saved empty disable arm, one allowed independent
branch schedule and no intervening local mutations are explicit assumptions.
Native pilot count/public-error defaults, handler blocking, indirect actors,
complete concurrency and restart remain open. Whole Acquisition is not
declared complete; Supervision was not extended in this lane.

## Latest Acquisition continuation 2026-10-04

The [controlled-stop and lifecycle proof](ELYSE_ACQ_CONTROLLED_STOP_2026-10-04.md)
adds the final 57 unregistered main-VI diagrams and 204 exact direct nets.
All 475 original main diagrams have named facets. This addition initially
brought the register to527 named identities; six NI6259 diagrams had only
static call-graph exclusions. The later NI6259 continuation below adds
bounded facets for those six as well. Neither NI6259 VI has an inbound
saved IUVI call from any of the17 original members. Named facets are not
full behavioral coverage.

The inert Python stop model retains all seven phases, independent local
read snapshots, both counter polls, every staged wait and the duplicate
status frames. The parallel stop I/O loop remains a distinct AI-DIO-AO
caller and mirrors C2/local20 field7 into the HT readback scalar. Final
cleanup is not conflated with DAQ task deinitialization or output zeroing.
Current shared lvkit matches four pure scalar fragments on 826 fixtures;
no converter modification was needed for those fragments.

The broad ACQ regression passed747 tests with one warning in1469.32s.
A subsequent separate front-panel/property proof checks seven control
identities and ten DisabledEnum writes, with four additional tests. UI
availability writes are not conflated with Boolean stop requests. That
lane passed4 tests with one warning in6.21s. All13 changed Python files
pass Ruff lint/format checks; all17 original VI hashes and the converter
fingerprint remain unchanged.

The subsequent [stop-memory and repeated-runtime proof](ELYSE_ACQ_STOP_TCP_ERROR_TRACE_2026-09-29.md#repeated-runtime-faults-and-reset-ownership-2026-10-04)
checks all20 stop-bank gRefs and11 Boolean literal writers, including the
absence of initializer gRef resets for stop30/general-stop47. The inert
model supports explicit repeated iterations, absorbing exited loops and
the five-loop join. All720 permutations of six entered fault-arm writes
retain four distinct final flag pairs; these ordering counts are not
probabilities or exhaustive whole-program scheduling coverage. A supplied
trace retains four exited loops while the dispatcher continues32 further
read-fault iterations. All48 completed-frame reset postconditions are
checked. The updated VI-projection/source selection passed321 tests with
one warning in20.52s; this is not a rerun of the747-test source selection.

Seven further inert request-pipeline tests compose all23 registered DPS
requests with their NewVal envelopes and distinguish event6 normal
modulator stop from program shutdown. DPS3 reaches event6 only after
separately supplied property/event completion; the first-True DPS search
can select an earlier field instead. Fresh publication snapshots are not
atomic reset acknowledgments. These add no new source-diagram identities.
The current shared lvkit fingerprint
`FA1E6520BFBC81C4EB841B94F7B1D22749D5FCF17516073F092BC20D291D75C8`
again matches all826 stop scalar fixtures; its new receipt is linked in
the stop trace. Parallel converter changes are not treated as an unchanged
fingerprint. Original17 member hashes still match.

Final updated VI-projection/source selection passed328 tests with one
warning in20.40s and network denied. Five scoped Python files pass Ruff
lint/format checks. The new scalar qualification receipt matches the final
shared converter fingerprint. No original VI or hardware interface changed.

Whole Acquisition remains open: omitted numeric defaults, Diagram Disable
activation, native property/error/default returns, complete concurrent
event/I/O fault schedules, native restart and source-matched screenshots. The local
32-bit LabVIEW capture first returned another app, followed by
`failed to activate captured window`; no input was issued in that attempt.
After the user freed the computer, the start window and Open dialog became
visible, but input targeting still selected the disabled parent and the
original VI did not open. No VI Run/Save or XP action was issued. Manual
opening of the original diagram is required for those native checks.
The previous counts below are historical, not current coverage.

The next [NI6220 typed-index continuation](ELYSE_ACQ_NI6220_RUNTIME_TRACE_2026-10-03.md#typed-index-array-defaults-and-shared-lvkit-correction-2026-10-04)
pins three original Index Array nodes,25 typed terminals and11 DBL outputs.
NI's archived manual establishes DBL0.0 for missing indexed entries; this
closes short-array indexing and out-of-range display lookup, not failed
driver returns or six-to-eight Array To Cluster padding. The inert model
still processes supplied empty/short data after a returned read error;
error status does not substitute for the independent stop snapshot.

Shared lvkit previously unpacked a single Index Array scalar into four/six
outputs and discarded subsequent index inputs. The narrow 1D correction
now matches65734 fixture sets, including all65536 U16 display selectors,
with source and converter provenance retained in the linked receipt.
It respects explicit catalog overrides and unknown-operation resolution,
rejects unresolved wired inputs, preserves unwired-row progression and does
not claim N-D indexing. Fifty-two
new converter tests plus35 neighboring regressions passed87 tests in0.91s;
315 ACQ VI-projection tests passed in5.29s. The affected source/model lane
passed35 tests in316.69s; the final grammar lane passed2 in0.15s. Tests used
an explicit outbound-network guard. All17 original VI hashes still match.
No new census identity was registered or promoted to whole-VI closure;
native defaults, restart and full concurrency gates above remain open.

The subsequent [NI6259 dormant-helper proof](ELYSE_ACQ_NI6259_DORMANT_TRACE_2026-10-04.md)
checks all six saved diagrams and49 direct nets for the two previously
excluded VIs. The register now contains all533 original diagram identities
across17 members. Dormancy remains separate: no root initialization or
hardware path was added. NI6259 has eight +/-0.2 V channels, input-mode
code0x277A, concrete Start Trigger (None), and an unassigned public error
output. Disconnected64-channel range/timebase constants are not settings.
Its reader fixes mean-loop N8 independently of requested sample count,
passes Read error directly and does not consume Mean error. All standard
Read/Mean returns remain supplied external boundaries in the inert model.

The shared lvkit matches584 pure array cases across both scaling arms;
saved False remains raw passthrough and True remains inactive. No converter
change was needed for this path. Final model/new-source/qualification/register
selection passed351 tests with one warning and1906 subtests in11.32s,
with outbound networking denied. Eight scoped Python files pass Ruff
lint/format checks. All17 original member hashes still match. The native
activation recovery failed again; no source-matched screenshot was added.
All533 facets therefore remain separate from full behavioral closure.

The [DFDS recovery and selector cross check](ELYSE_ACQ_DFDS_RECOVERY_2026-10-04.md)
now decodes 829 records with exact-length reads across 56852 original bytes.
Five independently decoded numeric records match nine saved cases containing
64 frames. This is concordance of saved ranges, not unique table identity:
those cases have no direct tdOffset link. Omitted numeric defaults and loaded
control values remain unproven. The first recovery and count-guard test runs
are historical records in that report, not the current final parse.

The earlier interpretation of TypeID 3057 as a malformed selector record is
superseded. A lazy repeated-block descriptor had not been prepared: TypeID
3056 consumed zero bytes instead of 1995 I32 values. The following record
absorbed the tail, and permissive EOF reads fabricated later zeros. Descriptor
preparation, exact reads and narrowly scoped VariableContainer/Task reference
corrections restore alignment. Independent decoding checks all 1995 values
and the actual 3057 header `(0, 2, 2)`. The ten-test count guard remains useful
defense, not evidence that the original 3057 record is inconsistent. All
829 decoded records are still not semantically certified.

The [saved stop-data proof](ELYSE_ACQ_SAVED_STOP_DATA_2026-10-04.md) checks
all 69 DCO rows/2208 fields and their DSINIT/type-map links. Stop banks 30,
45, 46 and 47 each have persisted Boolean byte 00, matched to four original
front-panel identities and all 20 previously traced local references.
The inert Python snapshot makes those saved False values explicit; it is not
automatically applied at startup or restart. Existing initializer writes
still clear only 45/46, and final cleanup still clears only 30. Live retained
memory and native initial control values therefore remain separate gates.

Final verification: shared parser/extractor/index selection **158 passed in
1.34 s**; updated source/qualification selection **76 passed and 2858 subtests
in 86.03 s**, with one warning; isolated VI-model/register selection **344
passed and 1816 subtests in 6.70 s**, with one warning. Network access was
denied. Ten scoped new/affected Python files pass Ruff lint/format checks.
All 17 original VI hashes and the LLB still match. No diagram identity,
native screenshot, hardware path or whole-Acquisition closure was added.

The local 32-bit diagram window remains marked unsaved, with a disabled
parent; its capture returned another app and activation recovery returned
`failed to activate captured window`. UI input stopped. No VI run/save or
hardware command occurred. Source-matched native Default/disabled-arm/control
checks still require a usable unchanged local diagram. Whole Acquisition
remains open at native behavior, full concurrency, faults and restart.

## HT business logic continuation 2026-10-04

The [HT command ownership and phase proof](ELYSE_ACQ_HT_COMMAND_OWNERSHIP_2026-10-04.md)
joins all thirteen original C9/local12 references: ten reads and exactly
three direct writes, in initialization, runtime reception and outer stop.
Front-panel/type identities, complete local wire peers and lifecycle owners
are checked. The ordinary PSP receiver belongs to frame367; the ramp belongs
to the following frame41058, after all five runtime loops have joined.
That receiver therefore cannot oppose the later outer ramp in the same
invocation. This narrows earlier generic concurrent-writer wording; indirect
UI/VI Server actors and additional invocations remain unqualified.

Business-level Python acceptance traces compose existing proved projections,
without new guards or hardware enablement. Initialization6.5 requests3.25V;
supplied12.7 requests6.35V. The strictly-below6.6 returning ramp preserves a
nonzero command rather than zeroing it. Returned PSP faults, EPS variations,
conditional cooling trip and distinct supply start/stop/reset procedures do
not silently become a C9 zero assignment. Numeric setpoint and supply state
are kept separate. TCP ED outer entry, Arrêt général sequence request and
stop urgence sampled loop exit are three different controller contracts,
not one generic emergency action or a physical safety certification.

Final verification: focused source/business lane **24 passed and100 subtests
in7.15s**; six-file source regression **55 passed and204 subtests in424.47s**;
isolated VI-model/register suite **357 passed and1826 subtests in6.95s**.
Each selection denied network access and reported one assertion-rewriting
warning. Four new/affected Python files pass Ruff lint/format checks. All17
original VI hashes and the LLB remain unchanged. Shared lvkit was not changed.
No extra census identity, native screenshot, VI Run/Save, XP/NI control,
PSP/VISA/serial command or hardware write was added. Full Acquisition remains
open at the native/default/disabled-arm, indirect control, external-return,
complete concurrency and restart gates; these results close the stated
HT contract only.

## Runtime fault to cleanup continuation 2026-10-04

The [fault and cleanup proof](ELYSE_ACQ_FAULT_STOP_CLEANUP_2026-10-04.md)
composes the existing five-loop runtime join with both outer-stop loops and
the final resource-close frame. The new inert replay keeps General47 arm
selection separate from Emergency46 condition reads, requires entered work
to return, and retains both independent final flag writes. All24 orders of
two flag writes and two condition reads yield four captured condition pairs;
those counts are neither probabilities nor complete event/I/O schedules.

Publication faults with supplied General=False/Emergency=False can enter
idle outer loops rather than request the seven-phase sequence. The outer
I/O caller checks Emergency46, not runtime stop30: a supplied12.7 command
still requests6.35V at C9 despite stop30=True. An I/O fault does not add a
flag assignment or cancel an already entered call-node trace. Conversely,
General=False/Emergency=True permits returning bodies to exit without the
staged sequence. None of these fixtures certifies physical shutdown.

The cleanup model records27 fixed PSP tag-close nodes, two TPG closes and
three independent handlers, with an explicitly supplied uninitialized PSP
error-register seed. The source validator now qualifies all three handler
identities/connectors, including UID88; outputs are unused and modes unwired.
Local30 reset remains independent of resource-close completion. No DAQ
Stop/Clear or voltage-zero action is added. Conditional retained-General
restart fixtures are distinguished from saved defaults and native retention.

The broad source/model selection passed438 tests and2007 subtests in230.45s.
After five additional business tests, a full-model test-helper identity
conflict was fixed by self-contained fixtures, not changed controller logic.
The final model/register selection passed396 tests and1914 subtests in7.14s;
the final focused source/model selection passed70 tests and90 subtests in36.01s.
Each run denied network access and reported one existing rewrite warning.
Six scoped Python files pass Ruff lint/format checks. All17 original VI
hashes and the LLB still match; shared lvkit was unchanged at fingerprint
`AF6B25B199C17DF8B0DB729965A727D66498083CE7FB72CA20EA51554E0C3BFB`.

No census identity or native figure was added. Local32-bit LabVIEW remains
disabled and marked unsaved; capture returned another app and one refreshed
activation failed with `failed to activate captured window`. No app input,
VI Run/Save, XP/NI action or hardware command occurred. Native Defaults,
disabled-arm activation, indirect actors, external returns, complete
concurrent event/I/O schedules and restart remain open. Whole Acquisition
is not declared complete; no Supervision work was started in this lane.

## Saved measurement state continuation 2026-10-04

The [saved WCM and publication proof](ELYSE_ACQ_SAVED_MEASUREMENT_STATE_2026-10-04.md)
adds seven original DCO/DFDS/front-panel associations and21 root-local
ownership checks. Banks59/65/66/67 contain saved array dimension0, not four
DBL zeros; banks62/63/68 contain I32/U16/U32 zero. Independent decoding checks
26 saved bytes and exact measured record intervals. No new census identity
is added, and saved values are not promoted to native loading or restart resets.

The inert counter projection now accepts variable-length prior WCM arrays.
VAM-A can consume independently supplied short-array conversion returns for
both WCM banks, without guessed padding or atomic multi-bank sampling.
First-pass NaN/finite Mean fixtures remain conditional external returns;
True unmatched-counter dispatch and actual Mean(empty) remain open.
Final model/register selection passed410 tests and1942 subtests in7.81s;
focused source/model selection passed64 tests and2560 subtests in89.19s.
Both denied network and reported one existing rewrite warning. Eight scoped
Python files pass Ruff lint/format checks; original17 VI and LLB hashes match.
Shared lvkit remains unchanged at fingerprint
`AF6B25B199C17DF8B0DB729965A727D66498083CE7FB72CA20EA51554E0C3BFB`.
No native screenshot, VI Run/Save, XP/NI action or apparatus command occurred.
Whole Acquisition remains open at the explicitly listed native/default,
indirect-actor, concurrency and restart boundaries; no Supervision work started.

## Historical Acquisition continuation 2026-10-03

The [command-procedure proof](ELYSE_ACQ_PROCEDURE_SEQUENCES_2026-10-03.md)
qualifies all23 procedure bodies:159 stacked frames,7 focal cells,4
conditioning For bodies and2 counter-poll While bodies. These172 identities
contain694 direct nets. Typed effects agree with independent inert Python
plans. External-call completion and concurrent/event scheduling remain
separate boundaries. This closes a graph facet, not whole Acquisition.
The final affected source/envelope/register lane passed14 tests in135.31s;
the complete Acquisition controller/projection lane passed286 in4.07s.
The original17 member and LLB hashes still match. The native tool returned
a different app after targeting the disabled32-bit LabVIEW window; no
keyboard/click action was issued and no native diagram evidence was added.

The [NI6220 runtime proof](ELYSE_ACQ_NI6220_RUNTIME_TRACE_2026-10-03.md)
adds 14 direct diagram graphs and 61 nets, the relative WCM change
predicate, all explicit counter cases, six separate sample-length20 Mean
calls and the six-element bank59 producer. The missing True-counter
default dispatch and downstream eight-element cluster short-input result
remain explicit gaps. The U32 counter and U16 display index are now pinned.

The [Timeout receiving-frame proof](ELYSE_ACQ_TIMEOUT_COMMAND_READ_TRACE_2026-10-03.md)
adds six direct graphs and 53 nets, all twelve PSP command/status readers,
their error chain, whole-cluster destinations and default-data arguments.
The final read error resets stop/TCP ED to False; publication errors set
them True in independent loops. This competing-writer behavior must be
retained in the whole-program fault model. No guaranteed emergency-stop
latency follows from the independent Wait/Event Timeout values.

Timeout frame10526 also has a complete 16-operation, 29-net proof and
20 command-to-Consigne copies. Its nested Bundle By Name indices include
each device container, not just scalar fields. The Python projection
preserves all other device fields; command intent is not measured output.

The [Timeout dispatch proof](ELYSE_ACQ_TIMEOUT_DISPATCH_TRACE_2026-10-03.md)
adds31 complete direct graphs/60 nets, all24 property targets and all3
NI6602 caller frames. DPS searches29 fields; unmatched tail selectors
remain unknown, and DPS22 has no registered event handler. Counter reset
is not gated by a returned helper error after the preceding frame completes.

The [complete cooling frame proof](ELYSE_ACQ_COOLING_FLOW_SAFETY_TRACE_2026-09-29.md)
adds12 complete direct graphs/38 nets, both Diagram Disable arms and all7
trip frames. Requested waits are independent of same-frame command writes,
so they do not prove exact local hold or physical pulse duration. Explicit
active/default arm metadata is absent in the pinned original export; the
historical screenshot is not a current source-hash match.

The [event-envelope proof](ELYSE_ACQ_EVENT_ENVELOPES_2026-10-03.md)
adds71 new identities: all26 direct event envelopes and both arms of
all23 procedureNewVal gates are proved, with Timeout53 already registered.
EveryFalse is empty; event25 magnet-zero also has a NewVal guard, contrary
to an absence inference from the earlier native inner-frame view. Its
special registration high bit remains uninterpreted. The separate procedure
proof now covers the nested graph facet; event delivery remains open.

The original named-facet overlay references 371 diagram identities; the
vendor overlay remains 50. Neither count promotes any original census row
or entire VI to full behavioral/native closure. Native screenshots and
the initialization/shutdown Word revision remain open. All new Python
modules are non-actuating projections; hardware adapters are unchanged.

Four initializer caller/error gates and the one-pass AI fallback now have
complete14-diagram/52-net direct-graph proofs. Five additional parent graphs
pin56 nets in total, including clock-sync request/handler without an error
or return-code gate into later card initialization. Two discovery graphs
bring the continuation to21 graphs/70 nets, with exact operations and
literal populations plus an inert supplied-cardinality/error projection.
No name whitelist or successful-open filter is inferred. Task references write outside
error Cases; errors can be cleared before the next initializer. AI test-read
sample count is unwired, and the original read error is retained separately
from the fallback result. Explicit inert projections do not assume task
validity or a NI6071E public-error seed. Initialization Diagram Disable arms
remain open. See the procedure report's initializer continuation.

Initialization Diagram Disable76550 differs from cooling: its saved
activeDiag/defaultDiag are explicitly01, commentModeTrue, with empty second
arm76564. Parent1356 and this empty arm add two graph facets and one net.
The73-net sibling76558 now has its separate full direct-graph proof:
24 named opens with24 READ-only type anchors, chained errors and unused
reference/access outputs. These are not bank assignments or publications.
The inert model requires explicit branch selection. Native activation semantics
must not be inferred from the cooling metadata gap or a display caption.

Next closure work: both beam-line event bodies and native initialization activation,
remaining lifecycle/controlled-stop graphs, unmatched Timeout dispatch,
enabled-arm metadata, upstream permissions, local reset/restart writers,
short-input returns and cross-loop normal/fault stop schedules.
Acquisition remains active; no Supervision completion claim is made.

Initialization census accounting now has zero missing named facets across
all29 descendants of outer frame1. A rejecting register test compares the
explicit29-identity set with the original census subtree. The24 newly
registered graphs add144 direct nets; five final-startup graphs were already
registered. This is graph accounting, not external success or full ACQ/native
closure. Next unverified beam-line sequences are11069 and19041, each with
four frames and nested numeric range Cases; no full default handling is
inferred from the observed range table.

Final initialization continuation:310 controller/projection tests passed
in4.50s;41 caller/named-open/register tests passed in125.07s; the explicit
29-descendant assertion then passed with all3 register tests in0.11s.
Ten-file Ruff/format checks pass; original17 VI and LLB byte hashes match.
Native control remains unavailable because the window tool returned ChatGPT
instead of the selected disabled LabVIEW window. No wrong-app input occurred.

The stop-local integration now includes explicit single-iteration schedules
for all five loop conditions, both publication-error True assignments,
Timeout-error False assignments and the runtime-frame join before outer
TCP selection. Seven golden tests retain early snapshots, competing writes
and a fixture in which every runtime loop exits but outerTCP remainsFalse.
These are supplied-order projections, not an executed scheduler, complete
restart parity or an apparatus safety claim.

A separate whole-root local-reference facet pins38 sites in banks35/43/
65/68. ACTION has26 writes and zero gRef reads; WCM prior-array/counter
gRef writers are confined to the runtime branch, with no initialization
seed/reset gRef writer. This does not close primary terminals, properties,
VI Server, UI edits or restart defaults. It adds no fully covered diagram
to the current named-identity overlay.

Native review attempt: the available local32-bit LabVIEW root window's
VI Properties identifies
`C:\dev\ELYSE-ACQ-analysis\offline\extracted\ACQUISITION_VIs_verified\0_ACQ_ELYSE.vi`,
source version20.0, SHA256
`CB396B27F5459E2BD0102CF1184630DD4AAD493CF5C39C6283D3226ED431FDEF`,
not the pinned original root SHA256. It is a modified review copy and
cannot certify original-source native closure. A modal VI Properties
dialog is not separately targetable through current computer control;
the user has been asked to dismiss it. No Run/Save command was issued.
An unsaved blank review harness was created; no source VI was edited.

### Verification of this continuation

| Batch | Result | Limit |
|---|---|---|
|Complete then-current Acquisition source/mutation selection|329 passed,893.03s, network denied|Completed before the later runtime-register and event-envelope test files were added; not a336-test single-batch rerun|
|Runtime-register additions|3 passed,4.41s|Whole-root gRef population only|
|Event-envelope focused source/model additions|7 passed,76.36s|4 source tests,3 projection tests; mutation subtests visit all23 NewVal fields|
|Final original/vendor facet-register test|2 passed,0.07s|175 original identities/50 vendor identities; both universal completion flags remainFalse|
|Final Acquisition controller/projection selection|264 passed,3.52s, network denied|Inert fixtures and existing controller contracts, not apparatus tests|
|Final isolated VI projections on Python3.11|211 tests passed,0.354s|Standard-library in-memory boundary models|

Original17 member SHA256 values, source LLB
`EB7C08800823D025F1B4F9E8EEA89ED9878F0CF00A02427871583B99989B2F8A`
and existing Word
`E4E9C63C0360042A64E16BE57C9831CAA2BA3B6E8D335425985883B771698D8B`
remain unchanged. No source VI Run/Save command, apparatus connection,
PSP command or hardware write was issued. The source census still requires
complete row-level semantic/native reconciliation; the175 named facets
must not be reported as175 fully behaviorally covered diagrams or100%
Acquisition closure. Supervision remains deferred.

## Decision

Acquisition remains the active review target. Supervision review resumes
after the Acquisition controller logic has passed the completion
criteria below. Parsing a VI, visiting an event selector or passing a
validator for one facet does not close an entire member. Physical output
polarity, measured card behavior and driver internals are not prerequisites
for this software-logic review; they are separate commissioning work.

For each reachable saved diagram, completion requires a source identity,
entry condition, selector/loop input, relevant locals and field indices,
ordered versus concurrent effects, external-call arguments, error path,
exit/result, and retained evidence. Standard DAQmx/VISA/PSP calls are
abstract boundaries with supplied returns/errors, not reimplemented
drivers. User-requested native screenshots remain a distinct evidence
requirement. No code or transport can issue physical writes during this
review.

## Original source diagram register

The [original diagram census](ELYSE_ACQ_ORIGINAL_DIAGRAM_CENSUS_2026-10-01.csv)
was generated from fresh read-only exports of all 17 manifest-matching
members, with source VI hashes checked before/after extraction. It contains
533 diagrams: 17 member roots, 272 stacked-sequence frames, 11 flat-sequence
frames, 166 Case arms, 26 event diagrams, 20 For bodies, 13 While bodies
and eight Diagram Disable arms. There are 516 non-root diagrams; 512
belong to the 15 statically reachable members. The two NI6259 members
remain statically unreferenced, not proven dynamically impossible.

The older 520-row normalized inventory is retained as a historical search
aid, not the authoritative source denominator. Its four extra sequence
rows are assigned to the two focal VIs (two each); neither original focal
member contains a sequence structure. Root frame/loop counts agree after
including the 11 flat-sequence cells. This comparison does not identify
whether the four normalized rows came from a working-source change or
graph normalization; their source origin is unresolved.

The census deliberately initializes all rows to `UNREVIEWED` and leaves
local names unresolved. This means existing evidence has **not yet been
cross-indexed into this new register**, not that previous reviews are
discarded. Behavioral status must be assigned only after matching the
actual member/diagram UID and all required proof facets. Diagram Disable
ancestry is listed without guessing its active arm. Data-fill/variant
parser warnings are recorded; no decoded defaults are inferred from
those failed resources.

The [census report](ELYSE_ACQ_ORIGINAL_DIAGRAM_CENSUS_2026-10-01.json) records
source hashes and local call reachability. The durable XML archive is
`legacy/xp_acq_agent/data/source_exports/ACQ_17_original_members_XML_20261001.zip`,
SHA256 `645694B964BA594F0563DAE37E67E49A03A0B57B4BA6C2A0639C916717F04A2F`.
Seven structural tests cover flat sequences, nested loops, comment
ancestry, qualified call links and rejection of automatic coverage claims.

## Review gates

| Scope | Closed evidence in the current record | Required to close Acquisition |
|---|---|---|
| Source and structural inventory | All 17 original member hashes; all 533 raw diagrams; 15-member static call graph | Cross-index existing native/validator evidence and copied custom-driver dependencies; do not equate source identity with live deployed equality |
| Initialization | Root error-clearing gates and AI fallback; all five card initializer contracts; dynamic PSP discovery; startup command/publication/initial-I/O/reset facets; five TPG initializer states, serial setup and byte-loop/error facets | Integrate helper results and local-variable schedules into the entire root lifecycle; retain missing native evidence; external-call outcomes remain supplied boundaries |
| Runtime acquisition and publication | Five loop identities; field/status traces; NI6220 Read mean bound/errors; NI6703 arithmetic/calls; full direct I/O frame 0 and PSP publication frame 1; focal and counter helper facets | Remaining exchange frames and calculations, pressure-call result consumers, all shared-state writers/readers and concurrent publication outcomes |
| Event/control paths | 26 native event selectors; many literal DIO/status paths and stop-stage validators | Row-level nested guard, argument, wait, restore, exit and error facets for every enabled reachable diagram; no inferred event for orphan DPS request 23 |
| Stop and fault paths | Distinct event-6 and outer seven-phase paths; root stop ingress and conditional liveness; staged waits/status assignments; all45 sequence51954 diagrams now have static native20 image links; four init error Cases photographed in both arms | Full fault/cancellation/restart transition traces; correlate remaining local identities; native coverage outside sequence51954, including separate event6, remains distinct |
| Final cleanup | Entire final frame's fixed 27-tag close source, error shift register, independent branches, stop reset; complete custom TPG300 Close body | Integrate these verified branches into whole-program lifecycle/restart analysis; distinguish requested closes from successful physical outcomes |
| Python parity | Bounded, non-actuating projections; five separate initializer translations with saved-node traces, source literal correspondence and injection at all 267 external call sites | Integrate helper results into root lifecycle; golden traces for remaining closed paths; full fault/stop/restart and concurrency parity; no hardware commissioning claim |

The [final cleanup and NI6220 trace](ELYSE_ACQ_FINAL_CLEANUP_TRACE_2026-10-01.md)
closes two previously open software questions. It also corrects the
earlier unconditional NI6220 mean-array length: For N shares the input
sample-count net, so output length is bounded by both N and returned
channel count.

## Next Acquisition work

The latest offline script suite passed **161 tests in 114.529 s**. All
17 original member hashes and the original LLB hash were rechecked after
this work without drift. The [machine-readable check](ELYSE_ACQ_STATIC_CLOSURE_CHECK_2026-10-01.json)
records exact test counts, closed facets and remaining gates. This test
count is not a percentage of complete business-logic coverage. The Word
artifact remains unchanged and requires the initializer supplement
until its next rendered-and-verified revision.

The [initializer error-contract supplement](ELYSE_ACQ_INITIALIZER_ERROR_CONTRACTS_2026-10-01.md)
now checks DIO96/NI6703, all eight NI6602 frames and NI6220's connected
configuration. NI6703's discarded Create Task errors are a controller
semantics issue, not a reason to inspect DAQmx internals.

The PSP discovery stage has no expected-name/type whitelist or final-error
consumer. Parameter 61 receives the discovered open-reference array but
has no diagram-local reader; final cleanup uses a separate 27-tag constant.
No PSP resource-leak claim follows without external boundary semantics.

Continue with startup state, then runtime I/O/field projections and
fault/restart paths. Native evidence capture must use only a free local
32-bit LabVIEW window and copied source, without VI run/save. No
Supervision step is authorized by a partial Acquisition gate pass.

## Python initializer transfer

The [VI translation package](../DeviceServers/control/elyse_acq/vi_simulation/README.md)
now contains one Python file per verified DIO96, NI6071E, NI6220, NI6602 and
NI6703 initializer. Its 21 task slots span cards 1..11. The normal helper
traces contain 267 abstract external-call requests; a parameterized test
injects a returned fault at every call site and checks the distinct legacy
error contracts. This is not a complete root initialization or a hardware
enablement step. External returns, not DAQmx internals, are modeled.

Nine source correspondence tests check original node/diagram identities,
polymorphic selections and connected configuration values. The NI6071E
source validator additionally verifies both Volts literals and their ordinary
loop tunnels. NI6703's `FFFFFFFF` ring is explicitly identified as output
terminal configuration Default, correcting the earlier DAC-reference label.

Verification after this transfer: **175 source/mutation tests passed in
116.942 s**; **156 ELYSE controller/projection tests passed in 1.80 s**
with external network access denied. The latter includes 31 initializer
simulation tests; those 31 also passed on Python 3.11. No VI was run/saved,
no network transport or NI/VISA call was used, and no executable procedure
plan or Tango adapter was changed. The older 161-test record above describes
the preceding review batch, not the final count for this transfer.

## Acquisition-only continuation, 2026-10-02

The [NI6703 writer proof](ELYSE_ACQ_NI6703_WRITER_TRACE_2026-10-02.md)
adds the active helper's 42-net wire graph, all connected conversion
coefficients/formulas, four ordered DAQmx request sites and the public
error/task contract. All three root call sites now have proved bank/task/
error input edges and final error-consumer edges. Those are caller facets,
not closure of entire initialization/runtime/stop frames. The inactive old
cluster implementation is not mixed into the active array implementation.

Python now reproduces requested-voltage calculations and supplied-error
flow without an adapter or transport. Thirty-one focused tests passed;
170 ELYSE controller/projection tests passed with network access denied.
The full Acquisition source/mutation suite passed 192 tests in 155.03 s;
all 17 original members and the original LLB remain hash-identical.
Python-only shape/finiteness/domain guards and unverified LabVIEW invalid-
input behavior are explicitly distinguished. No native screenshot or Word
revision was added; no Supervision review was started. Acquisition remains
open at the full runtime, event, concurrency, fault/restart and native
evidence gates listed above. Next: complete the DIO96 helper that precedes
the AO writer, then the remaining seven-frame root I/O sequence.

## Runtime/counter/focal continuation, 2026-10-02

The [runtime I/O trace](ELYSE_ACQ_RUNTIME_IO_TRACE_2026-10-02.md) closes
the named DIO96, NI6071E and NI6602 helper graph facets, their selected
caller edges, all 58 runtime line readback copies, eight-write PSP
publication and the saved disabled comparison frame. Both focal ON/OFF
roots additionally have complete operation/net censuses, connected command
arguments, independent error/session chains and merge order. Vendor calls
remain abstract boundaries. These supersede the preceding batch's next-
helper list; they do not close the whole runtime or either root stop path.

The [facet overlay](ELYSE_ACQ_SOURCE_FACETS_2026-10-02.json) registers
26 original VI/diagram identities without promoting historical census
rows to complete behavior. Earlier initializer/event/cleanup/native
evidence still needs separate cross-indexing.

New discriminating findings: final command/readback comparison is saved
False; deviated targets 91/103 both receive C1[34]; each explicit I/O read
requests 1000 samples/channel; counter exit is Done=True OR i>20, not an
error-status exit or guaranteed 22-ms deadline; focal OFF resets/configures
before requesting output False. The visible focal 9600 constants are
unwired. None of these is silently corrected in the simulator.

Still required after that batch: runtime frame-0 conversion/default integration, all remaining
event/calculation/argument facets, root initialization and custom-driver
integration, full shared-state scheduling, faults/cancellation/restart, and
the missing native screenshots. Current simulation imports no transport and
is not connected to Tango or the adapter-capable engine. Local LabVIEW modal
recovery and removal of an added unsaved path label await user confirmation;
the VI must not be saved. No new native evidence or Word revision is claimed.

## Runtime frame zero continuation

The frame-0 validator adds all 32 wire nets, 33 operations and 12 saved
conversion shapes. Original cluster sizes are AI 64/64, DI 56/64/56,
DO 40/32/40 and AO 10/10/10/10. Heap and consolidated type IDs are resolved
through the saved DTHP slice; nested descriptors use flat indices.
The isolated `record_runtime_io` composes AI, DIO and AO error chains plus
the error-handler boundary, with faults injected at all 13 call sites.
No error flag silently becomes a guaranteed physical stop.

Frame 0's card error terminates at the error-handler boundary. Frame 1
starts a separate PSP error chain with an unwired input. With a returning
handler and supplied successful PSP returns, a card fault alone produces
no publication stop assignment. This bounded result must not be generalized
to other concurrent or hardwired stop paths.

The facet overlay now names 27 diagrams, not 27 completely understood
diagrams and not a percentage of Acquisition coverage. Short-array defaults,
all remaining event calculations, root initialization/custom serial
integration, shared-state schedules, faults/restart and native evidence
remain open. The source VI files and Word document are not edited.

Final verification for this continuation: 254 source/mutation tests passed
in 385.24 s; 233 ELYSE controller/projection tests passed in 3.36 s;
108 isolated VI-model tests passed on Python 3.11 in 0.402 s. Pytest network
access was denied. Ruff check passed and 21 scoped files passed format
checking. All 17 original members, LLB and Word hashes remained unchanged.
These are test counts, not coverage percentages or proof of safe actuation.

## Initial exchange and instrument startup continuation

The [startup integration report](ELYSE_ACQ_STARTUP_IO_TPG_TRACE_2026-10-02.md)
adds independent frame 25990 proof (33 operations, 32 nets, 12 conversions)
and frame 33052 proof (31 operations, 17 nets). It distinguishes the three
NI6220/COM1/COM2 branches from software resets and UI disabling, which do
not wait for aggregate initialization success. The original facet overlay
now names 32 diagrams; native review and full controller coverage remain open.

Copied TPG Initialize and Serial Init add 12 vendor diagrams and 103 direct
nets outside the original-member census. The five-state outer transition
projection preserves serial/probe faults, cyclic rate search, BAU coding,
literal Init Error replacement and unconditional exit after the final PNR.
Explicit Def.Value snapshots preserve the unresolved root local-write
schedule. Driver Core's 30 diagrams, full root scheduling, event/stop/restart
ownership and native screenshots remain gates. No hardware transport or
executable adapter was changed.

Three additional outer Driver Core facets cover 25 nets and 18 direct
operations. Retry=3 permits four attempts only when inner phases return.
The final error.status is replaced by OR of two supplied phase-two flags,
not ORed with the incoming VISA error.status. The isolated retry projection
preserves code/source and leaves flag production and suppress-warning open.

## Startup publication continuation

Three additional named source facets cover command assignment 14803,
command publication 24611 and final status publication 17881: 40 direct
wire nets, 53 operations and 152 logical command fields. `VDM-A[0]`
(`Pilote présent ?`) is NOT the original pilot-read error status retained
in sequence local 25655; a cleared fallback result does not replace it.
It is not an aggregate card/instrument readiness indication. Command
publication and final DPS/EPS/VDM-A publication have separate error chains.
The isolated Python recorder imports no transport or adapter.

The facet register now contains 30 named diagram identities, not 30 fully
reviewed diagrams. Startup initial I/O frame 25990 and serial/NI6220/reset
frame 33052 still require their own proofs. Remaining concurrent events,
fault/restart paths and native screenshots are not closed. See the
[startup trace](ELYSE_ACQ_STARTUP_PUBLICATION_TRACE_2026-10-02.md).

Final verification for the startup continuation: 261 source/mutation tests
passed in 441.84 s with network denied; 241 existing ELYSE controller and
projection tests passed in 2.84 s; 116 isolated VI-model tests passed on
Python 3.11 in 0.326 s. Ruff check and 22-file format check passed. All 17
original VI files, source LLB and existing Word document remain unchanged.

## TPG byte loop and returned error continuation

The [protocol report](ELYSE_ACQ_TPG_PROTOCOL_TRACE_2026-10-02.md) adds all
27 remaining Driver Core direct graphs (199 nets) to the three outer
facets (25 nets). Nine Boolean cases, primitive argument slots, register
pairing, sequence-local origins, command framing, ACK/NAK/ENQ/CR handling
and both Continue conditions are checked. The copied suppress-warning
helper adds three diagrams and seven nets. It replaces the entire error
cluster when error.code equals `0x3FFF0006`, regardless of incoming status.

Fresh-byte branches bypass elapsed<timeout; no-data branches use that
predicate and request 50-ms polling waits. Outer Retry bounds returning
attempts, not total latency. No error.status wire supplies either inner
Continue AND. These source properties are retained in pure Python
projections, not silently repaired. External VISA outcomes remain supplied.

The vendor register now names 45 diagram identities, separate from the
32 named original-member identities and the original 533-diagram census.
These are facet registrations, not fully closed diagrams or percentages.
No VI run/save, remote control, PSP/serial command or hardware write occurred.

The next localized caller path is pressure polling loop `59483`, sequence
`48312`, frames `48320` and `52460`. The three custom Get Pressure-Status
calls are `46178`, `53865` and `52475`. Their results feed local banks
53, 54 and 60. The stop-local polarity for this loop was already checked
in `validate_acq_stop_ingress.py`; repeating that check is not additional
coverage. Remaining work here is pressure/status argument and result
semantics, their downstream control consumers, and interactions with
concurrent writers. Event/stop/restart and native evidence gates remain open.

This continuation passed 287 Acquisition source/mutation tests in 524.63 s,
276 existing ELYSE controller/projection tests in 3.46 s, and 151 isolated
VI-model tests on Python 3.11 in 0.377 s. Network access was denied in pytest.
Ruff and the ten-file format check passed. All 17 original members, LLB,
four copied TPG sources and the existing Word document retained their hashes.

## Pressure reading and complete VAM-A sequence continuation

The [pressure report](ELYSE_ACQ_PRESSURE_READ_TRACE_2026-10-02.md) adds
89 direct nets across thirteen diagram identities. This includes both
pressure caller frames, all custom separator/parser diagrams, the complete
VAM-A loop body, its three ordered frames and both publication-error cases.
The first frame copies pressure banks into fields 10/11/20; the next
frame preserves them while adding other readings. The two VAM-A writers
are ordered in one sequence, not independent racing writers.

The pressure callers discard sensor Status. Their returned errors feed
handlers independently of numeric assignment. A VAM-A publication error
sets stop banks 30 and 45, but the independent stop snapshot does not
guarantee same-iteration consumption. The loop Wait is 80 ms, not a hard
stop deadline. The custom separator loop replaces periods with commas
before a localized LabVIEW numeric conversion; Python numeric returns
remain supplied fixtures rather than an approximate parser.

The original facet register now names 40 identities and the separate vendor
register names 50. These are not fully closed diagrams or a percentage of
the original 533-row census. Next paths are input-bank producers and their
physical meanings, all permission/interlock consumers, cross-loop timing,
stop/restart and native screenshot reconciliation. No Supervision review,
VI run/save, remote control or apparatus command occurred.

The final affected source/model/register selection passed 23 tests in
23.93 s; the Acquisition controller/projection selection passed 216 tests
in 3.08 s, and 163 isolated VI models passed on Python 3.11 in 0.306 s.
The earlier 293-test source/mutation regression passed in 524.92 s before
the final VAM-A addition; it is not claimed as a full later-suite rerun.
Ruff and the eleven-file format check passed. Original 17 members, LLB,
both newly examined vendor sources and the existing Word file are unchanged.
