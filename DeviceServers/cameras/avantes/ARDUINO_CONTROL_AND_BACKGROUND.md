# Arduino Control and Background Measurement

## New Features

### Arduino Control Panel
Complete control over the Arduino TTL pulse generator directly from the UI.

#### Buttons:
1. **Lamp ON**: Triggers both flash lamp (Pin 7) and spectrometers (Pin 8)
   - Use for: Sample measurements with excitation
   - Status: Green "Lamp + Avantes"

2. **Lamp OFF**: Triggers only spectrometers (Pin 8), lamp OFF
   - Use for: Background/dark measurements
   - Status: Orange "Avantes Only"

3. **Advanced**: Opens manual Arduino modes
   - Lamp + Avantes
   - Avantes Only
   - Arduino OFF

#### Status Display:
- Shows current Arduino mode
- Color-coded for quick identification
- Updates automatically when mode changes

### Background Measurement

#### Purpose:
Measure background light (ambient + dark current) with lamp OFF for proper OD calculations.

#### Workflow:
1. Click **"Measure Background"** button
2. Arduino automatically switches to "Avantes Only" mode (lamp OFF)
3. Averages N measurements (same counter as reference, default 10)
4. Displays background as **blue dashed lines** on Ch1 and Ch2 plots
5. Leaves measurement idle until user starts collection or live preview

### Color Scheme

#### Channel Plots (Ch1 and Ch2):
- **White solid line (RT)**: Real-time measurement
- **Magenta/Purple dashed line (REF)**: Reference spectrum (lamp ON)
- **Blue dashed line (BG)**: Background spectrum (lamp OFF)

#### OD Plot:
- **White solid line**: Optical density spectrum

### Auto-Start Behavior

On application startup:
1. Connects to both spectrometers
2. Connects to Arduino (IP: 10.20.30.47)
3. Reads Arduino state without changing lamp mode
4. Starts no automatic measurement loop

If Arduino is not reachable:
- Logs warning
- Shows "Status: Not Connected" in red
- Measurements remain user-triggered

## Usage Examples

### Typical Measurement Sequence

#### 1. Reference Measurement (with excitation)
```
1. Ensure sample cuvette is in place
2. Click "Lamp ON" (if not already active)
3. Click "Measure Reference"
   → Arduino stays in "Lamp + Avantes" mode
   → Collects hardware-averaged pulses
   → Displays magenta reference lines
```

#### 2. Background Measurement (no excitation)
```
1. Click "Measure Background"
   → Arduino automatically switches to "Avantes Only"
   → Collects hardware-averaged pulses
   → Displays blue background lines
```

#### 3. Sample Measurement
```
1. Replace with sample cuvette
2. Click "Lamp ON" to re-enable lamp
3. Watch real-time OD calculation
4. Start data collection if needed
```

### OD Calculation with Background Correction

The OD calculation uses the ratio of ratios method:

```
OD(λ) = log₁₀[(I₀_ch1(λ) / I₀_ch2(λ)) / (I_ch1(λ) / I_ch2(λ))]
```

Where:
- `I₀`: Reference measurement (lamp ON)
- `I`: Current measurement (lamp ON for sample, OFF for background)
- Background can be subtracted if needed (future enhancement)

## Arduino Hardware Setup

### Connections:
- **Pin 7**: Flash lamp trigger (10µs pulse)
- **Pin 8**: Avantes spectrometers trigger (10µs pulse)
- **Frequency**: 40 Hz (25ms interval)
- **IP Address**: 10.20.30.47
- **Port**: 80 (HTTP)

### Modes:
| Mode | Pin 7 (Lamp) | Pin 8 (Avantes) | Use Case |
|------|--------------|-----------------|----------|
| Lamp + Avantes | ON | ON | Sample measurement with excitation |
| Avantes Only | OFF | ON | Background/dark measurement |
| OFF | OFF | OFF | Pause/idle |

## Logging

### Logged Events:
- Arduino mode changes
- Reference measurement start/complete (lamp ON)
- Background measurement start/complete (lamp OFF)
- Arduino connection status
- Errors

### Example Log Output:
```
2026-02-09 12:15:30 - INFO - AUTO-START: Arduino reachable
2026-02-09 12:16:45 - INFO - REFERENCE: Starting measurement (lamp ON, hardware averaging 40 pulses)
2026-02-09 12:16:47 - INFO - REFERENCE: Measurement complete (lamp ON)
2026-02-09 12:17:15 - INFO - ARDUINO: Avantes Only mode activated (lamp OFF)
2026-02-09 12:17:16 - INFO - BACKGROUND: Starting measurement (lamp OFF, hardware averaging 40 pulses)
2026-02-09 12:17:18 - INFO - BACKGROUND: Measurement complete (lamp OFF)
```

## Troubleshooting

### Arduino Not Connected
**Symptom**: Status shows "Not Connected" in red

**Solutions**:
1. Check Arduino IP address (should be 10.20.30.47)
2. Verify Arduino is powered on
3. Check network connection
4. Ping Arduino: `ping 10.20.30.47`
5. Test with browser: `http://10.20.30.47`

### Background Measurement Too Bright
**Symptom**: Background signal is not near zero

**Possible Causes**:
1. Lamp not actually turning off (check Arduino status LED)
2. Ambient light leaking into measurement chamber
3. Delayed lamp shut-off (wait a few seconds after switching mode)

**Solutions**:
- Verify "Avantes Only" mode is active (orange status)
- Shield measurement chamber from ambient light
- Wait 1-2 seconds after mode change before measuring

### Reference and Background Have Same Values
**Symptom**: Magenta and blue lines overlap

**Possible Causes**:
1. Lamp is not working
2. Sample is completely opaque
3. Wrong Arduino mode selected

**Solutions**:
- Check lamp power
- Verify lamp trigger output (Pin 7)
- Test with known transparent sample

## Future Enhancements

### Planned Features:
- [ ] Background subtraction from reference and sample
- [ ] Automatic background re-measurement at intervals
- [ ] Save/load reference and background spectra
- [ ] Background-corrected OD calculation option
- [ ] Visual indicator for lamp status (sync with Arduino)
- [ ] Arduino connection monitoring with auto-reconnect

## Technical Notes

### Measurement Timing:
- Reference collection: depends on Avantes hardware averaging (`avg=40` at 40Hz is about 1s)
- Background collection: depends on Avantes hardware averaging (`avg=40` at 40Hz is about 1s)
- Mode switching: <100ms (Arduino HTTP response)

### Memory Usage:
- Reference spectra: 2 × 2068 pixels × 8 bytes = ~33 KB
- Background spectra: 2 × 2068 pixels × 8 bytes = ~33 KB
- Total additional memory: ~66 KB (negligible)

### Thread Safety:
- Arduino commands sent from main GUI thread
- No conflicts with measurement thread
- Status updates are thread-safe
