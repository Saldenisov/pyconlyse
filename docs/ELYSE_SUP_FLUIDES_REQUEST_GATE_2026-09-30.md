# Supervision Page Fluides request gate: saved VI wire trace (2026-09-30)

## Question and evidence boundary

This trace asks when the saved Supervision VI sends the operator's cooling
start/stop request to Acquisition, and what happens when a temperature-step
button is active. It does not infer whether water is flowing, a contact is
safe, a PSP write succeeds, or the installed executables match the copies.
No VI, PSP variable, XP computer, or NI card was operated.

Evidence is `Supervision/analysis/source_exports/0_SUP_ELYSE_XML_sha2257.zip`
(SHA-256 `68920CD0C441D2F99037FBE60565AF12C80D2DC01EF421892F1D2D69AF9FE5D2`),
its `vi_BDHb.xml` and `vi.xml` members, the saved
[`Page Fluides` diagram screenshot](../Supervision/analysis/screenshots/0_SUP_ELYSE_outer_frame_2_event_case_14_full.png),
and the frame-keyed [static audit](../Supervision/analysis/all_frame_static_audit.jsonl).
The [validator](../tools/validate_sup_fluides_request_gate.py) pins the source
hash and checks the relevant UIDs, selector cases, wires, field positions, and
PSP destination.

## Direct observations

In main Event Structure `5909`, event frame 14 (`38030`, `Page Fluides` Value
Change), local DPS `paramIdx=176` feeds Cluster To Array `38487`, then Or Array
Elements `38498`. Four fields of the event's `NewVal` cluster—`< Canon`,
`> Canon`, `< Section`, `> Section`—feed Build Array `19507`, then Or Array
Elements `27087`. The two Boolean results feed Or `9710`, which selects outer
Case `38117`. Its False arm (`38154`) is the only arm containing the cooling
DPS writer `38229`; True arm (`38451`) contains a second Case `39025`, selected
by the four-temperature-button OR result.

| Outer Case `38117` | Inner Case `39025` | Saved-graph branch |
|---|---|---|
| False: no local DPS bit and no temperature button | Not entered | Map `Page Fluides` `Marche régulation` → `DPS[0]` (`Marche refroidissement X`); `Arrêt régulation` → `DPS[1]` (`Arret refroidissement X`); preserve other DPS fields; write `ni.var.psp://localhost/SUPERVISION/DPS`. |
| True: at least one of those conditions | False: no temperature button | No shared-variable write in this inner arm. A cooling button coincident with an already-pending DPS request is not forwarded by this event pass. |
| True | True: a temperature button is active | Enter four-bit temperature action selector `19503`; cooling DPS writer is bypassed, including when a cooling button is also active. |

The two cooling source terminals `38187`/`38191` wire directly to DPS bundle
terminals `38218`/`38222`; the bundle feeds writer data terminal `38246`.
Literal PSP URI terminal `38160` feeds writer `38234`. The False arm also
contains `Wait (ms)` with literal `200`. Its presence establishes a wait in
that arm, not that the shared-variable write finishes before the wait starts:
there is no wire imposing that order.

The temperature selector uses Boolean Array To Number `10152` on the four
buttons in `< Canon`, `> Canon`, `< Section`, `> Section` order. Cases `1`, `2`,
`4`, and `8` respectively subtract/add **0.1** to Canon/Section setpoint
fields, update local Page Fluides, and write `C8NI6703[1]` (Canon) or `[2]`
(Section). The four arithmetic nodes and literal `0x3FB999999999999A`
are checked against each direct C8 field wire; no clamp primitive occurs
inside these four cases. Case `0`
has no shared-variable write. The four writer UIDs are `36455`, `42992`,
`44982`, and `48837`. The behavior when *multiple* temperature buttons are
simultaneously true is not claimed here; the saved selector lists only cases
`0`, `1`, `2`, `4`, and `8` in this trace.

## Bounded inference and Python projection

The `Page Fluides` controls are a **request serializer**, not a cooling
permissive. A successful Boolean branch into the DPS writer does not imply
that Acquisition receives or executes the request. The existing [DPS
crosswalk](../Supervision/integration_analysis/SUP_ACQ_DPS_FIELD_CROSSWALK_2026-09-29.csv)
maps `DPS[0]` and `[1]` to ACQ event cases 3 and 4. The separate [ACQ
cooling-flow guard](ELYSE_ACQ_COOLING_FLOW_SAFETY_TRACE_2026-09-29.md) uses
raw C4/C3 input bits and can command stop-line pulses independently of a
Supervision UI request; input polarity and real flow are unresolved.

`DeviceServers/control/elyse_acq/supervision_requests.py` implements only the
proven cooling DPS branch as the pure function
`project_page_fluides_dps_write`. It returns a projected 29-Boolean snapshot
or `None`; it cannot publish, start a VI, or actuate a card. An all-False
button vector still returns an all-False snapshot for the idle branch because
the saved writer is reached on any qualifying Page Fluides Value Change.
`adjust_fluides_temperature_setpoint` in
`DeviceServers/control/elyse_acq/legacy_supervision_setpoints.py` returns
the selected C8 field index and requested numeric value for one of the four
proven one-hot actions; unlisted multi-button masks fail closed. It does
not publish the value or impose an unobserved temperature clamp.
Unit tests exercise all 29 pending-DPS bits, four temperature buttons,
four one-hot ±0.1 actions, start/stop mapping, simultaneous start/stop priority in the copied ACQ
first-True dispatcher, input validation, and non-mutation. They do not test
PSP delivery, DIO output, or physical cooling.

Reproduce offline:

```powershell
python tools/validate_sup_fluides_request_gate.py Supervision/analysis/source_exports/0_SUP_ELYSE_XML_sha2257.zip
python -m unittest tests.device_servers.control.test_elyse_supervision_requests
python -m unittest tests.device_servers.control.test_elyse_fluides_temperature_setpoint
```

## Unknowns before a hardware-capable replacement

- Whether the deployed Supervision and Acquisition binaries match these
  saved VIs; whether the PSP write is delivered and acknowledged.
- Whether UI button mechanics can produce simultaneous start/stop or
  temperature requests, and how LabVIEW handles the temperature selector's
  unlisted multi-bit values.
- ACQ event 3/4 full frame-by-frame behavior, NI write-loop scheduling,
  electrical polarity, water-flow truth table, and physical interlocks.
