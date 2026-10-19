"""Two new original bodies through signed stateless RPC with no runtime access."""
import copy
import time
import unittest
import uuid
from elyse_agent.supervision_rpc import SupervisionEndpoint
from elyse_agent.supervision_wire import json_bytes, request_mac, response_mac
from second_next_event_fixtures import acq_payload, sup_payload


class UnusableRuntime(object):
    def __getattribute__(self, name):
        raise AssertionError('Replay accessed runtime: ' + name)


class SavedSecondNextEventsRpcTests(unittest.TestCase):
    def setUp(self):
        self.key = b'software-only-G61-stateless-replay-test-key'
        self.endpoint = SupervisionEndpoint(UnusableRuntime(), self.key)

    def request(self, path, payload, method='POST'):
        timestamp, nonce = str(int(time.time())), uuid.uuid4().hex
        body = b'' if method == 'GET' else json_bytes(payload)
        return dict(method=method, path=path, payload=payload, timestamp=timestamp,
            nonce=nonce, signature=request_mac(self.key, 'RPC/' + method, path, timestamp, nonce, body))

    def dispatch(self, path, payload, status=200):
        request = self.request(path, payload)
        response = self.endpoint.dispatch(request)
        self.assertEqual(response['status'], status)
        self.assertFalse(response['body']['execution_allowed'])
        self.assertFalse(response['body']['hardware_writes'])
        self.assertEqual(response['body']['physical_status'], 'NOT_EXECUTED')
        self.assertEqual(response['signature'], response_mac(self.key, 'RPC/POST', path,
            request['nonce'], status, json_bytes(response['body'])))
        return response['body'].get('result')

    def test_acq_source_field_positions_and_independent_psp_snapshot(self):
        payload = acq_payload()
        payload['snapshots']['27807'][7] = True
        payload['snapshots']['28294'][7] = True
        before = copy.deepcopy(payload)
        result = self.dispatch('/v1/replay/acquisition-event-26012', payload)
        writes = {row['node_uid']: row['value'] for row in result['writes']}
        self.assertFalse(writes['26272'][6])
        self.assertTrue(writes['26356'][6])
        self.assertTrue(writes['26296'])
        self.assertFalse(writes['27605'][7])
        self.assertEqual((writes['27523'][20], writes['27523'][21], writes['27523'][23]), (False, False, True))
        calls = {row['node_uid']: row['input_ports'] for row in result['leaf_calls']}
        self.assertTrue(calls['28312']['28355'][7])
        self.assertEqual(calls['28364']['28454'], payload['leaf_returns']['28312']['28346'])
        self.assertTrue(result['selected_body_completed'])
        self.assertFalse(result['whole_event_equivalence'])
        self.assertEqual(payload, before)

    def test_false_arm_ignores_other_boundaries_and_prefix_preserves_pending_call(self):
        payload = acq_payload(False)
        for key in ('schedule', 'snapshots', 'leaf_returns', 'unwired_inputs', 'reference_binding'):
            payload[key] = None
        result = self.dispatch('/v1/replay/acquisition-event-26012', payload)
        self.assertEqual((result['writes'], result['leaf_calls']), ([], []))
        payload = acq_payload()
        payload['schedule'] = payload['schedule'][:5]
        result = self.dispatch('/v1/replay/acquisition-event-26012', payload)
        self.assertEqual(result['pending_leaf_uids'], ['26304'])
        self.assertFalse(result['selected_body_completed'])

    def test_t2_gain_field_and_scalar_sink_survive_supplied_writer_error(self):
        for selector, gain in enumerate((2.126, 8.98, 5.553)):
            payload = sup_payload(selector)
            before = copy.deepcopy(payload)
            result = self.dispatch('/v1/replay/supervision-position-t2-event', payload)
            self.assertEqual(result['projected_cluster'][5], gain)
            self.assertEqual(result['multiplied_value'], gain * 10.0)
            self.assertEqual(result['local_assignments']['57843']['data'], gain * 10.0)
            self.assertEqual(result['local_assignments']['57843']['saved_param_index'], 152)
            self.assertEqual(result['local_assignments']['71434']['data'], result['projected_cluster'])
            self.assertEqual(result['writer_call']['data'], result['projected_cluster'])
            self.assertTrue(result['writer_call']['supplied_returns']['71480']['status'])
            self.assertEqual(result['completed_sinks'], ['71458', '57843'])
            self.assertFalse(result['writer_success_gates_local_assignments'])
            self.assertFalse(result['native_float_bitwise_equivalence'])
            for index in (0, 1, 2, 3, 4, 6, 7, 8, 9):
                self.assertEqual(result['projected_cluster'][index], payload['local_reads']['71442'][index])
            self.assertEqual(payload, before)

    def test_signed_authentication_nonce_and_method(self):
        for path, fixture in (('/v1/replay/acquisition-event-26012', acq_payload),
                ('/v1/replay/supervision-position-t2-event', sup_payload)):
            request = self.request(path, fixture())
            request['signature'] = '0' * 64
            self.assertEqual(self.endpoint.dispatch(request)['status'], 401)
            request = self.request(path, fixture())
            self.assertEqual(self.endpoint.dispatch(request)['status'], 200)
            self.assertEqual(self.endpoint.dispatch(request)['status'], 401)
            self.assertEqual(self.endpoint.dispatch(self.request(path, None, 'GET'))['status'], 404)

    def test_unknown_selector_shape_and_cross_body_identity_refused(self):
        for selector in (True, -1, 3, 65535, 1.0):
            self.dispatch('/v1/replay/supervision-position-t2-event', sup_payload(selector), 400)
        payload = sup_payload()
        payload['local_reads']['71442'].pop()
        self.dispatch('/v1/replay/supervision-position-t2-event', payload, 400)
        payload = acq_payload()
        payload['schedule'][0] = dict(kind='step', uid='26272')
        self.dispatch('/v1/replay/acquisition-event-26012', payload, 400)
        payload = sup_payload()
        payload['frame_uid'] = '56135'
        self.dispatch('/v1/replay/supervision-position-t2-event', payload, 400)
        payload = acq_payload()
        payload['frame_uid'] = '22879'
        self.dispatch('/v1/replay/acquisition-event-26012', payload, 400)


if __name__ == '__main__':
    unittest.main()
