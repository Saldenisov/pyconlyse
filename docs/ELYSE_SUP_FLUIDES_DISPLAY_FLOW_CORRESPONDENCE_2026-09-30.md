# Page Fluides display versus ACQ cooling-flow guard (2026-09-30)

## Question and boundary

Does Supervision show the same input bits that ACQ uses in its cooling-flow
guard, or only its own command/`OK` flags? This is a comparison of two saved
LabVIEW graphs. It does not prove that the two deployed programs are current,
that cross-computer PSP values are fresh, or that an electrical `True` means
flow present. No VI, XP host, PSP variable, or NI card was operated.

Supervision evidence: frame 8 (`23993`) of 23-frame display sequence `36869`
in `Supervision/analysis/source_exports/0_SUP_ELYSE_XML_sha2257.zip`
(SHA-256 `68920CD0C441D2F99037FBE60565AF12C80D2DC01EF421892F1D2D69AF9FE5D2`).
The [raw-wire validator](../tools/validate_sup_fluides_display_projection.py)
checks source cluster dimensions, local-reference indices, and eleven direct
source-to-Page-Fluides wires. The [frame audit](../Supervision/analysis/all_frame_static_audit.jsonl)
supplies the displayed field names from saved LabVIEW terminal metadata.

## Direct Supervision mapping

| Page Fluides field | Direct source |
|---|---|
| `Canon 220V` | `C3_IN_DIO96[0]` |
| `Canon Défauts` | `C3_IN_DIO96[1]` |
| `Canon Pressostat` | `C3_IN_DIO96[4]` |
| `Section 220V` | `C3_IN_DIO96[6]` |
| `Section Défauts` | `C3_IN_DIO96[7]` |
| `Section Pressostat` | `C3_IN_DIO96[10]` |
| `Canon débimètre` | `C4_IN_DIO96[19]` |
| `Section débimètre` | `C4_IN_DIO96[38]` |
| `Résistivité` | `C4_IN_DIO96[39]` |
| `Lec T° CANON:` | `C1NI6071E[0]` |
| `Lec T° SECTION:` | `C1NI6071E[8]` |

These wires update Page Fluides local display cluster (`paramIdx=4`); their
source references are `paramIdx=31` (C3 input), `29` (C4 input), and `32`
(C1 analog input). There is no EPS completion flag substituted for the nine
listed Boolean displays in this frame. A field label does not establish
electrical polarity or the sensor's physical validity.

## Relation to ACQ's independent guard

The [ACQ timeout guard](ELYSE_ACQ_COOLING_FLOW_SAFETY_TRACE_2026-09-29.md)
reads precisely four of those source bits: C4[19], C4[38], C3[0], and C3[6].
If both computers had an identical, simultaneous bank snapshot, its raw
Boolean expression could be written with Page Fluides field names:

`trip = (Canon débimètre OR Section débimètre) AND
        ((NOT Canon 220V) OR (NOT Section 220V))`

This equality is an index-level correspondence, **not** a rule for an
operator to infer safety from the screen. The guard executes in ACQ; the
display is a separate Supervision projection with unknown PSP freshness and
latency. The `True`/`False` electrical meaning and actual flow must be
verified independently. The [Page Fluides request gate](ELYSE_SUP_FLUIDES_REQUEST_GATE_2026-09-30.md)
is a third path: start/stop UI buttons write DPS[0,1], not these raw input
bits. The ACQ start handler sets `EPS[2]` and `EPS[8]` `OK` bits by literal
assignments, which are likewise separate from measured inputs.

`project_fluides_raw_display_flags` in
`DeviceServers/control/elyse_acq/supervision_status.py` is a pure,
non-actuating projection of only the nine Boolean display wires. It leaves
analog temperatures out, preserving the measured numeric values and any
scaling question for separate analysis. Tests toggle each raw bit alone,
check exact display mapping, and reject malformed banks.

Reproduce offline:

```powershell
python -X utf8 tools/validate_sup_fluides_display_projection.py Supervision/analysis/source_exports/0_SUP_ELYSE_XML_sha2257.zip
python -m unittest tests.device_servers.control.test_elyse_supervision_status
```

## Open points

- Physical input polarity, timing, and sensor fault semantics.
- Timestamped C3/C4 bank equivalence between ACQ's guard and the visible
  Supervision frame; UI refresh and stale-data indication.
- Analog C1 temperature conversion/calibration and how its display relates
  to C8 temperature setpoint writes.
