# Andor SDK2 Research Notes

Source archive used for this note:
- `/Volumes/Everest/Andor SDK.zip`

Date:
- 2026-04-13

## What Is In The Archive

The mounted archive is a full Andor SDK2 distribution, not just a loose DLL.

Top-level components confirmed:
- `Andor SDK/atmcd32d.dll`
- `Andor SDK/atmcd64d.dll`
- `Andor SDK/ATMCD32D.H`
- `Andor SDK/Software Development Kit.pdf`
- `Andor SDK/SDKReadme.htm`
- `Andor SDK/Examples/C/...`
- `Andor SDK/Examples/LabVIEW/...`
- `Andor SDK/atspectrograph/...`
- `Andor SDK/Shamrock/...`
- `Andor SDK/Device Driver/USB/...`
- `Andor SDK/Device Driver/PCI/...`

This means we have enough local material to drive the Tango integration from the vendor SDK itself, without guessing from screenshots alone.

## Direct SDK2 Functions Confirmed

Confirmed in `ATMCD32D.H`:
- `Initialize`
- `InitializeDevice`
- `SetAcquisitionMode`
- `SetADChannel`
- `SetExposureTime`
- `SetFastExtTrigger`
- `SetHSSpeed`
- `SetKineticCycleTime`
- `SetMultiTrack`
- `SetNumberAccumulations`
- `SetNumberKinetics`
- `SetPreAmpGain`
- `SetReadMode`
- `SetTemperature`
- `SetTriggerMode`
- `SetVSSpeed`
- `CoolerON`
- `CoolerOFF`
- `StartAcquisition`
- `GetAcquiredData`
- `GetAcquisitionTimings`
- `AbortAcquisition`
- `ShutDown`
- `GetFastestRecommendedVSSpeed`
- `GetNumberADChannels`
- `GetHSSpeed`
- `GetTemperatureRange`
- `SendSoftwareTrigger`

The current Python Tango device server already wraps a useful subset of these, but not all of the setup and validation helpers.

## SDK2 Readout And Trigger Modes Confirmed

From the local header and manual:

Readout modes:
- `0` = Full Vertical Binning
- `1` = Multi-Track
- `2` = Random-Track
- `3` = Single-Track
- `4` = Image

Acquisition modes:
- `1` = Single Scan
- `2` = Accumulate
- `3` = Kinetics
- `4` = Fast Kinetics
- `5` = Run Till Abort

Trigger modes:
- `0` = Internal
- `1` = External
- `6` = External Start
- `7` = External Exposure (Bulb)
- `9` = External FVB EM
- `10` = Software Trigger
- `12` = External Charge Shifting

## What The Vendor C Examples Show

The Andor C examples are useful because they show the expected order of operations.

### Common startup used by multiple examples

From `Examples/C/Kinetic/common.c`:
- call `Initialize(current_working_directory)`
- call `GetCapabilities`
- call `GetHeadModel`
- call `GetDetector`
- call `SetAcquisitionMode(...)`
- call `SetReadMode(...)`
- call `GetFastestRecommendedVSSpeed(...)`
- call `SetVSSpeed(...)`
- enumerate `GetNumberADChannels`, `GetNumberHSSpeeds`, `GetHSSpeed`
- choose an A/D channel and HSSpeed
- call `SetADChannel(...)`
- call `SetHSSpeed(0, selected_index)`
- optionally enable `SetBaselineClamp(1)` when supported

Important implication:
- the vendor examples initialize from a directory containing required support files, not with an empty string.

### Kinetic example

From `Examples/C/Kinetic/kntcwndw.c`:
- set `SetExposureTime(exposure)`
- set accumulation and kinetic parameters
- `SetNumberAccumulations(...)`
- `SetAccumulationCycleTime(...)`
- `SetNumberKinetics(...)`
- `SetKineticCycleTime(...)`
- call `GetAcquisitionTimings(...)`
- call `StartAcquisition()`
- poll status until `DRV_IDLE`
- call `GetAcquiredData(...)`

This is the closest vendor-side example to the current TRAPS/TA usage.

### Multi-Track example

From `Examples/C/Multi Track/mtrkwndw.c`:
- set `SetExposureTime(exposure)`
- call `GetAcquisitionTimings(...)`
- validate track count and track height against detector height
- call `SetMultiTrack(noTracks, trackHeight, trackOffset, &bottom, &gap)`
- start acquisition
- call `GetAcquiredData(...)`

Important implication:
- bottom and gap returned by `SetMultiTrack` are meaningful and can be surfaced in diagnostics or UI.
- detector height should be queried before blindly applying a multi-track geometry.

### Cooler example

From `Examples/C/Cooler Image/coolimg.c`:
- call `GetTemperatureRange(&min, &max)`
- validate requested temperature
- call `CoolerON()`
- call `SetTemperature(target)`

Important implication:
- the SDK examples do explicit range validation before temperature writes.

## DETECTOR.INI And Initialization Notes

The local SDK manual and header confirm:
- `Initialize(char* dir)` may need access to `DETECTOR.INI`
- this is relevant especially for Classic CCD, ICCD and iStar families
- the manual notes that `DETECTOR.INI` is not required on some models such as iDus, iXon or Newton

Design implication for Pyconlyse:
- the Tango server should not assume one fixed initialization strategy for all Andor cameras.
- the selected model should drive whether we require a directory containing `DETECTOR.INI`.

## 32-bit / 64-bit Notes

The archive includes both:
- `atmcd32d.dll`
- `atmcd64d.dll`

Current Pyconlyse registration still points to a 32-bit DLL path. The server should eventually support choosing the DLL based on the Python runtime and installed driver pack on the target Windows machine.

## Relevance To The Existing LabVIEW Flow

The LabVIEW screenshots provided by the user match SDK2 concepts directly:
- `Initialize`
- `SetAcquisitionMode(Kinetics)`
- `SetExposureTime`
- `SetHSSpeed`
- `SetVSSpeed`
- `SetADChannel`
- `SetPreAmpGain`
- `SetTriggerMode(External)`
- `SetFastExtTrigger`
- `SetReadMode(Multi-Track)`
- `SetMultiTrack`
- `SetBaselineClamp`
- `GetAcquisitionTimings`
- `SetTemperature`
- `CoolerON`

This aligns well with the current Tango property structure in `add_ds_ANDOR_CCD.py`, so the main task is to tighten the implementation rather than redesign it from scratch.

## Pyconlyse Development Takeaways

The SDK archive gives us a reliable base for the next iteration of the Andor Tango server:
- initialization should become directory-aware
- detector geometry should come from the SDK, not hardcoded values
- readout speed selection should support recommended or enumerated values
- kinetic and multi-track configuration should be explicit and validated
- cooling should be range-checked
- 32-bit vs 64-bit DLL choice should be configurable
- web and Taurus UI can stay centered around the existing Tango attributes and commands
