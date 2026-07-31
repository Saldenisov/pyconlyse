# Hardware Power Topology

This inventory is the source for `power_dependency_device` and
`power_dependency_output_id`. A Tango server may report `POWER_OFF` only when
its hardware is listed below. All other devices report transport availability
without guessing their physical power state.

## Managed PDU dependencies

| Hardware | Tango device | PDU output |
| --- | --- | --- |
| OWIS PS90 IP delay-line controller | `manip/general/DS_OWIS_PS90_IP` | `manip/V0/PDU_VO / 2` |
| V0 Standa controllers | `manip/V0/*` motor axes | `manip/V0/PDU_VO / 3` |
| UV-vis Andor CCD | `manip/CR/ANDOR_CCD1` | `manip/SD1/PDU_SD1 / 1` |
| Andor Shamrock 1 | `manip/CR/ANDOR_SHAMROCK1` | `manip/SD1/PDU_SD1 / 1` |
| Andor Kymera 328i and Hamamatsu streak hardware | `manip/CR/ANDOR_KYMERA1`, `manip/camera/hamamatsu_streak_main` | `manip/SD2/PDU_SD2 / 1` |
| DG645 | `manip/sync/DG645` | `manip/SD2/PDU_SD2 / 2` |

## Not PDU-managed by PyConlyse

| Hardware | Reason |
| --- | --- |
| DAQmx | Powered with its host computer. |
| Laser-pointing cameras | Permanently powered. |
| PSP receiver | No PDU dependency. |
| Keysight 33509B | No PDU dependency. |
| Avantes devices | Not currently installed. |
| PDU ELYSE | External equipment; out of PyConlyse ownership. |
| VD2 flashlamp, Xe lamp, and Zaber supplies | No corresponding Tango hardware server. |

Update this file and the device registration/configuration before assigning a
new PDU dependency. Do not infer a mapping from a device name or PDU label.
