# Arduino Trigger Setup for Avantes Spectrometers

## Overview

Your Arduino-based HTTP server provides synchronized TTL trigger pulses for:
- **Flash lamp** (Pin 7) - For gamma source excitation
- **Avantes spectrometers** (Pin 8) - For synchronized measurement

## Hardware Configuration

### Arduino Ethernet Shield
- **IP Address**: `10.20.30.47`
- **Port**: `80` (HTTP)
- **MAC Address**: `A8:61:0A:AE:84:DA`

### TTL Outputs
- **Pin 7**: Flash lamp trigger (HAMAMATSU)
- **Pin 8**: Avantes spectrometer trigger
- **Pulse Width**: 10 µs
- **Pulse Frequency**: 10 Hz (100 ms between pulses)

## Operating Modes

### 1. LAMP AND AVANTES
**URL**: `http://10.20.30.47/?status=LAMP+AND+AVANTES`

**Function**: Triggers both flash lamp and spectrometers simultaneously

**Use case**: Sample measurement with flash lamp excitation
```
Both pins HIGH for 10 µs → Both pins LOW → Wait 100 ms → Repeat
```

### 2. ONLY AVANTES  
**URL**: `http://10.20.30.47/?status=ONLY+AVANTES`

**Function**: Triggers only spectrometers (no lamp)

**Use case**: Background/dark measurement
```
Pin 8 HIGH for 10 µs → Pin 8 LOW → Wait 100 ms → Repeat
```

### 3. OFF
**URL**: `http://10.20.30.47/?status=OFF`

**Function**: Stops all TTL generation

**Use case**: Idle state, manual control
```
All pins LOW
```

## Using the Arduino Controller in Python

### Quick Example

```python
from arduino_trigger_controller import ArduinoTriggerController

# Create controller
arduino = ArduinoTriggerController(ip="10.20.30.47")

# Start TTL pulses for spectrometers only
arduino.start_spectrometers_only()

# Check status
lamp_on, avantes_on = arduino.get_state()
print(f"Lamp: {lamp_on}, Avantes: {avantes_on}")

# Stop when done
arduino.stop_all()
```

### Full API

```python
from arduino_trigger_controller import ArduinoTriggerController

# Initialize
arduino = ArduinoTriggerController(
    ip="10.20.30.47",  # Arduino IP
    port=80,            # HTTP port
    timeout=2.0         # Request timeout
)

# Test connection
if arduino.is_connected():
    print("Arduino is online!")

# Set modes
arduino.start_lamp_and_spectrometers()  # Sample mode
arduino.start_spectrometers_only()      # Background mode
arduino.stop_all()                       # Stop

# Or use string mode
arduino.set_mode("LAMP AND AVANTES")
arduino.set_mode("ONLY AVANTES")
arduino.set_mode("OFF")

# Get current state
lamp_enabled, avantes_enabled = arduino.get_state()

# Get status string
status = arduino.get_status_string()
print(status)  # e.g., "ONLY AVANTES (Background mode)"

# Properties (cached values)
print(arduino.lamp_enabled)     # bool
print(arduino.avantes_enabled)  # bool
```

## Testing Arduino Connection

### Command Line Test

```powershell
# Test directly with PowerShell
Invoke-WebRequest -Uri "http://10.20.30.47" -Method Get

# Set mode
Invoke-WebRequest -Uri "http://10.20.30.47/?status=ONLY+AVANTES" -Method Get
```

### Python Test Script

```powershell
# Run the built-in test
python arduino_trigger_controller.py
```

Expected output:
```
============================================================
Arduino Trigger Controller - Test
============================================================

1. Testing connection...
   ✓ Arduino is reachable

2. Getting current state...
   Lamp: OFF
   Avantes: OFF
   Status: OFF (Idle)

3. Testing mode changes...
   Setting: ONLY AVANTES
   ✓ Mode set successfully
   Current: Lamp=False, Avantes=True
...
```

## Integration with Parallel Viewer

The Arduino controller can be added to the dual viewer application for hardware-triggered measurements.

### Example Integration

```python
# In avantes_dual_viewer.py

from arduino_trigger_controller import ArduinoTriggerController

class AvantesDualViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        # ... existing init ...
        
        # Add Arduino controller
        self.arduino = ArduinoTriggerController(ip="10.20.30.47")
        
    def single_measurement(self):
        # Start Arduino triggers for hardware mode
        if self.hardware_trigger_enabled:
            self.arduino.start_spectrometers_only()
        
        # ... rest of measurement code ...
        
        # Stop Arduino after measurement
        if self.hardware_trigger_enabled:
            self.arduino.stop_all()
```

## Workflow for Hardware-Triggered Measurements

### Sample Measurement (with Flash Lamp)

```python
# 1. Configure both spectrometers for hardware trigger
cfg1.m_Trigger.m_Mode = 1  # HW trigger
cfg2.m_Trigger.m_Mode = 1  # HW trigger

# 2. Prepare both spectrometers
parallel_prepare_measure([spec1, spec2], [cfg1, cfg2])

# 3. Start measurements (they wait for trigger)
parallel_measure([spec1, spec2], num_measurements=1)

# 4. Start Arduino TTL generation
arduino.start_lamp_and_spectrometers()
# Arduino sends: lamp pulse + spectrometer pulse every 100ms

# 5. Poll for data
results = parallel_poll_and_get_data([spec1, spec2], timeout=5.0)

# 6. Stop Arduino
arduino.stop_all()

# 7. Process results
for idx, (success, data) in results.items():
    if success:
        print(f"Spec {idx}: {len(data)} pixels")
```

### Background Measurement (no Lamp)

```python
# Same as above, but use:
arduino.start_spectrometers_only()
```

## Timing Diagram

```
Time  →

Arduino:   ____╔═╗_________╔═╗_________╔═╗_____
Lamp (7):      ║ ║         ║ ║         ║ ║      (LAMP AND AVANTES mode)
               ╚═╝         ╚═╝         ╚═╝      
           <10µs>    <100ms>     <100ms>

Avantes(8):____╔═╗_________╔═╗_________╔═╗_____
               ║ ║         ║ ║         ║ ║
               ╚═╝         ╚═╝         ╚═╝

Spec1:         [Integrate][Read]  [Integrate][Read]
Spec2:         [Integrate][Read]  [Integrate][Read]
```

## Troubleshooting

### Cannot Connect to Arduino

**Symptoms**: HTTP requests timeout or fail

**Solutions**:
1. Verify Arduino is powered and running
2. Check network connection:
   ```powershell
   ping 10.20.30.47
   ```
3. Verify IP is correct (check Arduino serial monitor)
4. Check firewall isn't blocking port 80
5. Try accessing from browser: `http://10.20.30.47`

### Arduino Not Triggering

**Symptoms**: Spectrometers timeout waiting for trigger

**Solutions**:
1. Check Arduino TTL state:
   ```python
   lamp, avantes = arduino.get_state()
   print(f"Lamp: {lamp}, Avantes: {avantes}")
   ```
2. Verify cables are connected to pins 7 and 8
3. Check TTL levels with oscilloscope
4. Verify spectrometers are in hardware trigger mode
5. Try software trigger mode first to isolate issue

### Wrong Mode Active

**Symptoms**: Lamp triggering when it shouldn't, or vice versa

**Solutions**:
1. Check current state:
   ```python
   print(arduino.get_status_string())
   ```
2. Explicitly set correct mode:
   ```python
   arduino.set_mode("ONLY AVANTES")
   ```
3. Verify by checking state again

### Pulses Too Fast/Slow

**Current settings**: 10 Hz (100 ms between pulses)

**To modify**: Edit Arduino code (`arduino_sync_code`):
```cpp
unsigned long btw_ttl = 100; // Change this value (in ms)
// Examples:
// btw_ttl = 200;  // 5 Hz
// btw_ttl = 50;   // 20 Hz
```

Then re-upload to Arduino.

## Arduino Web Interface

You can also control the Arduino via web browser:

1. Open: `http://10.20.30.47`
2. Click buttons:
   - **LAMP AND AVANTES** - Sample mode
   - **ONLY AVANTES** - Background mode
   - **OFF** - Stop
3. Current state displayed on page:
   - `my_ttl_on_lamp`: 0 or 1
   - `my_ttl_on_avantes`: 0 or 1

## Safety Notes

⚠️ **Flash Lamp Safety**:
- Do not look directly at lamp when triggered
- Ensure proper shielding
- Allow cooling time between long measurement series

⚠️ **Timing Considerations**:
- Spectrometer integration time must be ≤ 100ms (pulse interval)
- For longer integrations, modify `btw_ttl` in Arduino code
- Ensure spectrometers are ready before starting Arduino

## Quick Reference

| Task | Code |
|------|------|
| **Start background mode** | `arduino.start_spectrometers_only()` |
| **Start sample mode** | `arduino.start_lamp_and_spectrometers()` |
| **Stop all** | `arduino.stop_all()` |
| **Check state** | `lamp, avantes = arduino.get_state()` |
| **Test connection** | `arduino.is_connected()` |
| **Get status** | `arduino.get_status_string()` |

## Files

- **`arduino_trigger_controller.py`** - Python controller class
- **`arduino_sync_code`** - Arduino sketch (C++)
- **`DS_AVANTES_SPECTRO.py`** - Tango integration example

---

**Your setup is ready to use!** The Arduino is at `10.20.30.47` and ready to generate synchronized triggers. 🚀
