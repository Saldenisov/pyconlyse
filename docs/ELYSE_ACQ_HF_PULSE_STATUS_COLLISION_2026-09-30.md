# ACQ HF-power and pulse-stop status-field overlap

## Question and source boundary

Do the saved Acquisition event handlers keep `Marche Att Déph OK` and
`Arret Att Déph OK` mutually consistent? This is a static check of the
copied `0_ACQ_ELYSE.vi`, not a runtime or hardware test. The
[read-only validator](../tools/validate_acq_hf_status_collision.py) pins
the source XML archive and checks direct literal-to-cluster-field wires.
It reuses the independent [impulsion event validator](../tools/validate_acq_impulsion_mod_status.py).
No VI, PSP variable, or NI card was operated.

## Observation

The normal HF attenuator/dephaser power request events set these local
software flags in their ordered completion frames:

| ACQ event | Request reset | EPS[39] `Marche Att Déph OK` | EPS[42] `Arret Att Déph OK` |
|---|---|---|---|
| 18, start HF power | DPS[13]=False | True | False |
| 19, stop HF power | DPS[14]=False | False | True |

Separately, event 24 (`Arrêt impulsion modulateur`) assigns
`EPS[42]=True` and `EPS[52]=False`, resets `DPS[19]`, and **does not assign
EPS[39]** or its nominal pulse-stop `EPS[55]`. Its assignment to EPS[42]
therefore overlaps the HF-power stop field. This is exact saved-code field
identity, not an interpretation of the front-panel caption.

A no-intervening-writer local replay of HF-power start event 18 followed by
pulse stop event 24 produces `EPS[39]=True` **and** `EPS[42]=True`. Those
opposed HF-power status flags can coexist in the saved local Boolean state.
An actual EPS PSP ingest, another event, or scheduling difference may change
the observed sequence. Neither flag is a measured HF chassis readback.
The saved Supervision root's [EPS-reader census](../tools/validate_sup_impulsion_eps_consumers.py)
has no direct EPS[42] reader, so this overlap does not by itself predict
a specific operator lamp color.

The pure [Python projections](../DeviceServers/control/elyse_acq/acq_status_projection.py)
preserve the overlap rather than silently correcting a suspected source
mistake. The [replay tests](../tests/device_servers/control/test_elyse_acq_hf_status_collision.py)
check both HF event assignments and the event-18→event-24 combination.

```powershell
python tools/validate_acq_hf_status_collision.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
python -m unittest tests.device_servers.control.test_elyse_acq_hf_status_collision
```
