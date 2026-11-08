# Laser Pointing iris calibration — 2026-10-21

Completed at operator request. Four unique irises are shared by Laser Pointing1/2:
DE1 (`elyse/motorized_devices/de1`) and DV01/DV02/DV03 (`manip/V0/*`).

## Procedure and evidence

Acquisition, automatic alignment and preparation jobs were inactive. Existing
device servers remained running. Each iris was commanded to 100%, its current
coordinate was redefined as 90% without movement, and one bounded opening move
to 100% was issued. Only an ON/stationary controller with the physical RIGHT
end switch active was accepted as the opening endpoint. That endpoint was then
defined as 100%. No software limits or conversion factors were changed.

| Iris | Initial position (%) | First opening readback (%) | End-switch stop after temporary 90% definition (%) | Low-position verification (%) |
| --- | ---: | ---: | ---: | ---: |
| DE1 | 9.200 | 100.000, BETWEEN | 90.320, RIGHT | 5.000, BETWEEN |
| DV01 | 10.000 | 100.000, BETWEEN | 95.408, RIGHT | 5.000, BETWEEN |
| DV02 | 20.000 | 100.000, BETWEEN | 90.534, RIGHT | 5.000, BETWEEN |
| DV03 | 99.063 | 99.063, RIGHT | 90.000, RIGHT | 5.000, BETWEEN |

The earlier DV01 failure reported a stop at 5.825% for a 5% target. The new
5% command reached 5.000% on all four devices, with no transport-error counter
increments. This verifies the reported operating point, not a closed-end zero
or an absolute optical-aperture calibration.

On the return-to-open check, DE1/DV01/DV02 activated RIGHT at 99.915%, 99.920%
and 99.826%. DV03 reached nominal 100% without RIGHT, so its opening endpoint
was reseated once using the same bounded 90-to-100 procedure; RIGHT activated
at temporary 90.064%, then was redefined as 100%. These observations are not a
repeatability study or a guarantee of reference retention after a power cycle.

## Final handover

Laser Pointing1 successfully applied `point1` through its own controller:

| Iris | Final readback (%) |
| --- | ---: |
| DE1 | 9.200 |
| DV01 | 10.000 |
| DV02 | 20.000 |
| DV03 | 100.000, RIGHT |

All eight mirror position/state snapshots matched the initial snapshot. No
alignment search, server restart, PDU switching or DG645 command was performed.

Machine-readable snapshots and command events are retained locally in
`.tmp/iris-calibration-20261021/` (`before.json`, `calibrated.json`,
`low-check.json`, `dv03-final-open.json`, `final.json`, `events.jsonl`).
