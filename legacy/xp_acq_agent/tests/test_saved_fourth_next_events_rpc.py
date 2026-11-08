"""G65 supplied source bodies via authenticated stateless software replay."""
import copy
import time
import unittest
import uuid
from elyse_agent.supervision_rpc import SupervisionEndpoint
from elyse_agent.supervision_wire import json_bytes, request_mac, response_mac
from fourth_next_event_fixtures import acq_payload, sup_payload


class UnusableRuntime(object):
    def __getattribute__(self, name):
        raise AssertionError('Software replay accessed runtime: ' + name)


class SavedFourthNextEventsRpcTests(unittest.TestCase):
    def setUp(self):
        self.key = b'software-only-G65-stateless-test-key'
        self.endpoint = SupervisionEndpoint(UnusableRuntime(), self.key)

    def request(self, path, payload, method='POST'):
        timestamp, nonce = str(int(time.time())), uuid.uuid4().hex
        body = b'' if method == 'GET' else json_bytes(payload)
        return dict(method=method, path=path, payload=payload, timestamp=timestamp,
            nonce=nonce, signature=request_mac(self.key, 'RPC/' + method, path,
                timestamp, nonce, body))

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

    def test_task_reference_slots_error_routing_and_independent_publication(self):
        payload = acq_payload()
        payload['snapshots']['45357'][18] = True
        payload['snapshots']['45445'][18] = True
        payload['snapshots']['45333'][52] = False
        payload['snapshots']['45469'][52] = False
        before = copy.deepcopy(payload)
        result = self.dispatch('/v1/replay/acquisition-event-45123', payload)
        calls = {row['node_uid']: row['input_ports'] for row in result['leaf_calls']}
        self.assertEqual(calls['46267']['46274'], payload['snapshots']['50001'][3])
        self.assertEqual(calls['54874']['54881'], payload['snapshots']['50001'][4])
        for consumer, port, producer, returned in (
            ('52872', '52891', '46267', '46319'),
            ('54874', '54914', '52872', '52879'),
            ('2548', '20510', '54874', '54926'),
            ('45475', '45483', '45451', '45463'),
            ('45515', '45545', '45475', '45486')):
            self.assertEqual(calls[consumer][port], payload['leaf_returns'][producer][returned])
        writes = {row['node_uid']: row['value'] for row in result['writes']}
        self.assertTrue(writes['45254'])
        self.assertFalse(writes['45339'][18])
        self.assertEqual((writes['45312'][55], writes['45312'][52]), (False, True))
        self.assertTrue(calls['45451']['45466'][18])
        self.assertFalse(calls['45475']['45489'][52])
        self.assertEqual(calls['45594']['45599'], 100)
        self.assertTrue(result['selected_body_completed'])
        self.assertFalse(result['native_callee_equivalence'])
        self.assertFalse(result['native_task_reference_qualified'])
        self.assertFalse(result['whole_event_equivalence'])
        self.assertEqual(payload, before)

    def test_false_arm_avoids_boundaries_and_prefix_keeps_started_leaf_pending(self):
        payload = acq_payload(False)
        for key in ('schedule', 'snapshots', 'leaf_returns', 'unwired_inputs', 'reference_bindings'):
            payload[key] = None
        result = self.dispatch('/v1/replay/acquisition-event-45123', payload)
        self.assertEqual((result['writes'], result['leaf_calls']), ([], []))
        payload = acq_payload()
        stop = next(index + 1 for index, token in enumerate(payload['schedule'])
                    if token == dict(kind='leaf_call', uid='46267'))
        payload['schedule'] = payload['schedule'][:stop]
        result = self.dispatch('/v1/replay/acquisition-event-45123', payload)
        self.assertEqual(result['pending_leaf_uids'], ['46267'])
        self.assertFalse(result['selected_body_completed'])

    def test_axis_gap_reads_saved_subtract_slots_and_writer_error_handler(self):
        payload = sup_payload()
        before = copy.deepcopy(payload)
        result = self.dispatch('/v1/replay/supervision-event-65050', payload)
        reads = payload['local_reads']
        first = (reads['62327'] * .0979 + 5.0) - reads['62319'] * .049
        second = (reads['69089'] * -.0979 + 5.0) - reads['69067'] * .049
        self.assertAlmostEqual(result['projected_cluster'][2], first, places=12)
        self.assertAlmostEqual(result['projected_cluster'][3], second, places=12)
        for index in (0, 1, 4, 5, 6, 7, 8, 9):
            self.assertEqual(result['projected_cluster'][index], reads['88920'][index])
        self.assertEqual(result['local_assignments']['88976']['data'], result['projected_cluster'])
        self.assertEqual(result['writer_call']['data'], result['projected_cluster'])
        self.assertEqual(result['handler_call']['supplied_error_in'], payload['native_returns']['88939']['88950'])
        self.assertTrue(result['handler_call']['supplied_error_in']['status'])
        self.assertFalse(result['writer_success_gates_local_assignment'])
        self.assertFalse(result['native_float_bitwise_equivalence'])
        self.assertFalse(result['whole_event_equivalence'])
        self.assertEqual(payload, before)

    def test_event_newval_is_not_used_in_sup_projection(self):
        payload = sup_payload()
        first = self.dispatch('/v1/replay/supervision-event-65050', payload)
        payload['event_returns']['65078']['65097'] = 123456.0
        payload['event_returns']['65078']['65094'] = -654321.0
        second = self.dispatch('/v1/replay/supervision-event-65050', payload)
        self.assertEqual(first['projected_cluster'], second['projected_cluster'])
        self.assertEqual(first['local_assignments'], second['local_assignments'])

    def test_signed_authentication_nonce_and_method(self):
        for path, fixture in (('/v1/replay/acquisition-event-45123', acq_payload),
                              ('/v1/replay/supervision-event-65050', sup_payload)):
            request = self.request(path, fixture())
            request['signature'] = '0' * 64
            self.assertEqual(self.endpoint.dispatch(request)['status'], 401)
            request = self.request(path, fixture())
            self.assertEqual(self.endpoint.dispatch(request)['status'], 200)
            self.assertEqual(self.endpoint.dispatch(request)['status'], 401)
            self.assertEqual(self.endpoint.dispatch(self.request(path, None, 'GET'))['status'], 404)

    def test_wrong_source_version_shape_and_cross_body_identity_refused(self):
        for path, fixture, wrong_frame in (
            ('/v1/replay/acquisition-event-45123', acq_payload, '23449'),
            ('/v1/replay/supervision-event-65050', sup_payload, '73301')):
            payload = fixture()
            payload['source_version'] = '0' * 64
            self.dispatch(path, payload, 400)
            payload = fixture()
            payload.pop('source_version')
            self.dispatch(path, payload, 400)
            payload = fixture()
            payload['frame_uid'] = wrong_frame
            self.dispatch(path, payload, 400)
        payload = acq_payload()
        payload['snapshots']['50001'].pop()
        self.dispatch('/v1/replay/acquisition-event-45123', payload, 400)
        payload = sup_payload()
        payload['local_reads']['88920'].pop()
        self.dispatch('/v1/replay/supervision-event-65050', payload, 400)


if __name__ == '__main__':
    unittest.main()
