# DS_ANDOR_CCD Development Plan

Date:
- 2026-04-13

Related files:
- [DS_ANDOR_CCD.py](/Users/sad/dev/pyconlyse/DeviceServers/cameras/andor/DS_ANDOR_CCD.py)
- [DS_ANDOR_CCD_Widget.py](/Users/sad/dev/pyconlyse/DeviceServers/cameras/andor/DS_ANDOR_CCD_Widget.py)
- [add_ds_ANDOR_CCD.py](/Users/sad/dev/pyconlyse/DeviceServers/cameras/andor/add_ds_ANDOR_CCD.py)
- [device_api.py](/Users/sad/dev/pyconlyse/web/backend/device_api.py)
- [SDK2_RESEARCH_NOTES.md](/Users/sad/dev/pyconlyse/DeviceServers/cameras/andor/SDK2_RESEARCH_NOTES.md)

## Current State

The project already has:
- a Tango device server class for Andor CCD
- a Taurus widget that draws spectra and transient absorption style output
- web API support that already treats `DS_ANDOR_CCD` as a camera family

This is a strong base. The next step is to remove the hardcoded assumptions that make the server fragile on a real Andor installation.

## Main Gaps In The Current Device Server

### 1. Initialization path is too weak

Current code:
- `find_device()` calls `_Initialize()` without a directory
- `_Initialize()` defaults to `""`

Relevant lines:
- [DS_ANDOR_CCD.py](/Users/sad/dev/pyconlyse/DeviceServers/cameras/andor/DS_ANDOR_CCD.py:64)
- [DS_ANDOR_CCD.py](/Users/sad/dev/pyconlyse/DeviceServers/cameras/andor/DS_ANDOR_CCD.py:336)

SDK examples do this instead:
- `GetCurrentDirectory(...)`
- `Initialize(current_directory)`

Why it matters:
- SDK2 may need local support files and, for some cameras, `DETECTOR.INI`.

### 2. Detector width is hardcoded into acquisition

Current code uses fixed values:
- `_GetData(size=1024 * self.n_kinetics * 2)`
- reshape to `(-1, 1024)`

Relevant lines:
- [DS_ANDOR_CCD.py](/Users/sad/dev/pyconlyse/DeviceServers/cameras/andor/DS_ANDOR_CCD.py:273)
- [DS_ANDOR_CCD.py](/Users/sad/dev/pyconlyse/DeviceServers/cameras/andor/DS_ANDOR_CCD.py:277)

Why it matters:
- the SDK examples query detector geometry via `GetDetector`.
- a hardcoded width will break as soon as the camera, ROI or mode changes.

### 3. Speed selection is static instead of SDK-driven

Current configuration uses a fixed tuple such as:
- `HSSpeed = (0, 1)`
- `VSSpeed = 1`
- `ADChannel = 1`

The vendor examples instead:
- query `GetFastestRecommendedVSSpeed`
- enumerate `GetNumberADChannels`
- enumerate `GetNumberHSSpeeds`
- inspect `GetHSSpeed`
- then choose valid values

Why it matters:
- the same integers do not have the same meaning across all cameras and output amplifiers.

### 4. Kinetics setup is incomplete

Current loop sets:
- `SetNumberKinetics`
- `StartAcquisition`
- `GetAcquiredData`

Relevant lines:
- [DS_ANDOR_CCD.py](/Users/sad/dev/pyconlyse/DeviceServers/cameras/andor/DS_ANDOR_CCD.py:269)

But the Andor kinetic example also uses:
- `SetNumberAccumulations`
- `SetAccumulationCycleTime`
- `SetKineticCycleTime`
- `GetAcquisitionTimings`

Why it matters:
- for TRAPS-like operation, valid timing readback is just as important as setting the nominal values.

### 5. Cooling path needs range validation

Current code exposes:
- `_SetTemperature`
- `_CoolerON`
- `_CoolerOFF`

Relevant lines:
- [DS_ANDOR_CCD.py](/Users/sad/dev/pyconlyse/DeviceServers/cameras/andor/DS_ANDOR_CCD.py:776)
- [DS_ANDOR_CCD.py](/Users/sad/dev/pyconlyse/DeviceServers/cameras/andor/DS_ANDOR_CCD.py:804)

What is missing:
- `GetTemperatureRange`
- validation of the requested setpoint against the model limits
- a readable Tango attribute for current temperature and cooling status

### 6. Device startup still contains lab-specific hardcoding

Current `turn_on_local()` opens a TCP socket to `10.20.30.131:5025` and sends `*RCL 8`.

Relevant line:
- [DS_ANDOR_CCD.py](/Users/sad/dev/pyconlyse/DeviceServers/cameras/andor/DS_ANDOR_CCD.py:201)

Why it matters:
- this is not a generic camera initialization step.
- it should be isolated behind an optional property or removed from the core server path.

### 7. DLL selection is still fixed to 32-bit

Current Tango registration points to:
- `C:/dev/pyconlyse/DeviceServers/ANDOR_CCD/atmcd32d.dll`

Relevant line:
- [add_ds_ANDOR_CCD.py](/Users/sad/dev/pyconlyse/DeviceServers/cameras/andor/add_ds_ANDOR_CCD.py:1057)

Why it matters:
- the SDK archive includes both 32-bit and 64-bit DLLs.
- this needs to be runtime-aware or at least deployment-configurable.

## Current UI Status

### Taurus widget

The widget already:
- can start and stop grabbing
- requests ordered data via `register_order` and `give_order`
- draws several spectra plus a transient absorption plot

Relevant file:
- [DS_ANDOR_CCD_Widget.py](/Users/sad/dev/pyconlyse/DeviceServers/cameras/andor/DS_ANDOR_CCD_Widget.py)

This means we do not need to invent a new desktop widget. We need better Tango data semantics underneath it.

### Web API

The web API already:
- lists `DS_ANDOR_CCD` in `/api/cameras`
- serves `/api/camera/<device>/info`
- serves `/api/camera/<device>/parameters`
- serves `/api/camera/<device>/grabbing`
- serves `/api/camera/<device>/image`

Relevant lines:
- [device_api.py](/Users/sad/dev/pyconlyse/web/backend/device_api.py:1744)
- [device_api.py](/Users/sad/dev/pyconlyse/web/backend/device_api.py:1805)
- [device_api.py](/Users/sad/dev/pyconlyse/web/backend/device_api.py:1842)
- [device_api.py](/Users/sad/dev/pyconlyse/web/backend/device_api.py:1881)
- [device_api.py](/Users/sad/dev/pyconlyse/web/backend/device_api.py:1935)

This is enough for a first usable browser client once the Tango server reports coherent data.

## Recommended Implementation Order

### Phase 1. Make the Tango server trustworthy

1. Add robust initialization path handling.
2. Add wrappers for missing geometry and timing helpers:
   - `GetDetector`
   - `GetTemperatureRange`
   - `GetFastestRecommendedVSSpeed`
   - `GetNumberHSSpeeds`
   - `GetHSSpeed`
3. Remove hardcoded acquisition width from the grabbing loop.
4. Make HSSpeed/VSSpeed/ADChannel selection validated.
5. Isolate the TCP side-effect in `turn_on_local()` behind a property or feature flag.

### Phase 2. Improve Tango attributes

Add or improve attributes for:
- detector width and height from SDK
- actual exposure, accumulation and kinetic timings
- current temperature
- cooler state
- multitrack geometry
- selected AD channel and speed indices

### Phase 3. Align configuration with the LabVIEW/TRAPS path

Make the device property layer express:
- acquisition mode
- read mode
- trigger mode
- fast external trigger
- multitrack tuple
- kinetic count
- accumulation count
- accumulation cycle time
- kinetic cycle time
- temperature target
- cooler enabled

### Phase 4. Finish visualization

On top of the corrected Tango server:
- keep the current Taurus widget and wire any missing controls
- add a web visualization that treats Andor output as spectra, not a generic 2D image only
- expose wavelength axis and transient absorption-friendly payloads if needed

## Immediate Next Coding Tasks

The next implementation pass should start with:
1. refactor `_Initialize()` to accept a real SDK directory
2. add detector geometry and temperature-range wrappers
3. replace the hardcoded `1024` acquisition logic with SDK-derived dimensions
4. add a configuration mode for "recommended speed" vs "fixed speed"
5. document deployment expectations for 32-bit vs 64-bit SDK

## Working Assumptions To Revisit When Hardware Is Available

- We still need the exact Andor camera model.
- We still need to confirm whether a Shamrock spectrograph is part of the acquisition chain.
- We still need to confirm whether the target Windows host is 32-bit Python or 64-bit Python.
- We still need to validate whether the desired trigger mode is plain external trigger or external exposure.
- We still need to confirm whether `Temperature -> CoolerON` or `CoolerON -> Temperature` is preferred on the actual hardware for this model.
