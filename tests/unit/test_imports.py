#!/usr/bin/env python

import sys
import os
from pathlib import Path

print("Testing DeviceServers import resolution...")
print(f"Python executable: {sys.executable}")
print(f"Working directory: {os.getcwd()}")
print(f"Python path:")
for p in sys.path:
    print(f"  {p}")

# Add pyconlyse root to path if needed
pyconlyse_root = Path(__file__).parent.parent.parent  # Go up from tests/unit/ to project root
print(f"\nPyconlyse root: {pyconlyse_root}")

if str(pyconlyse_root) not in sys.path:
    sys.path.insert(0, str(pyconlyse_root))
    print("Added pyconlyse root to sys.path")

print("\nAttempting to import DeviceServers.base.pdu...")
try:
    from DeviceServers.base.pdu import DS_PDU
    print("SUCCESS: DeviceServers.base.pdu.DS_PDU imported successfully!")
    print(f"DS_PDU class: {DS_PDU}")
except ImportError as e:
    print(f"FAILED: Import error - {e}")
except Exception as e:
    print(f"FAILED: Other error - {e}")

print("\nTest complete.")