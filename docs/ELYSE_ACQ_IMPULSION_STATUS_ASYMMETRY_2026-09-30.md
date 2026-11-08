# Impulsion modulateur: saved status-field asymmetry

## Scope and observation

The saved Acquisition event 23 (`Marche impulsion modulateur`) and event
24 (`Arrêt impulsion modulateur`) status frames were checked by direct
raw wires with
[`validate_acq_impulsion_mod_status.py`](../tools/validate_acq_impulsion_mod_status.py).
The [DPS reset-order audit](ELYSE_ACQ_DPS_HANDLER_RESET_ORDER_2026-09-30.md)
separately checks next-frame publication attempts. Neither VI nor NI task
was run, and no PSP variable was changed.

| Event | Local EPS assignments | Local DPS assignment |
|---|---|---|
| 23, start | `EPS[55] Arret impulsion mod OK=False`; `EPS[52] Marche impulsion mod OK=True` | `DPS[18]=False` |
| 24, stop | `EPS[42] Arret Att Déph OK=True`; `EPS[52] Marche impulsion mod OK=False` | `DPS[19]=False` |

The event-24 frame has one EPS Bundle By Name writer, targeting fields
42 and 52. It does **not** assign `EPS[55] Arret impulsion mod OK` in
that event. Calling `EPS[42]` a copy/paste defect would be an inference;
the code may intentionally reuse that status, although its label belongs
to the attenuator/phase-shifter subsystem. No correction is made in the
non-actuating Python projection.
The [cross-event HF status check](ELYSE_ACQ_HF_PULSE_STATUS_COLLISION_2026-09-30.md)
shows the concrete consequence: after saved HF-power start event 18 sets
EPS[39]=True and EPS[42]=False, pulse-stop event 24 can set EPS[42]=True
without clearing EPS[39]. The local status pair can therefore become
simultaneously True in a no-intervening-writer replay; runtime PSP/loop
interleaving and physical HF state remain unknown.

The saved Supervision root's
[EPS consumer census](../tools/validate_sup_impulsion_eps_consumers.py)
finds four references to its local EPS cluster: PSP ingest/type, an
unbundle of field 58, and an unbundle of stage-OK fields
8/14/20/26/32. There is **no direct root read of EPS[42] or EPS[55]**
in that copy. This bounds the apparent UI effect; another VI, another
PSP consumer, deployed-code difference, or front-panel state not traced
through EPS could still make these flags relevant.

[`project_impulsion_modulator_local_completion`](../DeviceServers/control/elyse_acq/acq_status_projection.py)
replays only the saved local literal assignments. In a stop-only replay,
the previous EPS[55] value is preserved; the model neither polls
`CO.GénImpTerminée`, stops NI6602 tasks, publishes PSP, nor treats EPS
as hardware readback.

```powershell
python tools/validate_acq_impulsion_mod_status.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
python tools/validate_sup_impulsion_eps_consumers.py Supervision/analysis/source_exports/0_SUP_ELYSE_XML_sha2257.zip
python -m unittest tests.device_servers.control.test_elyse_acq_impulsion_status_projection
```
