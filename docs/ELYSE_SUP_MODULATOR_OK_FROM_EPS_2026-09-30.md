# Supervision Modulateur OK indicators from ACQ EPS software flags (2026-09-30)

## Question and source boundary

What directly drives the five `OK` indicators on Supervision's Modulateur
page? This trace uses saved LabVIEW wiring only. It does not establish relay
readback, physical stage readiness, PSP freshness, or deployed-program
parity. No VI, PSP variable, XP host, or NI card was operated.

Source: `Supervision/analysis/source_exports/0_SUP_ELYSE_XML_sha2257.zip`
(SHA-256 `68920CD0C441D2F99037FBE60565AF12C80D2DC01EF421892F1D2D69AF9FE5D2`).
The [validator](../tools/validate_sup_modulator_stage_ok_projection.py)
checks five direct wires in sequence `49452` frame 10 (`9031`), their
EPS/Page Modulateur type indices, and their local-reference indices. The
upstream [Supervision EPS ingest](../tools/validate_sup_eps_ingest.py)
reads the ACQ-published EPS bank into local `paramIdx=175`; this frame
writes Page Modulateur local `paramIdx=164`.

## Direct field mapping

| ACQ/Supervision EPS field | Page Modulateur indicator |
|---|---|
| EPS[8] `Marche GENERAL Mod. OK` | [54] `GENERAL MOD OK` |
| EPS[14] `Marche CHAUFFAGE Mod. OK` | [55] `CHAUFFAGE OK` |
| EPS[20] `Marche PREMA Mod. OK` | [56] `PREMA OK` |
| EPS[26] `Marche RELAIS HT Mod. OK` | [57] `RELAIS HT OK` |
| EPS[32] `Marche FOCALE Mod. OK` | [58] `FOCALES OK` |

There is no C3/C4 digital-input read, inversion, or additional Case in these
five direct assignment wires. The indicators copy EPS **software status
bits**, not independent hardware confirmation. Their front-panel color and
operator interpretation are separate UI semantics.

## Consequence for cooling and startup interpretation

The saved [ACQ cooling-start event](ELYSE_ACQ_COOLING_START_COMPLETION_2026-09-30.md)
sets EPS[8] to True by a literal constant, even though its handler is the
cooling request, not the separate `Marche GENERAL Mod.` event 5. The
[parallel EPS publisher](ELYSE_ACQ_EPS_PUBLICATION_CONCURRENCY_2026-09-30.md)
and Supervision ingest provide a static path by which this can reach
`GENERAL MOD OK` while event 3 remains in its final wait. The [cooling-stop
event](ELYSE_ACQ_COOLING_STOP_COMPLETION_2026-09-30.md) and [timeout
flow-trip status frame](ELYSE_ACQ_COOLING_FLOW_SAFETY_TRACE_2026-09-29.md)
do not directly assign EPS[8]. In a pure replay of these saved assignments,
`GENERAL MOD OK` therefore remains True after cooling stop or flow trip;
the [ACQ General-stop event 6 frame 15](../tools/validate_acq_general_stop_status.py)
does assign EPS[8,14,20,26,32] False and the five corresponding stop-OK
fields True. Thus a separate General-stop status transition clears all five
displayed stage-OK inputs in the saved graph. This is a bounded
software-state finding, **not** proof that the installed UI displays a green
indicator during an actual fault, or that hardware remains energized.

`project_modulator_stage_ok_from_eps` in
`DeviceServers/control/elyse_acq/supervision_status.py` is a pure,
non-actuating copy of the five fields. Tests toggle each EPS bit independently
and reject malformed banks.

Reproduce offline:

```powershell
python -X utf8 tools/validate_sup_modulator_stage_ok_projection.py Supervision/analysis/source_exports/0_SUP_ELYSE_XML_sha2257.zip
python tools/validate_acq_general_stop_status.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
python -m unittest tests.device_servers.control.test_elyse_supervision_status
```

## Open points

- Whether any other active EPS writer, subsequent event, or Supervision UI
  rule changes these indicators in the deployed program.
- PSP delivery/error/staleness behavior, front-panel color mapping, and
  independent physical permissives for stage commands.
