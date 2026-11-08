# Magnet request and local-status chain in saved SUP/ACQ VIs

## System and evidence boundary

The saved Supervision Page Alimentations event 17 can request magnet start,
stop, or zero setpoint through DPS. The saved Acquisition timeout selector
and event handlers turn those requests into ordered command procedures and
software status assignments. This note concerns *controller business logic*
in the two copied VIs, not NI driver internals, measured magnet current,
successful PSP delivery, or currently deployed binaries. No VI, PSP value,
or card was operated.

## Observation

The [Supervision request validator](../tools/validate_sup_magnet_request_gate.py)
checks the idle-DPS gate and three direct wires. The existing
[crosswalk](ELYSE_SUP_ACQ_CORRESPONDENCE_2026-09-29.md) checks the ACQ
dispatcher and event identities. A new
[ACQ completion validator](../tools/validate_acq_magnet_status.py) checks
the exact literal-to-field wires in the ordered completion frames:

| Operator request | DPS bit | ACQ event | Local EPS assignments in event completion frame |
|---|---:|---:|---|
| `Marche Aimants.` | 20 | 16 | 56=False, 58=True (`Marche alimentation aimant OK`), 64=False (`PT OK`), 67=False (`Arrêt aimant OK`) |
| `Arrêt Aimants` | 23 | 17 | 65=False, 58=False, 64=False, 67=True (`Arrêt aimant OK`), 61=False (`0V OK`) |
| `Aimant 0V` | 21 | 25 | 59=False, 64=False, 61=True (`0V OK`) |

Each completion frame also assigns its own DPS request bit False. The
[23-handler reset-order validator](../tools/validate_acq_dps_handler_reset_order.py)
confirms that the next ordered frame attempts to publish the cleared DPS
cluster to PSP. The status table describes **local software assignments**.
It does not mean a supply actually enabled, stopped, or reached 0 V.
The source event 16/17/25 command frames and their hardware result are
separate proof obligations; existing output inventory locates the C3/C6/C7
logical command writes, but this table is not a physical outcome test.

The saved Supervision root's [EPS-reader census](../tools/validate_sup_impulsion_eps_consumers.py)
finds direct local EPS readers only for field 58 and Modulator stage fields
8/14/20/26/32. Thus the saved root has **no direct EPS[61], EPS[64], or
EPS[67] read**. This is not proof that the page lacks other raw-input or
derived displays, or that a deployed variant behaves identically.

## Conditional liveness issue

The Supervision event skips its DPS write whenever *any* of 29 sampled DPS
bits is True. ACQ dispatches the lowest True bit among 0–23; the PT bit 22
has a selector arm but no registered handler and no handler-local reset.
If an external writer or imported PSP snapshot leaves `DPS[22]=True`, a
new `Arrêt Aimants` UI action would not write `DPS[23]` through this event;
even a pre-existing bit 23 could be bypassed by repeated selection of 22.
Normal UI operation in this saved Supervision root does not explicitly set
bit 22. This is a **conditional software failure mode**, not an observed
failure or a conclusion about physical interlocks.

The pure [Python request projection](../DeviceServers/control/elyse_acq/supervision_requests.py)
and [local-status projection](../DeviceServers/control/elyse_acq/acq_status_projection.py)
retain only these proven assignments. They have no PSP/NI side effects and
do not model timing, retries, or hardware permission. Their tests include
all pending DPS bit positions and literal field preservation.

```powershell
python tools/validate_sup_magnet_request_gate.py Supervision/analysis/source_exports/0_SUP_ELYSE_XML_sha2257.zip
python tools/validate_acq_magnet_status.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
python -m unittest tests.device_servers.control.test_elyse_supervision_requests tests.device_servers.control.test_elyse_acq_magnet_status_projection
```
