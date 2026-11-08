"""G72 current signed stateless routes; supplied data never proves native execution."""
import copy
import time
import unittest
import uuid
from elyse_agent.supervision_rpc import SupervisionEndpoint
from elyse_agent.supervision_wire import MAX_BYTES, json_bytes, request_mac, response_mac
from elyse_agent import saved_acq_event_38732 as acq, saved_sup_event_26490 as sup
from eleventh_next_event_fixtures import (
    acq_payload, false_acq_payload, inflight_acq_payload,
    sup_payload, minimal_sup_payload, sparse_sup_payload, oversized_sup_payload)

ACQ_PATH = '/v1/replay/acquisition-event-38732'
SUP_PATH = '/v1/replay/supervision-event-26490'
CONTRACT_NAME = 'saved_eleventh_next_event_slices_contract.json'
BOUNDARY_SCOPE = 'EXPLICIT_UNQUALIFIED_LITERAL_FIELD_BINDINGS_SNAPSHOTS_SCHEDULE_WAIT_AND_NATIVE_LEAVES'
SELECTED_FALSE_FLAGS = (
    'event_selection_qualified', 'native_property_or_reference_validity_qualified',
    'native_literal_serializer_qualified', 'native_range_mode_qualified',
    'native_error_case_selection_qualified', 'native_wait_units_or_timing_qualified',
    'supplied_snapshots_are_acquired_data_qualified', 'supplied_completion_is_feasible_native_trace',
    'native_variant_conversion_qualified', 'native_argmax_tie_or_empty_policy_qualified',
    'native_loop_output_policy_qualified', 'native_field_index_selection_qualified',
    'native_unwired_input_defaults_qualified')


class BinaryPath(object):
    """Test-only actual-host checker carrier for Python3.4 binary/UTF8 reads."""
    def __init__(self, path):
        self.path = str(path)

    def __truediv__(self, part):
        import os
        return BinaryPath(os.path.join(self.path, part))

    def read_bytes(self):
        with open(self.path, 'rb') as stream:
            return stream.read()

    def read_text(self, encoding='utf-8'):
        with open(self.path, 'r', encoding=encoding) as stream:
            return stream.read()


class UTF8JsonCompat(object):
    """Explicit bytes decoding for exact host checker json.loads on Python3.4."""
    @staticmethod
    def loads(value):
        import json
        return json.loads(value.decode('utf-8') if isinstance(value, bytes) else value)


def _portable_contract_metadata(agent_root):
    """Local identity/coreSHA/policy/proof-shape guard; no external proof reads."""
    import hashlib
    import json
    import os
    import re
    with open(os.path.join(agent_root, 'data', CONTRACT_NAME), 'r', encoding='utf-8') as stream:
        value = json.load(stream)
    flags = ('native_execution', 'hardware_execution', 'PSP_execution', 'deployed',
             'whole_event_equivalence', 'whole_business_scope_complete')
    if value.get('schema_version') != 1 or any(value.get(f) is not False for f in flags):
        raise ValueError('Bounded packaged event contract required')
    expected = {('APP-00', '43', '38732', 'saved_acq_event_38732.py'): acq.SOURCE_VERSION,
                ('APP-17', '5909', '26490', 'saved_sup_event_26490.py'): sup.SOURCE_VERSION}
    rows = value.get('sources')
    if type(rows) is not list or len(rows) != 2:
        raise ValueError('Exact two packaged event rows required')
    actual = {(row['source_id'], row['event_uid'], row['frame_uid'], row['module']) for row in rows}
    if actual != set(expected):
        raise ValueError('Exact current packaged source identities required')
    for row in rows:
        identity = tuple(row[k] for k in ('source_id', 'event_uid', 'frame_uid', 'module'))
        if (row.get('source_version') != expected[identity] or row.get('scope') != 'SUPPLIED_SELECTED_EVENT_BODY'
                or row.get('native_execution') is not False or row.get('whole_event_equivalence') is not False):
            raise ValueError('Bounded version-specific packaged row required')
        if row.get('boundary_scope') != BOUNDARY_SCOPE or any(row.get(f) is not False for f in SELECTED_FALSE_FLAGS):
            raise ValueError('Thirteen packaged open boundaries required')
        with open(os.path.join(agent_root, 'elyse_agent', row['module']), 'rb') as stream:
            data = stream.read()
        if hashlib.sha256(data).hexdigest().upper() != row['implementation_sha256']:
            raise ValueError('Packaged implementation changed')
        proof = row.get('source_proof')
        if (type(proof) is not dict or set(proof) != {'path', 'bytes', 'sha256'}
                or type(proof['path']) is not str or not proof['path']
                or type(proof['bytes']) is not int or proof['bytes'] < 0
                or type(proof['sha256']) is not str
                or re.match(r'^[0-9A-F]{64}\Z', proof['sha256']) is None):
            raise ValueError('Packaged source proof metadata required')
        # Deliberately no open(proof.path): extracted package carries metadata.
    return value


def check_current_saved_contract():
    """Host invokes exact current checker definitions; extracted package stays local."""
    import hashlib
    import os
    import re
    agent_root = os.path.dirname(os.path.abspath(__file__))
    while not (os.path.isfile(os.path.join(agent_root, 'data', CONTRACT_NAME))
               and os.path.isdir(os.path.join(agent_root, 'elyse_agent'))):
        parent = os.path.dirname(agent_root)
        if parent == agent_root:
            raise ImportError('Current agent contract and modules required')
        agent_root = parent
    source_root = os.path.dirname(os.path.dirname(agent_root))
    builder = os.path.join(source_root, 'tools', 'build_elyse_acq_supervision.py')
    is_source = (os.path.basename(agent_root) == 'xp_acq_agent'
                 and os.path.basename(os.path.dirname(agent_root)) == 'legacy'
                 and os.path.isfile(builder))
    if not is_source:
        return _portable_contract_metadata(agent_root)
    with open(builder, 'r', encoding='utf-8') as stream:
        source = stream.read()
    names = ('check_saved_eleventh_next_event_slices_contract', '_check_saved_event_slices_contract')
    blocks = []
    for name in names:
        matches = re.findall(r'^def ' + re.escape(name) + r'\([^\n]*\):\n.*?(?=^def |\Z)', source, re.M | re.S)
        if len(matches) != 1:
            raise AssertionError('Exactly one current source checker required: ' + name)
        blocks.append(matches[0])
    namespace = {'hashlib': hashlib, 'json': UTF8JsonCompat, 'AGENT': BinaryPath(agent_root), 'Path': BinaryPath}
    exec(compile('\n'.join(blocks), builder, 'exec'), namespace)
    return namespace[names[0]]()


class UnusableRuntime(object):
    def __getattribute__(self, name):
        raise AssertionError('Stateless replay accessed runtime: ' + name)


class Tripwire(object):
    def __iter__(self):
        raise AssertionError('Inactive source input read')

    def __getitem__(self, key):
        raise AssertionError('Inactive source input read')

    def __bool__(self):
        raise AssertionError('Inactive source input read')


class SavedEleventhNextEventsRpcTests(unittest.TestCase):
    def setUp(self):
        self.key = b'G72-software-only-current-source-key'
        self.endpoint = SupervisionEndpoint(UnusableRuntime(), self.key)

    def request(self, path, payload, method='POST'):
        stamp, nonce = str(int(time.time())), uuid.uuid4().hex
        raw = b'' if method == 'GET' else json_bytes(payload)
        return dict(method=method, path=path, payload=payload, timestamp=stamp, nonce=nonce,
                    signature=request_mac(self.key, 'RPC/' + method, path, stamp, nonce, raw))

    def response(self, path, payload, status=200):
        req = self.request(path, payload)
        before = copy.deepcopy(payload)
        response = self.endpoint.dispatch(req)
        self.assertEqual(response['status'], status)
        body = response['body']
        raw = json_bytes(body)
        self.assertLessEqual(len(raw), 65536)
        self.assertFalse(body['execution_allowed'])
        self.assertFalse(body['hardware_writes'])
        self.assertEqual(body['physical_status'], 'NOT_EXECUTED')
        self.assertEqual(response['signature'], response_mac(self.key, 'RPC/POST', path, req['nonce'], status, raw))
        self.assertEqual(payload, before)
        return body

    def replay(self, path, payload, status=200):
        return self.response(path, payload, status).get('result')

    def test_six_exact_examples_same_adapter_and_signed_envelope(self):
        self.assertEqual(MAX_BYTES, 65536)
        rows = ((ACQ_PATH, acq_payload, acq.replay_saved_acq_event_38732),
                (ACQ_PATH, false_acq_payload, acq.replay_saved_acq_event_38732),
                (ACQ_PATH, inflight_acq_payload, acq.replay_saved_acq_event_38732),
                (SUP_PATH, sup_payload, sup.replay_saved_sup_event_26490),
                (SUP_PATH, minimal_sup_payload, sup.replay_saved_sup_event_26490),
                (SUP_PATH, sparse_sup_payload, sup.replay_saved_sup_event_26490))
        for path, factory, adapter in rows:
            payload = factory()
            result = self.replay(path, payload)
            self.assertEqual(result, adapter(payload))
            self.assertEqual(tuple(result[k] for k in ('source_id', 'source_version', 'event_uid', 'frame_uid')),
                             tuple(payload[k] for k in ('source_id', 'source_version', 'event_uid', 'frame_uid')))
            self.assertFalse(result['whole_event_equivalence'])

    def test_selected_contract_thirteen_present_false_flags(self):
        contract = check_current_saved_contract()
        self.assertEqual(len(SELECTED_FALSE_FLAGS), 13)
        self.assertEqual({(r['source_id'], r['event_uid'], r['frame_uid']) for r in contract['sources']},
                         {('APP-00', '43', '38732'), ('APP-17', '5909', '26490')})
        for row in contract['sources']:
            self.assertEqual(row['boundary_scope'], BOUNDARY_SCOPE)
            for flag in SELECTED_FALSE_FLAGS:
                self.assertIs(row[flag], False)

    def test_portable_contract_guard_is_local_and_rejects_corrupt_metadata(self):
        import json
        import os
        import shutil
        import tempfile
        source = check_current_saved_contract()
        with tempfile.TemporaryDirectory() as temp:
            os.mkdir(os.path.join(temp, 'data'))
            os.mkdir(os.path.join(temp, 'elyse_agent'))
            for row in source['sources']:
                module = acq if row['source_id'] == 'APP-00' else sup
                shutil.copyfile(module.__file__, os.path.join(temp, 'elyse_agent', row['module']))
            value = copy.deepcopy(source)
            for row in value['sources']:
                row['source_proof']['path'] = os.path.join(temp, 'NEVER_READ_EXTERNAL_PROOF.json')
            path = os.path.join(temp, 'data', CONTRACT_NAME)
            def save(item):
                with open(path, 'w', encoding='utf-8') as stream:
                    json.dump(item, stream)
            save(value)
            self.assertEqual(_portable_contract_metadata(temp), value)
            mutants = []
            for flag in SELECTED_FALSE_FLAGS:
                for mode in ('missing', 'true'):
                    item = copy.deepcopy(value)
                    if mode == 'missing':
                        del item['sources'][0][flag]
                    else:
                        item['sources'][0][flag] = True
                    mutants.append(item)
            for key, replacement in (('source_version', '0' * 64), ('frame_uid', '38733'),
                                     ('implementation_sha256', '0' * 64), ('boundary_scope', 'WHOLE_EVENT')):
                item = copy.deepcopy(value)
                item['sources'][0][key] = replacement
                mutants.append(item)
            item = copy.deepcopy(value)
            item['sources'][0]['source_proof']['bytes'] = True
            mutants.append(item)
            item = copy.deepcopy(value)
            item['sources'][0]['source_proof']['sha256'] = 'X' * 64
            mutants.append(item)
            for item in mutants:
                save(item)
                with self.assertRaises((ValueError, KeyError)):
                    _portable_contract_metadata(temp)

    def test_acq_six_phases_five_assignments_and_untouched_fields(self):
        payload = acq_payload()
        result = self.replay(ACQ_PATH, payload)
        first = list(payload['snapshots']['38883'])
        for index in (0, 1, 2, 3, 4, 5, 6, 7, 9):
            first[index] = payload['literal_inputs']['38829']
        second = list(payload['snapshots']['38959'])
        for index in (0, 1, 3, 4, 6, 7, 8, 9):
            second[index] = payload['literal_inputs']['38829']
        eps = list(payload['snapshots']['39636'])
        eps[59], eps[64], eps[61] = payload['literal_inputs']['42005'], payload['literal_inputs']['39475'], True
        dps = list(payload['snapshots']['39698'])
        dps[21] = payload['literal_inputs']['39502']
        self.assertEqual({r['node_uid']: r['value'] for r in result['writes']},
                         {'38841': first, '38889': True, '38897': second, '39559': eps, '39654': dps})
        self.assertEqual(result['completed_stages'], ['38812', '38987', '39227', '39387', '39743', '39965'])
        self.assertTrue(result['selected_body_completed'])
        self.assertEqual(first[8], payload['snapshots']['38883'][8])
        self.assertEqual([second[i] for i in (2, 5)], [payload['snapshots']['38959'][i] for i in (2, 5)])

    def test_acq_field_and_literal_boundaries_are_explicit(self):
        # Qualified replay policy admits exact positive 0.0 and False only.
        # Caller-supplied storage does not widen the frozen projection domain.
        payload = acq_payload()
        self.assertEqual(payload['literal_inputs'], {'38829': 0.0, '39475': False,
                                                    '39502': False, '42005': False})
        result = self.replay(ACQ_PATH, payload)
        writes = {r['node_uid']: r['value'] for r in result['writes']}
        self.assertEqual(writes['38841'][0], 0.0)
        self.assertIs(writes['39559'][59], False)
        self.assertIs(writes['39559'][64], False)
        self.assertIs(writes['39654'][21], False)
        for face in ('38855', '38911'):
            for replacement in (None, True, 1):
                item = acq_payload()
                item['field_index_bindings'][face] = replacement
                self.replay(ACQ_PATH, item, 400)
            item = acq_payload()
            del item['field_index_bindings'][face]
            self.replay(ACQ_PATH, item, 400)
        for replacement in (7.25, -0.0, 0, None, False, '0.0'):
            item = acq_payload()
            item['literal_inputs']['38829'] = replacement
            self.replay(ACQ_PATH, item, 400)
        item = acq_payload()
        del item['literal_inputs']['38829']
        self.replay(ACQ_PATH, item, 400)
        for uid in ('39475', '39502', '42005'):
            for replacement in (True, 0, None, 'False', 0.0):
                item = acq_payload()
                item['literal_inputs'][uid] = replacement
                self.replay(ACQ_PATH, item, 400)
            item = acq_payload()
            del item['literal_inputs'][uid]
            self.replay(ACQ_PATH, item, 400)

    def test_acq_fresh_reads_error_routes_reference_and_wait_inputs(self):
        payload = acq_payload()
        result = self.replay(ACQ_PATH, payload)
        calls = {row['node_uid']: row['input_ports'] for row in result['leaf_calls']}
        for uid, face, read in (('39140', '39158', '39043'), ('39162', '39180', '39059'),
                                ('39861', '39875', '39855'), ('39885', '39901', '39878')):
            self.assertEqual(calls[uid][face], payload['snapshots'][read])
        self.assertNotEqual(calls['39140']['39158'], result['writes'][0]['value'])
        for uid, face, producer, output in (('39162', '39171', '39140', '39153'),
                                           ('39076', '39134', '39162', '39176'),
                                           ('39885', '39895', '39861', '39872'),
                                           ('39904', '39934', '39885', '39898')):
            self.assertEqual(calls[uid][face], payload['leaf_returns'][producer][output])
            self.assertTrue(calls[uid][face]['status'])
        for uid, face, constant in (('39140', '39144', '38993'), ('39162', '39164', '39011'),
                                    ('39861', '39863', '39778'), ('39885', '39888', '39813')):
            self.assertEqual(calls[uid][face], payload['reference_bindings'][constant]['native_ref'])
        self.assertEqual(calls['39266'], {'39273': 1000})
        self.assertEqual(calls['39983'], {'39988': 200})
        self.assertFalse(result['wait_units_or_pulse_duration_qualified'])
        self.assertFalse(result['scheduler_qualified'])

    def test_acq_false_nonaccess_and_inflight_are_distinct_from_native_completion(self):
        item = false_acq_payload()
        for key in ('schedule', 'snapshots', 'leaf_returns', 'unwired_inputs', 'reference_bindings',
                    'field_index_bindings', 'literal_inputs'):
            item[key] = None
        result = self.replay(ACQ_PATH, item)
        self.assertEqual(result['selected_case_frame'], '38786')
        self.assertEqual(result['writes'], [])
        self.assertEqual(result['leaf_calls'], [])
        opaque = Tripwire()
        pure = acq.replay_event(False, opaque, snapshots=opaque, leaf_returns=opaque, unwired_inputs=opaque,
                                reference_bindings=opaque, field_index_bindings=opaque, literal_inputs=opaque)
        self.assertEqual(pure['writes'], [])
        item = inflight_acq_payload()
        result = self.replay(ACQ_PATH, item)
        self.assertEqual(result['pending_leaf_uids'], ['39140'])
        self.assertEqual(result['active_stage'], '38987')
        self.assertFalse(result['selected_body_completed'])
        item['schedule'].append(dict(kind='stage_complete', uid='38987'))
        self.replay(ACQ_PATH, item, 400)

    def test_sup_three_phase_bindings_and_distinct_raw_boolean_storage(self):
        for first in (False, True):
            for last in (False, True):
                payload = sup_payload()
                payload['literal_inputs'] = {'20659': first, '21637': last}
                result = self.replay(SUP_PATH, payload)
                self.assertEqual(result['source_sequence_uid'], '20194')
                self.assertEqual(result['source_phase_order'], ['20201', '21020', '21238'])
                assignments = result['source_assignments']
                self.assertEqual([r['node_uid'] for r in assignments], ['19732', '21619'])
                self.assertEqual([r['value'] for r in assignments], [first, last])
                self.assertEqual([r['source_literal_raw_hex'] for r in assignments], ['01', '0000'])
                self.assertEqual([r['source_diagram_uid'] for r in assignments], ['20206', '21245'])
                for row in assignments:
                    self.assertEqual((row['explicit_paramIdx'], row['saved_FP_bank_uid'], row['control_terminal_uid']),
                                     (132, '19944', '19961'))
                    self.assertTrue(row['decoded_literal_is_hypothetical'])
                wait = result['wait_observation']
                self.assertEqual((wait['node_uid'], wait['source_container_uid'], wait['source_diagram_uid'],
                                  wait['input_terminal_uid'], wait['provided_data_U32_input'], wait['unused_output_terminal_uid']),
                                 ('22081', '21020', '21027', '22091', 200, '22087'))
                self.assertFalse(wait['native_units_and_timing_qualified'])
                self.assertIn('InRangeAndCoerce', result['actual_absent_structures'])

    def test_sup_opaque_unused_outputs_and_completion_reports(self):
        unused_wait, unused_event = Tripwire(), Tripwire()
        pure = sup.project_event_26490({'20659': True, '21637': False}, unused_wait, unused_event,
                                       ('21619', '19732'))
        self.assertIs(pure['wait_observation']['supplied_unused_return'], unused_wait)
        self.assertIs(pure['supplied_unused_event_outputs'], unused_event)
        self.assertFalse(pure['completion_observations_are_feasible_trace'])
        payload = sparse_sup_payload()
        payload['completed_sinks'] = ['21619', '19732']
        result = self.replay(SUP_PATH, payload)
        self.assertEqual(result['completed_sinks'], payload['completed_sinks'])
        self.assertFalse(result['completion_observations_prove_success'])
        self.assertFalse(result['native_storage_serializer_qualified'])

    def test_sup_literal_boundary_and_json_refusals(self):
        for value in (0, 1, None, 'False'):
            payload = sup_payload()
            payload['literal_inputs']['21637'] = value
            self.replay(SUP_PATH, payload, 400)
        for flag in sup.QUALIFICATION_FLAGS:
            payload = sup_payload()
            payload['unqualified_boundaries'][flag] = True
            self.replay(SUP_PATH, payload, 400)
        for completion in (['19732', '19732'], ['22087'], ['20194']):
            payload = sup_payload()
            payload['completed_sinks'] = completion
            self.replay(SUP_PATH, payload, 400)
        payload = sup_payload()
        payload['wait_return'] = 'X' * 4097
        self.replay(SUP_PATH, payload, 400)

    def test_source_identity_exact_keys_and_no_execute_extension(self):
        for path, factory in ((ACQ_PATH, acq_payload), (SUP_PATH, sup_payload)):
            for key in ('source_id', 'source_version', 'event_uid', 'frame_uid'):
                payload = factory()
                payload[key] = 'wrong'
                self.replay(path, payload, 400)
            payload = factory()
            payload['execute_native'] = True
            self.replay(path, payload, 400)
        payload = acq_payload()
        del payload['field_index_bindings']
        self.replay(ACQ_PATH, payload, 400)

    def test_signed_authentication_path_and_nonce_replay(self):
        request = self.request(SUP_PATH, sup_payload())
        self.assertEqual(self.endpoint.dispatch(request)['status'], 200)
        self.assertEqual(self.endpoint.dispatch(request)['status'], 401)
        request = self.request(SUP_PATH, sup_payload())
        request['path'] = ACQ_PATH
        self.assertEqual(self.endpoint.dispatch(request)['status'], 401)
        request = self.request(SUP_PATH, sup_payload())
        request['signature'] = '0' * 64
        self.assertEqual(self.endpoint.dispatch(request)['status'], 401)

    def test_pure_acceptance_and_signed_response_cap_are_separate(self):
        payload = oversized_sup_payload()
        self.assertEqual(payload['literal_inputs'], minimal_sup_payload()['literal_inputs'])
        self.assertLessEqual(len(json_bytes(payload)), 65536)
        result = sup.replay_saved_sup_event_26490(payload)
        body = dict(schema_version=1, execution_allowed=False, hardware_writes=False,
                    physical_status='NOT_EXECUTED', result=result)
        self.assertGreater(len(json_bytes(body)), 65536)
        refusal = self.response(SUP_PATH, payload, 400)
        self.assertEqual(refusal['error'], 'Supervision response exceeds 65536 bytes')
        self.assertFalse(refusal['accepted'])
        payload['wait_return'] = ['X' * 4096] * 17
        with self.assertRaises(ValueError):
            self.endpoint.dispatch(self.request(SUP_PATH, payload))
        payload = sup_payload()
        payload['wait_return'] = float('nan')
        with self.assertRaises(ValueError):
            self.request(SUP_PATH, payload)


if __name__ == '__main__':
    unittest.main()
