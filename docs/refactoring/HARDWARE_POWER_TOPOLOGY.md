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

## Web experiment preparation

`Prepare Experiment` is the startup entry point for V0 and VD2. Equipment
Control Center contains instrument controls, not a second experiment launcher.

Preparation follows the dependency order:

1. Check Tango Starter and start/recover the required PDU servers.
2. Enable only the configured experiment outputs, verify their output IDs and
   state readback, and allow switched instruments to settle.
3. Check the dependent instruments. Attempt supported recovery, initialization,
   or turn-on commands before restarting an unhealthy server. A failed power
   check blocks the dependent instrument; preparation must not guess an outlet.
4. Verify instrument availability and the experiment-specific configuration.
   DG645 readiness includes a nonempty `*IDN?` response, not merely an exported
   Tango device. VD2 additionally checks RemoteEx, HPD-TA, and its optical profile.

V0 includes the UV-visible CCD and Shamrock, Standa axes, OWIS controllers and
axes, DG645, DAQmx, and its configured cameras. Devices without a documented
PDU dependency are checked without inventing a power mapping.

VD2 also requires `manip/V0/PDU_VO` output 2 for the shared OWIS controller.
Its preparation checks both OWIS backends and the existing aggregator, then
verifies the VD2 sample-stage axis 2 and its finite position readback. No movement
or homing command is issued. DG645 Recall 9 is applied immediately after generator
readiness, followed by `BURM 0` and a `BURM?` readback check, before the other
instrument servers and HPD-TA startup. Invalid burst readback blocks preparation.
The configured web checklist describes this VD2 mode only; acquisition is separate.

Kymera grating selection uses `manip/CR/ANDOR_KYMERA1` and the SDK's physical
index 2, not the ambiguous RemoteEx label `150 g/mm` (all three gratings use it).
Preparation refuses active acquisition, closes both shutters, stops HPD-TA if
running, stops the RemoteEx process to unload its SDK, then starts/initializes
`DS_ANDOR_SPECTROGRAPH/2_ANDOR_KYMERA1` and calls
`PrepareVD2Grating`. Target and actual metadata must be 150 g/mm / Blaze 800 nm.
The SDK is closed and that exact server process is stopped before RemoteEx is
restarted and HPD-TA starts. `AppEnd` alone is not an SDK-ownership boundary.
HPD-TA then independently verifies the optical profile without selecting a
grating by label. Kymera uses Starter's manual mode (`mode=0`, `level=0`),
which supports explicit `DevStart`/`DevStop` without boot autostart. Startup
checks use the all-server inventory (`DevGetRunningServers(True)`), not just
the automatic-control inventory, so manual-mode owners are also stopped.

Everest's Kymera configuration uses `spectrograph_serial=KY-3804`; the SDK
index is resolved by serial number on each open and verified again before any
configuration. Missing/duplicate identity fails without opening another unit.
The deployed index hint is `0` (only Kymera is currently enumerated), not the
old `1`. SDK paths are `C:\Program Files\Andor SDK` and
`C:\Program Files\Andor SDK\Shamrock64`. `power_dependency_auto_probe=0`
avoids competing SDK discovery while preparation explicitly initializes it;
power checks still guard every hardware operation. SDK Blaze strings such as
`800nm` are parsed as nm, not metres.

RemoteEx responses are matched to the requested command name; late AppStart or
status replies are never accepted as parameter readback. Reply draining is
bounded by the command deadline and 16 unrelated replies. Optical writes use
a 30 s timeout without automatic replay. Profile verification still fails closed
and closes both shutters if readback is invalid.

`AppStart` uses the configured initialization budget (`async_timeout_s=120` on
Everest), not the 5 s status-command timeout. Its failed background startup
remains `FAULT` through disconnected polling rather than being overwritten by
the launcher's ordinary `ON` state. Web preparation allows 180 s for application
startup plus optical verification and never sends a second `AppStart` on timeout.
If AppStart resets its command socket, the read-only AppInfo probe on the new
socket uses the initialization budget too; a 3 s probe timeout must not create
repeated abandoned sockets while the native application initializes devices.
An already-exported OFF Kymera uses explicit `turn_on` with a 60 s SDK timeout
before considering Init/restart. An unexported DServer is treated as stopped only
after the all-server inventory confirms its process has exited.

Server restart waits until `DevGetRunningServers` no longer reports the old
process before sending `DevStart`. An `ALREADY_RUNNING` response is accepted
only if the subsequent device health check succeeds. A stop timeout fails
preparation without forced process termination.

Failed checks retain their component diagnostics. After correcting physical
power or a connection, press `Prepare` again to rerun the checks; failure does
not require restarting the web server. Passing automated checks does not replace
the separate operator verification checklist.

### Live validation, 2026-10-05

After the Everest reboot, the updated RemoteEx client completed a full warm
handoff in 56.5 s: both shutters closed, HPD-TA and RemoteEx stopped, SDK grating
2 verified (150 g/mm, Blaze 800 nm), Kymera server stopped, RemoteEx/HPD-TA
restarted, and the complete VD2 optical profile verified. Actual acquisition
state was `0,AcqStatus,idle`; DG645 readback was `BURM=0`. The Kymera PID was
confirmed absent from the local process list after handoff. No acquisition,
stage movement, or homing was requested.

Before the client changes, failed starts displayed the native TaRemoteEx modal
`Error setting TCP_NODELAY option: 10038`. The successful updated-client cycle
does not establish long-run reliability or readout/acquisition readiness.

Full Prepare in the web page still fails at the OWIS IP backend before optical
startup: PDU V0 output 2 is ON, but TCP `10.20.30.134:8777` does not answer.
The page correctly remains failed at 33%, with the VD2 checklist marked
Configured. Hamamatsu/Kymera validation is not a full experiment-ready result.

The current Hamamatsu device server loaded the client fixes. Deployment of the
latest web-backend changes still requires a web-process restart; the scoped
restart attempt was rejected by execution policy. The existing listener remains
on `0.0.0.0:5000`. The persistent treatment database retained 3 sessions and
2 completed processing jobs before the attempted restart.
