# HPD-TA RemoteEx Research Notes

Date:
- 2026-04-13

Source material used for this note:
- `/Volumes/Everest/HPDTA950.zip`
- `/Volumes/Everest/Hamamatsu.zip`
- Hamamatsu public pages and public GitHub references listed in `EXTERNAL_SOLUTIONS_SURVEY.md`

## Executive summary

The local installation is not a plain Hamamatsu camera SDK integration. It is a complete streak-camera system controlled by HPD-TA and remotely accessible through the RemoteEx text protocol. This is the most important architectural fact for the future Tango device server.

For this setup, the right first implementation is:

- Tango device server
- speaking to `TaRemoteEx.exe` over TCP
- exposing a lab-friendly subset of HPD-TA controls
- preserving HPD-TA as the owner of synchronization, acquisition state, and device coordination

## Vendor protocol facts confirmed from the local handbook

Confirmed from `RemoteExProgrammersHandbook.pdf` in `HPDTA950.zip`:

- product scope:
  - `HiPic/HPD-TA RemoteEx Programmers Handbook`
  - version `9.5`
  - document date `2019-01-11`
- transport:
  - text protocol over TCP/IP
  - command messages terminated by `<CR>` / ASCII 13
  - responses also terminated by `<CR>`
- connection greetings:
  - command port returns `RemoteEx Ready`
  - data port returns `RemoteEx Data Ready`
- response format:
  - `EC,CommandName`
  - or `EC,CommandName,param1,param2,...`
- success code:
  - `EC=0`
- important asynchronous commands:
  - `AcqStart`
  - `SeqStart`
  - `SeqSave`
  - `SeqLoad`
- async status helper:
  - `AsyncCommandStatus()`
- image/data related commands:
  - `ImgSave`
  - `ImgDataGet`
  - `ImgDataDump`
  - `ImgRingBufferGet`
- HPD-TA-only external-device commands:
  - `DevParamGet(Location,Parameter)`
  - `DevParamSet(Location,Parameter,Value)`
  - `DevParamsList(Device)`

## Concrete command examples confirmed from the handbook and local scripts

RemoteEx command examples:

- `AppStart()`
- `AcqStart(Live)`
- `AcqStart(SingleLive)`
- `AcqStop()`
- `DevParamGet(Spec,Wavelength)`
- `DevParamSet(Spec,Slit Width,20)`
- `DevParamSet(TD,Mode,Operate)`
- `ImgSave(Current,IMG,<file>,1)`
- `ImgDataDump(Current,Data,<file>)`

Confirmed from the local script `4ScanWavelengthAndAcquire.hsc`:

- set spectrograph wavelength with:
  - `DevParamSet(Spec,Wavelength,<value>)`
- acquire a single exposure with:
  - `AcqStart(SingleLive)`
- wait for completion by polling:
  - `AsyncCommandStatus()`
- save the current image with:
  - `ImgSave(Current,IMG,<file>,1)`

This script is especially valuable because it matches the exact workflow expected in a spectroscopy-driven streak experiment.

## Local HPD-TA installation profile

Confirmed from `Hamamatsu/RemoteExClient.INI`:

- host:
  - `localhost`
- command port:
  - `1001`
- data port:
  - `1002`
- default sample command:
  - `AcqStart(SingleLive)`

Confirmed from `Hamamatsu/HPDTA/Streaker.ini`:

- streak name:
  - `C5680`
- plugin:
  - `M5676`
- effect area:
  - `12.4 x 9.44`
- pulse distance:
  - `50 ns`

Confirmed from `Hamamatsu/HPDTA/HPDTA8.INI`:

- hardware profile:
  - `C:\ProgramData\Hamamatsu\HPDTA\defaultHW.hwp`
- active hardware roles:
  - `miUseTD=-1`
  - `miUseSPEC=-1`
  - `miUseDELAY=-1`
  - `miUseDELAY2=0`
  - `miUseFW=0`
- sync enabled:
  - `mfDoSync=1`
- external-device automation settings:
  - `AutoStreakShutter=0`
  - `AutoSpecShutter=0`
  - `AutoMCP=0`
  - `AutoStreakDelay=0`
- global timing-related values:
  - `TriggerDelay=150`
  - `PostTriggerTime=10`
  - `ExposureTime=10`
  - `TriggerMethod=2`

## Local readout-camera facts from HPDTA8.INI

Confirmed from the `DCamAPI213Plus camera` section:

- camera family section name:
  - `DCamAPI213Plus camera`
- trigger mode:
  - `TriggerMode=3`
- trigger polarity:
  - `TriggerPolarity=1`
- binning:
  - `Binning=1`
- scan mode:
  - `ScanMode=2`
- mechanical shutter:
  - `MechanicalShutter=Auto`
- subarray:
  - `SubarrayHOffs=176`
  - `SubarrayHWidth=640`
  - `SubarrayVOffs=258`
  - `SubarrayVWidth=508`
- lines per image:
  - `LinesPerImage=512`
- default exposure presets:
  - `Exposuretime1=10 ms`
  - `Exposuretime2=10 ms`
  - `Exposuretime3=10 ms`
  - `Exposuretime4=10 ms`

These values are useful not because the future Tango server should write directly to DCAM first, but because they describe the HPD-TA state that users already trust.

## Local external-device layout from HPDTA8.INI

The INI layout strongly suggests this mapping:

- `External devices Device1`
  - streak camera controls
  - includes `Time Range`, `Mode`, `Gate Mode`, `II-Gain`, `Shutter`, `Trig. Mode`
- `External devices Device2`
  - spectrograph controls
  - includes `Wavelength`, `Grating`, `Blaze`, `Ruling`, `Exit Mirror`, `Turret`, `Shutter`, `Focus Mirror`, `Side Entry Iris`
- `External devices Device3`
  - delay generator controls
  - includes `Delay A`..`Delay H`, repetition rate, burst mode, trigger mode

The same INI also contains `_DG645_` sections and saved settings, which is a strong confirmation that the delay unit in this setup is an SRS DG645 or a compatible control profile.

## Calibration facts confirmed locally

Confirmed from `Hamamatsu/HPDTA/C7700_0.5ns-1ms_Flash40.txt` and `HPDTA8.INI`:

- streak time ranges include:
  - `0.5 ns`
  - `1 ns`
  - `2 ns`
  - `5 ns`
  - `10 ns`
  - `20 ns`
  - `50 ns`
  - `100 ns`
  - `200 ns`
  - `500 ns`
  - `1 us`
  - `2 us`
  - `5 us`
  - `10 us`
  - `20 us`
  - `50 us`
  - `100 us`
  - `200 us`
  - `500 us`
  - `1 ms`
- system scaling:
  - X unit: `nm`
  - Y unit: `us`
- active Y scaling file:
  - `C:\ProgramData\Hamamatsu\HPDTA\C7700_0_5ns_1ms_1_us_v1.scl`
- spectrograph scaling is active through system scaling metadata

This is a strong hint that future Tango attributes should expose calibrated axes where possible, not just raw pixels.

## Spectrograph facts confirmed locally

Confirmed from `Spectro.pdf` in `HPDTA950.zip`:

- supported spectrographs include:
  - `Shamrock 303`
  - `Kymera 193i`
  - `Kymera 328i`

Confirmed from the bundled HPD-TA installation files:

- `atshamrock.dll`
- `Shamrock32.dll`
- `ShamrockCIF.dll`

Inference:
- HPD-TA is almost certainly talking to the spectrograph through the Andor Shamrock/Kymera stack internally.
- The future Tango server should not try to outsmart that stack at first. It should call HPD-TA through RemoteEx and let HPD-TA coordinate the spectrograph.

## Design implications for the Tango server

1. RemoteEx should be treated as the primary control API.

2. The device server should enforce a single serialized command path.

Why:
- the handbook explicitly describes the application as effectively single-threaded
- asynchronous acquisition needs careful handling with `AsyncCommandStatus()`

3. File-based data export is the safest first implementation.

Recommended first path:
- acquire with `AcqStart(SingleLive)` or `SeqStart()`
- save with `ImgSave` or `SeqSave`
- optionally dump raw image data with `ImgDataDump`

Later path:
- support direct binary transfer via the RemoteEx data port

4. Startup should prefer a known INI file.

Preferred RemoteEx startup form:
- `AppStart(1,<ini-path>,1,1)`

Reason:
- this anchors the session to the already validated HPD-TA profile instead of relying on whatever default state the target PC currently has

## Recommended minimum functional scope

The first Tango device server should support at least:

- connection and startup
- state reporting
- current time range readback
- current wavelength readback
- setting spectrograph wavelength
- setting spectrograph slit width
- setting streak time range
- setting MCP gain
- starting a single acquisition
- saving current image
- starting a sequence
- saving sequence
- stopping acquisition

## Open questions still worth checking on hardware

- Which exact Kymera model is connected in this installation?
- Which RemoteEx `DevParamsList(Spec)` parameters are actually exposed on the live system?
- Are there any HPD-TA dialogs or interlocks that still appear despite `fNoDialogs=true`?
- Is the lab workflow based on `SingleLive`, `Acquire`, or `Sequence` for the main use case?
- What image file format should be considered canonical for the lab:
  - `IMG`
  - `HIS`
  - TIFF variants
  - raw dumps
