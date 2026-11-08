# Hardware Power Topology

This inventory is the source for `power_dependency_device` and
`power_dependency_output_id`. A Tango server may report `POWER_OFF` only when
its hardware is listed below. All other devices report transport availability
without guessing their physical power state.

## V0 laser-setup preparation — 2026-10-21

Paused follow-up: [V0 functional diagnostics task](V0_PREPARATION_DIAGNOSTICS_TASK.md).
This task does not change the active preparation policy or initiate hardware tests.

The current V0 Prepare operation replaces the earlier temporary check-only policy.
It confirms/starts the two required local PDU servers and enables only V0 outputs
2/3 and SD2 outputs 2/3/4. NETIO Action 5 retains every unrelated outlet; SD2
output 1, SD1/Andor power, VD2 outlets, Zaber and Xe cooling are not switched.

Existing healthy local servers are retained. Missing local controls can start;
available faulted controls receive bounded recovery without killing an existing
process or replaying a timed-out initialization. OWIS backends, routing and V0
axes must pass actual status/position checks. Numeric Tango OFF/FAULT states do
not count as successful OWIS status strings.

All STANDA devices, including actuator aliases in both Laser Pointing `ds_dict`
properties, are check-only on Elysium2. Prepare issues no STANDA start, restart,
recovery, Init, stop, homing or movement command on either host. A discovered but
uninitialized STANDBY motor is reported, not silently treated as ready. Both Laser
Pointing servers, camera streams and every configured actuator/diaphragm/shutter
dependency are checked; no alignment search is started.

DG645 timing is read-only in Prepare: no `*RCL`, `*SAV`, `BURM` or delay writes.
Differences from the saved V0 timing reference remain visible as failed checks;
the current operator timing and memory are preserved. This does not change the
separate acquisition/commissioning requirements or declare Andor acquisition ready.

`POST /api/pump-probe-v0/hardware/initialize?background=1` creates a durable V0
preparation job. Repeated in-flight requests attach to it; later explicit clicks
recheck current hardware. V0 and VD2 share the mutation mutex. SQLite progress,
individual failed/verified checks and history survive reload without command
replay. Production/strict-auth preparation remains fail-closed until an exact
approved runtime plan is available; local laboratory mode uses the fixed scope.

## V0 Unprepare: translation-stage return and Andor shutdown — 2026-10-21

The V0 shutdown sequence stops web acquisition and trigger power first, then
returns `TranslationStage1` (OWIS aggregator axis 3, the long V0 delay line) to
0 mm. This is one absolute move, not homing or coordinate redefinition. Native
Ethernet-backend status/position commands must yield three stationary readbacks
within 0.01 mm. Invalid positions, backend errors, an active laser-pointing
operation or a pending alignment decision block the return. The initial position
must be within the configured V0 travel range. A failed/uncertain move receives
one stop, never an automatic move replay; OWIS power remains available. The
return has a 900 s deadline, accommodating -700 mm at 1 mm/s. Other OWIS axes and
STANDA coordinates are not moved. Final zero is checked again after warm-up.

Andor SD1/1 power is removed only after fresh SDK readback confirms acquisition
stopped, cooling disabled, CCD temperature >= 0 C, and SDK release. The camera
server receives up to three read-only reconnection attempts, separated by 1.1 s;
no server start/restart or camera initialization is issued during shutdown. An
unreachable server cannot establish a safe CCD temperature: its power remains
on and the lifecycle ends failed, with an actionable connection error. An
already-off SD1/1 outlet is not powered up for discovery. Independent branches
continue after a stage/camera failure, but cannot turn the job into success.

The dedicated power-off whitelist is unchanged: SD1/1 (Andor/UV-vis), SD2/2
(DG645), SD2/4 (Power_current), SD2/3 (Power_control). Shared OWIS and STANDA power,
VD2 outlets, Zaber and Xe cooling are retained. Confirmation text and exact
shutdown authorization describe the axis-3 return. Stage/warm-up results remain
in the existing durable lifecycle log; page restoration never replays commands.

Read-only inspection of the most recent live V0 shutdown found
`API_CantConnectToDevice` for `manip/CR/ANDOR_CCD1`; that job explicitly failed and
retained Andor power rather than cutting a detector at an unknown temperature.
A later read-only snapshot found SD1/1 OFF. This does not establish who switched
that outlet off or whether the physical camera was warmed before that change.

The new sequence is qualified with software-only mocks. No stage movement,
camera command, power switching or equipment-server restart was performed during
this implementation. Live end-to-end return/warm-up/power-off remains untested.

Qualification: 193 focused backend tests and 31 preparation UI tests passed.
Frontend build completed with existing unrelated React-hook warnings. The web
process alone was restarted (PID 28632 -> 2104), retaining the original launch
command/environment and listener `0.0.0.0:5000`. The served bundle is
`main.b9aee02a.js`; its SHA-256 matches the isolated build. Both lifecycle jobs
restored with unchanged IDs/statuses and without replay. Read-only snapshots
confirmed unchanged PDU outputs, eight mirror coordinates, lambda/2 position and
equipment-server PIDs. Three SQLite databases and overwritten frontend assets
were backed up under `.tmp/v0-shutdown-stage-deploy-20261021/`. The new sequence
is deployed; its live Unprepare action was not invoked.

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
Preparation, readiness, VD2 sample motion and shutdown use axis 2 directly on
`manip/general/DS_OWIS_PS90_IP`, with finite position and motor-state readback.
The USB backend for axis 4 and the shared aggregator are not VD2 dependencies;
their faults remain available in device diagnostics. V0 routing is unchanged. No movement
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

### Reverse VD2 shutdown and repeat-start checks

Repeated Prepare has a read-only, already-ready branch. It checks required
servers, PDU output IDs/states, `BURM?=0`, stage readback, native HPD-TA version,
Blaze 800 / ruling 150 / Operate, acquisition idle, and absence of a competing
Kymera SDK server. Existing wavelength, time range, shutters and DG645 timing
are preserved. A missing/failed check enters normal power-first recovery.

`POST /api/pump-probe-vd2/deinitialize` reverses ownership before power:

1. Refuse shutdown while the web HIS worker is acquiring/saving or HPD-TA is
   preparing. Manual Live may be stopped, but native `AcqStatus()` must become idle.
2. Close both shutters with native readback, close HPD-TA, stop RemoteEx and
   release any Kymera SDK owner. Closure failure blocks power-off.
3. Switch off only VD2 flashlamp output 1. Retain output 2 (Xe-lamp-CW): this
   powers cooling, while the lamp must be switched off physically. Unprepare
   never removes Xe cooling power. Stop Zaber without homing and verify its
   stationary position; always retain output 3 and its Tango server.
4. Request Stop only for OWIS axis 2. Retain shared V0/OWIS power and report an
   unavailable axis explicitly. Switch off SD2 output 2 (DG645), confirm OFF,
   then output 1 (streak/Kymera). Retain control output 3 and unrelated outlets.

Tango processes remain running, except a competing Kymera SDK owner when
release requires stopping it. Startup, shutdown and new web hardware mutations
share a lifecycle lock. Partial failures retain completed checks in the response.

Thermal safety correction, 2026-10-13: shutdown authorization excludes VD2
output 2; each whole-PDU write preserves its existing state and verifies retained
outlet readback. A changed/missing cooling readback fails explicitly, without
replaying the power command. An already-OFF Xe outlet is not automatically
repowered; the result warns that physical lamp state and cooling need inspection.
The confirmation dialog and preparation page instruct manual lamp-off while
leaving cooling powered. No cooldown duration or automated lamp-off is assumed.
The older live-cycle records below describe behavior before this correction;
their Xe power-off is not the current shutdown policy.

Live CLI cycle, 2026-10-05: first startup failed at OWIS after 43.42 s; repeat
startup failed at the same backend after 58.33 s. Shutdown took 10.44 s and
verified both shutters closed, HPD-TA/RemoteEx stopped, lamps OFF, then DG645
and streak/Kymera supplies OFF. Zaber was unreachable, so its supply remained ON
and shutdown reported partial failure, not success. V0/OWIS outputs remained
unchanged. Independent checks found no HPDTA95/TaRemoteEx process; Hamamatsu
Tango PID 25652 and web PID 26512 remained running. The full cycle is not verified:
OWIS `10.20.30.134:8777` times out; `elysium2` `10.20.30.204:22` also times out.

`tools/validate_vd2_lifecycle.py` defaults to read-only. `--execute` runs startup,
shutdown, startup, repeat startup, and final shutdown using the current source and real web HIS
worker status. It never starts acquisition or moves/homes a stage. The new web
handler/UI and strengthened stale-cache HPD-TA process guard require deployment;
the live validation used the fresh CLI handler and existing Tango command server.

### Durable VD2 preparation and cold-power settling

The Prepare Experiment page requests `POST /api/pump-probe-vd2/initialize?background=1`
or `deinitialize?background=1`. Both retain existing mutation authentication,
hardware-authorization guards and the shared lifecycle lock. A background worker
owns the operation; repeated requests attach to its job instead of replaying it.
`GET /api/pump-probe-vd2/lifecycle` reads progress only, without hardware commands.
The page restores that job after reload and polls its phase, completed checks,
errors and server-clock countdown. Completed results are explicitly historical,
not a fresh claim that the physical rig remains ready.

SQLite persists VD2 state at `%USERPROFILE%\.pyconlyse\experiment_preparation.sqlite3`,
overridable with `PYCONLYSE_EXPERIMENT_STATE_DB`. The deployed laboratory server
must remain a single web worker: the hardware lifecycle mutex is process-local.
After a web-process restart, an unfinished operation is marked interrupted and
its checks remain visible. No saved hardware command is replayed automatically.
Explicit Prepare rechecks actual equipment before recovery. V0 preparation is
unchanged; this durable lifecycle applies to VD2.

When SD2 output 1 is newly enabled, preparation confirms power, then waits 30 s
before starting dependent instrument initialization. The page displays the
remaining time. Timer completion is followed by another power readback, then
normal hardware/SDK readiness checks; elapsed time alone does not prove calibration.
Changing only DG645/control supplies or rechecking an already-powered camera
does not repeat the cold-camera delay. A power-write intent is persisted before
the PDU command; an interrupted or uncertain write retains a settling requirement
for the next explicit retry. A known interrupted deadline is honored after restart.

Fresh read-only diagnosis, 2026-10-05: `manip/general/DS_OWIS_PS90_IP` is registered
and exported as `DS_OWIS_PS90/2_IP`; Everest Starter reports the instance running.
The device's `state()` times out at 2500 ms. Shared V0 PDU output 2 reports ON,
but an independent TCP connection to `10.20.30.134:8777` times out after 3.01 s.
The device log reports `Connection failed: timed out` for the same endpoint.
This establishes current controller-path unavailability, not a missing Tango
registration. It does not distinguish physical power, cable/network failure,
controller failure or changed endpoint, nor establish why it worked earlier.
The Kymera settling delay cannot correct an independently unreachable OWIS controller.

Verification: 171 focused backend tests and 18 Prepare Experiment UI tests passed.
An isolated loopback preview (no Tango import) showed a 30 s countdown continuing
after page reload, with exactly one simulated preparation invocation, followed
by restoration of the completed result. Frontend compilation succeeded with
pre-existing warnings. The production listener has not been restarted and the
new frontend has not been copied into its served build; these changes are not
yet active at `10.20.30.202:5000`.

The VD2 Prepare Experiment page pairs `Prepare VD2` with `Safely switch off VD2`.
Switch-off first opens an explicit confirmation dialog; no shutdown request is
sent until OK is clicked or a new Enter keypress confirms it. Cancel/Escape leaves
equipment unchanged. Held/repeated Enter does not auto-confirm, Tab stays within
the dialog, and confirmation dispatches only one lifecycle request. The backend
still independently rejects unsafe shutdown conditions. V0 shutdown remains
unconfigured and is not offered as a working action. VD2 controls remain locked
if the backend does not expose the durable lifecycle endpoint, preventing the
new UI from calling an old backend's shutdown handler. All 23 preparation UI
tests passed after adding the confirmation flow and backend-capability gate.
Browser verification on the isolated simulator confirmed zero shutdown calls
when the dialog opens and after Cancel, and exactly one shutdown call after
Enter confirms OK. No live hardware commands were issued during this UI test.

### Five-phase fault-tolerant validation, 2026-10-05

Completed Prepare on an already healthy rig now rejects with
`experiment_already_on` (HTTP 409 on the synchronous route; a failed job with
the same code on the background route). This is the operator-requested error,
not a request to reset wavelength, time range, shutters or DG645 timing.
An in-flight duplicate still attaches to the existing worker. A partially
prepared rig is not already-on: explicit retry rechecks and recovers failures.

Startup checks independent PDUs and device branches despite other failures.
Only dependencies of a failed PDU/controller/timing check are skipped. Optical
startup requires confirmed SD2 power and DG645 burst disabled, but does not
depend on external stage connectivity. Recovery progress records each supported
command, its result, server stop/start and verified process/readiness transitions.
An Init timeout does not enqueue more commands into the same unresponsive process.
Independent shutdown branches also continue after VD2 PDU or Zaber failure;
optical/software closure remains a prerequisite for removing camera power.

SQLite atomically records the current job, its archived snapshot and timestamped
events. Previous jobs remain available after a new operation or page reload.
The page shows the newest 100 events, with read-only pagination for older ones.
Failed independent checks are never marked complete merely because later
optical initialization succeeded. Reload never replays hardware commands.

Live cycle using current source, not the old production web worker:

| Phase | Duration (s) | Result |
| --- | ---: | --- |
| On | 170.58 | Optics prepared; OWIS IP / Zaber unavailable |
| Off | 12.88 | Optics/trigger/lamps OFF; Zaber power retained |
| On | 151.58 | Same external-stage failures; optics prepared |
| Repeated on | 113.05 | Recovery retried; not falsely reported already-on |
| Off | 12.92 | Optics/trigger/lamps OFF; Zaber power retained |

All five operations exited; none remained running. The complete healthy cycle
is **not** verified because required stages remain unavailable. OWIS was
restarted through Everest Starter and remained unhealthy; Zaber recovery could
not reach `tango/admin/elysium2`. Independent legacy OWIS, DG645, Hamamatsu,
Kymera SDK selection and HPD-TA readiness checks continued. Cold starts observed
the 30 s power wait. No acquisition or external stage movement/homing was requested.

Fresh final readback: SD2 outputs 1/2 OFF, control output 3 ON; VD2 lamp outputs
1/2 OFF, Zaber output 3 ON because stopped motion could not be confirmed. Shared
V0 outputs stayed `{1:0, 2:1, 3:1, 4:0}`. Both shutters report Closed;
RemoteEx is disconnected and HPD-TA stopped. Windows process inventory found no
HPDTA/TaRemoteEx process. Web listener remains `0.0.0.0:5000`, PID 26512.

Evidence: `.tmp/vd2-five-phase-live-20261005.jsonl`; durable database contains
5 jobs, 261 events and zero running jobs. Verification: 218 focused backend/device
tests and 25 UI tests passed. A loopback-only browser test restored the countdown
and both operation histories with exactly one simulated Prepare and one shutdown.
The production worker/frontend have **not** been updated; restart was previously
rejected by execution policy. Fresh lifecycle/log UI requires that deployment.
