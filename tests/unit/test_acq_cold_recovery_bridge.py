"""One dual-mode server can forward VI while prior NI recovery stays blocked.

Actual Python 3.4-compatible tests; temporary marker and synthetic XML only.
No driver imports, native child, Task, equipment command or live endpoint.
"""
import os
import tempfile
import unittest

from legacy.xp_acq_control.elyse_agent.acquisition_control_runtime import AcquisitionControlRuntime
from legacy.xp_acq_control.elyse_agent.acquisition_recovery import OwnershipMarker
from legacy.xp_acq_control.elyse_agent.dual_mode_telemetry import DualModeTelemetryPublisher, BRIDGE_SITE
from legacy.xp_acq_control.elyse_agent.shared_state import BANKS


def synthetic_xml():
    records = []
    for bank in BANKS:
        records.append('<Cluster><Name></Name><NumElts>3</NumElts>'
            '<String><Name>bank</Name><Val>{0}</Val></String>'
            '<LvVariant><Name>value</Name><DBL><Name>fixture</Name><Val>1.25</Val></DBL></LvVariant>'
            '<Cluster><Name>error</Name><NumElts>3</NumElts>'
            '<Boolean><Name>status</Name><Val>0</Val></Boolean>'
            '<I32><Name>code</Name><Val>0</Val></I32>'
            '<String><Name>source</Name><Val></Val></String></Cluster></Cluster>'.format(bank))
    return ('<LvVariant><Name></Name><Array><Name></Name><Dimsize>27</Dimsize>'
            + ''.join(records) + '</Array></LvVariant>').encode('ascii')


class ColdRecoveryBridgeTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.folder.name, 'prior.ownership')
        prior = OwnershipMarker(self.path, 'a' * 32, 'b' * 64)
        prior.acquire()
        with open(self.path, 'rb') as stream:
            self.original = stream.read()
        self.calls = []
        identity = dict(runtime_protocol_version=2, session_id='c' * 32, build_id='d' * 64)
        guard = OwnershipMarker(self.path, identity['session_id'], identity['build_id'])
        self.runtime = AcquisitionControlRuntime(lambda: self.calls.append('NI forbidden'),
            recovery_guard=guard, identity=identity)
        self.clock = [100.]
        self.publisher = DualModeTelemetryPublisher(self.runtime, ('127.0.0.1', 1), b'r' * 32,
            clock=lambda: self.clock[0])
        self.runtime.telemetry_publisher = self.publisher

    def tearDown(self):
        self.publisher.close()
        self.assertEqual(self.calls, [])
        with open(self.path, 'rb') as stream:
            self.assertEqual(stream.read(), self.original)
        self.folder.cleanup()

    def test_cold_prior_marker_forwards_all_banks_but_keeps_recovery_and_no_owner(self):
        self.assertTrue(self.publisher.ingest(synthetic_xml(), '127.0.0.1')['accepted'])
        packet = self.publisher.outbox.peek()['packet']
        self.assertEqual(packet['source_site'], BRIDGE_SITE)
        self.assertEqual(len(packet['data']['banks']), 27)
        self.assertTrue(all(row['data'] == 1.25 for row in packet['data']['banks']))
        state = self.runtime.snapshot()
        self.assertEqual(state['state'], 'RECOVERY_REQUIRED')
        self.assertTrue(state['recovery']['required'])
        self.assertEqual(state['resource_count'], 0)
        self.assertFalse(state['control']['enabled'])

    def test_silent_vi_does_not_unlock_initialize_or_clear_prior_marker(self):
        self.publisher.ingest(synthetic_xml(), '127.0.0.1')
        self.clock[0] += 3
        with self.assertRaises(RuntimeError):
            self.runtime.initialize(startup_confirmed=True)
        self.assertEqual(self.runtime.snapshot()['state'], 'RECOVERY_REQUIRED')

    def test_never_replays_cached_vi_as_a_new_receipt(self):
        self.publisher.ingest(synthetic_xml(), '127.0.0.1')
        item = self.publisher.outbox.peek()
        self.publisher.outbox.acknowledge(item['relay_id'], item['message_id'])
        self.clock[0] += 30
        self.assertFalse(self.publisher.publish_once())
        self.assertEqual(self.publisher.sequence, 1)
        self.assertIsNone(self.publisher.outbox.peek())

    def test_owned_pending_shutdown_and_cleanup_uncertainty_each_refuse_vi(self):
        for field, value in (('_backend', object()), ('_pending', 'close'),
                             ('_operation', 'initialize'), ('_shutdown_requested', True),
                             ('_marker_cleanup_uncertain', True)):
            original = getattr(self.runtime, field)
            setattr(self.runtime, field, value)
            try:
                # Use projection for a dummy owner without invoking any driver.
                if field == '_backend':
                    class Owner(object):
                        resource_count = 1
                    self.runtime._backend = Owner()
                with self.assertRaises(ValueError):
                    self.publisher.ingest(synthetic_xml(), '127.0.0.1')
            finally:
                setattr(self.runtime, field, original)

    def test_later_recovery_or_native_fault_has_no_cold_fallback(self):
        self.runtime._cold_prior_recovery_bridge = False
        with self.assertRaises(ValueError):
            self.publisher.ingest(synthetic_xml(), '127.0.0.1')
        self.runtime._cold_prior_recovery_bridge = True
        self.runtime._state = 'FAULT'
        with self.assertRaises(ValueError):
            self.publisher.ingest(synthetic_xml(), '127.0.0.1')

    def test_cold_stop_exits_without_claiming_or_releasing_prior_ownership(self):
        self.runtime.start()
        try:
            self.runtime.request_shutdown()
            self.assertTrue(self.runtime.join(3))
            self.assertEqual(self.runtime.snapshot()['state'], 'STOPPED')
        finally:
            if not self.runtime.join(0):
                self.runtime.request_shutdown()
                self.runtime.join(3)


if __name__ == '__main__':
    unittest.main()
