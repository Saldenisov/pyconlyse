# Avantes Dual Spectrometer Viewer - Quick Start Guide

## Overview

A standalone PyQt5 application for **simultaneous parallel readout** of two Avantes spectrometers without any Tango dependencies. Perfect for lab measurements, data acquisition, and real-time spectral analysis.

![Application Screenshot](screenshot_placeholder.png)

## Features

✅ **True Parallel Operation** - Both spectrometers measure simultaneously  
✅ **No Tango Required** - Standalone application  
✅ **Live Plotting** - Real-time spectrum visualization with pyqtgraph  
✅ **Independent Control** - Configure each spectrometer separately  
✅ **Continuous Mode** - Configurable update rates up to 10 Hz  
✅ **Data Export** - Save measurements to CSV  
✅ **Hardware Trigger** - Support for external trigger (Arduino, etc.)  

## Installation

### Prerequisites

```powershell
# Install required Python packages
pip install PyQt5 pyqtgraph numpy msl-equipment
```

### Verify Installation

Check that you have the required libraries:

```powershell
python -c "import PyQt5, pyqtgraph, numpy, msl.equipment; print('All dependencies installed!')"
```

## Quick Start

### 1. Launch the Application

```powershell
cd C:\dev\pyconlyse\DeviceServers\cameras\avantes
python avantes_dual_viewer.py
```

### 2. Connect Spectrometers

**For Spectrometer 1:**
1. Enter the serial number (e.g., `1810225U1`)
2. Click "Connect"
3. Wait for green "Connected" status

**For Spectrometer 2:**
1. Enter the serial number (e.g., `1810226U1`)
2. Click "Connect"
3. Wait for green "Connected" status

### 3. Configure Measurement Parameters

For each spectrometer, set:
- **Integration Time (ms)**: Exposure time (0.1 - 10000 ms)
- **Averages**: Number of spectra to average (1-100)
- **Trigger Mode**: 
  - Software (immediate start)
  - Hardware (wait for external trigger)
  - Synchronous (sync mode)

### 4. Acquire Data

**Single Measurement:**
- Click "Single Measurement" button
- Both spectrometers measure in parallel
- Results display immediately

**Continuous Mode:**
1. Check "Continuous" checkbox
2. Set "Update Rate" (e.g., 1 Hz)
3. Watch live spectra update
4. Uncheck to stop

## Application Layout

```
┌─────────────────────────────────────────────────────────────┐
│  Measurement Controls                                       │
│  [Single] [☑Continuous] [Rate: 1.0 Hz] [Export] [Clear]   │
├──────────────────────────┬──────────────────────────────────┤
│ Spectrometer 1           │ Spectrometer 2                   │
│ ┌────────────────────┐   │ ┌────────────────────┐          │
│ │ Serial: 1810225U1  │   │ │ Serial: 1810226U1  │          │
│ │ Status: Connected  │   │ │ Status: Connected  │          │
│ │ Integration: 100ms │   │ │ Integration: 100ms │          │
│ │ Averages: 1        │   │ │ Averages: 1        │          │
│ │ Trigger: Software  │   │ │ Trigger: Software  │          │
│ │ Pixels: 2048       │   │ │ Pixels: 2048       │          │
│ │ λ: 200.0-1100.0 nm │   │ │ λ: 200.0-1100.0 nm │          │
│ │ Mean: 15234.5      │   │ │ Mean: 14892.3      │          │
│ │ Max: 62341.0       │   │ │ Max: 61234.0       │          │
│ └────────────────────┘   │ └────────────────────┘          │
├──────────────────────────┴──────────────────────────────────┤
│         Spectrometer 1 Plot (Red)                           │
│  Intensity vs Wavelength                                    │
├─────────────────────────────────────────────────────────────┤
│         Spectrometer 2 Plot (Blue)                          │
│  Intensity vs Wavelength                                    │
└─────────────────────────────────────────────────────────────┘
```

## Usage Examples

### Example 1: Basic Measurement

```python
# 1. Enter serial numbers for both spectrometers
# 2. Click "Connect" for both
# 3. Leave default settings (100ms integration, 1 average, software trigger)
# 4. Click "Single Measurement"
# 5. View results in both plots
```

### Example 2: Continuous Monitoring at 2 Hz

```python
# 1. Connect both spectrometers
# 2. Set integration time to 100 ms for both
# 3. Check "Continuous" checkbox
# 4. Set update rate to 2.0 Hz
# 5. Watch live spectra update every 0.5 seconds
```

### Example 3: Hardware-Triggered Synchronized Measurement

```python
# 1. Connect both spectrometers
# 2. For BOTH: Set "Trigger Mode" to "Hardware"
# 3. Click "Single Measurement"
# 4. Application waits for external trigger (Arduino, function generator, etc.)
# 5. When trigger fires, both measure simultaneously
# 6. Results display once both complete
```

### Example 4: High-SNR Measurement with Averaging

```python
# 1. Connect both spectrometers
# 2. Set integration time to 50 ms
# 3. Set averages to 10 (for both)
# 4. Click "Single Measurement"
# 5. System performs 10 measurements and averages automatically
```

### Example 5: Export Data for Analysis

```python
# 1. Perform measurement(s)
# 2. Click "Export Data"
# 3. Choose save location (e.g., "measurement_001")
# 4. Two files created:
#    - measurement_001_spec1.csv
#    - measurement_001_spec2.csv
# 5. Each contains: wavelength (nm), intensity (counts)
```

## Key Advantages Over Sequential Readout

| Aspect | Sequential | Parallel (This App) |
|--------|-----------|---------------------|
| **Total Time** (100ms integration) | ~220 ms | ~110 ms |
| **Synchronization** | Poor (time offset) | Excellent (simultaneous) |
| **Throughput** | 1x | ~2x |
| **Hardware Trigger** | One at a time | Both triggered together |
| **Live Updates** | Slower | Faster |

## Keyboard Shortcuts

- **Ctrl+Q**: Quit application
- **Space**: Single measurement (when enabled)
- **Ctrl+E**: Export data
- **Ctrl+C**: Clear plots

## Troubleshooting

### "Failed to connect" Error

**Problem**: Cannot connect to spectrometer  
**Solutions**:
1. Verify serial number is correct
2. Check USB cable is connected
3. Ensure no other software is using the spectrometer
4. Try disconnecting/reconnecting USB
5. Check DLL path: `DeviceServers/cameras/avantes/drivers/avaspecx64.dll`

### "Both spectrometers must be connected" Warning

**Problem**: Trying to measure with only one spectrometer connected  
**Solution**: Connect both spectrometers before starting measurement

### Plots Not Updating in Continuous Mode

**Problem**: Continuous mode checked but no updates  
**Solutions**:
1. Check integration time isn't too long relative to update rate
2. Verify both spectrometers are connected
3. Look for error messages in status bar
4. Try unchecking and re-checking "Continuous"

### Slow Update Rate

**Problem**: Updates slower than expected  
**Solutions**:
1. Reduce integration time
2. Reduce number of averages
3. Lower update rate setting
4. Check CPU usage (close other programs)

### Hardware Trigger Not Working

**Problem**: Measurement hangs waiting for trigger  
**Solutions**:
1. Verify trigger cable is connected properly
2. Check trigger signal voltage (TTL 3.3V or 5V)
3. Confirm Arduino/trigger source is sending pulses
4. Test with software trigger first
5. Check trigger polarity (rising/falling edge)

## Performance Tips

### For Maximum Speed
- Set integration time as low as possible for your light levels
- Use averages = 1
- Use software trigger mode
- Close other applications

### For Maximum SNR (Signal-to-Noise Ratio)
- Increase integration time (longer exposure)
- Increase number of averages (10-100)
- Use dark current subtraction (implement in post-processing)

### For Synchronized Measurements
- Use hardware trigger mode for both spectrometers
- Connect both to same trigger source
- Short trigger cables to minimize delay

## Data Export Format

CSV files contain two columns:

```csv
Wavelength(nm),Intensity(counts)
200.12,1234.5
200.67,1289.3
201.23,1345.8
...
```

Import into Excel, MATLAB, Python, or any analysis software:

```python
# Python/NumPy
import numpy as np
data = np.loadtxt('measurement_spec1.csv', delimiter=',', skiprows=1)
wavelengths = data[:, 0]
intensities = data[:, 1]
```

## Technical Details

### Threading Model
- **Main Thread**: GUI (PyQt5)
- **Worker Thread**: Parallel measurement (background)
- **Benefits**: Non-blocking UI, responsive during acquisition

### Parallel Measurement Strategy
1. Prepare both spectrometers (set configs)
2. Start both measurements (non-blocking)
3. **Round-robin polling** (key innovation!)
4. Retrieve data from whichever finishes first
5. Update both plots

### Timing Characteristics
- Poll interval: 1 ms (configurable)
- Minimum integration: 0.1 ms (hardware limit)
- Maximum integration: 10000 ms (10 seconds)
- Continuous mode overhead: ~10-20 ms

## Support and Feedback

For issues, questions, or feature requests:
- Check `PARALLEL_READOUT_README.md` for technical details
- Review `avantes_parallel.py` source code
- Contact: [Your contact info]

## License

Same license as parent project (MIT).

---

**Enjoy your parallel spectrometer measurements!** 🚀📊
