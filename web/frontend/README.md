# Getting Started with Create React App

## Prepare / Unprepare experiment (2026-10-08)

The VD2 preparation page pairs `Prepare VD2` with `Unprepare VD2`. Unprepare
uses the existing durable `/api/pump-probe-vd2/deinitialize?background=1`
operation, not a new hardware sequence. OK or Enter confirms; Cancel or Escape
leaves equipment unchanged. Shutdown progress and historical results restore
without replay after reload. Shared OWIS power and control supplies remain ON.
V0 has a separate, narrowly scoped shutdown as described below; it does not
reuse VD2's optical/stage sequence.

### V0 passive preparation and scoped shutdown (2026-10-14)

Prepare V0 is check-only. Failure does not trigger a startup/repair POST, PDU
power-on, axis initialization, server recovery or DG645 recall. The legacy
`POST /api/pump-probe-v0/hardware/initialize` is disabled with HTTP 409 and
`v0_prepare_read_only`, including trusted local/development mode. All 16 STANDA
devices are checked against `tango/admin/elysium2`, not Everest's inventory.
An unavailable Elysium2 Starter is reported once and blocks remote device
checks without starting local replacements. Andor CCD, UV-visible spectrograph
and their SD1/1 supply are temporarily excluded from preparation requirements.

Unprepare V0 requires OK/Enter confirmation and uses a separate durable
`experiment_preparation_v0.sqlite3` journal. Reload only reads/polls saved
progress; interrupted commands are not replayed. Authorization owns this plan:

| Supply | Outlet | Unprepare action |
| --- | --- | --- |
| SD1 | 1 — UV-vis / Andor | Power OFF only after verified camera warm-up and SDK release |
| SD2 | 2 — DG645 | Power OFF before camera/bias supplies; verify readback |
| SD2 | 4 — Power_current | Power OFF, preserving every other outlet |
| SD2 | 3 — Power_control | Power OFF last, preserving every other outlet |

STANDA/Elysium2, OWIS, Zaber, VD2 flash/Xe lamps and Xe cooling are not switched
off or moved. Shared SD2 power is retained if streak outlet 1 is ON/unknown,
HPD-TA/RemoteEx or a VD2 measurement/lifecycle is active, or ownership cannot be
verified. The shared mutation lock prevents V0/VD2 operations from overlapping;
ownership is rechecked after warm-up and before each shared-supply write.

Andor's SDK guidance requires cooler-off and controlled warm-up before SDK
shutdown ([SDK example, section 10](https://andor.oxinst.com/downloads/uploads/Software%20Development%20Kit.pdf)).
The conservative software gate is a fresh native temperature >= 0 C, cooler
OFF and acquisition stopped, followed by verified SDK release. Warm-up is
bounded at 15 minutes; timeout, invalid/stale reads or close failure retains
camera power while independent supply checks continue. No cooler/fan power is
cut during warm-up. Camera safety uses `BeginSafePowerOff`, `GetPowerOffSafety`
and `ReleaseAfterWarmup`; an old server lacking these commands is not restarted
or initialized automatically, and its camera supply is retained. Activate the
new Andor server version only through a controlled, thermally safe update.

As of 2026-10-09, Zaber is also an always-on device. Unprepare stops its motion
without homing, but never disables VD2 PDU output 3 or stops the Zaber server.
As of 2026-10-13, only VD2 flashlamp output 1 and SD2 trigger/camera outputs
2/1 are disabled. VD2 output 2 (Xe-lamp-CW) powers cooling and is never switched
off by Unprepare: the Xe lamp must first be switched off physically, while PDU
power stays ON for cooling. No automatic cooldown duration or remote lamp-off
capability is assumed. Existing ON/OFF outlet state is preserved on every PDU
write, including repeated shutdown and device-failure paths. An already-OFF
Xe outlet is reported as a warning rather than automatically repowered.
Confirmation and preparation-page notices identify this exception explicitly.
Every PDU vector preserves Zaber's existing outlet state; an externally unpowered
Zaber is not powered up during shutdown. Failure to verify stopped motion is still
reported, while independent optical/trigger shutdown checks continue.

VD2 preparation retains operational OWIS servers in ON/MOVING/RUNNING instead
of classifying shared-axis motion as a server fault. If advertised, the separate
`initialization_state` must also be SUCCEEDED. Existing initialization or missing
live-position readback is observed without another Init/turn_on or process reset.
An exported OFF/STANDBY controller receives one turn_on with a 60 s client timeout;
a faulted controller tries recover then turn_on, without Init. A timed-out recovery
is only observed during that preparation attempt; unresolved readiness is logged
as failure and independent branches continue. Starter is used only to start
absent OWIS processes, not to restart running ones. These changes are
software-tested; the running laboratory web worker is not automatically restarted.

As of 2026-10-09, Prepare retains running Kymera, DG645 and OWIS server processes
even after failed or uncertain hardware readback. Starter starts only absent
processes; a start race also retains the process without stop/start. OFF/STANDBY
equipment gets one turn_on; FAULT gets device recovery followed by turn_on, never
Init replay or a process restart. Readback failure stays an explicit failure,
not a claim that a registered server was missing.

Kymera hands its SDK to HPD-TA by turn_off and verified Tango OFF state, with its
server still running. The handoff requires power_dependency_auto_probe=0 so the
background monitor cannot reopen the SDK. Failed or uncertain release blocks
HPD-TA startup. A retained OFF Kymera server no longer invalidates the already-on
check. Unprepare also releases the SDK without stopping the Tango process.

### Focus-before-shutdown and calibrated DG645 timing (2026-10-09)

Unprepare stops acquisition and verifies both shutters closed, writes streak
`Focus` only when needed, and confirms `DevParamGet(TD,Mode)` before closing
HPD-TA/RemoteEx or disabling any supply. Unconfirmed Focus retains power. A
stopped application cannot prove safe camera mode while its supply is still ON.
Repeating an already completed shutdown does not restart software to set Focus.

The operator's 20-entry calibration is stored in
`web/pump_probe/config/vd2_streak_dg645_recall9.json`: A = T0 + 2.0417 ms;
E = T0 + the tabulated millisecond delay for each ns/us/ms sweep range.
Decimal conversion preserves supplied digits. Only A/E (`DLAY 2,0,...` and
`DLAY 6,0,...`, seconds) are written and read back. No gate-channel write,
interpolation, or persistent `*SAV` is added. The command format and channel
mapping follow the [DG645 manual, page 56](https://www.thinksrs.com/downloads/pdfs/manuals/DG645m.pdf).
Output roles are fixed by the operator: AB = pre-pulse, CD = main flashlamp
pulse, EF = streak-camera trigger, GH = gate. A never varies with sweep range.
B/D/F pulse widths, existing C-to-A relation, and G/H settings are retained;
new gate parameters and physical calibration verification remain pending.

An explicitly authorized maintenance operation may save the 1 us baseline to
slot 9 once. This is separate from Prepare/Time range, which never saves slots.
DG645 slots 1–9 each contain one setup, not a lookup table: the 20 calibrated
E values remain in software. Slot 8 (V0) must not be rewritten. Maintenance
requires HPD-TA/RemoteEx stopped and camera/flashlamp/Xe supplies confirmed OFF,
snapshots of active setup and old slot 9, then verification after `*SAV 9` /
`*RCL 9`. Only A/E and burst OFF may change from the old slot 9; every other
queried setting must remain identical.
T1 is a derived trailing edge, not a programmable gate: its readback follows
the maximum of trigger holdoff and the longest delay plus 25 ns (manual p. 27).

On 2026-10-09, slot 9 was explicitly saved and recalled with
A = T0 + 2.0417 ms, E = T0 + 2.2065 ms (1 us), BURM = 0. All 20 A/E profiles
passed real-instrument SCPI readback checks while optical supplies remained
OFF; the saved 1 us baseline was restored afterward. Pulse widths, G/H, output
levels and trigger settings remained unchanged. This does not verify actual
waveforms. Old and verified slot snapshots are retained alongside the timing
config as `vd2_dg645_memory9_before_20261009.json` and
`vd2_dg645_memory9_verified_20261009.json`. `verified_on_hardware: false` still
denotes pending physical timing verification; `memory_readback_verified` is
the separate successful configuration check.

Initial preparation applies A/E after HPD-TA's own Recall 9 can no longer
overwrite them. Changing Time range authorizes and applies its exact profile
after native range confirmation. Unknown calibration (including 0.5 ns) is
rejected before any parameter write. The selector now includes 2 ms.
Operate acquisition requires calibrated A/E readback and BURM=0; failed writes
are not replayed. Focus live imaging does not require sweep-trigger calibration.
Repeat Prepare only verifies timing on an already operational rig; mismatch
fails explicitly without resetting optics, restarting servers or rewriting timing.

## ELYSE Supervision business layer (2026-10-07)

The `Supervision / ACQ` tab separates durable operator intent from the existing
evidence-replay panels. `web/backend/elyse_supervision_business.py` owns validation,
SQLite intent/event persistence, single-flight admission, and acknowledgement
reconciliation. Procedure sequencing belongs to the existing stdlib Python 3.4
agent, `legacy/xp_acq_agent/main.py --supervision`, on `tcp://10.20.30.10:8765`,
connected by `web/backend/elyse_acq_transport.py`. The original agent and
Supervision share one listener and logical state. Hardware sequencing remains
uncommissioned; no second HTTP acquisition server is started.

Current implementation is simulation-qualified only. The default adapter is
`UNCONFIGURED`; there is no UI switch enabling real hardware. The existing replay
API and all `execution_allowed: false` responses remain unchanged. Twenty-three
procedure labels and twenty arrow labels reuse recovered domain crosswalks. All
23 procedures / 158 steps are admitted by the unified simulation agent; three
magnet procedures are explicitly stubbed, with no retired DAQmx fallback. All 20
named arrows execute through the TCP simulation link. Their native arithmetic
and clamps are not commissioned physical limits. Existing replay panels remain
separate: their preview controls never silently submit to ACQ.

Two additional `Cycle ACQ` actions use the same server-owned intent lane:
`Initialiser ACQ` and `Arrêt général ACQ`. Their 42/87 steps orchestrate synthetic
initializer, resource and loop returns; they are not physical startup/shutdown
or a complete native scheduler. The seven controlled-stop phases remain
distinct from event6 shutdown, including HT <6.6 rather than zeroing and cleanup
without blanket task-clear. Stop opens an in-page confirmation dialog: Enter
confirms, Escape/cancel sends nothing. Cycle/phase/error and values are read in
one atomic signed observation, so polling cannot mix revisions during progress.
Repeated startup is refused; a failed simulated close still permits the other
close attempts but prevents a successful STOPPED claim. Mid-cycle process loss
retains UNKNOWN and blocks replay. Existing sessions migrate to UNMANAGED
without resetting prior values; managed transitions exclude arrows.

API under `/api/elyse/supervision/business`:

- `GET /`: adapter health, command catalog, latest 50 intents plus any older active
  intent, latest 100 events. Reconciliation never sends a command.
- `POST /intents`: exact `{intent_id, page, control}` for procedures; arrows also
  require finite numeric `base_value`. Save a `DRAFT`, never submit.
  Same ID/request is idempotent; changed request under the same ID returns 409.
- `POST /intents/<intent_id>/submit`: exact `{expected_revision}`. Explicit,
  simulation-only submission. Stale/missing state, any of 29 asserted DPS fields,
  an active ACQ run, or an unresolved local intent blocks procedure admission (409).
  Arrows ignore ordinary busy DPS and may overlap a procedure; their own brief
  flight and any UNKNOWN outcome block admission. ACQ also compares the base
  against its current logical value, so stale intentions cannot overwrite it.
- `GET /intents/<intent_id>/trace`: restore the selected intent's software phases,
  never resubmit. Initial arrow fields are unknown, not zero. The UI requires a
  seed for the first adjustment and restores subsequent bases from ACQ.

All routes use existing JWT/CSRF protection in production and no-store responses.
Browser-supplied DPS/telemetry, procedure names, and raw I/O are rejected. The
default database is Flask's instance directory, `elyse_supervision.sqlite3`;
`ELYSE_SUPERVISION_STATE_DB` in Flask config selects another durable path. Inject a
`SupervisionBusiness` instance through
`app.extensions['elyse_supervision_business']` for software tests.

The `AcqPort` boundary has an implemented signed, length-prefixed TCP adapter.
Configure backend `ELYSE_ACQ_URL=tcp://10.20.30.10:8765` and
`ELYSE_ACQ_SHARED_KEY_FILE` to a protected key file shared with the XP service.
The browser never receives this key. URL and key are not assumed by default;
missing configuration stays disconnected. Responses are authenticated, and both
directions have bounded frames and deadlines. The old HTTP adapter is retained
for compatibility tests only. See `legacy/xp_acq_agent/SUPERVISION.md` for installation and the LAN-only
security boundary. No existing lab service is automatically restarted.

Its normalized snapshot requires `session_id`, opaque `revision`, an
aware UTC `observed_at`, `quality: SIMULATED`, 29 typed Boolean `dps` values, and
`run: {state, intent_id, procedure, error}`. Default freshness limit is 5 s: a
modern policy, not a recovered LabVIEW safety guarantee. Submission must atomically
compare session/revision on the ACQ side and deduplicate immutable intent IDs.
Current `DS_ElyseAcq.execute_procedure_json` alone does not satisfy this boundary.

Lifecycle: `DRAFT/BLOCKED -> SUBMITTING -> ACCEPTED/RUNNING ->
SUCCEEDED/FAILED/CANCELLED`. A lost or malformed receipt yields `UNKNOWN` and
retains single-flight exclusion across restarts. Matching ID, procedure, and ACQ
session can resolve it via polling; unrelated or idle runs cannot. Authenticated
durable terminal history for the original acceptance session also resolves a
lost receipt after ACQ restart or a later client's run. Incomplete ACQ work
stays `UNKNOWN` after restart, with its DPS bit retained and no execution retry.
Never infer safe physical state from
procedure completion, cancellation, disconnection, or browser reload. Never
automatically retry, submit drafts, or clear an unknown outcome on reload.
An unacknowledged `SUBMITTING` record older than 15 s becomes `UNKNOWN`, including
after a worker crash before dispatch. It still blocks new submissions; this
timeout is not evidence that a remote command failed or did not execute.

Verification includes fake ACQ responses and actual Python 3.4 subprocesses:

```powershell
python -m pytest tests/web/test_elyse_supervision_business.py tests/web/test_elyse_acq_process_integration.py tests/web/test_elyse_acq_tcp_integration.py tests/web/test_elyse_acq_setpoint_integration.py tests/web/test_elyse_acq_lifecycle_integration.py -q
```

Local Everest harness (loopback only; no device routes or port 5000 restart):

```powershell
python tools/run_elyse_supervision_local.py --frontend-build .tmp/elyse-agent-lifecycle-build-20261007
```

The harness launches the original Python 3.4 agent on `127.0.0.1:8765` and an
isolated development web backend on `http://127.0.0.1:5059/elyse`, generating a
private key and retaining both SQLite journals in the agent's local runtime
directory. The UI restores intentions and ACQ phase logs without resubmission.

Frontend tests: `src/ElyseSupervisionBusiness.test.js` and
`src/api/elyseSupervisionClient.test.js`. Remote-host deployment, hardware authorization,
telemetry commissioning, physical setpoint submission, cancellation, and equipment-local
Supervision operations remain separate work.

This project was bootstrapped with [Create React App](https://github.com/facebook/create-react-app).

## Available Scripts

In the project directory, you can run:

### `npm start`

Runs the app in the development mode.\
Open [http://localhost:3000](http://localhost:3000) to view it in your browser.

The page will reload when you make changes.\
You may also see any lint errors in the console.

### `npm test`

Launches the test runner in the interactive watch mode.\
See the section about [running tests](https://facebook.github.io/create-react-app/docs/running-tests) for more information.

### `npm run build`

Builds the app for production to the `build` folder.\
It correctly bundles React in production mode and optimizes the build for the best performance.

The build is minified and the filenames include the hashes.\
Your app is ready to be deployed!

See the section about [deployment](https://facebook.github.io/create-react-app/docs/deployment) for more information.

### `npm run eject`

**Note: this is a one-way operation. Once you `eject`, you can't go back!**

If you aren't satisfied with the build tool and configuration choices, you can `eject` at any time. This command will remove the single build dependency from your project.

Instead, it will copy all the configuration files and the transitive dependencies (webpack, Babel, ESLint, etc) right into your project so you have full control over them. All of the commands except `eject` will still work, but they will point to the copied scripts so you can tweak them. At this point you're on your own.

You don't have to ever use `eject`. The curated feature set is suitable for small and middle deployments, and you shouldn't feel obligated to use this feature. However we understand that this tool wouldn't be useful if you couldn't customize it when you are ready for it.

## Learn More

You can learn more in the [Create React App documentation](https://facebook.github.io/create-react-app/docs/getting-started).

To learn React, check out the [React documentation](https://reactjs.org/).

### Code Splitting

This section has moved here: [https://facebook.github.io/create-react-app/docs/code-splitting](https://facebook.github.io/create-react-app/docs/code-splitting)

### Analyzing the Bundle Size

This section has moved here: [https://facebook.github.io/create-react-app/docs/analyzing-the-bundle-size](https://facebook.github.io/create-react-app/docs/analyzing-the-bundle-size)

### Making a Progressive Web App

This section has moved here: [https://facebook.github.io/create-react-app/docs/making-a-progressive-web-app](https://facebook.github.io/create-react-app/docs/making-a-progressive-web-app)

### Advanced Configuration

This section has moved here: [https://facebook.github.io/create-react-app/docs/advanced-configuration](https://facebook.github.io/create-react-app/docs/advanced-configuration)

### Deployment

This section has moved here: [https://facebook.github.io/create-react-app/docs/deployment](https://facebook.github.io/create-react-app/docs/deployment)

### `npm run build` fails to minify

This section has moved here: [https://facebook.github.io/create-react-app/docs/troubleshooting#npm-run-build-fails-to-minify](https://facebook.github.io/create-react-app/docs/troubleshooting#npm-run-build-fails-to-minify)
