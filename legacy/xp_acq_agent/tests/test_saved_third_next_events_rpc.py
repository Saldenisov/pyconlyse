"""Two new original bodies through signed stateless RPC with no runtime access."""
import copy
import time
import unittest
import uuid
from elyse_agent.supervision_rpc import SupervisionEndpoint
from elyse_agent.supervision_wire import json_bytes, request_mac, response_mac
from third_next_event_fixtures import acq_payload, sup_payload


class UnusableRuntime(object):
    def __getattribute__(self, name):
        raise AssertionError('Replay accessed runtime: ' + name)


class SavedThirdNextEventsRpcTests(unittest.TestCase):
    def setUp(self):
        self.key = b'software-only-G64-stateless-replay-test-key'
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
        payload['snapshots']['31454'][9] = True
        payload['snapshots']['31526'][9] = True
        before = copy.deepcopy(payload)
        result = self.dispatch('/v1/replay/acquisition-event-23449', payload)
        writes = {row['node_uid']: row['value'] for row in result['writes']}
        self.assertFalse(writes['31082'][17])
        self.assertTrue(writes['31237'][17])
        self.assertTrue(writes['31106'])
        self.assertFalse(writes['31433'][9])
        self.assertEqual((writes['31396'][26], writes['31396'][27], writes['31396'][29]), (False, False, True))
        calls = {row['node_uid']: row['input_ports'] for row in result['leaf_calls']}
        self.assertTrue(calls['31532']['31546'][9])
        self.assertEqual(calls['41569']['41599'], payload['leaf_returns']['31532']['31543'])
        self.assertTrue(result['selected_body_completed'])
        self.assertFalse(result['whole_event_equivalence'])
        self.assertEqual(payload, before)

    def test_false_arm_ignores_other_boundaries_and_prefix_preserves_pending_call(self):
        payload = acq_payload(False)
        for key in ('schedule', 'snapshots', 'leaf_returns', 'unwired_inputs', 'reference_binding'):
            payload[key] = None
        result = self.dispatch('/v1/replay/acquisition-event-23449', payload)
        self.assertEqual((result['writes'], result['leaf_calls']), ([], []))
        payload = acq_payload()
        payload['schedule'] = payload['schedule'][:5]
        result = self.dispatch('/v1/replay/acquisition-event-23449', payload)
        self.assertEqual(result['pending_leaf_uids'], ['31114'])
        self.assertFalse(result['selected_body_completed'])

    def test_t3_gain_field_and_scalar_sink_survive_supplied_writer_error(self):
        for selector, gain in enumerate((2.126, 8.98, 5.553)):
            payload = sup_payload(selector)
            before = copy.deepcopy(payload)
            result = self.dispatch('/v1/replay/supervision-position-t3-event', payload)
            self.assertEqual(result['projected_cluster'][6], gain)
            self.assertEqual(result['multiplied_value'], gain * 10.0)
            self.assertEqual(result['local_assignments']['13401']['data'], gain * 10.0)
            self.assertEqual(result['local_assignments']['13401']['saved_param_index'], 19)
            self.assertEqual(result['local_assignments']['73345']['data'], result['projected_cluster'])
            self.assertEqual(result['writer_call']['data'], result['projected_cluster'])
            self.assertTrue(result['writer_call']['supplied_returns']['73380']['status'])
            self.assertEqual(result['completed_sinks'], ['13401', '73369'])
            self.assertFalse(result['writer_success_gates_local_assignments'])
            self.assertFalse(result['native_float_bitwise_equivalence'])
            for index in (0, 1, 2, 3, 4, 5, 7, 8, 9):
                self.assertEqual(result['projected_cluster'][index], payload['local_reads']['73353'][index])
            self.assertEqual(payload, before)

    def test_signed_authentication_nonce_and_method(self):
        for path, fixture in (('/v1/replay/acquisition-event-23449', acq_payload),
                ('/v1/replay/supervision-position-t3-event', sup_payload)):
            request = self.request(path, fixture())
            request['signature'] = '0' * 64
            self.assertEqual(self.endpoint.dispatch(request)['status'], 401)
            request = self.request(path, fixture())
            self.assertEqual(self.endpoint.dispatch(request)['status'], 200)
            self.assertEqual(self.endpoint.dispatch(request)['status'], 401)
            self.assertEqual(self.endpoint.dispatch(self.request(path, None, 'GET'))['status'], 404)

    def test_unknown_selector_shape_and_cross_body_identity_refused(self):
        for selector in (True, -1, 3, 65535, 1.0):
            self.dispatch('/v1/replay/supervision-position-t3-event', sup_payload(selector), 400)
        payload = sup_payload()
        payload['local_reads']['73353'].pop()
        self.dispatch('/v1/replay/supervision-position-t3-event', payload, 400)
        payload = acq_payload()
        payload['schedule'][0] = dict(kind='step', uid='31082')
        self.dispatch('/v1/replay/acquisition-event-23449', payload, 400)
        payload = sup_payload()
        payload['frame_uid'] = '56135'
        self.dispatch('/v1/replay/supervision-position-t3-event', payload, 400)
        payload = acq_payload()
        payload['frame_uid'] = '22879'
        self.dispatch('/v1/replay/acquisition-event-23449', payload, 400)


if __name__ == '__main__':
    unittest.main()
