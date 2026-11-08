# Supervision Page Alimentations magnet-request gate

## Question and boundary

This note follows the saved `0_SUP_ELYSE.vi` event 17 (`Page Alimentations`)
through its DPS write. The copied [native event print](../Supervision/analysis/screenshots/0_SUP_ELYSE_outer_frame_2_event_case_17_full.png)
identifies the three UI labels; the [raw-wire validator](../tools/validate_sup_magnet_request_gate.py)
pins the source-export hash and checks selector polarity, target fields,
URI, and direct terminal connections. No VI, PSP server, or NI card was run.

## Observation

The event reads its local 29-Boolean DPS cluster, converts it to an array,
and applies `Or Array Elements`. If **any** DPS bit is True, Case `47154`
selects its branch 1, which has no PSP writer. With all bits False, branch 0
uses the event's `NewVal` cluster to assign exactly three DPS fields and
attempts a write to `ni.var.psp://localhost/SUPERVISION/DPS`:

| Page action | DPS request | ACQ event case after first-True dispatch |
|---|---:|---:|
| `Marche Aimants.` | 20 | 16, start magnet supplies |
| `Arrêt Aimants` | 23 | 17, stop magnet supplies |
| `Aimant 0V` | 21 | 25, zero selected setpoints |

The local-reference set in this Supervision event is DPS (`paramIdx=176`)
and an error-display local (`paramIdx=184`); no C4 input, EPS stage status,
or radioprotection field is directly read by this event. A nested Case
receives the PSP-write error output and updates the error display in its
error arm; this is not an ACQ execution acknowledgement. The event's
saved frame does not assign `DPS[22]` (`Alimentation aimant = PT`). The
[complete root writer census](ELYSE_SUP_DPS22_PRODUCER_CENSUS_2026-09-30.md)
confirms no other fieldwise root UI writer for that bit.

If multiple magnet buttons are True in one `NewVal` snapshot, all matching
bits are bundled, but the saved ACQ timeout dispatcher selects the lowest
asserted DPS index in one poll. For all three buttons, `DPS[20]` start is
the first selection. This establishes neither later scheduling nor
successful execution of the zero/stop requests.

## Consequence and limit

This gate serializes **operator request writes**, not hardware permission.
If an imported or external writer leaves orphaned `DPS[22]=True`, this
Supervision event's any-bit gate would skip even an operator `Arrêt Aimants`
request, while the saved ACQ dispatcher has no handler-local reset for the
orphaned bit. This is a conditional software liveness risk, not evidence
that normal operation reaches that state or that a hardwired stop fails.
The deployed binaries, PSP timing, electrical interlocks, and measured
power-supply response have not been checked.

The pure [Python projection](../DeviceServers/control/elyse_acq/supervision_requests.py)
models only the sampled Boolean gate and three request fields; it neither
publishes DPS nor actuates hardware. Its [unit tests](../tests/device_servers/control/test_elyse_supervision_requests.py)
check each mapping, every pending-bit position, invalid inputs, and the
simultaneous-button first selection.

```powershell
python tools/validate_sup_magnet_request_gate.py Supervision/analysis/source_exports/0_SUP_ELYSE_XML_sha2257.zip
python -m unittest tests.device_servers.control.test_elyse_supervision_requests
```
