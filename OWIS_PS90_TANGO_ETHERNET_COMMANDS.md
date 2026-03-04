# OWIS PS90 Direct Ethernet Command Reference for Tango Development
This document captures the command set and working sequences for controlling an OWIS PS90 over direct TCP (`port 8777`) without `ps90.dll`.
It is intended for implementing/maintaining a Tango Ethernet controller class.

## 1) Transport and protocol basics
- TCP endpoint: `<controller_ip>:8777`
- Encoding: ASCII
- Line termination: `\r` (CR)
- Typical request/response behavior:
  - Query commands (`?xxx`) return data
  - Action commands (`xxx...`) often return `OK` or empty string
- Recommended socket timeout: 3–5 s
- Recommended inter-command delay: 50–200 ms (depending on command)

## 2) Commands verified working
## 2.1 System / identification
- `?SERNUM` -> controller serial number
- `?VERSION` -> firmware version
- `?ERR` -> error code (observed `0` for no error)
- `?MSG` -> last message text (e.g. `00 NO MESSAGE AVAILABLE`)
- `?TERM` -> terminal mode
- `TERM=2` -> set terminal verbosity (useful for diagnostics)

## 2.2 Axis state and control (axis 1 examples)
- `?ASTAT` -> global axis status summary string
- `?AXIS1` -> numeric axis state (observed `1` on current hardware)
- `AXIS1=1` -> release/activate axis channel for operation
- `INIT1` -> initialize axis 1
- `MON1` -> motor on command (accepted but can report wrong state depending on sequence)
- `MOFF1` -> motor off
- `STOP1` -> stop movement

## 2.3 Motion / position
- `?CNT1` -> current position counter (controller units)
- `?PSET1` -> current target position
- `ABSOL1=1` -> absolute mode
- `ABSOL1=0` -> relative mode (controller behavior should always be validated)
- `PSET1=<value>` -> set target
- `PGO1` -> execute move to target
- `PVEL1=<value>` -> set positioning velocity (controller units / s)
- `?PVEL1` -> read positioning velocity

## 2.4 Configuration/status queries seen on current controller
- `?MOTYPE1` -> motor type (observed `2` for stepper)
- `?MCSTP1` -> microstep parameter (observed `50`)
- `?SMK1` -> state/mask-like parameter (observed values like `0000`)

## 3) Commands tested but not accepted on current controller
These returned empty response + message like `05 WRONG COMMAND ERROR`:
- `?APTS1`, `?MSTA1`, `?MPOS1`, `?MOV1`, `?AXST1`, `?POS1`
- `MOVE1=...`, `TARGET1=...`, `REL1=1`, `ABS1=...`, etc.

Keep unsupported commands out of Tango class logic unless firmware-specific validation is added.

## 4) Working startup and move sequence (recommended)
Use this sequence for deterministic behavior:

1. Connect TCP socket
2. `AXIS1=1`
3. `INIT1`
4. Set velocity (`PVEL1=...`)
5. Wait until ready (`?ASTAT` first character should indicate ready)
6. `ABSOL1=1`
7. `PSET1=<target_cnt>`
8. `PGO1`
9. Poll `?ASTAT` and `?CNT1` until stable/ready
10. Check `?ERR` and `?MSG`

For return move, repeat steps 7–10 with the original position target.

## 5) `?ASTAT` interpretation observed in tests (inference)
Observed first-character transitions for axis 1:
- `I...` -> not initialized
- `R...` -> initialized/ready
- `T...` -> moving (transient)
- `O...` -> motor off / standby-like
- `U...` -> unused axis slots

This mapping is inferred from live behavior and should be kept configurable per firmware revision.

## 6) Unit conversion for mm-based motion
From Tango DB axis parameters:

- `units_per_mm = revolution * gear_ratio / pitch`
- `velocity_units_per_s = speed_mm_s * units_per_mm`
- `target_cnt = round(target_mm * units_per_mm)`

Example for axis 1 (current DB values):
- `pitch=1`, `revolution=200`, `gear_ratio=1`
- `units_per_mm=200`
- `speed=6 mm/s` -> `PVEL1=1200`
- `+30 mm` -> `+6000` counter units

## 7) Tango class design mapping (Ethernet-only backend)
Suggested method mapping:
- `connect()` -> open socket
- `disconnect()` -> close socket
- `send(cmd)` / `query(cmd)` -> low-level transport
- `init_axis(axis)` -> `AXIS{axis}=1`, `INIT{axis}`
- `set_velocity(axis, vel_mm_s)` -> convert to units and call `PVEL`
- `move_absolute_mm(axis, mm)` -> convert and call `ABSOL=1`, `PSET`, `PGO`
- `move_relative_mm(axis, dmm)` -> read `CNT`, compute target, then absolute move
- `stop_axis(axis)` -> `STOP{axis}`
- `get_status(axis)` -> parse `?ASTAT`, `?AXIS{axis}`, `?ERR`, `?MSG`

## 8) Safety checks to enforce in Tango commands
- Always read limits from Tango DB (`limit_min`, `limit_max`) before moves
- Reject out-of-range mm targets before sending `PSET`
- Use motion timeout watchdog and fail to safe state on timeout
- On error:
  - query `?ERR`, `?MSG`
  - call `STOP{axis}`
  - optionally `MOFF{axis}`
- Add retries for transient socket timeouts (not for semantic command errors)

## 9) Minimal command session (manual debug)
```text
?SERNUM
?VERSION
?ASTAT
AXIS1=1
INIT1
PVEL1=1200
ABSOL1=1
PSET1=7000
PGO1
?CNT1
?ASTAT
PSET1=1000
PGO1
?CNT1
?ERR
?MSG
```

## 10) Notes for future development
- Keep direct-socket backend as primary path when USB is unavailable.
- Keep DLL backend optional/fallback only.
- Add a firmware capability probe at startup (command support matrix).
- Persist verified command set per controller serial if multiple PS90 variants are used.
