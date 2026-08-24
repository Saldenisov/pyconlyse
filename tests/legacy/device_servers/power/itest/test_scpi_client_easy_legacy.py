#!/usr/bin/env python3
"""
Unit tests for the easy-scpi refactored SCPI client.

Tests that the new easy-scpi implementation maintains the same API
and behavior as the original socket-based implementation.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

import pytest

pytest.importorskip("easy_scpi")

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

from DeviceServers.power.iTest.scpi_client import SCPISocket, SCPIError


class TestSCPISocketEasyImpl(unittest.TestCase):
    """Test the easy-scpi implementation of SCPISocket."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.host = "192.168.1.100"
        self.port = 5025
        self.timeout = 3.0
        self.eol = "\n"
    
    def test_constructor_valid_parameters(self):
        """Test constructor with valid parameters."""
        client = SCPISocket(self.host, self.port, self.timeout, self.eol)
        self.assertEqual(client._host, self.host)
        self.assertEqual(client._port, self.port)
        self.assertEqual(client._timeout_s, self.timeout)
        self.assertEqual(client._eol, self.eol)
        self.assertIsNone(client._inst)
    
    def test_constructor_invalid_eol(self):
        """Test constructor with invalid EOL character."""
        with self.assertRaises(ValueError) as cm:
            SCPISocket(self.host, self.port, self.timeout, "\t")
        self.assertIn("Unsupported EOL", str(cm.exception))
    
    def test_constructor_different_eol_variants(self):
        """Test constructor with different valid EOL variants."""
        for eol in ["\n", "\r\n", "\r"]:
            client = SCPISocket(self.host, self.port, self.timeout, eol)
            self.assertEqual(client._eol, eol)
    
    @patch('DeviceServers.power.iTest.scpi_client.EasyInstrument')
    def test_connect_success(self, mock_instrument_class):
        """Test successful connection."""
        mock_inst = Mock()
        mock_inst.connected = True
        mock_instrument_class.return_value = mock_inst
        
        client = SCPISocket(self.host, self.port)
        client.connect()
        
        # Verify EasyInstrument was called with correct parameters
        mock_instrument_class.assert_called_once()
        call_args = mock_instrument_class.call_args
        self.assertEqual(call_args[1]['port'], f"TCPIP::{self.host}::{self.port}::SOCKET")
        self.assertEqual(call_args[1]['port_match'], False)
        self.assertEqual(call_args[1]['timeout'], 3000)  # converted to ms
        self.assertEqual(call_args[1]['read_termination'], "\n")
        self.assertEqual(call_args[1]['write_termination'], "\n")
        
        mock_inst.connect.assert_called_once()
    
    @patch('DeviceServers.power.iTest.scpi_client.EasyInstrument')
    def test_connect_already_connected(self, mock_instrument_class):
        """Test connect when already connected."""
        mock_inst = Mock()
        mock_inst.connected = True
        
        client = SCPISocket(self.host, self.port)
        client._inst = mock_inst
        client.connect()
        
        # Should not create new instance
        mock_instrument_class.assert_not_called()
        mock_inst.connect.assert_not_called()
    
    @patch('DeviceServers.power.iTest.scpi_client.EasyInstrument')
    def test_connect_exception(self, mock_instrument_class):
        """Test connection failure."""
        mock_instrument_class.side_effect = Exception("Connection failed")
        
        client = SCPISocket(self.host, self.port)
        with self.assertRaises(SCPIError) as cm:
            client.connect()
        
        self.assertIn("Failed to connect", str(cm.exception))
        self.assertIn("Connection failed", str(cm.exception))
    
    def test_close_when_connected(self):
        """Test closing connection."""
        mock_inst = Mock()
        
        client = SCPISocket(self.host, self.port)
        client._inst = mock_inst
        client.close()
        
        mock_inst.disconnect.assert_called_once()
        self.assertIsNone(client._inst)
    
    def test_close_when_not_connected(self):
        """Test closing when not connected."""
        client = SCPISocket(self.host, self.port)
        client.close()  # Should not raise exception
        self.assertIsNone(client._inst)
    
    def test_ensure_not_connected(self):
        """Test _ensure when not connected."""
        client = SCPISocket(self.host, self.port)
        with self.assertRaises(SCPIError) as cm:
            client._ensure()
        self.assertIn("SCPI not connected", str(cm.exception))
    
    def test_ensure_connected(self):
        """Test _ensure when connected."""
        mock_inst = Mock()
        mock_inst.connected = True
        
        client = SCPISocket(self.host, self.port)
        client._inst = mock_inst
        
        result = client._ensure()
        self.assertEqual(result, mock_inst)
    
    def test_write_success(self):
        """Test successful write operation."""
        mock_inst = Mock()
        mock_inst.connected = True
        
        client = SCPISocket(self.host, self.port)
        client._inst = mock_inst
        
        client.write("*IDN?")
        mock_inst.write.assert_called_once_with("*IDN?")
    
    def test_write_not_connected(self):
        """Test write when not connected."""
        client = SCPISocket(self.host, self.port)
        with self.assertRaises(SCPIError) as cm:
            client.write("*IDN?")
        self.assertIn("SCPI not connected", str(cm.exception))
    
    def test_write_exception(self):
        """Test write with exception."""
        mock_inst = Mock()
        mock_inst.connected = True
        mock_inst.write.side_effect = Exception("Write failed")
        
        client = SCPISocket(self.host, self.port)
        client._inst = mock_inst
        
        with self.assertRaises(SCPIError) as cm:
            client.write("*IDN?")
        self.assertIn("Write failed", str(cm.exception))
    
    def test_query_success(self):
        """Test successful query operation."""
        mock_inst = Mock()
        mock_inst.connected = True
        mock_inst.query.return_value = "Keysight,E36313A,MY12345678,1.0.0"
        
        client = SCPISocket(self.host, self.port)
        client._inst = mock_inst
        
        result = client.query("*IDN?")
        self.assertEqual(result, "Keysight,E36313A,MY12345678,1.0.0")
        mock_inst.query.assert_called_once_with("*IDN?")
    
    def test_query_exception(self):
        """Test query with exception."""
        mock_inst = Mock()
        mock_inst.connected = True
        mock_inst.query.side_effect = Exception("Query failed")
        
        client = SCPISocket(self.host, self.port)
        client._inst = mock_inst
        
        with self.assertRaises(SCPIError) as cm:
            client.query("*IDN?")
        self.assertIn("Query failed", str(cm.exception))
    
    def test_idn(self):
        """Test IDN query."""
        mock_inst = Mock()
        mock_inst.connected = True
        mock_inst.query.return_value = "ITECH,IT6432,123456,V1.0"
        
        client = SCPISocket(self.host, self.port)
        client._inst = mock_inst
        
        result = client.idn()
        self.assertEqual(result, "ITECH,IT6432,123456,V1.0")
        mock_inst.query.assert_called_once_with("*IDN?")
    
    def test_output_on(self):
        """Test output on command."""
        mock_inst = Mock()
        mock_inst.connected = True
        
        client = SCPISocket(self.host, self.port)
        client._inst = mock_inst
        
        client.output_on()
        mock_inst.write.assert_called_once_with("OUTP ON")
    
    def test_output_off(self):
        """Test output off command."""
        mock_inst = Mock()
        mock_inst.connected = True
        
        client = SCPISocket(self.host, self.port)
        client._inst = mock_inst
        
        client.output_off()
        mock_inst.write.assert_called_once_with("OUTP OFF")
    
    def test_set_current(self):
        """Test set current command."""
        mock_inst = Mock()
        mock_inst.connected = True
        
        client = SCPISocket(self.host, self.port)
        client._inst = mock_inst
        
        client.set_current(1.5)
        mock_inst.write.assert_called_once_with("SOUR:CURR 1.5000")
    
    def test_get_current_setpoint(self):
        """Test get current setpoint query."""
        mock_inst = Mock()
        mock_inst.connected = True
        mock_inst.query.return_value = "2.500000E+00"
        
        client = SCPISocket(self.host, self.port)
        client._inst = mock_inst
        
        result = client.get_current_setpoint()
        self.assertEqual(result, 2.5)
        mock_inst.query.assert_called_once_with("SOUR:CURR?")
    
    def test_measure_current(self):
        """Test measure current query."""
        mock_inst = Mock()
        mock_inst.connected = True
        mock_inst.query.return_value = "1.234567"
        
        client = SCPISocket(self.host, self.port)
        client._inst = mock_inst
        
        result = client.measure_current()
        self.assertEqual(result, 1.234567)
        mock_inst.query.assert_called_once_with("MEAS:CURR?")
    
    def test_measure_voltage(self):
        """Test measure voltage query."""
        mock_inst = Mock()
        mock_inst.connected = True
        mock_inst.query.return_value = "12.34"
        
        client = SCPISocket(self.host, self.port)
        client._inst = mock_inst
        
        result = client.measure_voltage()
        self.assertEqual(result, 12.34)
        mock_inst.query.assert_called_once_with("MEAS:VOLT?")
    
    def test_template_functionality(self):
        """Test template configuration and usage."""
        mock_inst = Mock()
        mock_inst.connected = True
        
        client = SCPISocket(self.host, self.port)
        client._inst = mock_inst
        
        # Configure templates
        templates = {
            "set_current": "SOUR:CURR:LEV {value:.3f}",
            "output_on": "OUTP:STAT ON"
        }
        client.configure_templates(templates)
        
        # Test templated commands
        client.set_current(3.14159)
        mock_inst.write.assert_called_with("SOUR:CURR:LEV 3.142")
        
        client.output_on()
        mock_inst.write.assert_called_with("OUTP:STAT ON")
    
    def test_query_first_success(self):
        """Test query_first with successful first query."""
        mock_inst = Mock()
        mock_inst.connected = True
        mock_inst.query.return_value = "SUCCESS"
        
        client = SCPISocket(self.host, self.port)
        client._inst = mock_inst
        
        result = client.query_first(["CMD1?", "CMD2?", "CMD3?"])
        self.assertEqual(result, "SUCCESS")
        mock_inst.query.assert_called_once_with("CMD1?")
    
    def test_query_first_fallback(self):
        """Test query_first with fallback to second command."""
        mock_inst = Mock()
        mock_inst.connected = True
        mock_inst.query.side_effect = [Exception("Fail"), "SUCCESS_2"]
        
        client = SCPISocket(self.host, self.port)
        client._inst = mock_inst
        
        result = client.query_first(["CMD1?", "CMD2?"])
        self.assertEqual(result, "SUCCESS_2")
        self.assertEqual(mock_inst.query.call_count, 2)
    
    def test_query_first_all_fail(self):
        """Test query_first when all commands fail."""
        mock_inst = Mock()
        mock_inst.connected = True
        mock_inst.query.side_effect = Exception("All fail")
        
        client = SCPISocket(self.host, self.port)
        client._inst = mock_inst
        
        with self.assertRaises(SCPIError) as cm:
            client.query_first(["CMD1?", "CMD2?"])
        self.assertIn("All queries failed", str(cm.exception))
    
    def test_to_float_valid(self):
        """Test _to_float with valid input."""
        from DeviceServers.power.iTest.scpi_client import _to_float
        
        self.assertEqual(_to_float("1.234"), 1.234)
        self.assertEqual(_to_float(" 5.678 "), 5.678)
        self.assertEqual(_to_float("0"), 0.0)
        self.assertEqual(_to_float("-3.14"), -3.14)
    
    def test_to_float_invalid(self):
        """Test _to_float with invalid input."""
        from DeviceServers.power.iTest.scpi_client import _to_float
        
        with self.assertRaises(SCPIError) as cm:
            _to_float("not_a_number")
        self.assertIn("Could not parse float", str(cm.exception))
    
    def test_get_output_state(self):
        """Test get_output_state functionality."""
        mock_inst = Mock()
        mock_inst.connected = True
        
        client = SCPISocket(self.host, self.port)
        client._inst = mock_inst
        
        # Test various response formats
        test_cases = [
            ("1", True),
            ("0", False),
            ("ON", True),
            ("OFF", False),
            ("TRUE", True),
            ("FALSE", False),
            ("ON\n", True),
            ("1 ", True),
        ]
        
        for response, expected in test_cases:
            mock_inst.query.return_value = response
            result = client.get_output_state()
            self.assertEqual(result, expected, f"Failed for response '{response}'")


class TestSCPISocketTangoVersion(unittest.TestCase):
    """Test the tango_itest_psu version of SCPISocket."""
    
    def test_import_tango_version(self):
        """Test that the tango version can be imported."""
        try:
            from tango_itest_psu.scpi_client import SCPISocket as TangoSCPISocket, SCPIError
            # Basic smoke test
            client = TangoSCPISocket("127.0.0.1", 1234)
            self.assertIsNotNone(client)
        except ImportError as e:
            self.skipTest(f"tango_itest_psu module not available: {e}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
