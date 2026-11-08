# Five saved Supervision DPS request gates

## System and scope

The saved Supervision root has five fieldwise UI producers for the 29-Boolean
`DPS` request cluster; a sixth local writer ingests the whole cluster from
PSP. The [complete local-writer census](ELYSE_SUP_DPS22_PRODUCER_CENSUS_2026-09-30.md)
pins this distinction. The five event-specific validators below follow
raw Boolean gate wires and direct request-field assignments in the copied
`0_SUP_ELYSE.vi`. Neither program was run and no PSP/NI path was used.

| Supervision page event | Request fields | Saved DPS-write gate | Additional branch use |
|---|---|---|---|
| 14 `Fluides` | 0–1 | All 29 sampled local DPS bits False **and** four temperature-step buttons False | Temperature buttons select separate C8 setpoint path. [Trace](ELYSE_SUP_FLUIDES_REQUEST_GATE_2026-09-30.md). |
| 18 `Modulateur` | 2–12 | All 29 sampled local DPS bits False | No stage-EPS/C4 check in this event. [Trace](ELYSE_SUP_MODULATOR_REQUEST_GATE_2026-09-30.md). |
| 16 `HF` | 13–14 | All 29 sampled local DPS bits False **and** eight HF adjustment arrows False | Arrow activity selects the separate C8 adjustment path. [Validator](../tools/validate_sup_hf_request_gate.py). |
| 15 `HT` | 15–19 | All 29 sampled local DPS bits False **and** eight HT/preamplifier arrows False | Arrow activity selects the C8/C9 adjustment path. [Trace](ELYSE_SUP_PAGE_HT_REQUEST_GATE_2026-09-30.md). |
| 17 `Alimentations` | 20, 21, 23 | All 29 sampled local DPS bits False | No C4/EPS check in this event. [Trace](ELYSE_SUP_MAGNET_REQUEST_GATE_2026-09-30.md). |

For `Page HF`, the [new raw-wire validator](../tools/validate_sup_hf_request_gate.py)
checks event 16 UID `53716`: `DPS` local `paramIdx=176` → Cluster To Array
→ `Or Array Elements`; eight `Page HF` arrow fields
`[2,4,3,1,14,16,15,13]` → Build Array → `Or Array Elements`; both Boolean
results → `Or` → Case UID `53782`. Its false arm UID `53851` writes
`Page HF[7] Marche att./déph.` to `DPS[13]` and
`Page HF[6] Arrêt att./déph.` to `DPS[14]`, publishing the bundle to
`ni.var.psp://localhost/SUPERVISION/DPS`. The true arm UID `55584`
contains the adjustment branch and no local DPS reference. These are
source-terminal and branch facts, not operator action or hardware outcome.

## Mechanism and failure boundary

The five gates act on a *sampled local DPS cluster*. They are not a
cross-host atomic lock: the saved graph does not establish snapshot
freshness, simultaneous-write resolution, PSP delivery, or command
acknowledgement. An event may bundle several True buttons at once;
Acquisition's timeout dispatcher selects only the lowest asserted
`DPS[0..23]` bit from one read, then an implemented handler locally clears
its own request and attempts DPS publication in a later ordered frame.
Whether other simultaneous bits are later observed is a scheduling
question, not a guaranteed queue.

The aggregate gate includes bit 22, although none of these five UI producers
explicitly assigns it. ACQ has a selector arm for `DPS[22]` but no registered
handler or handler-local reset. If another writer or imported PSP state leaves
it True, **all five page events' DPS-write branches are skipped** on their
sampled local state; any pre-existing `DPS[23]` may also be bypassed by
ACQ's first-True selection. This is a conditional liveness issue, not an
observed fault or an assertion about a hardwired safety chain.

The pure [Python request projections](../DeviceServers/control/elyse_acq/supervision_requests.py)
model each gate and field assignment without publishing or actuating.
They intentionally do not infer radioprotection permission from the absence
of a gate in these particular event branches.

```powershell
python tools/validate_sup_dps_writer_census.py Supervision/analysis/source_exports/0_SUP_ELYSE_XML_sha2257.zip
python tools/validate_sup_hf_request_gate.py Supervision/analysis/source_exports/0_SUP_ELYSE_XML_sha2257.zip
python -m unittest tests.device_servers.control.test_elyse_supervision_requests
```
