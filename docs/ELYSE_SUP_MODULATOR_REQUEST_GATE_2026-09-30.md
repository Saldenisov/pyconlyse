# Supervision Page Modulateur: DPS request gate and button map

Scope: saved `0_SUP_ELYSE.vi`, root Event Structure UID 5909, event 18,
diagram UID 30817. This is a read-only trace of the copied VI, not a test of
the deployed software, PSP timing, or equipment.

## Observed wire graph

Local `gRef paramIdx=176` (`DPS`) feeds `Cluster To Array` UID 43109, then
`Or Array Elements` UID 43129, then selector UID 30946. Selector value 0
enters frame UID 31001; value 1 enters UID 42181. Frame 31001 contains a
write to literal `ni.var.psp://localhost/SUPERVISION/DPS`. Its source is
the event's `Page Modulateur` NewVal cluster; its target starts from the
same local DPS cluster and overwrites these 11 fields directly:

| Page index | Button | DPS index | Request |
|---:|---|---:|---|
| 22 | Marche MOD | 2 | Marche GENERAL Mod. |
| 23 | Arrêt MOD | 3 | Arrêt GENERAL Mod. |
| 46 | Marche CHAUFFAGE MOD | 4 | Marche CHAUFFAGE Mod. |
| 47 | Arrêt CHAUFFAGE MOD | 5 | Arrêt CHAUFFAGE Mod. |
| 48 | Marche PREMA MOD | 6 | Marche PREMA Mod. |
| 49 | Arrêt PREMA MOD | 7 | Arrêt PREMA Mod. |
| 50 | Marche RELAIS HT MOD | 8 | Marche RELAIS HT Mod. |
| 51 | Arrêt RELAIS HT MOD | 9 | Arrêt RELAIS HT Mod. |
| 52 | Marche FOCALES MOD | 10 | Marche FOCALE Mod. |
| 53 | Arrêt FOCALES MOD | 11 | Arrêt FOCALE Mod. |
| 21 | Reset MOD | 12 | RESET Mod. |

Frame 42181 has no shared-variable write. The saved
[native screenshot](../Supervision/analysis/screenshots/0_SUP_ELYSE_outer_frame_2_event_case_18_full.png)
shows the same `False` request branch and its instruction that no other
request be in progress. The raw event has only local references `176`
(`DPS`) and `184` (error/status path): there is no direct EPS stage-status,
`C4_IN_DIO96`, or Page Radioprotection reference inside this event.

## Bounded interpretation and Python projection

The saved event's 11-button DPS write occurs when **no bit of the current
29-field local DPS cluster is True**. It does not itself require the
operator's prior General, Heating, Premagnetization, Relay, or Focal stages
to be confirmed. That is a statement about *request creation in this UI
event*, not proof that Acquisition or hardware accepts an out-of-order
request. The local DPS snapshot may be stale relative to another PSP writer;
the copied graph does not establish atomic mutual exclusion.

The pure
[`project_page_modulator_dps_write`](../DeviceServers/control/elyse_acq/supervision_requests.py)
returns a new 29-field tuple or `None` for the busy branch. It neither
publishes to PSP nor actuates a card. A General-start button projection maps
to ACQ event 5 through the existing pure `dps_bridge.py`. The model does
not emulate polling, request clearing, equipment readiness, or error paths.

## Reproduction

Source VI SHA-256:
`2257C86FF6285E1E144BCC5039B4CA5455A34E0DB95B8A15D4DA8503C3A8686B`.
The stable [XML export archive](../Supervision/analysis/source_exports/0_SUP_ELYSE_XML_sha2257.zip)
is SHA-256 `68920CD0C441D2F99037FBE60565AF12C80D2DC01EF421892F1D2D69AF9FE5D2`.
The validator pins that archive and its diagram/type member hashes, then
checks the primitive IDs, case polarity, 11 direct source/destination wires,
PSP URI/data path, schemas, and local-reference set.

```powershell
python tools/validate_sup_modulator_request_gate.py Supervision/analysis/source_exports/0_SUP_ELYSE_XML_sha2257.zip
python -m unittest tests.device_servers.control.test_elyse_supervision_requests
```
