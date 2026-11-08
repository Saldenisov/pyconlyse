"""Run isolated Tango receiver on loopback only; never a live Tango DB."""
import json
from pathlib import Path
import tempfile
import unittest
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.native_tango]

from tango import AttrWriteType, DevState
from tango.test_context import DeviceTestContext
from DeviceServers.control.elyse_acq.DS_AcqTelemetry import DS_AcqTelemetry


class TangoFacadeTests(unittest.TestCase):
    def test_missing_key_configuration_faults_without_listening(self):
        with DeviceTestContext(DS_AcqTelemetry, host='127.0.0.1', process=True, timeout=15) as device:
            self.assertEqual(device.state(), DevState.FAULT)
            self.assertFalse(json.loads(device.telemetry_json)['available'])
            self.assertEqual(device.attribute_query('telemetry_json').writable, AttrWriteType.READ)
            commands = {c.cmd_name for c in device.command_list_query()}
            self.assertFalse({'initialize', 'write', 'put', 'StartAcquisition'} & commands)

    def test_configured_loopback_receiver_starts_and_reinitializes_without_leak(self):
        with tempfile.TemporaryDirectory() as temporary:
            key = Path(temporary) / 'fixture.key'
            key.write_bytes(b'fixture-key-not-a-production-secret-0123456789')
            properties = dict(listen_host='127.0.0.1', listen_port=0, key_file=key.as_posix(),
                              permitted_xp_host='127.0.0.1')
            with DeviceTestContext(DS_AcqTelemetry, properties=properties, host='127.0.0.1',
                                   process=True, timeout=15) as device:
                self.assertEqual(device.state(), DevState.ON, device.status())
                self.assertFalse(json.loads(device.telemetry_json)['hardware_writes'])
                snapshot = json.loads(device.telemetry_json)
                self.assertEqual(snapshot['storage_mode'], 'ram_latest')
                self.assertFalse(snapshot['durable'])
                self.assertFalse(snapshot['history_available'])
                self.assertEqual(list(Path(temporary).iterdir()), [key])
                device.Init()
                self.assertEqual(device.state(), DevState.ON)
                self.assertEqual(device.received_messages, 0)


if __name__ == '__main__':
    unittest.main()
