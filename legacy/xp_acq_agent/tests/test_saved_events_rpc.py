"""Signed replay guards and source-derived results without runtime access."""
import copy
import time
import unittest
import uuid
from elyse_agent.supervision_rpc import SupervisionEndpoint
from elyse_agent.supervision_wire import json_bytes, request_mac, response_mac
from saved_event_fixtures import acq_control_payload, sup_frequency_payload


class UnusableRuntime(object):
    def __getattribute__(self, name):
        raise AssertionError('Replay accessed runtime: ' + name)


class SavedEventsRpcTests(unittest.TestCase):
    def setUp(self):
        self.key = b'software-only-event-replay-32-byte-key'
        self.endpoint = SupervisionEndpoint(UnusableRuntime(), self.key)

    def request(self, path, payload, method='POST'):
        timestamp, nonce = str(int(time.time())), uuid.uuid4().hex
        body = b'' if method == 'GET' else json_bytes(payload)
        return dict(method=method, path=path, payload=payload, timestamp=timestamp,
            nonce=nonce, signature=request_mac(self.key, 'RPC/' + method,
                path, timestamp, nonce, body))

    def dispatch(self, path, payload, status=200):
        request = self.request(path, payload)
        response = self.endpoint.dispatch(request)
        self.assertEqual(response['status'], status)
        self.assertFalse(response['body']['execution_allowed'])
        self.assertFalse(response['body']['hardware_writes'])
        self.assertEqual(response['body']['physical_status'], 'NOT_EXECUTED')
        self.assertEqual(response['signature'], response_mac(self.key, 'RPC/POST',
            path, request['nonce'], status, json_bytes(response['body'])))
        return response

    def test_sup_indices_and_independent_faulted_fanout(self):
        payload = sup_frequency_payload()
        before = copy.deepcopy(payload)
        result = self.dispatch('/v1/replay/supervision-frequency-event', payload)['body']['result']
        self.assertEqual(result['projected_cluster'][2], 2.25)
        self.assertEqual(result['projected_cluster'][3], 4294967295.0)
        self.assertEqual(result['projected_cluster'][32], 4.0)
        for uid in ('59714', '70290'):
            self.assertEqual(result['local_assignments'][uid]['data'], result['projected_cluster'])
        self.assertEqual(result['completed_sinks'], ['70253', '59714'])
        self.assertFalse(result['writer_success_gates_local_assignments'])
        self.assertFalse(result['fanout_order_qualified'])
        self.assertFalse(result['whole_event_equivalence'])
        self.assertEqual(payload, before)

    def test_acq_independent_publication_and_error_handler_input(self):
        payload = acq_control_payload()
        before = copy.deepcopy(payload)
        result = self.dispatch('/v1/replay/acquisition-control-event', payload)['body']['result']
        writes = {row['node_uid']: row['value'] for row in result['writes']}
        self.assertTrue(writes['33723'][2])
        self.assertFalse(writes['33796'][2])
        self.assertFalse(writes['33891'][12])
        self.assertFalse(writes['34320'][36])
        self.assertTrue(writes['33747'])
        calls = {row['node_uid']: row['input_ports'] for row in result['leaf_calls']}
        self.assertTrue(calls['34036']['34060'][12])
        self.assertEqual(calls['34076']['34106'], payload['leaf_returns']['34036']['34047'])
        self.assertTrue(result['selected_body_completed'])
        self.assertFalse(result['wait_units_or_pulse_duration_qualified'])
        self.assertFalse(result['whole_event_equivalence'])
        self.assertEqual(payload, before)

    def test_false_body_and_in_flight_prefix(self):
        payload = acq_control_payload(False)
        for key in ('schedule', 'snapshots', 'leaf_returns', 'unwired_inputs', 'reference_binding'):
            payload[key] = 'unconsumed supplied boundary'
        value = self.dispatch('/v1/replay/acquisition-control-event', payload)['body']['result']
        self.assertEqual(value['writes'], [])
        self.assertEqual(value['leaf_calls'], [])
        payload = acq_control_payload()
        payload['schedule'] = payload['schedule'][:5]
        value = self.dispatch('/v1/replay/acquisition-control-event', payload)['body']['result']
        self.assertEqual(value['pending_leaf_uids'], ['33755'])
        self.assertFalse(value['selected_body_completed'])

    def test_authentication_replay_nonce_and_wrong_method(self):
        path = '/v1/replay/supervision-frequency-event'
        request = self.request(path, sup_frequency_payload())
        request['signature'] = '0' * 64
        self.assertEqual(self.endpoint.dispatch(request)['status'], 401)
        request = self.request(path, sup_frequency_payload())
        self.assertEqual(self.endpoint.dispatch(request)['status'], 200)
        self.assertEqual(self.endpoint.dispatch(request)['status'], 401)
        self.assertEqual(self.endpoint.dispatch(self.request(path, None, 'GET'))['status'], 404)

    def test_invalid_source_storage_and_schedule(self):
        payload = sup_frequency_payload()
        payload['event_returns']['70885']['71474'] = True
        self.dispatch('/v1/replay/supervision-frequency-event', payload, 400)
        payload = sup_frequency_payload()
        payload['local_reads']['60452'] = payload['local_reads']['60452'][:-1]
        self.dispatch('/v1/replay/supervision-frequency-event', payload, 400)
        payload = acq_control_payload()
        payload['schedule'][0] = dict(kind='step', uid='33723')
        self.dispatch('/v1/replay/acquisition-control-event', payload, 400)
        for path in ('/v1/replay/acquisition-control-event', '/v1/replay/supervision-frequency-event'):
            self.dispatch(path, {'wrong': 'source'}, 400)


if __name__ == '__main__':
    unittest.main()
