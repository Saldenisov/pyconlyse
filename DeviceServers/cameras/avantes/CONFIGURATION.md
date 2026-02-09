# Configuration - Default Serial Numbers

## Default Avantes Spectrometer Serial Numbers

The application has been pre-configured with your Avantes spectrometer serial numbers:

- **Spectrometer 1**: `1810225U1` (AVANTES_CCD1)
- **Spectrometer 2**: `1810226U1` (AVANTES_CCD2)

## What's Pre-Configured

### 1. Standalone GUI Application (`avantes_dual_viewer.py`)

When you launch the application, the serial number fields are **automatically filled** with:
- Spectrometer 1: `1810225U1`
- Spectrometer 2: `1810226U1`

You can:
- ✅ Use them as-is by just clicking "Connect"
- ✅ Change them if you have different devices
- ✅ Leave one empty if you only have one spectrometer

### 2. Test Suite (`test_parallel_readout.py`)

All test functions use your default serial numbers:
- `test_parallel_basic()` - Uses 1810225U1 and 1810226U1
- `test_parallel_hardware_trigger()` - Uses 1810225U1 and 1810226U1
- `test_timing_comparison()` - Uses 1810225U1 and 1810226U1

**To run tests immediately:**
```powershell
python tests\device_servers\cameras\avantes\test_parallel_readout.py
```

### 3. DLL Path

The default DLL path is set to:
```
C:/dev/pyconlyse/DeviceServers/cameras/avantes/drivers/avaspecx64.dll
```

This matches your existing configuration in `add_ds_AVANTES_CCD.py`.

## Quick Start (Even Faster Now!)

### Launch GUI Application

```powershell
cd C:\dev\pyconlyse\DeviceServers\cameras\avantes
python avantes_dual_viewer.py
```

**What you'll see:**
1. Serial number fields **already filled** with 1810225U1 and 1810226U1
2. Just click "Connect" for each spectrometer
3. Start measuring immediately!

### Run Tests

```powershell
# From the avantes directory
cd C:\dev\pyconlyse\DeviceServers\cameras\avantes

# Run all tests with your devices
python ..\..\..\..\tests\device_servers\cameras\avantes\test_parallel_readout.py
```

## Changing Configuration

### For Different Serial Numbers

If you need to use different spectrometers:

**In GUI Application:**
- Just type the new serial number in the text field before connecting

**In Test Scripts:**
Edit the serial numbers in `test_parallel_readout.py`:
```python
serial="YOUR_SERIAL_HERE",  # Change this line
```

**In Application Code:**
Edit `avantes_dual_viewer.py` line 121:
```python
default_serials = {1: "YOUR_SERIAL_1", 2: "YOUR_SERIAL_2"}
```

### For Different DLL Path

If your DLL is in a different location, update the path in:

**GUI Application** (line 183):
```python
dll_path = Path(__file__).parent / "drivers" / "avaspecx64.dll"
```

**Test Scripts**:
```python
address="SDK::YOUR_DLL_PATH_HERE"
```

## Configuration Source

These defaults come from your existing Tango configuration file:
- `add_ds_AVANTES_CCD.py`
- Device names: AVANTES_CCD1, AVANTES_CCD2
- Integration time: 100 ms (default)
- Trigger mode: 2 (Synchronous)
- Arduino sync IP: 10.20.30.47

## Hardware Setup

Based on your configuration:

### Spectrometer 1 (1810225U1)
- **Wavelength Range**: ~173.5 - 1347.9 nm
- **Pixels**: 2068
- **Device Name**: AVANTES_CCD1
- **Default Integration**: 100 ms

### Spectrometer 2 (1810226U1)
- **Wavelength Range**: ~173.5 - 1347.9 nm (similar calibration)
- **Pixels**: 2068
- **Device Name**: AVANTES_CCD2
- **Default Integration**: 100 ms

### Arduino Synchronization
- **IP Address**: 10.20.30.47
- **Purpose**: Hardware trigger for synchronized measurements
- **Modes**: 
  - "LAMP AND AVANTES" - Both lamp and spectrometers
  - "ONLY AVANTES" - Spectrometers only (background)
  - "OFF" - All off

## Verification

### Check Serial Numbers Match Your Hardware

Run this simple test to verify your spectrometers:

```python
from msl.equipment import EquipmentRecord, ConnectionRecord

# Check spec 1
record1 = EquipmentRecord(
    manufacturer="Avantes",
    model="AvaSpec-2048L",
    serial="1810225U1",
    connection=ConnectionRecord(
        address="SDK::C:/dev/pyconlyse/DeviceServers/cameras/avantes/drivers/avaspecx64.dll"
    )
)

spec1 = record1.connect()
print(f"Spec 1 connected! Pixels: {spec1.get_num_pixels()}")
spec1.disconnect()

# Repeat for spec 2...
```

### Expected Output
```
Spec 1 connected! Pixels: 2048
Spec 2 connected! Pixels: 2048
```

If you get an error about serial numbers not matching, check:
1. USB cables are connected
2. Serial numbers are correct (check labels on devices)
3. No other software is using the spectrometers
4. Try `AVS_Init()` manually to scan for devices

## Troubleshooting Serial Numbers

### "Serial number not found" Error

**Cause**: The serial number doesn't match any connected device

**Solutions**:
1. Check device labels for actual serial numbers
2. Run device scan to find connected devices:
```python
from msl.equipment.resources.avantes import Avantes

# Scan for devices
devices = Avantes.find(path='C:/dev/pyconlyse/DeviceServers/cameras/avantes/drivers/avaspecx64.dll')
for dev in devices:
    print(f"Found: {dev.SerialNumber.decode()}")
```

3. Update configuration with correct serial numbers

### Multiple Devices with Same Serial

**Not possible** - Each Avantes device has a unique serial number burned into hardware.

## Summary

✅ **Ready to Use** - Serial numbers pre-configured  
✅ **No Manual Entry** - Just click "Connect"  
✅ **Tests Work** - All examples use your devices  
✅ **Matches Tango** - Same config as existing system  

Just launch the application and start measuring! 🚀
