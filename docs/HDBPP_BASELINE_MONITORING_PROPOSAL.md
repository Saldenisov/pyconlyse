# ELYSE HDB++ baseline monitoring proposal

## Purpose

The baseline archive answers four operational questions without storing
heartbeat noise:

1. When did a Device Server start, initialise, change state, disconnect, or
   recover?
2. What critical error was reported, and when?
3. What hardware-changing command was requested, by whom, with which
   arguments, and what reply or exception was returned?
4. Which small set of physical readbacks explains the transition?

HDB++ and the command audit journal have different responsibilities. HDB++
stores timestamped Tango attributes. The hash-chained audit journal stores
authenticated actions, command arguments, replies, exceptions, and caller
identity. HDB++ cannot identify the caller of a command.

## Baseline event policy

The baseline is change-driven. It must not create periodic archive samples
merely to prove that a device is alive.

- Archive a sample when a tracked value or quality changes.
- Archive state transitions including `FAULT`, `ALARM`, `UNKNOWN`, `DISABLE`,
  `OFF`, `STANDBY`, and recovery to `ON`.
- Archive connection and initialisation transitions.
- Archive a new non-empty error immediately, plus its UTC timestamp and count.
- Detect an unavailable Device Server in a separate health monitor, because an
  unavailable device cannot emit its own final `State` value.
- Do not archive heartbeat commands, heartbeat replies, unchanged polling
  snapshots, camera images, spectra, or repeated convergence-history JSON.
- Keep image and spectrum data in experiment HDF5 files; archive only their
  identifiers and small scalar metadata when needed.

Tango/HDB++ supports archive events triggered by value changes without an
`archive_period`. The production profile should therefore omit
`archive_period` for baseline lifecycle fields. Numeric motion/readback fields
need a device-resolution threshold. A periodic profile is reserved for a
time-bounded experiment session and is not part of the baseline.

## Common attributes for every ELYSE Device Server

The following attributes already exist on the current common base and should
be archived on change:

- `State`
- `Status`
- `last_error`
- `hardware_connection_state`
- `initialization_state`
- `hardware_lifecycle_status`
- `fault_recovery_status`
- `power_dependency_status`

`last_comment` is deliberately excluded from the baseline. It contains routine
informational messages and would mix operator audit with device health.

The following common attributes were implemented on 2026-09-02. They become
visible on each Device Server after its next controlled restart:

- `process_started_at_utc`
- `initialization_started_at_utc`
- `initialization_completed_at_utc`
- `initialization_duration_ms`
- `last_error_at_utc`
- `error_count`
- `last_state_change_at_utc`

All UTC timestamps are ISO 8601 strings. Counters reset when the process
restarts; the health monitor records the restart as a separate transition.
The common base now pushes change and archive events for these values, state,
status, hardware connection, and initialisation. It does not push unchanged
polling samples.

## Device families and selected readbacks

### Priority 0: infrastructure, power, and synchronization

Follow these first because their failure affects several downstream devices:

- `sys/database/2`
- `tango/admin/everest`
- `tango/admin/elysium2`
- `tango/admin/elysevm` after HDB++ registration
- `manip/V0/PDU_VO`
- `manip/VD2/PDU_VD2`
- `manip/SD1/PDU_SD1`
- `manip/SD2/PDU_SD2`
- `manip/ELYSE/PDU_ELYSE`
- `ELYSE/pdu/iTest`
- `control/DAQ/TRANCON-DAQ`
- `manip/general/PSP`
- `manip/sync/DG645`
- `manip/awg/keysight33509b_laser`

Selected additional attributes:

- Netio PDU: `states`.
- iTest PSU: `states`, `currents_setpoint`, `currents_meas`, `current_limits`.
- DAQmx: `states`, `counter_values`; analog values belong to an experiment
  profile unless individually classified as an interlock.
- PSP: `pending_commands_count`, `commands_received_total`,
  `commands_ack_total`, `last_command_json`, and `last_command_ack_json` after
  heartbeat messages are filtered before these attributes are updated.
- DG645: `active_backend`, `trigger_source`, `trigger_rate_hz`,
  `burst_enabled`, `burst_count`, `burst_period_s`, and `delays_json`.
- Keysight 33509B: `output_enabled`, `burst_enabled`, `waveform`,
  `frequency_hz`, `amplitude_vpp`, and `offset_v`.

### Priority 1: laser alignment, motion, and cameras

Follow all active alignment controllers:

- `manip/V0/LaserPointing-Cam1`
- `manip/V0/LaserPointing-Cam2`
- `manip/V0/Cam1_V0`
- `manip/V0/Cam2_V0`
- `manip/V0/Cam3_V0`
- `manip/general/DS_OWIS_Aggregator`
- `manip/general/DS_OWIS_PS90`
- `manip/general/DS_OWIS_PS90_IP`

Follow all 25 registered Standa axes:

- `ELYSE/motorized_devices/DE1`, `DE2`, `MM1_X`, `MM1_Y`, `MM2_X`,
  `MM2_Y`, `MME_X`, `MME_Y`
- `manip/V0/DV01`, `DV02`, `DV03`, `DV04`, `F1`, `L-2_1`, `MM3_X`,
  `MM3_Y`, `MM4_X`, `MM4_Y`, `OPA_X`, `OPA_Y`, `S1`, `S2`, `S3`,
  `TS_OPA_m`, `TS_SC_m`

Selected additional attributes:

- Standa: `power_status`, `position`, `temperature`, `power_current`, and
  `power_voltage`. Position uses a threshold based on the configured motor
  resolution; it is not sampled periodically.
- OWIS: `controller_connection_status`, `states`, and `pos1` through `pos4`.
- LaserPointing: `automatic_search_status`, `automatic_search_progress`,
  `active_point`, `active_actuator_group`, and
  `actuator_initialization_status`. Alignment sessions additionally expose
  `alignment_session_event_json`, `alignment_session_event_count`,
  `alignment_reference_json`, and `alignment_reference_revision`. These are
  change-only, append/revision-oriented records; accepting one controller's
  reference does not replace the other controller's history. Do not archive
  `automatic_search_history` in the baseline.
- Basler: `exposure_time`, `trigger_mode`, `trigger_source`, `trigger_delay`,
  and acquisition state. Do not archive image attributes.

LaserPointing should additionally expose small scalar attributes so HDB++ does
not need to store or parse a growing JSON history:

- `beam_visible`
- `centroid_delta_x`
- `centroid_delta_y`
- `centroid_error_norm`
- `automatic_iteration`

### Priority 2: detectors and experimental diagnostics

- `manip/camera/hamamatsu_streak_main`
- `manip/CR/ANDOR_CCD1`
- `manip/CR/ANDOR_SHAMROCK1`
- `manip/CR/ANDOR_KYMERA1`
- `ml/analysis/ML_UV1`

Archive lifecycle/error fields first. Add acquisition state, exposure,
spectrograph wavelength/grating, active file/run identifier, and small scalar
diagnostics only after each currently disconnected device is available and its
live attribute contract has been verified. Images and spectra remain outside
HDB++.

## Detecting a Device Server that disappears

Archiving `State` alone is insufficient: a crashed or disconnected Device
Server cannot send a final state event. Add one lightweight
`DS_HealthMonitor` on Everest. It polls reachability internally but pushes an
archive event only when something changes. It should expose:

- `last_transition_json`: device, server, previous state, new state, quality,
  UTC time, and error summary;
- `last_critical_event_json`;
- `unreachable_devices_json`;
- `transition_count` and `critical_event_count`;
- `last_scan_completed_at_utc` for the UI only, not for HDB++.

The monitor excludes `dserver/*` mirror devices, HDB++'s own high-frequency
statistics, and all heartbeat traffic. It follows the operational device names
listed above. For local Windows processes it may also record PID and process
start time; remote-host restart time must come from the Device Server's common
timestamp attributes.

`DS_HealthMonitor/elyse` was registered in Astor on 2026-09-02 and is live at
`sys/health/elyse`. It is passive: it sends only Tango reads and does not call
hardware commands. Its code-pushed archive attributes are configured locally,
but they are not yet subscribed by HDB++ pending the disposable database
acceptance test.

## Command and reply audit

Every hardware-changing web or WebSocket operation should append one journal
entry containing:

- correlation/event ID;
- request start and completion UTC timestamps and duration;
- authenticated username, roles, source IP, and client type;
- Tango device, command or attribute write, and redacted arguments;
- success, authorization denial, timeout, or failure;
- JSON-safe, size-limited reply;
- for a Tango exception: reason, description, origin, severity, and stack text;
- previous and current journal hashes.

The journal now records authenticated mutation requests, caller, arguments,
HTTP status, duration, outcome, size-limited Tango/HTTP reply, structured error,
device and command, plus the hash chain. The verifier accepts the versioned
entry format and existing legacy entries. Exact heartbeat command names are
excluded.

Heartbeat, subscription, status polling, `State`, `Status`, read-only commands,
and connection keepalives are excluded. The exclusion is by an explicit
read-only/heartbeat classification, not by silently dropping arbitrary command
names.

Direct access has an unavoidable boundary:

- Web commands can be audited completely after the journal extension.
- Pyconlyse Qt and automation commands can be audited by using a shared
  `AuditedDeviceProxy`/gateway.
- Jive, arbitrary scripts, and LabVIEW commands are attributable only if they
  use the gateway or an instrumented client library.
- Commands sent directly by HPD-TA or LabVIEW to DG645 hardware bypass Tango
  entirely. Their resulting readback changes can be archived, but the original
  command and human identity cannot be reconstructed.

TangoAccessControl should restrict direct writes after clients are migrated,
but it is authorization rather than a complete audit log.

## Activation order

1. Provision the isolated `MariaDB-HDBPP` service and schema on `D:`.
2. Register and validate ConfigurationManager and EventSubscriber with one
   disposable attribute.
3. Add the common lifecycle/error timestamp attributes.
4. Extend and test the command journal reply/exception fields.
5. Deploy `DS_HealthMonitor` in passive observation mode.
6. Enable Priority 0 attributes, verify change-only behavior, restart recovery,
   storage growth, and backup/restore.
7. Add Priority 1, then Priority 2 after reviewing one week of event volume.

No production attribute should be enabled until the disposable round-trip,
database failure recovery, and backup restore tests have passed.
