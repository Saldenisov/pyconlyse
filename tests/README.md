# PyConlyse Test Suite

This directory contains the organized test suite for the PyConlyse project.

## Directory Structure

```
tests/
├── __init__.py                 # Main tests package
├── README.md                   # This file
├── unit/                       # Unit tests
│   ├── __init__.py
│   ├── netio/                  # NetIO related unit tests
│   │   ├── __init__.py
│   │   ├── test_netio_patient.py
│   │   ├── test_netio_selection.py
│   │   ├── test_netio_state.py
│   │   ├── test_netio_state_taurus.py
│   │   └── test_pyconlyse_netio.py
│   ├── test_fixes.py
│   └── test_imports.py
├── integration/                # Integration tests
│   ├── __init__.py
│   ├── test_integration.py
│   └── test_main_app_integration.py
├── device_servers/            # Device server tests
│   ├── __init__.py
│   ├── cameras/               # Camera device server tests
│   ├── data/                  # Data related device server tests
│   ├── motion/                # Motion device server tests
│   ├── testing/               # General device server testing utilities
│   └── test_*.py              # Various device server tests
├── gui/                       # GUI tests
│   └── views/
│       └── ui/
│           └── test.py
├── main_app/                  # Main application tests
│   ├── __init__.py
│   ├── test_gui.py
│   ├── test_responsive_gui.py
│   ├── test_simple.py
│   └── test_timing.py
├── legacy/                    # Legacy tests (to be refactored or removed)
│   ├── test_main_ctrl_modules.py
│   ├── test_simple.py
│   └── test_warp_update.py
├── utilities/                 # Utility and external library tests
│   ├── k-functime/
│   ├── mytests/              # Various test utilities
│   ├── prev_projects/        # Tests from previous projects
│   └── pypylon/              # PyPylon library tests
└── web/                      # Web-related tests
    └── old stuff/
        └── pyconlyse_control/
```

## Running Tests

### Using the Custom Test Runner

Use the provided `run_tests.py` script from the project root:

```bash
# Run all tests
python run_tests.py

# Run specific test categories
python run_tests.py --unit
python run_tests.py --integration
python run_tests.py --device-servers
python run_tests.py --gui
python run_tests.py --utilities
python run_tests.py --legacy

# Run with verbose output
python run_tests.py --verbose

# Run tests matching a specific pattern
python run_tests.py --pattern "test_netio*"
```

### Using pytest (if available)

If you have pytest installed, you can also use it directly:

```bash
# Run all tests
pytest

# Run specific test directories
pytest tests/unit/
pytest tests/integration/
pytest tests/device_servers/

# Run with specific markers
pytest -m unit
pytest -m integration
pytest -m device_server

# Run specific test files
pytest tests/unit/netio/test_netio_state.py
```

### Using unittest directly

You can also use Python's built-in unittest module:

```bash
# Run all tests
python -m unittest discover tests

# Run specific test modules
python -m unittest tests.unit.test_imports
python -m unittest tests.unit.netio.test_netio_state
```

## Test Categories

- **Unit Tests** (`unit/`): Fast, isolated tests for individual functions and classes
- **Integration Tests** (`integration/`): Tests that verify interactions between components
- **Device Server Tests** (`device_servers/`): Tests for Tango device server functionality
- **GUI Tests** (`gui/`): Tests for graphical user interface components
- **Utility Tests** (`utilities/`): Tests for utility functions and external library integrations
- **Legacy Tests** (`legacy/`): Older tests that may need refactoring

## Adding New Tests

1. Choose the appropriate category for your test
2. Create your test file following the naming convention `test_*.py`
3. Use proper imports and test structure
4. Add appropriate markers if using pytest
5. Update this README if you add new categories or significant changes

## Test Naming Conventions

- Test files: `test_*.py`, `*_test.py`, or `testing_*.py`
- Test classes: `Test*` (e.g., `TestNetIOState`)
- Test methods: `test_*` (e.g., `test_netio_connection`)

## Import Path Updates

After reorganizing tests, some import statements may need to be updated to reflect the new structure. The test runner will help identify any import issues.