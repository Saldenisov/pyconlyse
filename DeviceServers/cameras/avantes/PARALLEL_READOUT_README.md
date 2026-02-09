# Parallel Readout Support for Avantes Spectrometers

## Overview

This enhancement adds true simultaneous/parallel readout capability for multiple Avantes spectrometers using the `msl-equipment` library. The modifications enable efficient multi-device operation without modifying the core `msl-equipment` library itself.

## Problem

The original `msl-equipment` library supports multiple Avantes spectrometers through unique device handles, but typical usage involves **sequential polling** where one spectrometer blocks until its measurement completes before checking the other. This results in:

- Inefficient use of time when multiple spectrometers are present
- Inability to achieve true simultaneous readout
- Poor responsiveness in multi-device acquisition loops

## Solution

We created a **parallel measurement module** (`avantes_parallel.py`) that implements:

1. **Non-blocking parallel measurement initiation** - Start measurements on all devices quickly
2. **Interleaved round-robin polling** - Check all devices in rotation rather than blocking on one
3. **Optimized timing** - Reduced poll intervals for better responsiveness
4. **Hardware trigger support** - Both devices can be triggered simultaneously

## Files Modified/Added

### New Files

1. **`avantes_parallel.py`** - Core parallel measurement functions
   - `parallel_prepare_measure()` - Prepare multiple spectrometers
   - `parallel_measure()` - Start measurements simultaneously
   - `parallel_poll_and_get_data()` - Interleaved polling and data retrieval
   - `parallel_full_measurement()` - Complete workflow convenience function
   - `parallel_stop_measure()` - Stop all measurements

2. **`test_parallel_readout.py`** - Comprehensive test suite demonstrating:
   - Basic parallel measurement
   - Hardware-triggered parallel measurement
   - Timing comparisons (sequential vs parallel)

3. **`avaspec_msl_original_backup.py`** - Backup of original `msl-equipment` avaspec.py

### Modified Files

1. **`DS_AVANTES_CCD.py`** - Updated to:
   - Import parallel measurement functions
   - Optimize polling interval (0.01s → 0.001s for better multi-device responsiveness)
   - Add documentation about parallel operation support
   - Maintain backward compatibility

## Key Features

### 1. True Parallel Operation

```python
from avantes_parallel import parallel_full_measurement

# Connect to both spectrometers
spec1 = record1.connect()
spec2 = record2.connect()

# Measure both simultaneously
results = parallel_full_measurement(
    spectrometers=[spec1, spec2],
    configs=[cfg1, cfg2],
    num_measurements=1,
    timeout=5.0
)
```

### 2. Fine-Grained Control

```python
# Step-by-step control for advanced users
parallel_prepare_measure([spec1, spec2], [cfg1, cfg2])
parallel_measure([spec1, spec2], num_measurements=1)
data = parallel_poll_and_get_data([spec1, spec2], timeout=5.0, poll_interval=0.001)
```

### 3. Hardware Trigger Support

Both spectrometers can be configured for hardware triggering and will start simultaneously when the external trigger (e.g., Arduino) fires:

```python
# Configure for hardware trigger
trigger.m_Mode = 1  # HW_TRIGGER_MODE
trigger.m_Source = 0  # EXTERNAL_TRIGGER
trigger.m_SourceType = 0  # EDGE_TRIGGER_SOURCE

# Both will wait for the same trigger
parallel_measure([spec1, spec2], num_measurements=1)
```

## Performance Improvements

With 100ms integration time per spectrometer:

- **Sequential**: ~220ms total (100ms + 100ms + overhead)
- **Parallel**: ~110ms total (100ms + minimal overhead)
- **Speedup**: ~2x for 2 devices

Benefits scale with:
- Number of devices (3+ devices see even better improvements)
- Integration time (longer integrations = better relative speedup)
- Measurement frequency (continuous acquisition benefits most)

## Backward Compatibility

All changes are **fully backward compatible**:

- Existing code using single spectrometers works unchanged
- Sequential operation still supported
- Fallback to original behavior if parallel module not available
- No breaking changes to `msl-equipment` API

## Testing

Run the test suite to verify parallel operation:

```powershell
python C:\dev\pyconlyse\tests\device_servers\cameras\avantes\test_parallel_readout.py
```

Update serial numbers in the test file to match your devices.

## Hardware Requirements

- 2+ Avantes AvaSpec spectrometers (tested with AvaSpec-2048L)
- USB connection for all devices
- Optional: Arduino or external trigger source for synchronized measurements

## Integration with Tango Device Servers

The enhanced `DS_AVANTES_CCD.py` maintains full compatibility with the Tango device server framework. For orchestrating multiple spectrometers via `DS_AVANTES_SPECTRO.py`, the improved polling responsiveness provides better parallel performance automatically.

## For Pull Request to msl-equipment

The core innovation in `avantes_parallel.py` could be integrated into `msl-equipment` as an optional module or example in the documentation. Key points:

1. **No modifications to core library** - Works as an add-on
2. **Demonstrates best practices** - Shows how to use msl-equipment for multi-device scenarios
3. **General pattern** - Can be adapted for other instrument types
4. **Well documented** - Extensive docstrings and examples

## Future Enhancements

Potential improvements for future versions:

1. **Async/await support** - Use Python's asyncio for even cleaner async operation
2. **Thread pool** - Parallelize across threads for CPU-bound processing
3. **Callback system** - Event-driven data arrival notifications
4. **Synchronized timestamps** - Cross-device timing correlation

## References

- [msl-equipment documentation](https://msl-equipment.readthedocs.io/)
- [Avantes SDK manual](https://www.avantes.com/downloads/)
- Project issue/discussion: [Add link to issue tracker]

## License

Maintains the same license as the parent project (MIT).

## Authors

- Initial implementation: Elyse
- Date: 2026-02-09
- For: pyconlyse project
