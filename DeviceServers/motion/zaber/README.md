# VD2 Zaber stage on Elysium2

`manip/VD2/Zaber` controls the A-MCA with LSM050A-T4 stage on COM1 at 9600 baud.
The public Tango position attributes and movement commands use **millimetres**.
The vendor library receives native units only inside `stage.py`; one native unit
is 0.000047625 mm at the observed 64-microstep setting. The device server checks
controller identity, peripheral identity, resolution, and travel before serving
motion commands. It never homes or moves on startup or reconnect.

| Tango member | Effect |
| --- | --- |
| `position_mm` | Read current position in mm. |
| `minimum_mm`, `maximum_mm` | Read validated travel limits in mm. |
| `MoveAbsoluteMm(value)` | Move to absolute position in mm. |
| `MoveRelativeMm(value)` | Move by displacement in mm. |
| `Home()` | Explicit physical move to home switch. |
| `Stop()` | Stop current move. |
| `Reconnect()` | Close and reopen COM1, then read position without movement. |

The Tango server starts with Elysium2 Starter at boot (server mode 1, level 1).
It remains exported when the controller supply is off. Every 5 seconds it
checks the connection and reconnects after power returns; retries only read
identity, travel limits, and position. No automatic homing or movement occurs.

After a controller power cycle, home the stage before motion, following the
controller manual. Do not run Zaber Console and this device server simultaneously:
both need exclusive access to COM1. VD2 PDU output 3 supplies the controller;
the server can start while that output is off and will connect when it turns on.

Install `requirements.txt` in the `pyconlyse39` environment, register with
`add_ds_Zaber.py` on Elysium2, then start `DS_Zaber/1_Zaber` through Astor.
