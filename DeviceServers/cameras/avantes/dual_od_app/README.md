# Dual OD App - Avantes Spectrometer OD Measurement System

A professional PyQt5 application for parallel optical density (OD) measurements using dual Avantes spectrometers with Arduino trigger synchronization.

## Features

- **Dual Spectrometer Control**: Parallel readout from two Avantes AvaSpec-2048L spectrometers
- **OD Measurement**: Real-time optical density calculation with background correction
- **Arduino Sync**: Hardware trigger synchronization at 10Hz via Arduino
- **Reference/Background**: Separate measurement workflows for reference and background spectra
- **Wavelength Tracking**: Track OD changes at specific wavelengths over time
- **Professional Architecture**: Modular design with separation of concerns

## Project Structure

```
dual_od_app/
├── __init__.py           # Package initialization
├── core/                 # Core business logic
│   ├── __init__.py
│   ├── measurement.py    # Background thread for measurements
│   ├── od_calculator.py  # OD calculation with background correction
│   └── spectrometer.py   # Spectrometer connection manager
├── ui/                   # UI components (to be populated)
│   └── __init__.py
└── utils/                # Utility functions (to be populated)
    └── __init__.py

tests/                    # Unit tests
├── __init__.py
├── test_od_calculator.py # Tests for OD calculations
└── run_tests.py          # Test runner
```

## Architecture

### Core Modules

#### `measurement.py`
- `MeasurementThread`: QThread subclass for non-blocking parallel measurements
- Handles prepare → measure → poll workflow
- Emits signals for completion and errors

#### `od_calculator.py`
- `ODCalculator`: Stateful OD calculation engine
- Methods:
  - `set_reference()`: Set reference spectra (lamp ON)
  - `set_background()`: Set background spectra (lamp OFF)
  - `calculate_od()`: Compute OD with background correction
  - `get_od_at_wavelength()`: Extract OD at specific wavelength
  - `can_calculate_od()`: Check if prerequisites are met
  - `reset()`: Clear all data

#### `spectrometer.py`
- `SpectrometerManager`: Manages single spectrometer lifecycle
- Methods:
  - `connect()`: Establish connection via DLL
  - `disconnect()`: Clean shutdown
  - `get_measurement_config()`: Create config with trigger mode
  - `get_info()`: Query spectrometer properties

## OD Calculation Formula

```
OD = log10((I0_ch1 - BG_ch1) / (I0_ch2 - BG_ch2) / (I_ch1 - BG_ch1) / (I_ch2 - BG_ch2))
```

Where:
- `I0_ch1/I0_ch2`: Reference spectra (lamp ON)
- `BG_ch1/BG_ch2`: Background spectra (lamp OFF)
- `I_ch1/I_ch2`: Current measurement spectra

## Testing

### Run All Tests
```bash
cd tests
python run_tests.py
```

### Run Specific Test
```bash
python -m unittest tests.test_od_calculator
```

### Test Coverage
- ✅ OD calculation correctness
- ✅ Background correction
- ✅ Division by zero protection
- ✅ Reference/background requirements
- ✅ Wavelength extraction
- ✅ Reset functionality

## Development Workflow

1. **Core Logic**: Implement in `core/` modules with unit tests
2. **UI Components**: Build UI widgets in `ui/` (decoupled from logic)
3. **Integration**: Wire together in main application
4. **Testing**: Add tests for each module before integration

## Hardware Configuration

- **Spectrometer 1**: Serial `1810225U1` (Sample channel)
- **Spectrometer 2**: Serial `1810226U1` (Reference channel)
- **Arduino**: IP `10.20.30.47`, 10Hz trigger (100ms interval)
  - Pin 7: Flash lamp control
  - Pin 8: Avantes trigger

## Dependencies

- PyQt5
- pyqtgraph
- numpy
- msl-equipment
- Python 3.7+

## Next Steps

1. Extract UI components from monolithic file to `ui/` directory
2. Add integration tests
3. Add configuration file support
4. Implement data export utilities in `utils/`
5. Add GUI-less CLI mode for automation
