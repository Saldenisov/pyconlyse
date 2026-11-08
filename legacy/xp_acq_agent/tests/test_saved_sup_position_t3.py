"""Fresh T3 source expectations, explicit boundaries and nonaccess tripwires."""
import copy
import math
import os
import socket
import struct
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from elyse_agent import saved_sup_position_t3 as body

class Opaque(object):
    def __bool__(self):
        raise AssertionError('Opaque boundary truth tested')
    def __float__(self):
        raise AssertionError('Opaque boundary numerically coerced')
    def __call__(self, *args):
        raise AssertionError('Opaque boundary called')
    def __iter__(self):
        raise AssertionError('Opaque boundary iterated')

class FloatSubclass(float):
    pass

class PositionT3Tests(unittest.TestCase):
    def setUp(self):
        self.snapshot = tuple(1000.25 + i for i in range(10))
        self.opaque = Opaque()
        self.event = body.EventDataReturn(self.opaque, self.opaque, self.opaque, self.opaque, 1)
        self.error = body.UnwiredInput(self.opaque)
        self.writer = body.WriterReturn(self.opaque, self.opaque)

    def project(self, selector=1, completion=None, snapshot=None):
        return body.project_position_t3(self.snapshot if snapshot is None else snapshot,
            self.event._replace(new_value=selector), self.opaque, self.error, self.writer, completion)

    def test_fresh_selected_literal_bytes_and_exact_sites(self):
        literals = ('4001020C49BA5E35', '4021F5C28F5C28F6', '40163645A1CAC083')
        expected_frames = ('82124', '82176', '82226')
        expected_constants = ('82140', '82191', '82237')
        for selector, hex_ in enumerate(literals):
            expected = struct.unpack('>d', bytes.fromhex(hex_))[0]
            result = self.project(selector)
            self.assertEqual(result.selected_gain, expected)
            self.assertEqual(result.multiplied_value, expected * struct.unpack('>d', bytes.fromhex('4024000000000000'))[0])
            self.assertEqual((result.case_frame_uid, result.gain_constant_uid), (expected_frames[selector], expected_constants[selector]))
            self.assertEqual((result.local_read.node_uid, result.local_read.saved_param_index, result.local_read.saved_bank_uid), ('73353', 25, '66939'))
            self.assertEqual((result.local_assignments[0].node_uid, result.local_assignments[0].control_id, result.local_assignments[0].saved_param_index, result.local_assignments[0].saved_bank_uid), ('13401', '30877', 19, '30875'))

    def test_field6_and_input_identity(self):
        result = self.project()
        self.assertIs(result.local_read.data, self.snapshot)
        self.assertIsNot(result.updated_cluster, self.snapshot)
        for i, original in enumerate(self.snapshot):
            if i != 6:
                self.assertIs(result.updated_cluster[i], original)
        self.assertEqual(result.updated_cluster[6], struct.unpack('>d', bytes.fromhex('4021F5C28F5C28F6'))[0])
        self.assertIs(result.writer_call.data, result.updated_cluster)
        self.assertIs(result.local_assignments[1].data, result.updated_cluster)
        self.assertEqual(result.local_assignments[1].node_uid, '73345')

    def test_opaque_boundaries_never_accessed(self):
        result = body.project_position_t3(self.snapshot, self.event, self.opaque,
            self.error, self.writer)
        self.assertIs(result.event_return, self.event)
        self.assertIs(result.writer_call.reference_in, self.opaque)
        self.assertIs(result.writer_call.supplied_error_input, self.opaque)
        self.assertIs(result.writer_call.returned, self.writer)
        self.assertEqual((result.writer_call.node_uid, result.writer_call.reference_constant_uid), ('73369', '73386'))

    def test_fanout_completion_independent_of_writer_error(self):
        for completion in (None, (), ('73345',), ('73369', '13401'), ('73345', '13401', '73369')):
            result = self.project(completion=completion)
            self.assertEqual(result.completed_sinks, completion)
            self.assertEqual(len(result.local_assignments), 2)
            self.assertIs(result.writer_call.returned.error_out, self.opaque)

    def test_selector_u16_domain_exhaustive_no_default_inference(self):
        accepted = 0
        for selector in range(65536):
            if selector < 3:
                self.project(selector)
                accepted += 1
            else:
                with self.assertRaises(ValueError):
                    self.project(selector)
        self.assertEqual(accepted, 3)
        for selector in (-1, True, False, 1.0, None, '1'):
            with self.assertRaises(ValueError):
                self.project(selector)

    def test_explicit_carrier_and_boundary_contracts(self):
        for bad in (list(self.snapshot), self.snapshot[:-1], self.snapshot + (0.0,), (1,) + self.snapshot[1:], (True,) + self.snapshot[1:], (FloatSubclass(1.0),) + self.snapshot[1:]):
            with self.assertRaises(TypeError):
                self.project(snapshot=bad)
        for event, error, writer in ((tuple(self.event), self.error, self.writer), (self.event, None, self.writer), (self.event, self.error, tuple(self.writer))):
            with self.assertRaises(TypeError):
                body.project_position_t3(self.snapshot, event, self.opaque, error, writer)
        for completion in (['13401'], ('13401', '13401'), ('57843',), ('73369', 1), ('13401', '73345', '73369', '13401')):
            with self.assertRaises(ValueError):
                self.project(completion=completion)

    def test_json_fixture_fault_and_native_gates(self):
        from third_next_event_fixtures import sup_payload
        payload = sup_payload()
        result = body.replay_saved_sup_position_t3(payload)
        self.assertEqual(result['projected_cluster'][6], struct.unpack('>d', bytes.fromhex('4021F5C28F5C28F6'))[0])
        self.assertEqual(result['multiplied_value'], result['selected_gain'] * 10.0)
        self.assertEqual(result['writer_call']['supplied_returns']['73380']['code'], -73)
        self.assertEqual(result['completed_sinks'], ['13401', '73369'])
        self.assertFalse(result['writer_success_gates_local_assignments'])
        self.assertFalse(result['native_float_bitwise_equivalence'])
        self.assertFalse(result['whole_event_equivalence'])
        for bad in (dict(payload, frame_uid='71391'), dict(payload, source_id='APP-18'), dict(payload, extra=True)):
            with self.assertRaises(ValueError):
                body.replay_saved_sup_position_t3(bad)
        bad = copy.deepcopy(payload)
        bad['local_reads']['73353'][0] = float('nan')
        with self.assertRaises(ValueError):
            body.replay_saved_sup_position_t3(bad)

    def test_no_network_process_file_or_system_access(self):
        import builtins
        original = (socket.socket, subprocess.Popen, os.system, builtins.open)
        def refused(*args, **kwargs):
            raise AssertionError('I/O attempted by pure projection')
        socket.socket = subprocess.Popen = os.system = builtins.open = refused
        try:
            self.project()
        finally:
            socket.socket, subprocess.Popen, os.system, builtins.open = original

    def test_pure_nonfinite_untouched_fields_do_not_claim_json_or_native_domain(self):
        snapshot = (float('nan'), float('inf')) + self.snapshot[2:]
        result = self.project(snapshot=snapshot)
        self.assertIs(result.updated_cluster[0], snapshot[0])
        self.assertIs(result.updated_cluster[1], snapshot[1])
        self.assertTrue(math.isnan(result.updated_cluster[0]))

if __name__ == '__main__':
    unittest.main()
