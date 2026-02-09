# Optical Density (OD) Measurement Workflow

## Overview
The Avantes Dual Spectrometer Viewer now implements a reference-based OD measurement system with wavelength tracking capabilities.

## New Layout

```
┌──────────────────────────────────────────────────────────────┐
│  REFERENCE MEASUREMENT | DATA COLLECTION | WAVELENGTH TRACKING│
│  [Averages: 10] [Measure Reference]                          │
│  [Rate: 1.0s] [Start Data Collection]                        │
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
1. Set number of averages (default: 10)
2. Click **"Measure Reference"** button
3. System automatically:
   - Collects N measurements from both channels
   - Averages them to create reference spectra (I₀_ch1, I₀_ch2)
   - Displays reference as dashed lines on Ch1 and Ch2 plots
   - Enables continuous display mode
   - Enables "Start Data Collection" and "Track Wavelength" buttons

### 3. Continuous Monitoring (Optional)
- After reference measurement, continuous mode is automatically active
- Both channels displayed in real-time
- OD spectrum calculated and updated continuously
- No data is saved to disk yet

### 4. Start Data Collection
1. Set measurement rate (0.1-10.0 seconds, minimum 100ms)
2. Click **"Start Data Collection"**
3. System begins saving time-series OD data
4. Click again to stop collection

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
- **Rate (s)**: Measurement interval (0.1-10.0s, min 100ms)
- **Start/Stop Data Collection**: Toggle data recording

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
   - Click "Measure Reference" (averages 10 measurements)
3. **Sample Measurement**:
   - Replace with sample
   - Watch OD spectrum in real-time
4. **Time Series**:
   - Set wavelength of interest (e.g., 550 nm for rhodamine)
   - Click "Track Wavelength"
   - Watch OD change over time
5. **Data Collection**:
   - Set rate (e.g., 1.0s)
   - Click "Start Data Collection"
   - Record time-series data
6. **Export**: Save both full spectra and time-series data

## Technical Notes

### Minimum Measurement Interval
- Hardware limit: 100ms (Arduino trigger at 10 Hz)
- User-settable range: 0.1-10.0s
- Prevents USB bus overload

### Reference Stability
- Reference persists until "Clear Plots" is clicked
- Reference required for OD calculation and data collection
- Can re-measure reference anytime

### Connection Recovery
- Recoverable errors (timing) continue in background
- Fatal errors (device disconnect) stop continuous mode
- See logs for details

## Keyboard Shortcuts
- None currently implemented (future enhancement)

## Future Enhancements
- Automatic reference re-measurement at intervals
- Multiple wavelength tracking
- Peak detection and tracking
- Kinetics analysis tools
