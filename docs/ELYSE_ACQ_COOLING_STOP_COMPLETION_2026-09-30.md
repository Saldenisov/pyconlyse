# Acquisition cooling stop: command and completion trace (2026-09-30)

## Scope and evidence

This trace follows the saved ACQ event 4 (`Arrêt refroidissement`) from its
Boolean event value through its ordered output and status frames. It is a
static software trace, not a physical confirmation of stopped water, relay
polarity, or installed-program parity. No VI, PSP variable, XP host, or NI
card was operated.

Source: `legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip`
(SHA-256 `6A518B319B2D35B465DB9AAB557CCA751ACC8B58A600FBA0B8E13771B6EA1527`),
the saved [event 4 screenshot](../../ELYSE-ACQ-analysis/runs/20260922-085500-+0200/images/EV-ACQ-0025-event04-stop-cooling.png),
and the [hash-pinned raw-wire validator](../tools/validate_acq_cooling_stop_completion.py).
The [DPS dispatch map](ELYSE_ACQ_DPS_DISPATCH_MAP_2026-09-29.csv) identifies
`DPS[1]` as this event's request.

## Direct observations

Event Structure `43` frame 4 (`17899`) selects Case `17947` directly from
event `NewVal`. False arm is empty; True arm contains seven-frame ordered
sequence `7929`. Its direct local references are C3 output
(`paramIdx=17`), a graph (`35`), DPS (`36`), and EPS (`44`); no direct C3/C4
input-bank reference occurs in this event handler.

| Frame | Saved VI local command or wait | Raw UIDs |
|---:|---|---|
| 0 | `C3_OUT_DIO96[1]=False`; wait 150 ms | bundle `11019`, wait `16362` |
| 1 | `C3_OUT_DIO96[1]=True` | bundle `20420` |
| 2 | wait 400 ms | wait `21625`, literal `0x190` |
| 3 | `C3_OUT_DIO96[4]=False`; wait 150 ms | bundle `21826`, wait `21990` |
| 4 | `C3_OUT_DIO96[4]=True`; **another** wait 150 ms | bundle `22115`, wait `22147` |
| 5 | assign EPS and DPS local completion fields | bundles `22959`, `23043` |
| 6 | publish DPS to `ni.var.psp://10.20.30.2/SUPERVISION/DPS`; wait 100 ms | writer `23177`, literal `0x64` |

The field inventory labels C3 outputs 1 and 4 as Canon/Section cooling
**stop** lines. Their saved Boolean command pairs are `False→True`. The
shared 150-ms literal is `0x96` in event 4; frame 4's wait terminal is wired
separately from its restore assignment. The nominal wait budget is **0.95 s**:
150 + 400 + 150 + 150 + 100 ms. A local assignment and wait in one frame
can execute concurrently; this sum is not an electrical pulse-width claim.

Frame 5 writes these *local software* fields:

| Bank | Index | Value | Field |
|---|---:|---|---|
| EPS | 1 | False | `Marche refroidissement ED` |
| EPS | 2 | False | `Marche refroidissement OK` |
| EPS | 3 | False | `Arrêt refroidissement` |
| EPS | 5 | True | `Arret refroidissement OK` |
| DPS | 1 | False | `Arret refroidissement X` |

No EPS[8] (`Marche GENERAL Mod. OK`) assignment occurs in event 4, despite
event 3's [cooling-start sequence](ELYSE_ACQ_COOLING_START_COMPLETION_2026-09-30.md)
setting EPS[8] to True. This establishes **absence of an assignment in this
handler**, not that the field remains True in the full running application;
other events or loops may edit it. The independent [timeout cooling-flow
trip](ELYSE_ACQ_COOLING_FLOW_SAFETY_TRACE_2026-09-29.md) is a different stop
path with its own ordered frames and should not be conflated with event 4.
The [literal status-write inventory](ELYSE_ACQ_STATUS_FIELD_WRITES_2026-09-29.csv)
records three EPS[8] literal assignments in the saved root: True in event 3,
True in event 5 (`Marche GENERAL Mod.`), and False in event 6 (`Arrêt GENERAL
Mod.`). It records none in event 4 or the cooling-flow trip. This inventory
does not rule out non-literal or external writers. A pure start→stop status
projection consequently leaves EPS[8] True; the [event-6 status wire check](../tools/validate_acq_general_stop_status.py)
confirms one separate route that assigns it False.

## Python simulation and discrepancy

`DeviceServers/control/elyse_acq/acq_status_projection.py` adds a pure
`project_cooling_stop_local_completion` function and an immutable
`COOLING_STOP_FRAME_WAITS` tuple, keyed by the saved frame numbers. They do
not write a shared variable or call an adapter. Standard-library tests check
all assigned bits, preservation of other bits (including EPS[8]), input
validation, and the five wait literals.

The existing `cooling.stop` procedure in
`DeviceServers/control/elyse_acq/plans.py` contains waits `[0.15, 0.4, 0.15,
0.1]` s, omitting frame 4's additional **0.15 s**. That plan is also
hardware-adapter-capable, so this trace **does not silently change it** under
the current simulation-only boundary. A future hardware-capable port needs a
reviewed timing and concurrency model before correcting that plan.

Reproduce offline:

```powershell
python tools/validate_acq_cooling_stop_completion.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
python -m unittest tests.device_servers.control.test_elyse_acq_status_projection
```

## Unresolved

- Actual NI output update and relay response timing, Boolean polarity at
  physical terminals, and whether the deployed program matches the copy.
- Actual delivery timing through the [sibling EPS publication loop](ELYSE_ACQ_EPS_PUBLICATION_CONCURRENCY_2026-09-30.md)
  and whether another handler clears EPS[8] when cooling stops.
- How a cooling-stop request is prioritized against an ongoing start event;
  both handlers occupy the same Event Structure, but queued-event behavior
  has not been tested on the deployed system.
