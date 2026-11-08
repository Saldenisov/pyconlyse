# ELYSE Supervision ↔ Acquisition business-logic correspondence (2026-09-29)

## Verdict and boundary

The two copied LabVIEW programs have a coherent **division of roles**, not a
one-to-one VI correspondence. Supervision creates operator requests and local
setpoint/display changes; Acquisition reads shared-variable banks, runs timed
procedures, writes NI cards, and publishes status. The static evidence does
**not** prove that the installed pair currently executes every request, that
readback confirms each result, or that a Python replacement has equivalent
business behavior. No VI or hardware path was run for this comparison.

This explains the different event counts. Supervision has 34 main UI/timeout
cases: case 0 refreshes, cases 1–20 can command shared-variable banks (including
the DPS requests below), and cases 21–33 are local video, motor, file, and
optical-density workflows. ACQ has 26 runtime cases: case 0 polls/dispatches,
cases 1–2 handle the two beam lines, and cases 3–25 implement 23 DPS procedures.
Many Supervision bank writes are consumed by ACQ's polling/write loops, not by
an event case with the same name. The [event inventory](../Supervision/analysis/event_static_inventory.csv)
is the source for this classification.

NI-IMAQ/NI1409 driver parity is deliberately outside the target: the camera
will become an IP CCD. The required *business* contract still includes frame
availability/quality, ROI, centroid, thresholds, image save, and
centroid-driven autotune. Replacing the driver does not remove these workflows.

The [cooling–Modulator state-chain synthesis](ELYSE_COOLING_MODULATOR_STATIC_STATE_TRACE_2026-09-30.md)
assembles one bounded cross-host request, status, display, and flow-guard
path from the detailed wire traces below. Its status table is a software
replay, not a physical or deployed-system result.

## Exact DPS request bridge

The [field crosswalk](../Supervision/integration_analysis/SUP_ACQ_DPS_FIELD_CROSSWALK_2026-09-29.csv)
contains 24 DPS fields in the procedure-dispatch range. For **23 fields**, a
Supervision event's source control is wired into the named DPS bundle field and
a same-intent Acquisition event case exists. The Supervision source wires were
checked against the frame-keyed [static audit](../Supervision/analysis/all_frame_static_audit.jsonl);
bank indices and labels against the copied ACQ [field inventory](ELYSE_ACQ_SHARED_VARIABLE_FIELDS_2026-09-28.csv);
case numbers and names against the [ACQ procedure catalog](../Supervision/integration_analysis/ACQ_PROCEDURE_UI_TRACEABILITY.csv).
The [five-page DPS gate matrix](ELYSE_SUP_DPS_REQUEST_GATE_MATRIX_2026-09-30.md)
now joins the producer census and individual gate traces: every identified
fieldwise page producer requires all 29 sampled local DPS bits to be False,
with extra adjustment-button gates on Fluides, HF, and HT. This is local
request serialization, not a cross-host atomic queue or safety permission.
This is a static source-field/handler match, **not** an observed end-to-end
execution or acknowledgement. A separate inspection of the copied ACQ
[`0_ACQ_ELYSE.json`](../../ELYSE-ACQ-analysis/offline/lvkit_describe/0_ACQ_ELYSE.json)
found 25 timeout dispatcher frames (0..24): frame `i+1` sets both `Value=True`
and `Val(Sgnl)=True` on the corresponding local procedure control for DPS bank
index `i`. Frame 23 addresses the orphaned magnet PT control, for which no
event handler was recovered. The saved [native timeout-frame screenshot](../../ELYSE-ACQ-analysis/runs/20260922-085500-+0200/images/EV-ACQ-0020-timeout2-dps-command-ingress-ni6602.png)
shows `Search 1D Array(True)` followed by `Increment` before this selector:
within the 24 analyzed procedure fields, the lowest asserted index is
selected; no asserted field yields selector 0 and no procedure. The five
trailing DPS schema fields are not yet part of the Python snapshot model.
The independent
[dispatcher validator](../Supervision/integration_analysis/validate_acq_dps_dispatch.py)
passes on the copied description (SHA-256
`CE4C2A711B68FE6246210E4FE90166C994C68A3B41D41DBDB5B68C6AE39758B5`).
This checks the *normal static dispatch chain*, not its runtime guard,
repeated polling, clearing, error handling, or acknowledgement.
The later [handler-reset audit](ELYSE_ACQ_DPS_HANDLER_RESET_ORDER_2026-09-30.md)
closes one part of that gap: all 23 implemented event handlers locally
clear their own DPS bit and attempt a DPS PSP write in the next ordered
frame. Delivery, scheduling of later requests, and success acknowledgement
remain unproven.
The [validator](../Supervision/integration_analysis/validate_dps_crosswalk.py)
checks all 23 source-control wires, their shared-variable write reference,
the 24 ACQ DPS labels, and the 23 corresponding ACQ event names; it passes on
the copied artifacts.

| Supervision event | DPS request fields | ACQ event cases | Static result |
|---|---:|---|---|
| 14, `Page Fluides` | 0–1, cooling start/stop | 3–4 | 2/2 field and handler matches |
| 18, `Page Modulateur` | 2–12, general/stages/reset | 5–15 (nonsequential field order) | 11/11 matches |
| 16, `Page HF` | 13–14, HF enable/disable | 18–19 | 2/2 matches |
| 15, `Page HT` | 15–19, HT start/reset/stop and pulse start/stop | 20–24 (nonsequential field order) | 5/5 matches |
| 17, `Page Alimentations` | 20, 21, 23: magnet start/zero/stop | 16, 25, 17 | 3/3 matches |

The [Page HT request-gate trace](ELYSE_SUP_PAGE_HT_REQUEST_GATE_2026-09-30.md)
adds the Boolean branch condition for those five Supervision DPS writes:
the current 29-field local DPS request cluster and eight HT adjustment
buttons must all be false. This is UI request serialization, not a proven
radioprotection interlock or proof that ACQ executes a request.
The [bounded HT-start path](ELYSE_SUP_ACQ_HT_START_STATIC_PATH_2026-09-30.md)
continues one of these requests through the ACQ timeout selector and event
20. It identifies no direct C4-input check in those particular branches,
without establishing hardware permission or a deployed-code match.
The [Page Modulateur request trace](ELYSE_SUP_MODULATOR_REQUEST_GATE_2026-09-30.md)
finds a simpler gate: event 18 writes its 11 DPS request fields only when
no bit of its local DPS cluster is asserted. That UI branch does not
directly check prior-stage EPS statuses or C4 input state; it does not prove
that the corresponding ACQ procedures accept out-of-order operation.
The [Page Alimentations request trace](ELYSE_SUP_MAGNET_REQUEST_GATE_2026-09-30.md)
finds the same any-DPS-bit serialization for the three magnet requests,
without a direct C4 or EPS gate in that event. A pending orphaned
`DPS[22]` would conditionally suppress a new magnet-stop UI write, but
normal reachability of that bit and any physical consequence are unproved.
The [cross-host magnet-status chain](ELYSE_SUP_ACQ_MAGNET_STATUS_CHAIN_2026-09-30.md)
adds the three ACQ completion-frame EPS assignments and bounds which of
those flags the saved Supervision root reads directly.
The [Page Fluides request trace](ELYSE_SUP_FLUIDES_REQUEST_GATE_2026-09-30.md)
finds that event 14 writes cooling start/stop `DPS[0,1]` only when no local
DPS bit and none of four Canon/Section temperature-step buttons is asserted.
An active temperature button selects the separate C8 setpoint branch; an
already-pending DPS bit without a temperature button skips this event's
cooling write. This is request serialization, not proof of water flow or
an ACQ cooling permissive. The four one-hot temperature actions change
Canon/Section setpoints by ±0.1 and write C8[1]/[2] without a clamp in
those case frames; multi-button selector behavior remains unproved.
The [ACQ cooling-start trace](ELYSE_ACQ_COOLING_START_COMPLETION_2026-09-30.md)
shows that event 3's 12 ordered frames pulse C3 cooling-start outputs 0/3,
then C4 low-level-modulator start/reset outputs 0/2, and set local EPS
`Marche refroidissement OK=True` and `Marche GENERAL Mod. OK=True` from
literals. These flags are software assignments, not flow or relay readback;
the separate ACQ timeout flow check cannot run in the same Event Structure
while event 3's sequence is still active.
The [ACQ cooling-stop trace](ELYSE_ACQ_COOLING_STOP_COMPLETION_2026-09-30.md)
finds C3 stop-output pairs 1/4 and a fifth wait of 150 ms after the Section
restore assignment. The current hardware-adapter-capable Python
`cooling.stop` plan omits that wait; the simulation-only trace records it
without changing the executable plan. Event 4 clears cooling OK, but does
not directly clear `Marche GENERAL Mod. OK` in its completion frame. The
independent ACQ timeout flow-trip status frame also clears cooling OK and
sets cooling fault, without a direct EPS[8] General Mod. OK assignment;
start→trip local-status replay therefore retains EPS[8]. The separate ACQ
General-stop event 6 frame 15 explicitly clears EPS[8,14,20,26,32] and
sets five stop-OK flags; see the [raw-wire check](../tools/validate_acq_general_stop_status.py).
The [Page Fluides display cross-check](ELYSE_SUP_FLUIDES_DISPLAY_FLOW_CORRESPONDENCE_2026-09-30.md)
shows nine direct raw C3/C4 input projections and two C1 analog-temperature
readbacks, not EPS-derived success lamps. Four displayed raw bits—C3[0,6]
and C4[19,38]—are also inputs to the separate ACQ timeout cooling-flow
guard; matching indices do not establish cross-host freshness or electrical
polarity.
The [parallel EPS-publisher trace](ELYSE_ACQ_EPS_PUBLICATION_CONCURRENCY_2026-09-30.md)
finds the event/timeout loop and the EPS PSP-writing I/O loop as siblings.
It is therefore possible for event 3's literal EPS `OK` assignments to be
published during its final 5000-ms wait, before that Event Structure can
re-enter its timeout flow guard. This is a scheduling possibility from the
saved graph, not observed latency, delivered PSP data, or hardware safety.
The copied Supervision VI has a matching EPS PSP read into local
`paramIdx=175`. The [Modulateur OK projection](ELYSE_SUP_MODULATOR_OK_FROM_EPS_2026-09-30.md)
maps EPS[8,14,20,26,32] directly to the five displayed stage-OK fields.
Thus event 3's literal EPS[8] assignment can feed `GENERAL MOD OK`, while
cooling stop and timeout flow-trip frames do not directly clear that bit;
actual UI state and hardware readiness remain unobserved.
An [offline chain test](../tests/device_servers/control/test_elyse_cooling_chain_projection.py)
composes the proven Fluides DPS request, ACQ first-True dispatch, literal
cooling-start statuses, raw Page Fluides display, flow-trip predicate, and
trip statuses. It checks field correspondence only; it does not emulate
PSP timing, error delivery, electrical polarity, or hardware permission.
The [five-stage entry audit](ELYSE_MODULATOR_START_STAGE_ENTRY_2026-09-30.md)
finds that ACQ's General, Heating, PREMA, Relay HT, and Focal root event
handlers likewise enter their ordered sequences on `NewVal=True`, without
another root Case driven by preceding-stage EPS or C4 input. This bounds
software entry logic, not physical permissives or nested subVI behavior.
The [impulsion status recheck](ELYSE_ACQ_IMPULSION_STATUS_ASYMMETRY_2026-09-30.md)
finds that event 24 stop writes EPS[42] and EPS[52], but not its
nominal stop-OK EPS[55]. Saved Supervision root has no direct EPS[42/55]
consumer; the source asymmetry must not be silently repaired in Python.
The [cross-event replay](ELYSE_ACQ_HF_PULSE_STATUS_COLLISION_2026-09-30.md)
adds that HF-power start event 18 can leave EPS[39] True while pulse-stop
event 24 sets EPS[42] True. These are contradictory local status bits,
not a measured chassis state or a proven operator-display fault.
The ACQ outer-frame-3 [controlled-stop HT ramp](ELYSE_ACQ_CONTROLLED_STOP_HT_RAMP_2026-09-30.md)
is a separate conditional path: `TCP ED=True` and `Arrêt général=True`
select a seven-phase stop sequence whose first phase decrements logical
C9[0] until its command is `<6.6`. Its later phases and loop exit have
now been traced by raw wires. This is **not** the same as Supervision
`Arrêt MOD` → `DPS[3]` → ACQ event 6; the
[two-stop-path comparison](ELYSE_SUP_ACQ_DISTINCT_STOP_PATHS_2026-09-30.md)
keeps those triggers and effects separate. No Supervision action has yet
been proven to set the two outer-stop selector locals, and deployed
completion remains unverified.

`DPS[22]` is `X Alimentation aimant = PT`. The ACQ timeout dispatcher includes
this request (one-based selector arm 23), but the recovered ACQ Event Structure
has **no corresponding handler**: its target `ddoUID=66459` is absent from all
26 event registrations in the [raw UID audit](ELYSE_ACQ_DPS_EVENT_REGISTRATION_AUDIT_2026-09-29.md). The
Supervision `Page Alimentations` bundle exposes start, stop, and zero, not PT.
The [root DPS-writer census](ELYSE_SUP_DPS22_PRODUCER_CENSUS_2026-09-30.md)
independently checks all six local DPS writers: five page bundles assign
fields 0–21 and 23, never field 22; the sixth ingests a whole PSP cluster.
This bounds the absent normal UI producer without excluding an external
PSP writer or an unexpected imported value.
This is an orphaned intent in the visible code, not evidence of a working
procedure. `DPS[24..28]` are other schema fields and are not included in this
24-field procedure-dispatch comparison.

## Other cross-computer paths

| Capability | Supervision-side evidence | Acquisition-side evidence | Conclusion |
|---|---|---|---|
| C8/C9 analog setpoints | Events 2, 3, 7, 12–16 write named C8/C9 command fields; HT uses C9 AO0, temperatures C8 AO1/2, HF phase/attenuation C8 AO3/4, preamp C8 AO6, slits C9 AO2/3, translators C9 AO4–6. | Runtime reads C6–C9 PSP banks and writes NI6703 tasks; [channel map](../legacy/xp_acq_agent/data/channel_map.csv) agrees on these bank indices and physical channels. | Bank/index chain is identified. Numeric transforms, simultaneous writers, error behavior, and physical confirmation are not fully matched. |
| C5 digital diagnostics | Supervision events 3–5 and 8–13 update C5 output fields for translators/screens, laser mirror, Faraday, and slit supply. | Runtime reads C3–C5 output banks and writes DIO96. | Logical fields align by index; pulse/latch polarity, guards, and readbacks remain unverified. |
| NI6602 timing | Supervision frequency/synchronization events edit the C10–11 command bank. SUP itself handles selector >16 through `Dev1/ctr0..7` and C11 fields 16–31. | ACQ timeout handles integer selector 1–16 through `/10/ctr0..7` and C10 fields 0–15. The two controller graphs and their limits are in `ELYSE_SUP_ACQ_NI6602_OWNERSHIP_2026-09-30.md`. | UI producers, values outside 1–32, DAQmx update/restart outcomes, and PSP race/acknowledgement are not yet reconciled. |
| Direct/deviated line | In events 19/20, frame 1 conditionally transfers line setpoints into local C6/C7 banks (and C8 for the direct line) under the [arrow-bit guard](ELYSE_SUP_BEAM_LINE_TRANSFER_GUARD_2026-09-30.md); frame 2 writes four distinct PSP banks, `C6NI6703`–`C9NI6703`, regardless of that guard. See the [direct frame-1](../Supervision/analysis/labview_print_hidden_frames/0__SUP__ELYSEd347.png), [direct frame-2](../Supervision/analysis/labview_print_hidden_frames/0__SUP__ELYSEd350.png), [deviated frame-1](../Supervision/analysis/labview_print_hidden_frames/0__SUP__ELYSEd375.png), and [deviated frame-2](../Supervision/analysis/labview_print_hidden_frames/0__SUP__ELYSEd378.png) prints. | ACQ [timeout frame 0](../../ELYSE-ACQ-analysis/runs/20260922-085500-+0200/images/EV-ACQ-0018-timeout0-command-psp-reads.png) reads C6–C9 PSP banks; its NI6703 writer commits their analog outputs. ACQ's [local event 1](../../ELYSE-ACQ-analysis/runs/20260922-085500-+0200/images/EV-ACQ-0022-event01-voie-directe.png) and [event 2](../../ELYSE-ACQ-analysis/runs/20260922-085500-+0200/images/EV-ACQ-0023-event02-voie-deviee.png) also rebuild line rows. | **Bank-level producer/consumer handoff is established statically** for both lines. The saved ACQ root has [no explicit `Val(Sgnl)` writer](ELYSE_ACQ_LINE_EVENT_TRIGGER_AUDIT_2026-09-30.md) for local events 1/2; external triggering and applied/readback result remain untested. |
| Telemetry and safety | Supervision timeout projects PSP measurements, status, warnings, and UI indicators. Seven [Page HT indicators](ELYSE_SUP_HT_STATUS_INPUT_PROJECTION_2026-09-30.md) and 12 [Page Radioprotection fields](ELYSE_SUP_RADIOPROTECTION_DISPLAY_AND_GRAPH_2026-09-30.md) are direct `C4_IN_DIO96` Boolean projections; eight radioprotection fields feed a separate graph aggregate. | ACQ reads NI6071E/DIO/NI6220/TPG300, publishes shared values, and independently reacts to water-flow failure. | Expected asymmetry: ACQ safety behavior need not have an operator UI event. These display/graph wires establish neither electrical polarity nor permission to energize. Freshness, concurrent bank ownership, and readback truth tables remain open. |
| Camera/motion/files | Camera/centroid/NI1409, New Focus motor/autotune, optical-density wheel, image and shot files are local Supervision workflows. | No equivalent ACQ procedure for these local devices/workflows is expected. | IP CCD replaces IMAQ adapter only; centroid/autotune and file semantics still require review and replay tests. |

## Concrete non-equivalences and proof gaps

1. **Orphaned magnet PT request:** dispatched DPS field without an ACQ event
   handler. Do not expose it as a working control.
2. **Direct/deviated event and outcome:** the saved LabVIEW prints identify
   the frame-2 PSP payloads as the four C6–C9 command banks for both events.
   The parser's `Refnum(43)`, `VuM Canon`, `Charge`, and `WCM5D` associations
   for these four writes are contradicted by those prints and must not drive
   the Python mapping. Frame 1 updates C6[0–5], C7[0,1,5,8], and C8[5] for
   the direct line; the deviated line updates C6[6–9] and C7[3,4,6,7,9].
   The [20-field analog crosswalk](../Supervision/integration_analysis/BEAM_LINE_ANALOG_COMMAND_CROSSWALK_2026-09-29.csv)
   records each visible field and channel. `Correcteur H5.Consigne` appears to
   feed C6[8], labelled `Réserve` in the card map; `Focale.Consigne` appears to
   feed C7[5], labelled `Cmd I Solénoïde`. These are label mismatches, not
   verified physical identities. Both line events republish C8/C9 even when
   their visible frame-1 branch does
   not edit those banks. The saved ACQ root has
   [no explicit signaling-property writer](ELYSE_ACQ_LINE_EVENT_TRIGGER_AUDIT_2026-09-30.md)
   for its local `Voie directe`/`Voie déviée` Value Change events; the confirmed cross-host
   path is through C6–C9 PSP banks. The [frame-1 guard](ELYSE_SUP_BEAM_LINE_TRANSFER_GUARD_2026-09-30.md)
   is now traced: only arrow-bit changes transfer UI setpoints, but frame 2
   republishes the four PSP banks regardless. Temporal ordering against other
   writers and physical/readback result still require separate proof.
3. **Shared-bank ownership:** ACQ writes initial C6–C9/C3–C5/DPS values, while
   Supervision also writes command banks. ACQ's separate local `Voie directe`
   and `Voie déviée` UI handlers can also republish C6–C9 (the copied
   [procedure inventory](../../ELYSE-ACQ-analysis/offline/reports/procedure_steps.md)
   describes this path); they should not be conflated with Supervision events
   19/20. Static source order cannot establish who wins a simultaneous
   update, reconnect, or partially failed write.
4. **HF coarse increment is native behavior:** the saved [selector-8 `>> Att HF`
   print](../Supervision/analysis/labview_print_hidden_frames/0__SUP__ELYSEd301.png)
   visibly adds `+1` to the attenuation setpoint. The [selector-4 `> Att HF`
   print](../Supervision/analysis/labview_print_hidden_frames/0__SUP__ELYSEd300.png)
   also adds `+1`; selector 1 subtracts `5`, selector 2 subtracts `1`.
   The asymmetry is in the copied LabVIEW source, not merely the parser.
   Whether it was intended is unknown. Python must preserve this behavior
   for parity unless an explicit product decision changes it.
5. **No end-to-end outcome proof:** 100/200 ms UI waits and ACQ procedure state
   changes are not physical acknowledgement. Requested, last commanded,
   measured, and stale/invalid states must remain distinct.
6. **IP CCD boundary:** NI1409/IMAQ initialization can be discarded, but
   centroid, ROI, threshold, image timing/quality, motor feedback, and safe
   autotune termination cannot be discarded with it.

## Current Python state is not operational parity

`DeviceServers/control/elyse_acq` contains a deterministic simulator and plans
for the 23 ACQ procedure cases 3–25. Its Tango facade explicitly rejects
production hardware mode; it does not create NI tasks or write cards.
The pure [Supervision setpoint reference model](../DeviceServers/control/elyse_acq/legacy_supervision_setpoints.py)
now covers the verified direct/deviated arrow arithmetic, transfer guard, and HT/HF adjustments,
but is not wired to Tango, PSP, the web UI, or hardware.
The pure [DPS bridge](../DeviceServers/control/elyse_acq/dps_bridge.py)
resolves all 23 matched bank fields to ACQ procedure plans and rejects
`DPS[22]`/magnet PT. It models the first-true choice for one 24-flag snapshot,
and now projects one handler's *local* request-bit reset for an explicitly
supplied 29-field snapshot. It does not implement polling, PSP publication,
later-request scheduling, acknowledgement, or execution.
The pure [Supervision status projection](../DeviceServers/control/elyse_acq/supervision_status.py)
copies seven HT and 12 radioprotection C4 input flags into display fields,
and evaluates the eight-input radioprotection graph aggregate without
interpreting safety or sending commands. The pure `counter_dispatch.py` now separates Acquisition C10 requests from
Supervision C11 requests and models the latter's changed-field selection;
`interlocks.py` transcribes the saved Acquisition cooling-flow Boolean guard.
Neither module observes PSP, schedules loops, acknowledges DAQmx, or actuates
hardware. The source-terminal audits and **20** targeted standard-library tests
pass; these are limited transfer checks, not operational parity.
The later [EPS writer-coverage audit](ELYSE_ACQ_EPS_WHOLE_CLUSTER_INGEST_2026-09-30.md)
adds an important feedback edge: ACQ publishes local EPS to Supervision but
also reads that entire remote EPS cluster back into its local state during
Timeout. The pure simulator can replace EPS from an explicitly supplied
snapshot; it does not model PSP freshness, write/read races, or read errors.
The additional Supervision Page HT/Modulateur request and status tests passed
**15** standard-library tests on 2026-09-30; their source-hash-pinned
validators passed separately. These counts cover different test selections
and should not be added as a single suite total.
`web/frontend/src/Elyse.js` labels commands as not transmitted, telemetry as
simulated, and command authority as absent. The ACQ procedure-engine, DPS
bridge, and pure setpoint test files passed **38/38** tests locally with Python 3.12/pytest
8.4.2 on 2026-09-29. These tests establish limited simulator/reference-model
behavior, not the Supervision-to-ACQ PSP bridge, full UI behavior, hardware
control, or source-code equivalence.

## Bounded conclusion

The 23 explicit Supervision-to-ACQ DPS procedure requests have a complete
**static label-and-handler crosswalk**. The saved native LabVIEW prints also
establish the direct/deviated C6–C9 PSP bank writes and their arrow-bit frame-1
transfer guard, separate from unconditional frame-2 republication. This supports
the basic architectural split. It does **not**
establish complete business-logic equivalence between the programs or current
Python implementation. The next passive checks are external VI Server
trigger possibilities for ACQ line events, other high-risk nested branch
matrices, and shared-bank ownership;
then replay traces can test requests, phases, published state, errors,
reconnect, and stop. No live command or DAQ write is required for that review.
