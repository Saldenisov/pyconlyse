"""Relay configuration tests: construction only, never network startup."""
import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from elyse_agent.telemetry_relay import TelemetryOutbox
from elyse_agent.telemetry_runtime import load_relay


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix='acq-relay-test-')
        self.config = dict(enabled=True, everest_host='10.20.30.202',
                           everest_port=8767, key_file='fixture.key')
        with open(os.path.join(self.root, 'fixture.key'), 'wb') as stream:
            stream.write(b'fixture-only-not-production-secret-0123456789')

    def tearDown(self):
        shutil.rmtree(self.root)

    def write_config(self, config):
        with open(os.path.join(self.root, 'config.telemetry-relay.json'), 'w') as stream:
            json.dump(config, stream)

    def test_absent_or_disabled_stays_inert_without_key(self):
        box = TelemetryOutbox()
        self.assertIsNone(load_relay(self.root, box))
        self.write_config(dict(self.config, enabled=False, key_file='absent'))
        self.assertIsNone(load_relay(self.root, box))

    def test_enabled_only_constructs_for_verified_everest(self):
        self.write_config(self.config)
        with patch('elyse_agent.telemetry_relay.socket.create_connection',
                   side_effect=AssertionError('configuration must not connect')):
            relay = load_relay(self.root, TelemetryOutbox())
        self.assertIsNone(relay._thread)
        self.assertEqual(relay.address, ('10.20.30.202', 8767))

    def test_invalid_configuration_and_missing_key_fail_closed(self):
        for value in (dict(self.config, enabled=1),
                      dict(self.config, everest_host='0.0.0.0'),
                      dict(self.config, everest_port=8767.0),
                      dict(self.config, key_file='absent'),
                      dict(self.config, extra=True)):
            self.write_config(value)
            with self.assertRaises((ValueError, OSError)):
                load_relay(self.root, TelemetryOutbox())


if __name__ == '__main__':
    unittest.main()
