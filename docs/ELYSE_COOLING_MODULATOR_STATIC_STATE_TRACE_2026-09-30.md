# Cooling–Modulator state chain across saved Supervision and ACQ VIs

## System and boundary

The question is whether a Supervision cooling request, ACQ software `OK`
flags, displayed Modulateur stage indicators, and the ACQ water-flow guard
form one coherent safety decision. The saved graphs show **separate request,
status, display, and input-guard paths**. This report combines only
hash-pinned static wire traces and pure Python projections; it is not a
runtime experiment, physical interlock test, or certification of the
deployed binaries. No VI, PSP variable, XP computer, or NI card was operated.

## Ordered software path and independent feedback

| Stage | Saved-program observation | Limit |
|---|---|---|
| Supervision operator request | `Page Fluides` event 14 forwards `Marche régulation`/`Arrêt régulation` to DPS[0,1] only if no local DPS bit and no Canon/Section temperature-step button is asserted. | Request serialization, not flow or safety permission. [Wire trace](ELYSE_SUP_FLUIDES_REQUEST_GATE_2026-09-30.md). |
| ACQ dispatch | First asserted DPS field 0 selects cooling-start event 3; field 1 selects cooling-stop event 4. | Static selector match, not PSP delivery or acknowledgement. [Crosswalk](ELYSE_SUP_ACQ_CORRESPONDENCE_2026-09-29.md). |
| ACQ cooling start | Event 3 sends C3 cooling-start and C4 low-level-Modulator start/reset command pairs, then assigns EPS[2] (`cooling OK`) and EPS[8] (`GENERAL Mod. OK`) True from literal constants. | Output-loop scheduling and physical readback are unresolved. The event does not directly reference C3/C4 input banks. [Start frames](ELYSE_ACQ_COOLING_START_COMPLETION_2026-09-30.md). |
| EPS transport and UI | A sibling ACQ I/O loop publishes local EPS; Supervision reads it; Page Modulateur copies EPS[8,14,20,26,32] to its five `OK` indicators. | The saved path exists, but delivery time, freshness, UI color, and relay truth are unmeasured. [Publish/read topology](ELYSE_ACQ_EPS_PUBLICATION_CONCURRENCY_2026-09-30.md), [indicator wires](ELYSE_SUP_MODULATOR_OK_FROM_EPS_2026-09-30.md). |
| EPS return ingest | ACQ's runtime Timeout event reads the entire remote Supervision EPS cluster back into its local EPS. | A stale returned snapshot could replace a local event-frame flag; whether this occurs depends on unmeasured PSP and loop scheduling. [Complete local-writer audit](ELYSE_ACQ_EPS_WHOLE_CLUSTER_INGEST_2026-09-30.md). |
| Independent raw input display | Page Fluides copies six C3 and three C4 input bits plus two C1 analog temperature readings. Four displayed Boolean source bits are also the ACQ flow-guard inputs. | Input polarity, sensor validity, and cross-host snapshot equivalence are unresolved. [Display map](ELYSE_SUP_FLUIDES_DISPLAY_FLOW_CORRESPONDENCE_2026-09-30.md). |
| ACQ flow trip | Timeout event 0 evaluates `(C4[19] OR C4[38]) AND ((NOT C3[0]) OR (NOT C3[6]))`; its True arm commands C3 cooling-stop lines and assigns cooling fault/stop flags. Its selector has no direct `ACTION`/EPS gate and the Event Structure timeout input is 20 ms. | It is in the same Event Structure as start event 3, so it cannot run inside event 3's final 5000-ms wait. Repetition cadence and independent hardware protections are unknown. [Guard and stop sequence](ELYSE_ACQ_COOLING_FLOW_SAFETY_TRACE_2026-09-29.md). |

## Bounded status-state comparison

The pure assignments below assume each named saved frame executes in the
stated order and no other writer intervenes. They are **local Boolean
snapshots**, not observed physical or necessarily delivered PSP states.
In particular, the Timeout event's whole-cluster remote EPS ingest can
intervene between rows; the table does not assert persistence.

| After saved frame | Cooling fault EPS[1] | Cooling OK EPS[2] | Cooling stop OK EPS[5] | GENERAL Mod. OK EPS[8] |
|---|---:|---:|---:|---:|
| Cooling-start event 3 frame 10 | False | True | False | True |
| Then operator cooling-stop event 4 frame 5 | False | False | True | **unchanged True** |
| Or, instead, timeout flow-trip frame 5 | True | False | True | **unchanged True** |
| Then General Modulator stop event 6 frame 15 | unchanged | unchanged | unchanged | False |

The [General-stop status wire check](../tools/validate_acq_general_stop_status.py)
also finds EPS[14,20,26,32] set False and five corresponding stop-OK fields
set True in event 6 frame 15. Thus the saved software can represent
`cooling fault=True` and `GENERAL MOD OK=True` *between* a flow trip and a
separate General-stop status update. Since Page Modulateur copies EPS[8],
its `GENERAL MOD OK` field has the same logical source. This does **not**
prove that the installed UI actually shows this combination, that the
Modulator remains energized, or that a separate physical interlock fails.
The record does show that `GENERAL MOD OK` is **not** an independent hardware
readback at the traced display assignment.

The pure [integration replay](../tests/device_servers/control/test_elyse_cooling_chain_projection.py)
tests request → dispatch → start flags → raw input display/guard → trip
flags → General-stop flag. A separate branch supplies an older remote EPS
snapshot before the Timeout trip frame and demonstrates the different
local EPS[8] result. This is an explicit hypothetical input, not a measured
PSP race. The replay intentionally omits PSP timing, card writes,
contact polarity, and permissive policy. The existing hardware-adapter-
capable `cooling.stop` plan omits one 150-ms wait from ACQ event 4; this
discrepancy is documented but not silently changed under simulation-only
scope.

## Remaining proof obligations

- Confirm deployed VI/LLB and shared-variable versions against these saved
  archives; replay requests on a non-actuating test transport with explicit
  PSP write/read acknowledgements, timestamps, and stale-data states.
- Determine electrical polarity and independent interlock response from
  wiring/commissioning records; do not infer it from raw Boolean labels.
- Trace all active EPS writers and Supervision UI enable/disable logic before
  treating any displayed `OK` field as an operational permissive.
- Model the Event Structure and sibling I/O loop as separate schedulers;
  verify cancellation, queued stop-event behavior, and error paths.
