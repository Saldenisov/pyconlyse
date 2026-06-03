# Optical Density (OD) Measurement Workflow

## Overview
The Avantes Dual Spectrometer Viewer now implements a reference-based OD measurement system with wavelength tracking capabilities.

## Local Emulator

On macOS the standalone app uses an Avantes/Arduino emulator by default because the real Avantes DLL is Windows-only.

```bash
python DeviceServers/cameras/avantes/avantes_dual_viewer.py
```

Environment override:

```bash
AVANTES_EMULATOR=1 python DeviceServers/cameras/avantes/avantes_dual_viewer.py
AVANTES_EMULATOR=0 python DeviceServers/cameras/avantes/avantes_dual_viewer.py
```

The emulator generates 2048-pixel spectra from 200-1100 nm with Xe-flash-like spectral shape, 1-2% pulse amplitude jitter, slow spectral drift, channel-specific fiber transport, dark signal, and detector nonlinearity. Hardware averages still wait for Arduino-like 40 Hz trigger timing, so `Pulse avg = 40` takes about 1 second.

## New Layout

```
┌──────────────────────────────────────────────────────────────┐
│  REFERENCE MEASUREMENT | DATA COLLECTION | WAVELENGTH TRACKING│
│  [Averages: 40] [Measure Reference]                          │
│  [Rate: 1.0s] [Pulse avg: 40] [Start DC] [Show]              │
│  [λ: 550nm] [Track Wavelength]                               │
├──────────────────────┬───────────────────────────────────────┤
│ Channel 1 Spectrum   │                                       │
│ (with ref line)      │                                       │
├──────────────────────┤   Optical Density (OD) Spectrum       │
│ Channel 2 Spectrum   │                                       │
│ (with ref line)      │                                       │
└──────────────────────┴───────────────────────────────────────┘
```

## Measurement Workflow

### 1. Connect Spectrometers
- Manually connect both Channel 1 and Channel 2 spectrometers
- Default serial numbers: 1810225U1 (Ch1), 1810226U1 (Ch2)

### 2. Measure Reference (I₀)
1. Set number of hardware trigger averages (default: 40)
2. Click **"Measure Reference"** button
3. System automatically:
   - Collects N measurements from both channels
   - Averages them to create reference spectra (I₀_ch1, I₀_ch2)
   - Displays reference as dashed lines on Ch1 and Ch2 plots
   - Enables "Start DC" and "Track Wavelength" buttons after background exists

### 3. Live Preview (Optional)
- Live preview is manual and runs at 1 Hz
- Experiment data collection uses its own timer and does not run at 50 ms/100 ms in the background
- No data is saved to disk until data collection is started

### 4. Start DC
1. Set measurement rate (0.1-86400 seconds, minimum 100ms)
2. Set pulse average. This maps to Avantes `m_NrAverages`, so at 40 Hz `avg=40` takes about 1 second.
3. Click **"Start DC"**
4. System saves each hardware-averaged data point to CSV
5. Click **"Show"** to open the floating OD time map window
6. OD time map fills bottom-to-top during collection: X is wavelength in nm, Y is elapsed time in seconds
7. Click **"Stop DC"** to stop collection

### 5. Wavelength Tracking
1. Set target wavelength (e.g., 550 nm)
2. Click **"Track Wavelength"**
3. Opens separate window showing:
   - Large numeric OD value at selected wavelength
   - Time-series plot of OD vs time
   - Export button for time-series data

## OD Calculation Method

### Formula: Ratio of Ratios
```
OD(λ) = log₁₀[(I₀_ch1(λ) / I₀_ch2(λ)) / (I_ch1(λ) / I_ch2(λ))]
```

Where:
- **I₀_ch1, I₀_ch2**: Reference spectra (from "Measure Reference")
- **I_ch1, I_ch2**: Current measurement spectra
- **λ**: Wavelength

This method corrects for:
- Spectral lamp intensity variations
- Spectrometer sensitivity differences
- Optical path differences between channels

## Key Features

### Reference Lines
- Dashed lines on Ch1 and Ch2 plots show reference spectra
- Red dashed = Ch1 reference
- Blue dashed = Ch2 reference

### Wavelength Tracker Window
- **Large display**: Current OD value (4 decimal places)
- **Time series plot**: OD vs time with markers
- **Clear history**: Reset time series
- **Export**: Save time series as CSV (Time, OD@λ)

### Data Export
Main window "Export Data" button saves:
- `*_spec1.csv`: Ch1 current spectrum
- `*_spec2.csv`: Ch2 current spectrum  
- `*_OD.csv`: Full OD spectrum

Wavelength tracker exports:
- `od_timeseries_550nm.csv`: Time series at specific wavelength

## Controls

### Reference Measurement Section
- **Averages**: Number of spectra to average (1-100)
- **Measure Reference**: Start reference measurement

### Data Collection Section
- **Lamp ON**: Enable flash lamp and Avantes triggers
- **Lamp OFF**: Disable flash lamp while keeping Avantes triggers available
- **Advanced**: Manual Arduino modes (`Lamp + Avantes`, `Avantes Only`, `Arduino OFF`)
- **Rate (s)**: Time between saved data points, 0.1-86400 seconds
- **Pulse avg**: Avantes hardware trigger averages per saved data point
- **Start/Stop DC**: Toggle data recording
- **Show**: Open or raise floating OD time map window

### Long-Interval Lamp Management
- Lamp warmup lead time is 120 seconds.
- If DC starts while the lamp is off, the first point is delayed until the lamp has warmed for 120 seconds.
- If the next saved point is more than 120 seconds away, the lamp is switched off between points.
- If the next saved point is 120 seconds away or sooner, the lamp stays on.
- Each saved point still uses Avantes hardware averaging: `Pulse avg = 40` at 40 Hz means 40 TTL pulses and about 1 second of averaging.

### Wavelength Tracking Section
- **λ (nm)**: Target wavelength for tracking (200-1100 nm)
- **Track Wavelength**: Open tracker window

## Status Bar Information
Shows real-time status:
- Total measurement count
- Reference status (Active/None)
- Data collection status (if active)

Example: `523 measurements | Reference: Active | Collecting data`

## Logging
Only logs:
- Initialization events
- Reference measurement start/complete
- Data collection start/stop
- Errors
- Export events
- Shutdown summary

No periodic measurement logs to keep files clean.

## Typical Use Case

### Sample Absorption Measurement
1. **Setup**: Connect both spectrometers
2. **Blank/Reference**: 
   - Place reference sample (solvent only)
   - Click "Measure Reference" (hardware averages selected pulse count)
3. **Sample Measurement**:
   - Replace with sample
   - Watch OD spectrum in real-time
4. **Time Series**:
   - Set wavelength of interest (e.g., 550 nm for rhodamine)
   - Click "Track Wavelength"
   - Watch OD change over time
5. **Data Collection**:
   - Set rate (e.g., 1.0s)
   - Click "Start DC"
   - Record time-series data
6. **Export**: Save both full spectra and time-series data

## Technical Notes

### Minimum Measurement Interval
- Arduino trigger: 25ms interval (40 Hz)
- With `Pulse avg = 40`, one hardware-averaged spectrum takes about 1 second
- User-settable range: 0.1-86400s
- Prevents USB bus overload

### Reference Stability
- Reference persists until "Clear Plots" is clicked
- Reference required for OD calculation and data collection
- Can re-measure reference anytime

### Connection Recovery
- Recoverable errors (timing) continue in background
- Fatal errors (device disconnect) stop live preview
- See logs for details

## Keyboard Shortcuts
- None currently implemented (future enhancement)

## Future Enhancements
- Automatic reference re-measurement at intervals
- Multiple wavelength tracking
- Peak detection and tracking
- Kinetics analysis tools
