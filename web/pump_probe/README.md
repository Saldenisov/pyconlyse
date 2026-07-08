# Pump-Probe Experiment Control

Draft spec for replacing the LabVIEW `trancon` workflow with Python/web control in PyConlyse.

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

## V0 Raw Block

Each delay point stores one legacy-compatible raw block:

```text
raw block shape = (12, wavelength_pixels)
```

The block is split exactly as the old `raw_convert.ipynb` expects:

```text
split into 3 blocks of 4 spectra:

block 0 -> background
block 1 -> pulse state 1
block 2 -> pulse state 2

then split each block in half:

background -> BG1, BG2
state 1    -> Ir1, Is1
state 2    -> Ir2, Is2
```

Canonical in-memory shape after parsing:

```text
raw_data[delay, group, shot, wavelength]
shape = (n_delays, 6, 2, n_pixels)
```

Group order:

| index | name | shape per delay |
| --- | --- | --- |
| 0 | BG1 | `(2, pixels)` |
| 1 | Ir1 | `(2, pixels)` |
| 2 | Is1 | `(2, pixels)` |
| 3 | BG2 | `(2, pixels)` |
| 4 | Ir2 | `(2, pixels)` |
| 5 | Is2 | `(2, pixels)` |

`1` and `2` are pulse states:

```text
one state = electrons OFF
one state = electrons ON
```

Which state has electrons is configurable:

```text
first_state_has_electrons = true | false
```

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

Let:

```text
BG1 = mean(raw_data[:, BG1], axis=shots)
Ir1 = mean(raw_data[:, Ir1], axis=shots)
Is1 = mean(raw_data[:, Is1], axis=shots)

BG2 = mean(raw_data[:, BG2], axis=shots)
Ir2 = mean(raw_data[:, Ir2], axis=shots)
Is2 = mean(raw_data[:, Is2], axis=shots)
```

If state 1 is electrons OFF and state 2 is electrons ON:

```text
S_off = Is1 - BG1
R_off = Ir1 - BG1

S_on = Is2 - BG2
R_on = Ir2 - BG2
```

Reference-normalized V0 raw formula:

```text
OD = log10((S_off / R_off) / (S_on / R_on))
```

If `first_state_has_electrons=true`, swap ON/OFF state assignment before applying the formula.

Numerical guards:

- reject or mask pixels where denominator is <= 0
- store mask alongside OD
- keep raw frames unchanged
- store mean spectra used for OD

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

## Open Decisions

- Real Tango device names for delay line and Andor CCD.
- Delay sign convention.
- Exact CCD track order: signal/reference or reference/signal.
- Which pulse state has electrons by default.
- Whether accelerator pulse state is readable from Tango/PSP.
- Required output format besides HDF5: CSV, DAT, JSON, or Igor.
- Where run files should be saved by default.
