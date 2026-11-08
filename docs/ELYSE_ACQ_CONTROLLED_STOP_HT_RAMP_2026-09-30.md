# Acquisition controlled-stop HT command ramp: saved VI wire trace

## Question and boundary

What does the copied ACQ controller do to the HT *command* when the
outer-frame-3 controlled-stop branch is entered? This note addresses the
saved LabVIEW graph only. It does not measure the HT supply, define a safe
operating procedure, or establish that the deployed binary is identical.
The source is the hash-pinned `0_ACQ_ELYSE_XML_sha6fe8.zip`; no VI, PSP
variable, XP computer, or NI card was operated.

The [separate stop-ingress audit](ELYSE_ACQ_STOP_TCP_ERROR_TRACE_2026-09-29.md)
finds that checked PSP-write error paths set `stop` and `TCP ED` True,
but do not set `Arrêt général` True. The seven-phase sequence therefore
must not be assumed to follow every runtime-loop stop request.

## Observed control path

Outer sequence `359` frame 3 diagram `41058` reads `TCP ED` local
`paramIdx=45` into Case `43488`. Its False arm is empty. The True arm
contains a loop with an `Arrêt général` (`paramIdx=47`) Case `52981`.
The latter's True arm contains seven ordered stop phases in sequence
`51954`. Phase 0, diagram `60323`, contains While loop `18613`.
This is a *conditional* branch: the ramp does not run merely because the
normal acquisition loops finish.

Within each HT-ramp loop iteration, unbundle `41650` reads field 0 of
local `paramIdx=12`, previously identified by direct PSP wires as the
`C9NI6703` command cluster in the
[local PSP map](ELYSE_ACQ_LOCAL_PSP_WIRE_MAP_2026-09-29.csv).
Comparator `44754` tests that logical value
`< 6.6`. Its result selects Case `47558`:

| Comparator result | Saved branch | Loop test |
|---|---|---|
| False, command `>= 6.6` for ordinary finite numbers | Subtract literal `0.1`, bundle the result into C9 field 0, write local C9; a `Wait (ms)` receives literal `500`. | `False`, continue. |
| True, command `< 6.6` | No C9 field write or wait in this arm. | `True`, exit (`lTst objFlags=65537`, Stop-if-True). |

The comparator's True arm is empty of local-reference writes. The stop
terminal is wired only from the Case's Boolean result; no separate
iteration-count exit lies on that wire. The exact 6.6 comparison, 0.1
subtraction, 500-ms wait, field-0 bundle, and Case polarity are checked
by [`validate_acq_controlled_stop_ht_ramp.py`](../tools/validate_acq_controlled_stop_ht_ramp.py).

Two further local assignments occur in the loop body: the current C9[0]
value is mirrored into numeric local `paramIdx=48`, and literal `6.0` is
written to numeric local `paramIdx=50`. Their front-panel/business labels
have **not** been independently resolved. Nodes within one iteration are
not ordered by their positions on the diagram; this trace does not claim
that either auxiliary local is written before the comparison or C9 update.

The same numeric local `paramIdx=50` receives literals **6, 5, 4, 3, 2,
1, 0** in the seven successive outer stop phases. This pattern is
consistent with a phase countdown, but that role is an inference until
its front-panel label and consumers are independently traced.

## Phase 2 HT-supply stop command

The separate [phase-2 validator](../tools/validate_acq_controlled_stop_ht_supply.py)
pins nested sequence `49098` and its three ordered frames. Frame 0
assigns logical `C4_OUT_DIO96[19]=False` and contains a 150-ms wait;
frame 1 assigns the same field `True`; frame 2 waits 1000 ms. The
150-ms wait is **inside frame 0** of this nested sequence, correcting an
earlier description that called its ordering relative to the nested
sequence unresolved. The local output assignment and wait within frame 0
can execute concurrently; the saved graph does not establish an exact
150-ms electrical pulse width. The phase contains no direct PSP writer.
The sibling read/write loop's scheduling and physical line polarity remain
outside this static result.

## Phase 1 NI6602 pulse synchronization

The independently hash-pinned
[`validate_acq_controlled_stop_pulse_sync.py`](../tools/validate_acq_controlled_stop_pulse_sync.py)
checks ordered sequence `47655`, frames `47671`, `47989`, `48537`.
The first two frames read task-reference fields 3 and 4 from local
`paramIdx=21` in that order. Each While loop reads DAQmx property code
`6414` (`CO.GénImpTerminée`) and stops when the property equals `True`
**or** its zero-based loop index is `>40`. Each body contains a 1-ms
wait. After each loop, its task reference goes to `DAQmx Stop Task.vi`,
whose error output is wired into `Clear Errors.vi`. The third frame
waits 1000 ms. The phase therefore **attempts** to stop each task even
if the poll exits by count rather than confirmed pulse completion.
It does not prove that either Stop Task call succeeds, that the
`Clear Errors.vi` call represents a safe recovery policy, or that the
hardware pulse stops at a particular elapsed time.

`controlled_stop_pulse_poll_exits` transcribes only the Boolean loop
predicate for offline replay. Its input validation is Python-only.

## Phase 3 magnet-command and line-bit reset

The [phase-3 raw-wire validator](../tools/validate_acq_controlled_stop_magnets.py)
checks a four-frame sequence. Frame 0 sets local C6 command fields
`0–7,9` and C7 fields `0,1,3–9` to numeric zero; frame 1 waits 1000 ms.
Frame 2 sets 18 selected local C3 output fields
`9,11,15,17,21,23,25,27,29,31–39` to Boolean False; frame 3 waits
1000 ms. Fields not listed are preserved by each Bundle By Name node.
The local-bank-to-PSP identification is established separately in the
[wire map](ELYSE_ACQ_LOCAL_PSP_WIRE_MAP_2026-09-29.csv). These are
*command assignments*, not current/field readback or proof that the
corresponding magnet outputs reached zero. The C3 fields' electrical
polarity and the sibling card-writer timing remain unknown. Python
records the field sets and frame waits without sending them.

## Phases 4–6: stage pulses, cooling, exit

The [phase-4 raw-wire validator](../tools/validate_acq_controlled_stop_stage_pulses.py)
checks 15 ordered frames. The local C4 output fields `8,17,6,4,1` each
receive False in one frame and True in the next, followed by an
explicit interstage wait of `1000,1000,1000,2000,1000 ms`, respectively.
Each False frame also contains a Wait node. The separate
[sequence-tunnel validator](../tools/validate_acq_controlled_stop_wait_tunnels.py),
added on 2026-10-01, traces all five inputs to the parent phase's literal
`150 ms`. The constant is defined in `nodeList`, while `zPlaneList`
contains only its terminal reference; reading the latter alone missed
the value. Sequence tunnel `42404` links the parent input to each
frame's own terminal. This resolves the requested software wait, not
electrical pulse width or card-write acknowledgement.
These five C4 field/value pairs match normal ACQ event-6 General
Modulator stop, but the [two-path comparison](ELYSE_SUP_ACQ_DISTINCT_STOP_PATHS_2026-09-30.md)
finds important differences before and after the pulses.

The [phase-5 raw-wire validator](../tools/validate_acq_controlled_stop_cooling.py)
checks eight ordered frames. Local C3 output field 1 is assigned
False→True, followed by a 400-ms wait. Field 4 is assigned False→True.
Each of the next two frames independently repeats the same local status
assignments: EPS fields `3,2,5,1` become `False,False,True,False` and
DPS field `1` becomes False. A final frame waits 100 ms. Wait nodes
also occur in the first, fourth and fifth frames (zero-based 0,3,4).
The same 2026-10-01 tunnel validator follows them through sequence
tunnel `54282` to that phase's separate literal `150 ms`. Frame 4
therefore waits 150 ms while restoring C3[4] to True; it is not another
False-command frame. No direct PSP writer occurs inside this phase.
The duplicate status frames are observed in the saved graph, not
inferred acknowledgements or readback.

The eight resolved duration paths are:

| Phase | Frames | Source terminal | Sequence tunnel DCO | Requested Wait |
|---|---|---|---|---|
| 4 | 0,3,6,9,12 | 47276 (`sRN` 7985, hex `00000096`) | 42404 | 150 ms each |
| 5 | 0,3,4 | 52924 (`sRN` 52163, hex `00000096`) | 54282 | 150 ms each |

Phase 4's explicit Wait inputs sum to `5×150 + 4×1000 + 2000 = 6750 ms`;
phase 5's sum is `3×150 + 400 + 100 = 950 ms`. These sums describe
ordered software frames only. Same-frame assignments have no
wait-after-write dependency established by this trace, and the sibling
card-writer loop remains separately scheduled. Neither sum is measured
shutdown duration. The 20 missing native nested-frame screenshots
reported in the 2026-10-01 Word document remain missing; this raw-wire
result does not replace that visual coverage requirement.

The [phase-6 raw-wire validator](../tools/validate_acq_controlled_stop_completion.py)
checks `paramIdx=50` assigned zero, `stop urgence` (`paramIdx=46`)
assigned True, `Arrêt général` (`paramIdx=47`) assigned False, and a
1000-ms wait. **All four are independent nodes in the same final frame**;
there is no wait-before-flag wire. Both outer-frame-3 While loops test
`stop urgence` through local reads and Stop-if-True terminals, but they
may see the flag on different iterations. Thus this frame does not
establish that either loop continues I/O for a full second after the
flag assignment.

## Bounded interpretation

For an initial logical command exactly 6.6, the False arm decrements it
once, then a later iteration sees a value below 6.6 and exits. The saved
code compares the *command*, not a measured HT voltage. The 500-ms literal
is a minimum software wait in the decrement arm, not measured AO-output
cadence or supply ramp rate; a sibling I/O loop performs the card write.
Non-finite values, read/write failures, concurrent local/PSP updates,
stale state, and interruption behavior remain unverified. The graph does
not justify using this ramp as a certified shutdown procedure.

The pure Python `project_controlled_stop_ht_ramp` returns one logical
record per loop iteration, including the C9 field write (if any), 500-ms
wait marker, and the two auxiliary local assignments. It performs no
output or transport operation. Its finite-input validation and iteration
cap are **Python-only** safeguards, not features attributed to LabVIEW.
`CONTROLLED_STOP_HT_SUPPLY_FRAMES` and `CONTROLLED_STOP_PHASE_MARKERS`
record the separately verified phase-2 command and seven numeric literals.

## Reproduction

```powershell
python tools/validate_acq_controlled_stop_ht_ramp.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
python tools/validate_acq_controlled_stop_ht_supply.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
python tools/validate_acq_controlled_stop_pulse_sync.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
python tools/validate_acq_controlled_stop_magnets.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
python tools/validate_acq_controlled_stop_stage_pulses.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
python tools/validate_acq_controlled_stop_cooling.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
python tools/validate_acq_controlled_stop_completion.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
python tools/validate_acq_controlled_stop_wait_tunnels.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
python tests/scripts/test_elyse_acq_stop_wait_tunnels.py
python -m unittest tests.device_servers.control.test_elyse_acq_shutdown_projection
```
