# Tango Device Server Development Plan For Hamamatsu Streak

Date:
- 2026-04-13

Related notes:
- `README.md`
- `HPDTA_REMOTEEX_RESEARCH_NOTES.md`
- `EXTERNAL_SOLUTIONS_SURVEY.md`

## Goal

Implement a Tango device server that controls the local Hamamatsu streak-camera experiment through HPD-TA RemoteEx.

Primary design goal:
- provide stable remote control for experiment automation without bypassing the vendor's working acquisition stack

## Recommended architecture

Use a three-layer design:

### 1. Transport layer

`RemoteExClient`

Responsibilities:
- open command socket
- optionally open data socket
- send one command at a time
- wait for and parse one response at a time
- normalize error codes
- expose helper methods for:
  - plain command execution
  - async polling
  - connection health checks

Key rule:
- no concurrent command writes

### 2. Domain layer

`HamamatsuStreakController`

Responsibilities:
- translate high-level operations into RemoteEx commands
- enforce safe ordering
- expose meaningful Python methods such as:
  - `start_app()`
  - `stop_app()`
  - `get_status()`
  - `get_time_range()`
  - `set_time_range(value)`
  - `get_wavelength()`
  - `set_wavelength(value_nm)`
  - `set_slit_width(value_um)`
  - `get_mcp_gain()`
  - `set_mcp_gain(value)`
  - `acquire_single()`
  - `save_current_image(path)`
  - `start_sequence()`
  - `save_sequence(path)`
  - `abort()`

This layer should also convert RemoteEx errors into typed Python exceptions.

### 3. Tango layer

`DS_Hamamatsu_Streak`

Responsibilities:
- expose Tango attributes and commands
- keep Tango state coherent with controller state
- publish acquisition status, last error, and current configuration

## Why wrap HPD-TA instead of the camera directly

Reasons:

- HPD-TA already coordinates streak camera, spectrograph, and delay generator
- HPD-TA already manages synchronization and acquisition sequencing
- the installed setup is validated by existing INI/workflow files
- the RemoteEx handbook explicitly documents remote control for HPD-TA

Directly driving the readout camera SDK and the spectrograph SDK in parallel would create unnecessary risk in the first version.

## Recommended first Tango device model

Start with one Tango device class representing the whole streak experiment, not separate low-level devices.

Suggested device scope:

- one device server process
- one main device class for the HPD-TA session
- optional later split into logical child devices only after the end-to-end flow is stable

Suggested first device name style:

- `lab/hamamatsu_streak/main`

## Suggested attributes

Read-only or read-write attributes for the first version:

- `Host`
- `CommandPort`
- `DataPort`
- `Connected`
- `ApplicationRunning`
- `RemoteExStatus`
- `LastErrorCode`
- `LastErrorText`
- `CurrentTimeRange`
- `CurrentStreakMode`
- `CurrentGateMode`
- `CurrentMCPGain`
- `CurrentWavelength`
- `CurrentGrating`
- `CurrentSlitWidth`
- `CurrentSpectrographShutter`
- `CurrentTriggerMethod`
- `CurrentTriggerDelay`
- `CurrentExposureTime`
- `LastSavedImagePath`
- `LastSavedSequencePath`
- `LastAcquisitionDuration`

Potential later data attributes:

- `LastImagePath`
- `LastSequencePath`
- `LastImageShape`
- `LastImageTimestamp`
- `LastProfile`

I would avoid a direct large image Tango attribute in version 1 unless the lab clearly needs it. File-based export is simpler and more robust initially.

## Suggested commands

### Lifecycle

- `Connect`
- `Disconnect`
- `StartApplication`
- `StopApplication`
- `ShutdownRemoteEx`

### Discovery

- `RefreshMainParameters`
- `RefreshDeviceParameters`
- `ListStreakParameters`
- `ListSpectrographParameters`
- `ListDelayParameters`

### Streak controls

- `SetTimeRange`
- `SetStreakMode`
- `SetGateMode`
- `SetMCPGain`
- `SetStreakShutter`

### Spectrograph controls

- `SetWavelength`
- `SetGrating`
- `SetSlitWidth`
- `SetSpectrographShutter`

### Acquisition

- `AcquireSingle`
- `StartLive`
- `StopAcquisition`
- `StartSequence`
- `SaveCurrentImage`
- `SaveCurrentSequence`
- `DumpCurrentImageData`

### Utility

- `LoadIniProfile`
- `LoadWorkfile`
- `PingRemoteEx`

## Safe execution rules

The server should enforce these rules from day one:

1. Only one in-flight RemoteEx command at a time.

2. After `AcqStart`, `SeqStart`, `SeqSave`, or `SeqLoad`, use `AsyncCommandStatus()` to wait for the real state transition.

3. Never issue a new heavy command while an async action is still preparing or active.

4. Prefer `AppStart(..., fNoDialogs=true, ...)` for remote use.

5. Keep a structured operation log of:
   - outgoing command
   - response text
   - elapsed time
   - parsed error code

## Recommended startup path

Preferred sequence:

1. Connect to RemoteEx command socket.
2. Optionally connect to data socket.
3. Confirm greeting string.
4. Start HPD-TA with known INI:
   - `AppStart(1,<ini-path>,1,1)`
5. Query:
   - `AppInfo(Version)`
   - `MainParamsList()`
   - `DevParamsList(TD)`
   - `DevParamsList(Spec)`
   - `DevParamsList(Del)`
6. Cache the parameter surfaces.
7. Expose Tango attributes only after this cache is consistent.

## Development phases

### Phase 1. Transport and replay

Deliverables:

- `RemoteExClient`
- parser for `EC,CommandName,...`
- timeout handling
- command logging
- replay fixture based on recorded responses

Why first:
- this lets development continue without hardware for many cases

### Phase 2. Minimal working controller

Deliverables:

- app start/stop
- status readback
- wavelength read/write
- time-range read/write
- single acquisition
- save current image

Success criterion:
- a Python script can set wavelength, set time range, acquire, and save an image

### Phase 3. Tango wrapper

Deliverables:

- Tango device class
- key attributes and commands
- device properties for:
  - host
  - command port
  - data port
  - INI path
  - default save directory
  - command timeout

Success criterion:
- Jive or a simple PyTango client can operate the setup end-to-end

### Phase 4. Sequence and data products

Deliverables:

- sequence support
- profile extraction wrappers
- optional file metadata parsing
- optional path conventions for experiment storage

### Phase 5. Optional binary streaming

Deliverables:

- RemoteEx data-port handling
- image frame transfer
- ring-buffer support if truly needed

This phase should only happen after the file-based workflow is stable.

## Testing strategy

### Offline tests

- response parser unit tests
- async-state transition tests
- controller method tests with mocked RemoteEx replies
- property validation tests

### On-hardware smoke tests

- connect
- start app with the known INI
- read current wavelength
- read current time range
- change wavelength by a small step
- acquire one image
- save one image
- restore original wavelength

### Regression tests after every change

- command ordering under async operations
- safe stop / abort
- reconnect after RemoteEx restart

## Known risks

### 1. Dialogs or hidden interlocks

Mitigation:
- keep `fNoDialogs=true`
- capture all message responses
- maintain a clear operator log

### 2. Path handling on Windows

Mitigation:
- normalize path handling in one place
- always test saving to a known writable directory

### 3. RemoteEx single-threaded behavior

Mitigation:
- queue all commands
- no parallel acquisition control

### 4. Lab-specific HPD-TA state drift

Mitigation:
- prefer explicit startup with the validated INI
- read back important state after every set

## First coding tasks after these notes

1. Create `remoteex_client.py`
2. Create `remoteex_protocol.py` for parsing and error codes
3. Create `hamamatsu_streak_controller.py`
4. Add a tiny CLI smoke-test script
5. Add unit tests for parsing and async handling
6. Only then add the Tango device class

## Recommended non-goals for version 1

- do not reimplement HPD-TA image processing features
- do not bypass HPD-TA to talk to DCAM directly
- do not split the system into multiple Tango device classes too early
- do not depend on the RemoteEx binary data port for the first usable release
