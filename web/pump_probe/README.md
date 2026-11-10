# Pump-Probe Experiment Control

V0 control specification and implemented TRANCON numeric integration.

As of 2026-10-04, V0's **Files → load ZIP/H5/DAT → Corrections** supports
shot-wise signed OD recalculation, detector RAW background, scaling,
preview/apply/cancel/reset, and separate DAT/recipe downloads. Source files
remain unchanged. Native LabVIEW wire screenshot verification is pending.
See [integration evidence](../../docs/data-treatment/TRANCON_WEB_V0_INTEGRATION_2026-10-04.md).

## Goal

Run V0 pulse-radiolysis pump-probe measurements through existing Tango devices:

- delay line: OWIS Tango device, position in mm
- detector: Andor CCD Tango device, spectra from split CCD tracks
- web UI: PyConlyse V0 control page, same style as current treatment/device pages
- storage: raw spectra plus computed optical-density products
- emulator mode: no hardware required for development

## Experiment Model

User defines a scan in time delay units. Software converts each delay to delay-line position, moves the delay line, acquires spectra, saves raw data, and computes OD.

Core sequence:

1. Load experiment config.
2. Connect/verify Tango devices.
3. Convert requested delays to delay-line positions.
4. For each delay point:
   - move delay line to target mm
   - wait until motion is complete and position is within tolerance
   - acquire one V0 raw block
   - save every raw frame
   - calculate averaged spectra and OD for this delay
   - append point status to run manifest
5. Save final run summary.

## Devices

### Delay line

Existing candidates:

- `DeviceServers/motion/owis/DS_OWIS_delay_line.py`
- `DeviceServers/motion/owis/DS_OWIS_PS90.py`

Expected control surface:

- read current position, mm
- write/move target position, mm
- read Tango state
- stop motion
- apply limits before moving

Default delay conversion:

```text
position_mm = zero_position_mm + delay_ps * 0.149896229
```

Reason: optical delay changes by `2 * position / c`; `1 ps = 0.299792458 mm` light path, so reflector travel is `0.149896229 mm/ps`.

Sign must be configurable:

```text
position_mm = zero_position_mm + direction * delay_ps * 0.149896229
direction = +1 or -1
```

### Andor CCD

Existing candidates:

- `DeviceServers/cameras/andor/DS_ANDOR_CCD.py`
- `DeviceServers/cameras/andor/DS_ANDOR_CCD_client.py`

Useful existing API:

- `start_grabbing`
- `stop_grabbing`
- `image`
- `wavelengths_axis`
- `register_order_local`
- `give_order_local`
- `TriggerSoftware` / `Trigger`

Expected detector format:

```text
frame shape = (tracks, wavelength_pixels)
track 0 = signal
track 1 = reference
```

Track mapping must be configurable.

## RAW Layouts

The implementation distinguishes two formats. Their background channels have
separate physical meanings; names alone do not justify a permutation.

| Layout | Group order | Background meaning |
| --- | --- | --- |
| `trancon-detectors-v1` | `BGI, BGII, IeI, IeII, I0I, I0II` | Detector I and II; each shared across its two pulse states |
| `v0-pulse-states-v1` | `BG1, Ir1, Is1, BG2, Ir2, Is2` | OFF and ON state; each shared across signal/reference |

Modern TRANCON ZIP stores a wavelength header, then `S_<delay>`, six complete
shot groups, and `E_` markers. Rows are reshaped as `[group, shot, wavelength]`
without averaging. Shot count may differ between delay blocks. Incomplete or
malformed blocks are rejected.

V0 HDF5 stores `raw_data[delay, group, shot, wavelength]` and `frame_counts`.
Only acquired counts are read; unused NaN padding is excluded by those counts.
Unknown or permuted HDF5 channel semantics permit stored-OD viewing and scaling,
but block RAW reconstruction. New emulator runs write layout and algorithm
metadata explicitly.

## V0 Scan Parameters

Legacy/LabVIEW names:

| name | meaning |
| --- | --- |
| `OZ, ps` | optical zero, in ps |
| `# points` | number of delay points in scan |
| `Kinetic, ps` | scan duration after optical zero |
| `Total, ps` | total time window |
| `Real zero, ps` | real zero position in ps |
| `Pulses / point` | accelerator pulses acquired per delay point |
| `# Cyc` | number of cycles/repeats |

These values define the delay list and acquisition repetition counts; they do not change the raw block format.

## Raw Data

Must save all raw spectra. No averaging-only save.

Recommended HDF5 layout:

```text
/metadata/config_json
/metadata/device_snapshot_json
/metadata/run_started_iso
/metadata/run_finished_iso
/delays/{delay_index}/delay_ps
/delays/{delay_index}/position_mm
/raw_data                                    shape=(delays, 6, shots, pixels)
/od                                          shape=(pixels, delays)
/wavelength_nm                               shape=(pixels,)
/delay_ps                                    shape=(delays,)
/position_mm                                 shape=(delays,)
/manifest/events_jsonl
```

Required per-frame metadata:

- delay index
- requested delay ps
- target position mm
- readback position mm
- group name: BG1, Ir1, Is1, BG2, Ir2, Is2
- shot index
- Tango timestamp if available
- local timestamp ns
- detector exposure
- detector temperature
- accelerator state if available

## OD Calculation

For each TRANCON shot, in the division order of `Raw_data_to_data.vi`:

```text
QI  = (I0I  - BGI)  / (IeI  - BGI)
QII = (I0II - BGII) / (IeII - BGII)
OD(delay, wavelength) = mean_shots(log10(QI / QII))
```

For the existing V0 emulator's OFF/ON state convention:

```text
OD(delay, wavelength) = mean_shots(
    log10(((Is1-BG1)/(Ir1-BG1)) / ((Is2-BG2)/(Ir2-BG2)))
)
```

`mean_spectra` is a display/storage product. OD uses the mean of per-shot logs;
it is not computed from `mean_spectra`. Stored HDF5 OD has priority during
ordinary load. Explicit RAW recalculation starts a new recipe from source shots.

Signed ratios and NaN/+Inf/-Inf are retained internally and in DAT downloads.
Plotly receives `null` gaps and separate nonfinite counts. No automatic absolute
value, `nanmean`, clipping, whole-shot rejection, or NaN replacement is applied.
The `drop_whole_zero` policy excludes a shot only when every pixel in all six
groups is zero; selection is explicit and excluded counts are reported.

Detector RAW background accepts two integer count offsets and subtracts each
from both its detector's numerator and denominator before division/logarithm.
It is offered only for `trancon-detectors-v1`. Scaling multiplies the OD map by
a finite scalar through the generated `ScaleUp_corrSD.vi` translation.

## Web Control UI

First useful UI page should have:

- device selector/status: delay line, Andor CCD
- emulator toggle
- delay scan editor: start, stop, step or explicit list
- conversion settings: zero mm, direction, limits, tolerance
- acquisition settings: shots per group, exposure, trigger mode
- run controls: arm, start, pause, stop, abort
- live status: current delay, target mm, readback mm, group, shot counter
- live plots:
  - raw signal/reference spectra
  - mean spectra per group
  - OD spectrum for current delay
- OD heatmap delay x wavelength
- V0 DLIII stage schematic/control
- save path and run id

No hardware-specific logic should live in React components. React calls backend run-control APIs.

## Backend Control Service

Recommended modules:

```text
web/pump_probe/config.py
web/pump_probe/emulator.py
web/pump_probe/models.py
web/pump_probe/runner.py
web/pump_probe/storage.py
web/backend/pump_probe_api.py
```

Responsibilities:

| module | responsibility |
| --- | --- |
| `models.py` | dataclasses for config, point status, frame group, run summary |
| `emulator.py` | fake delay line and fake split-track spectrometer |
| `runner.py` | deterministic scan state machine |
| `storage.py` | HDF5 writer and manifest writer |
| `pump_probe_api.py` | Flask API endpoints |

## Emulator

Emulator must reproduce the same interface as hardware adapter layer.

Delay-line emulator:

- stores position in mm
- simulates movement time
- enforces limits
- returns states: `ON`, `MOVING`, `FAULT`

Andor emulator:

- generates wavelength axis
- returns frames with shape `(2, pixels)`
- track 0 signal, track 1 reference by default
- supports BG1, Ir1, Is1, BG2, Ir2, Is2 groups
- adds configurable noise
- adds kinetic OD feature changing with delay

Synthetic signal idea:

```text
reference = lamp_spectrum + noise
signal_off = reference * baseline_ratio + noise
od(delay, wavelength) = amplitude(delay) * gaussian(wavelength)
signal_on = signal_off / 10**od
background = dark_level + read_noise
```

## Run State Machine

```text
IDLE
  -> CONFIGURED
  -> ARMED
  -> RUNNING
  -> PAUSED
  -> RUNNING
  -> COMPLETED

Any active state -> ABORTING -> ABORTED
Any active state -> FAULT
```

Rules:

- `abort` stops acquisition and delay-line motion immediately.
- `pause` completes current frame group, then stops before next move.
- failed move marks point failed and stops run unless `continue_on_point_error=true`.
- failed detector read retries configurable number of times.

## API Sketch

```text
GET  /api/pump-probe/status
POST /api/pump-probe/config
POST /api/pump-probe/arm
POST /api/pump-probe/start
POST /api/pump-probe/pause
POST /api/pump-probe/resume
POST /api/pump-probe/abort
GET  /api/pump-probe/runs/{run_id}
GET  /api/pump-probe/runs/{run_id}/od
GET  /api/pump-probe/runs/{run_id}/raw
```

## Development Plan

1. Confirm this README/spec.
2. Implement emulator and unit tests in `conda run -n pyconlyse39`.
3. Implement runner against emulator only.
4. Add HDF5 storage and OD calculation tests.
5. Add Flask API.
6. Add minimal React control page.
7. Swap emulator adapters for Tango adapters.
8. Test with real delay line only.
9. Test with real Andor only.
10. Run full pump-probe hardware test.

## Emulator Trial Run

The V0 web `Start` control runs the emulator acquisition when `control=emulator`.
Choose or create a data folder first. The run waits for each virtual delay-line move,
writes `Pulses / point` unaveraged cycles for every delay, then publishes:

```text
v0_*.h5      canonical raw HDF5 run
v0_*.dat     computed OD matrix
v0_*.jsonl   frame-level acquisition manifest
```

Each emulator cycle records all six groups in `raw_data`:
`BG1, Ir1, Is1, BG2, Ir2, Is2`. Loading the generated `.h5` in the V0 Files window
shows both the OD heatmap and the raw-group spectra.

## Open Decisions

- Real Tango device names for delay line and Andor CCD.
- Delay sign convention.
- Exact CCD track order: signal/reference or reference/signal.
- Which pulse state has electrons by default.
- Whether accelerator pulse state is readable from Tango/PSP.
- Required output format besides HDF5: CSV, DAT, JSON, or Igor.
- Where run files should be saved by default.

## VD2 camera-only RemoteEx commissioning

The camera-only path uses `HPDTA8_VD2_RemoteEx.INI` and
`VD2_RemoteEx_Streak_Only.hwp` under `C:\ProgramData\Hamamatsu\HPDTA`.
The manual HPD-TA shortcut uses its own profile.

Deploy the Web and both Tango server changes together. On the camera Tango
device set `remote_camera_only=true` and `start_application_on_turn_on=0`.
The optional `camera_only_ini_path` property defaults to the path above.
Set `PYCONLYSE_VD2_CAMERA_ONLY=1` for Pyconlyse Web after checking that
RemoteEx starts with a working DCAM readout and Kymera responds through Tango.
Verify the trigger and the two outgoing pulses on the scope before capture.
A stale or absent HIS spectral header keeps the raw file and blocks H5
conversion until the calibration is verified.

For the Internal 5 Hz clock, the managed ABS and BASE sequence enables a
two-pulse burst at 100 ms spacing, waits ten seconds, and then starts camera
capture. Use an even frame count. After capture the worker verifies single-shot
standby and Burst OFF before saving. BRUIT uses 5 Hz without the flash-lamp
warm-up. Check that the dark optical path is configured before recording BRUIT.

### Paired beam acquisition design

Record BRUIT with the same camera geometry and gain before opening the
measurement run. Warm the flash lamp for 10 s at 10 Hz before retaining pairs.
A verified accelerator cycle contributes one ABS frame with electrons and one
BASE frame without electrons. Fixed mode counts completed tagged pairs, so a
target of 200 means 200 ABS and 200 BASE frames. Report incomplete cycles
separately. The internal timing check measures camera cadence only.

For continuous mode, retain raw frames, camera sequence numbers, cycle IDs,
beam tags, and probe-monitor values in acquisition order. Stream committed
pairs to server-side reduction independently of the latest-image browser
preview. Preview may skip images. A raw sequence gap is a recorded event.
The pulse budget and a user Stop must bound the run even if it never meets the
error target. Restore the verified DG645 5 Hz base clock and standby at exit.

The offline reducer in `utilities/dataio/vd2_paired_od.py` supports:

- OD of the background-corrected ABS and BASE means.
- The mean of per-pair OD. The first complete pair can produce a preview.
- Pairing each ABS with a BASE of similar probe intensity within bounded cycle
  distance and intensity mismatch. BASE reuse is auditable. Match using a lamp
  monitor or a pre-beam reference region outside the signal ROI.
- Replay with specified excluded cycles. Cleaning thresholds should be derived
  from a beam-off control. Raw frames and exclusions must remain accessible.

Show mean ROI OD and the estimated uncertainty of that mean in mOD. Use
contiguous cycle blocks to test the effect of correlated lamp drift. Include
the background contribution when material, and account for reused BASE frames
in the matched method. Changing ROI or reduction must recompute from stored
frames or sufficient statistics. Automatic termination requires a verified
frame/tag join, a validated block uncertainty estimate for the selected
method, and sufficient independent data. The offline reducer does not control
acquisition or claim a live uncertainty estimate.
