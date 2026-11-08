# ACQ DPS request-bit reset and publication order

## Question and source boundary

After Acquisition selects one of the 24 procedure-request bits, does its
handler clear that request and republish DPS? This note examines the saved
`0_ACQ_ELYSE.vi` only, not PSP delivery or successful hardware action.
The [raw-wire validator](../tools/validate_acq_dps_handler_reset_order.py)
pins the copied source hash and checks every implemented event case 3–25.
No VI, PSP server, or NI card was operated.

## Observation

For each of the **23 implemented handlers**, an ordered procedure frame
bundles literal False into exactly the handler's DPS request field in
the local 29-field DPS cluster. The **next ordered frame** has a dynamic
PSP write whose payload is that local DPS cluster and whose URI literal
ends in `/SUPERVISION/DPS`. The frame positions vary by procedure: for
example, General Modulator stop event 6 resets `DPS[3]` in frame 15 and
attempts publication in frame 16; HT-start event 20 resets `DPS[15]`
in frame 2 and attempts publication in frame 3. The validator checks
all 23 event/field/frame pairs, including `DPS[23]` magnet stop.

This establishes **local request consumption and ordered publication
attempt**, not a success acknowledgement. The event may fail, block,
be preempted by concurrent state changes, or publish stale/overwritten
values; the copied graph does not establish delivery or equipment state.
The timeout dispatcher chooses the *lowest* asserted DPS index from a
single snapshot. `DPS[22]` (`Alimentation aimant = PT`) has a dispatcher
selector but no recovered event handler and therefore no corresponding
handler reset/publication path. If it remains asserted, a later
`DPS[23]` request could be repeatedly bypassed by the first-True scan;
that is a **conditional liveness inference**, not an observed runtime
hang. External writers or UI constraints may clear/preclude that state.

## Python transfer

[`project_dps_handler_reset`](../DeviceServers/control/elyse_acq/dps_bridge.py)
accepts an explicit 29-Boolean snapshot and an implemented event case,
then returns a copy with only that handler's request bit False. It
preserves the orphaned PT bit and five trailing non-procedure fields.
It performs no procedure or PSP write. The existing first-True decoder
remains a *single-snapshot* model; the Python code does not yet schedule
later requests or simulate publication failure/reconnect.

```powershell
python tools/validate_acq_dps_handler_reset_order.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
python -m unittest tests.device_servers.control.test_elyse_acq_dps_reset_projection
```
