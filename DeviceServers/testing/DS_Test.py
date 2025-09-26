#!/usr/bin/env python3
"""
DS_Test shim for backward compatibility.

The actual DS_Test implementation has been moved to the tests/ directory structure.
This module provides a compatibility shim and basic test device.
"""

import sys
import os
from pathlib import Path

# Try to import the actual DS_Test from tests directory
try:
    # Add tests directory to path
    tests_dir = Path(__file__).resolve().parents[2] / "tests" / "device_servers" / "testing"
    sys.path.insert(0, str(tests_dir))
    
    from DS_Test import DS_Test
    
except ImportError:
    # Fallback: provide a minimal test device
    from tango.server import Device, command
    from DeviceServers.base.general import DS_General
    
    class DS_Test(DS_General):
        """Basic test device server for compatibility"""
        
        def find_device(self):
            """Implementation required by DS_General"""
            self._device_id_internal = 999
            self._uri = "test://localhost"
        
        def turn_on_local(self):
            """Turn on implementation"""
            return 0
        
        def turn_off_local(self):
            """Turn off implementation"""  
            return 0
        
        def get_controller_status_local(self):
            """Status check implementation"""
            return 0
        
        def register_variables_for_archive(self):
            """Archive registration implementation"""
            super().register_variables_for_archive()
        
        @command
        def test_command(self):
            """Basic test command"""
            self.info("Test command executed", True)

# Make DS_Test available at module level
__all__ = ['DS_Test']