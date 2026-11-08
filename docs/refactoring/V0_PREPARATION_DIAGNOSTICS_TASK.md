# V0 preparation: functional diagnostics follow-up

Status: paused by operator on 2026-10-21. Not implemented. Resume only after an explicit operator request; no hardware commands or tests are authorized while laser pointing is in progress.

## Requested checks

- STANDA on Elysium2: record initial position, make a bounded test move, verify actual position/readback, return to the initial position, and verify the return. Never start STANDA servers on Everest.
- Before implementation, define axis-specific safe travel, limits, tolerance and timeout. Do not home, zero or move an axis automatically on page restoration. Stop the affected test and report any failed move or return; do not retry movement blindly.
- PDU: verify communication, authentication and outlet-status readback without switching or cycling outputs. A read-only response verifies connectivity/readback, not physical relay operation. Any stronger functional test requires a separately agreed safe procedure.
- Preserve Xe lamp cooling, Zaber and shared supplies. Leave DG645 timings and memories untouched.
- Persist per-step results, initial/final positions, timestamps and failures across page reloads; restoration must not replay commands.

## Scope to resolve before resuming

The operator requested PDU checking without switching during this diagnostic test. Confirm whether this applies only to the new self-test or also changes normal Prepare V0 behavior. The existing Prepare power-on whitelist is unchanged by this task note.

## Immediate handover

Leave equipment and running services unchanged. No preparation, motion, power switching, restart or background test is initiated by this task. Elysium reboot and STANDA restart, if needed now, remain operator actions.
