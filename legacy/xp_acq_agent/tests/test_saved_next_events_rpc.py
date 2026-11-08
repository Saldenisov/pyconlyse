"""New original event body routing through signed stateless replay only."""
import copy
import time
import unittest
import uuid
from elyse_agent.supervision_rpc import SupervisionEndpoint
from elyse_agent.supervision_wire import json_bytes, request_mac, response_mac
from next_event_fixtures import acq_payload, sup_payload


class UnusableRuntime(object):
    def __getattribute__(self, name):
        raise AssertionError('Replay accessed runtime: ' + name)


class SavedNextEventsRpcTests(unittest.TestCase):
    def setUp(self):
        self.key = b'software-only-next-event-replay-key'
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

    def test_acq_source_changes_and_independent_writer_snapshot(self):
        payload = acq_payload()
        payload['snapshots']['25058'][5] = True
        payload['snapshots']['25526'][5] = True
        before = copy.deepcopy(payload)
        result = self.dispatch('/v1/replay/acquisition-event-22879', payload)
        writes = {row['node_uid']: row['value'] for row in result['writes']}
        self.assertFalse(writes['23331'][4])
        self.assertTrue(writes['23408'][4])
        self.assertTrue(writes['23357'])
        self.assertFalse(writes['24872'][5])
        self.assertEqual((writes['24589'][14], writes['24589'][15], writes['24589'][17]), (False, False, True))
        calls = {row['node_uid']: row['input_ports'] for row in result['leaf_calls']}
        self.assertTrue(calls['25625']['25700'][5])
        self.assertEqual(calls['25703']['25887'], payload['leaf_returns']['25625']['25697'])
        self.assertTrue(result['selected_body_completed'])
        self.assertFalse(result['whole_event_equivalence'])
        self.assertEqual(payload, before)

    def test_false_arm_and_inflight_completion(self):
        payload = acq_payload(False)
        for key in ('schedule', 'snapshots', 'leaf_returns', 'unwired_inputs', 'reference_binding'):
            payload[key] = None
        result = self.dispatch('/v1/replay/acquisition-event-22879', payload)
        self.assertEqual((result['writes'], result['leaf_calls']), ([], []))
        payload = acq_payload()
        payload['schedule'] = payload['schedule'][:5]
        result = self.dispatch('/v1/replay/acquisition-event-22879', payload)
        self.assertEqual(result['pending_leaf_uids'], ['23365'])
        self.assertFalse(result['selected_body_completed'])

    def test_sup_three_constants_and_faulted_independent_sinks(self):
        for selector, gain in enumerate((2.126, 8.98, 5.553)):
            payload = sup_payload(selector)
            before = copy.deepcopy(payload)
            result = self.dispatch('/v1/replay/supervision-gain-event', payload)
            self.assertEqual(result['projected_cluster'][4], gain)
            self.assertEqual(result['multiplied_value'], gain * 10.0)
            self.assertEqual(result['local_assignments']['53628']['data'], gain * 10.0)
            self.assertEqual(result['local_assignments']['57296']['data'], result['projected_cluster'])
            self.assertEqual(result['writer_call']['data'], result['projected_cluster'])
            self.assertTrue(result['writer_call']['supplied_returns']['57370']['status'])
            self.assertEqual(result['completed_sinks'], ['57358', '53628'])
            self.assertFalse(result['writer_success_gates_local_assignments'])
            self.assertFalse(result['native_float_bitwise_equivalence'])
            for index in (0, 1, 2, 3, 5, 6, 7, 8, 9):
                self.assertEqual(result['projected_cluster'][index], payload['local_reads']['57311'][index])
            self.assertEqual(payload, before)

    def test_authentication_nonce_and_wrong_method(self):
        for path, fixture in (('/v1/replay/acquisition-event-22879', acq_payload),
            ('/v1/replay/supervision-gain-event', sup_payload)):
            request = self.request(path, fixture())
            request['signature'] = '0' * 64
            self.assertEqual(self.endpoint.dispatch(request)['status'], 401)
            request = self.request(path, fixture())
            self.assertEqual(self.endpoint.dispatch(request)['status'], 200)
            self.assertEqual(self.endpoint.dispatch(request)['status'], 401)
            self.assertEqual(self.endpoint.dispatch(self.request(path, None, 'GET'))['status'], 404)

    def test_invalid_selector_and_unqualified_domains(self):
        for selector in (True, -1, 3, 65535, 1.0):
            self.dispatch('/v1/replay/supervision-gain-event', sup_payload(selector), 400)
        payload = sup_payload()
        payload['local_reads']['57311'].pop()
        self.dispatch('/v1/replay/supervision-gain-event', payload, 400)
        payload = acq_payload()
        payload['schedule'][0] = dict(kind='step', uid='23331')
        self.dispatch('/v1/replay/acquisition-event-22879', payload, 400)
        for path in ('/v1/replay/acquisition-event-22879', '/v1/replay/supervision-gain-event'):
            self.dispatch(path, {'wrong': 'source'}, 400)


if __name__ == '__main__':
    unittest.main()
