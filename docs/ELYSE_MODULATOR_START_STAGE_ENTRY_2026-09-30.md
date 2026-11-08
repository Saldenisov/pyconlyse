# Modulator startup stages: request and ACQ event entry

This static trace addresses whether the *saved controller code at these
entry points* enforces the operator's General → Heating → PREMA → Relay HT
→ Focal startup progression. It does not certify that progression as a
safe operating procedure or describe physical permissives.

## Observed entry path

The saved Supervision `Page Modulateur` event 18 projects five distinct
start buttons through one DPS request bank. Its only branch condition for
that write is that no bit in the local 29-field DPS cluster is asserted;
see the [11-button gate audit](ELYSE_SUP_MODULATOR_REQUEST_GATE_2026-09-30.md).
The existing [DPS field/event crosswalk](../Supervision/integration_analysis/SUP_ACQ_DPS_FIELD_CROSSWALK_2026-09-29.csv)
and pure bridge identify the matching ACQ events:

| Page button index | Request bit | ACQ event | True-arm ordered frames |
|---:|---:|---:|---:|
| 22, Marche MOD | DPS[2] | 5, Marche GENERAL Mod. | 10 |
| 46, Marche CHAUFFAGE MOD | DPS[4] | 12, Marche CHAUFFAGE Mod. | 7 |
| 48, Marche PREMA MOD | DPS[6] | 13, Marche PREMA Mod. | 8 |
| 50, Marche RELAIS HT MOD | DPS[8] | 14, Marche RELAIS HT Mod. | 8 |
| 52, Marche FOCALES MOD | DPS[10] | 15, Marche FOCALE Mod. | 8 |

Each saved ACQ root event has one two-arm selector directly wired from its
Boolean event NewVal. Its False arm is empty; its True arm holds the ordered
procedure sequence. Across all five root handlers, the local-reference set
is `15,35,36,44` and the only primitive ID is `1302` (the wait primitive).
No direct `paramIdx=16` (`C4_IN_DIO96`) read or additional root Case
selector occurs in these five handlers. EPS local `44` is present for
status updates, but it does not drive their entry selector. The detailed
output assignments and waits are separately inventoried in
[`ELYSE_ACQ_NATIVE_FRAME_COVERAGE_LEDGER_2026-09-28.md`](ELYSE_ACQ_NATIVE_FRAME_COVERAGE_LEDGER_2026-09-28.md)
and [`ELYSE_ACQ_DIO_OUTPUT_WRITE_INVENTORY_2026-09-29.md`](ELYSE_ACQ_DIO_OUTPUT_WRITE_INVENTORY_2026-09-29.md).

## Interpretation and boundary

At these *Supervision request* and *ACQ root-event entry* points, the
operator's stage order is **not encoded as a preceding-stage-status
prerequisite**. The DPS gate serializes outstanding requests, but does not
ask whether General or another stage has completed. The ACQ event entries
respond to NewVal=True without an additional root Case based on EPS or C4
input. This does **not** prove that the equipment can be energized out of
order: a focal subVI, concurrent output-write loop, electrical interlock,
external PLC, or different deployed VI may impose further constraints.
The copied code's EPS `OK` fields are software-assigned statuses, not
independent proof of hardware readiness.

The Python change is deliberately limited to
[`supervision_requests.py`](../DeviceServers/control/elyse_acq/supervision_requests.py):
it projects the 11 Page Modulateur button values into an immutable DPS
snapshot and leaves event selection to the existing non-actuating DPS
bridge. Tests check all five start-button-to-ACQ-case identities. No
equipment stage-sequencing policy has been invented or wired into runtime.

If both General-start and General-stop buttons were True in a single
NewVal cluster while DPS was otherwise idle, this source mapping would set
both `DPS[2]` and `DPS[3]`. The ACQ first-True scan would select the lower
index, start event 5, for that snapshot. Whether the actual UI can present
both states simultaneously, whether the later stop request survives PSP
updates, and whether hardware accepts either command are **not** established.

## Reproduction

```powershell
python tools/validate_sup_modulator_request_gate.py Supervision/analysis/source_exports/0_SUP_ELYSE_XML_sha2257.zip
python tools/validate_acq_modulator_start_event_guards.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
python -m unittest tests.device_servers.control.test_elyse_supervision_requests
```

The two source archives pin the copied Supervision and Acquisition raw XML
exports; the validators check case polarity, direct wires, local references,
field/handler identity, and sequence-frame counts. They do not inspect
deployed binaries, subVI error propagation, card readback, or hardwired
interlocks. No VI, PSP server, or hardware was operated.
