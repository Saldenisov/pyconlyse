#!/usr/bin/env python3
"""Timing test for PyConlyse initialization components"""

import sys
import time
from pathlib import Path

print("=== PyConlyse Initialization Timing Test ===")

# Test 1: Basic imports
start = time.time()
print(f"[{time.time():.2f}] Starting basic imports...")

print(f"[{time.time():.2f}] Basic imports done ({time.time() - start:.3f}s)")

# Test 2: PyQt5 imports
start = time.time()
print(f"[{time.time():.2f}] Starting PyQt5 imports...")

print(f"[{time.time():.2f}] PyQt5 imports done ({time.time() - start:.3f}s)")

# Setup path for local imports
main_app_path = Path(__file__).parent
sys.path.insert(0, str(main_app_path.parent))

# Test 3: Local module imports
start = time.time()
print(f"[{time.time():.2f}] Starting local module imports...")
try:
    from main_app.core.logging_config import setup_pyconlyse_logging

    print(f"[{time.time():.2f}] logging_config imported ({time.time() - start:.3f}s)")
except Exception as e:
    print(f"[{time.time():.2f}] logging_config FAILED: {e}")

start = time.time()
try:
    print(f"[{time.time():.2f}] async_manager imported ({time.time() - start:.3f}s)")
except Exception as e:
    print(f"[{time.time():.2f}] async_manager FAILED: {e}")

# Test 4: Manager imports (most likely culprit)
start = time.time()
print(f"[{time.time():.2f}] Starting manager imports...")
try:
    from main_app.managers.infrastructure_manager import TangoInfrastructureManager

    print(
        f"[{time.time():.2f}] infrastructure_manager imported ({time.time() - start:.3f}s)"
    )
except Exception as e:
    print(f"[{time.time():.2f}] infrastructure_manager FAILED: {e}")

start = time.time()
try:
    from main_app.managers.device_manager import DeviceServerManager

    print(f"[{time.time():.2f}] device_manager imported ({time.time() - start:.3f}s)")
except Exception as e:
    print(f"[{time.time():.2f}] device_manager FAILED: {e}")

# Test 5: Tango imports (likely biggest culprit)
start = time.time()
print(f"[{time.time():.2f}] Starting Tango imports...")
try:
    print(f"[{time.time():.2f}] tango imported ({time.time() - start:.3f}s)")
except Exception as e:
    print(f"[{time.time():.2f}] tango FAILED: {e}")

# Test 6: Logging setup timing
start = time.time()
print(f"[{time.time():.2f}] Starting logging setup...")
try:
    logger_manager = setup_pyconlyse_logging()
    print(f"[{time.time():.2f}] logging setup done ({time.time() - start:.3f}s)")
except Exception as e:
    print(f"[{time.time():.2f}] logging setup FAILED: {e}")

# Test 7: Manager instantiation
start = time.time()
print(f"[{time.time():.2f}] Starting manager instantiation...")
try:
    infra_mgr = TangoInfrastructureManager()
    print(
        f"[{time.time():.2f}] infrastructure_manager created ({time.time() - start:.3f}s)"
    )
except Exception as e:
    print(f"[{time.time():.2f}] infrastructure_manager creation FAILED: {e}")

start = time.time()
try:
    device_mgr = DeviceServerManager()
    print(f"[{time.time():.2f}] device_manager created ({time.time() - start:.3f}s)")
except Exception as e:
    print(f"[{time.time():.2f}] device_manager creation FAILED: {e}")

print("=== Test Complete ===")
