"""G78 current signed stateless routes; supplied data never proves native execution."""
import copy
import time
import unittest
import uuid
from elyse_agent.supervision_rpc import SupervisionEndpoint
from elyse_agent.supervision_wire import MAX_BYTES, json_bytes, request_mac, response_mac
from elyse_agent import saved_acq_event_42457 as acq, saved_sup_event_47072 as sup
from seventeenth_next_event_fixtures import (
    acq_payload, false_acq_payload, inflight_acq_payload,
    sup_payload, minimal_sup_payload, sparse_sup_payload, oversized_sup_payload, acq_expected_writes)

ACQ_PATH = '/v1/replay/acquisition-event-42457'
SUP_PATH = '/v1/replay/supervision-event-47072'
CONTRACT_NAME = 'saved_seventeenth_next_event_slices_contract.json'
BOUNDARY_SCOPE = 'EXPLICIT_UNQUALIFIED_LITERAL_CALLEE_COERCION_SNAPSHOTS_SCHEDULE_WAIT_AND_NATIVE_LEAVES'
SELECTED_FALSE_FLAGS = (
    'event_selection_qualified', 'native_property_or_reference_validity_qualified',
    'native_literal_serializer_qualified', 'native_range_mode_qualified',
    'native_error_case_selection_qualified', 'native_wait_units_or_timing_qualified',
    'supplied_snapshots_are_acquired_data_qualified', 'supplied_completion_is_feasible_native_trace',
    'native_variant_conversion_qualified', 'native_argmax_tie_or_empty_policy_qualified',
    'native_loop_output_policy_qualified', 'native_field_index_selection_qualified',
    'native_unwired_input_defaults_qualified', 'native_callee_equivalence_qualified',
    'native_primitive_coercion_qualified')


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
    expected = {('APP-00', '43', '42457', 'saved_acq_event_42457.py'): acq.SOURCE_VERSION,
                ('APP-17', '5909', '47072', 'saved_sup_event_47072.py'): sup.SOURCE_VERSION}
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
            raise ValueError('Fifteen packaged open boundaries required')
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
    names = ('check_saved_seventeenth_next_event_slices_contract', '_check_saved_event_slices_contract')
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
    def __getitem__(self, key):
        raise AssertionError('Inactive source boundary read')

    def __iter__(self):
        raise AssertionError('Inactive source boundary read')

    def __bool__(self):
        raise AssertionError('Inactive source boundary read')


class SavedSeventeenthNextEventsRpcTests(unittest.TestCase):
    def setUp(self):
        self.key = b'G78-software-only-current-source-key'
        self.endpoint = SupervisionEndpoint(UnusableRuntime(), self.key)

    def request(self, path, payload, method='POST'):
        stamp, nonce = str(int(time.time())), uuid.uuid4().hex
        raw = b'' if method == 'GET' else json_bytes(payload)
        return dict(method=method, path=path, payload=payload, timestamp=stamp, nonce=nonce,
                    signature=request_mac(self.key, 'RPC/' + method, path, stamp, nonce, raw))

    def response(self, path, payload, status=200):
        request = self.request(path, payload)
        before = copy.deepcopy(payload)
        response = self.endpoint.dispatch(request)
        self.assertEqual(response['status'], status)
        raw = json_bytes(response['body'])
        self.assertLessEqual(len(raw), MAX_BYTES)
        self.assertEqual(response['signature'], response_mac(self.key, 'RPC/POST', path, request['nonce'], status, raw))
        self.assertFalse(response['body']['execution_allowed'])
        self.assertFalse(response['body']['hardware_writes'])
        self.assertEqual(response['body']['physical_status'], 'NOT_EXECUTED')
        self.assertEqual(payload, before)
        return response['body']

    def replay(self, path, payload, status=200):
        return self.response(path, payload, status).get('result')

    def test_six_exact_examples_signed_and_shared_adapter(self):
        self.assertEqual(MAX_BYTES, 65536)
        for path, factory, adapter in (
            (ACQ_PATH, acq_payload, acq.replay_saved_acq_event_42457),
            (ACQ_PATH, false_acq_payload, acq.replay_saved_acq_event_42457),
            (ACQ_PATH, inflight_acq_payload, acq.replay_saved_acq_event_42457),
            (SUP_PATH, sup_payload, sup.replay_saved_sup_event_47072),
            (SUP_PATH, minimal_sup_payload, sup.replay_saved_sup_event_47072),
            (SUP_PATH, sparse_sup_payload, sup.replay_saved_sup_event_47072)):
            payload = factory()
            result = self.replay(path, payload)
            self.assertEqual(result, adapter(payload))
            self.assertEqual(tuple(result[k] for k in ('source_id', 'source_version', 'event_uid', 'frame_uid')),
                             tuple(payload[k] for k in ('source_id', 'source_version', 'event_uid', 'frame_uid')))
            self.assertFalse(result['whole_event_equivalence'])

    def test_selected_contract_fifteen_present_false_boundaries(self):
        contract = check_current_saved_contract()
        self.assertEqual(len(SELECTED_FALSE_FLAGS), 15)
        self.assertEqual({(r['source_id'], r['event_uid'], r['frame_uid']) for r in contract['sources']},
                         {('APP-00', '43', '42457'), ('APP-17', '5909', '47072')})
        for row in contract['sources']:
            self.assertEqual(row['boundary_scope'], BOUNDARY_SCOPE)
            for flag in SELECTED_FALSE_FLAGS:
                self.assertIs(row[flag], False)

    def test_portable_contract_metadata_no_external_proof_read_and_corruption_refusal(self):
        import json
        import os
        import shutil
        import tempfile
        contract = check_current_saved_contract()
        with tempfile.TemporaryDirectory() as folder:
            os.mkdir(os.path.join(folder, 'data')); os.mkdir(os.path.join(folder, 'elyse_agent'))
            for row in contract['sources']:
                module = acq if row['source_id'] == 'APP-00' else sup
                shutil.copyfile(module.__file__, os.path.join(folder, 'elyse_agent', row['module']))
            valid = copy.deepcopy(contract)
            for row in valid['sources']:
                row['source_proof']['path'] = os.path.join(folder, 'ABSENT_EXTERNAL_PROOF_MUST_NOT_READ.json')
            path = os.path.join(folder, 'data', CONTRACT_NAME)
            def save(value):
                with open(path, 'w', encoding='utf8') as stream:
                    json.dump(value, stream)
            save(valid)
            self.assertEqual(_portable_contract_metadata(folder), valid)
            mutants = []
            for index in (0, 1):
                for flag in SELECTED_FALSE_FLAGS:
                    for mode in ('missing', 'true'):
                        value = copy.deepcopy(valid)
                        if mode == 'missing':
                            del value['sources'][index][flag]
                        else:
                            value['sources'][index][flag] = True
                        mutants.append(value)
            for key, value in (('source_version', '0' * 64), ('frame_uid', '23144'),
                               ('implementation_sha256', '0' * 64), ('boundary_scope', 'WHOLE')):
                item = copy.deepcopy(valid); item['sources'][0][key] = value; mutants.append(item)
            for key, value in (('bytes', True), ('sha256', 'X' * 64), ('path', '')):
                item = copy.deepcopy(valid); item['sources'][0]['source_proof'][key] = value; mutants.append(item)
            for item in mutants:
                save(item)
                with self.assertRaises((ValueError, KeyError)):
                    _portable_contract_metadata(folder)

    def test_acq_seven_source_stages_separate_reads_and_error_dependencies(self):
        p = acq_payload(); result = self.replay(ACQ_PATH, p)
        self.assertEqual({row['node_uid']: row['value'] for row in result['writes']}, acq_expected_writes(p))
        self.assertEqual(result['completed_stages'], ['42539', '39882', '35750', '1926', '42901', '41314', '44333'])
        self.assertIs(result['selected_body_completed'], True)
        calls = {row['node_uid']: row['input_ports'] for row in result['leaf_calls']}
        for uid, face, read in (('41020', '41034', '40872'), ('41037', '41051', '40979'),
                               ('39791', '39805', '39762'), ('43112', '43127', '43106'), ('31968', '31982', '31683')):
            self.assertEqual(calls[uid][face], p['snapshots'][read])
        for uid, face, producer, output in (('41037', '41045', '41020', '41031'),
                ('40987', '41017', '41037', '41048'), ('43112', '43121', '39791', '39802'),
                ('31968', '31976', '43112', '43124'), ('31985', '32082', '31968', '31979')):
            self.assertEqual(calls[uid][face], p['leaf_returns'][producer][output])
        self.assertEqual(calls['42649'], {'42654': 1000})
        self.assertEqual(calls['40868'], {'40877': 200})
        self.assertNotEqual(calls['41020']['41034'], acq_expected_writes(p)['42565'])
        self.assertNotEqual(calls['43112']['43127'], acq_expected_writes(p)['43003'])
        self.assertIs(result['native_callee_equivalence'], False)
        self.assertIs(result['scheduler_qualified'], False)

    def test_acq_explicit_field_and_literal_hypotheses_do_not_expand_domain(self):
        p = acq_payload(); self.assertEqual(p['field_index_bindings'], {'42589': 0, '51321': 0})
        self.assertEqual(p['literal_inputs'], {'31686': False, '40767': 0.0, '42907': False,
            '42917': False, '42927': False, '42947': False, '42957': False})
        self.replay(ACQ_PATH, p)
        for face in ('42589', '51321'):
            for value in (None, False, -1, 1, 0.0):
                p = acq_payload(); p['field_index_bindings'][face] = value; self.replay(ACQ_PATH, p, 400)
            p = acq_payload(); del p['field_index_bindings'][face]; self.replay(ACQ_PATH, p, 400)
        for value in (7.25, -0.0, True, 0, None):
            p = acq_payload(); p['literal_inputs']['40767'] = value; self.replay(ACQ_PATH, p, 400)
        p = acq_payload(); del p['literal_inputs']['40767']; self.replay(ACQ_PATH, p, 400)
        for uid in ('31686', '42907', '42917', '42927', '42947', '42957'):
            for value in (True, 0, None):
                p = acq_payload(); p['literal_inputs'][uid] = value; self.replay(ACQ_PATH, p, 400)
            p = acq_payload(); del p['literal_inputs'][uid]; self.replay(ACQ_PATH, p, 400)

    def test_acq_false_and_inflight_preserve_source_dependency_boundaries(self):
        result = self.replay(ACQ_PATH, false_acq_payload())
        self.assertEqual(result['selected_case_frame'], '42511')
        self.assertEqual(result['writes'], []); self.assertEqual(result['leaf_calls'], [])
        p = inflight_acq_payload(); result = self.replay(ACQ_PATH, p)
        self.assertEqual(result['active_stage'], '39882')
        self.assertEqual(result['completed_stages'], ['42539'])
        self.assertEqual(result['pending_leaf_uids'], ['41020'])
        self.assertIs(result['selected_body_completed'], False)
        p['schedule'].append({'kind': 'stage_complete', 'uid': '39882'}); self.replay(ACQ_PATH, p, 400)
        p = acq_payload(); p['schedule'][0] = {'kind': 'step', 'uid': '42565'}; self.replay(ACQ_PATH, p, 400)
        p = acq_payload(); p['reference_bindings']['40910']['saved_uri'] += '/other'; self.replay(ACQ_PATH, p, 400)
        p = acq_payload(); p['leaf_returns']['41020']['41031']['status'] = 0; self.replay(ACQ_PATH, p, 400)
        p = acq_payload(); p['unwired_inputs']['41014'] = 65536; self.replay(ACQ_PATH, p, 400)
        p = acq_payload(); p['snapshots']['30243'][0] = 1; self.replay(ACQ_PATH, p, 400)

    def test_sup_nested_page_paths_independent_dps_and_byte_concat(self):
        p = sup_payload(); result = self.replay(SUP_PATH, p)
        self.assertEqual(result['source_case_uid'], '47154')
        self.assertEqual(result['source_selector_terminal_uid'], '47156')
        self.assertEqual(result['selected_case_frame'], '47168')
        self.assertEqual(result['source_busy_gate']['Boolean_array'], p['local_reads']['47137'])
        updated = list(p['local_reads']['47137'])
        for source, target in ((4, 20), (3, 23), (12, 21)): updated[target] = p['new_value'][source]
        self.assertEqual(result['local_assignments'][0]['value'], updated)
        self.assertEqual([(r['raw_flattened_field_index'], r['typed_position_path'], r['destination_raw_flattened_field_index'])
                          for r in result['field_updates']], [(11, [4], 20), (10, [3], 23), (19, [12], 21)])
        calls = {row['node_uid']: row for row in result['leaf_observations']}
        self.assertEqual(calls['32048']['inputs'], {'32652': p['reference_bindings']['31390']['native_reference'],
            '32658': p['unwired_inputs']['32658'], '32664': updated})
        self.assertEqual(calls['28270']['inputs'], {'28277': p['event_time_40518']})
        case = result['case_observations'][0]
        self.assertEqual((case['node_uid'], case['selector_terminal_uid'], case['selected_frame']), ('19594', '36566', '36477'))
        self.assertEqual(case['source_input_error'], p['native_boundaries']['32048']['outputs']['32661'])
        expected_hex = p['literal_inputs']['35281']['bytes_hex'] + p['native_boundaries']['32048']['outputs']['32661']['source_hex']
        self.assertEqual(result['local_assignments'][1]['node_uid'], '40558')
        self.assertEqual(result['local_assignments'][1]['value'], {'bytes_hex': expected_hex})
        self.assertEqual(result['completed_sinks'], ['40558', '32048'])
        self.assertIs(result['completion_observations_are_feasible_trace'], False)
        self.assertIs(result['native_ErrorCluster_Case_selection_qualified'], False)

    def test_sup_all29_busy_bits_only_wait_and_unselected_boundary_nonaccess(self):
        for index in range(29):
            p = minimal_sup_payload(); p['local_reads']['47137'] = [False] * 29; p['local_reads']['47137'][index] = True
            p['new_value'] = {'not_a_Page': 1}; p['reference_bindings'] = None; p['unwired_inputs'] = None
            p['intrinsic_inputs'] = None; p['event_time_40518'] = None
            p['literal_inputs']['35281'] = None; p['native_boundaries']['32048'] = 'unused'
            p['literal_inputs']['42462'] = 4294967295
            result = self.replay(SUP_PATH, p)
            self.assertEqual(result['selected_case_frame'], '47226')
            self.assertEqual(result['local_assignments'], []); self.assertEqual(result['field_updates'], [])
            self.assertEqual([r['node_uid'] for r in result['leaf_observations']], ['28270'])
            self.assertEqual(result['source_Wait_input_value'], 4294967295)
        p = sparse_sup_payload(); result = self.replay(SUP_PATH, p)
        self.assertEqual(result['case_observations'][0]['selected_frame'], '36498')
        self.assertEqual(len(result['local_assignments']), 1)
        self.assertEqual(result['decoded_literal_observations'], [])
        self.assertEqual(result['source_Wait_input_value'], 17)

    def test_sup_supplied_error_selection_time_and_exact_domains(self):
        for status in (False, True):
            for selector in (False, True):
                p = sup_payload(); p['native_boundaries']['32048']['outputs']['32661']['status'] = status
                p['intrinsic_inputs']['19594'] = selector; p['completed_sinks'] = ['28270', '47186']
                result = self.replay(SUP_PATH, p)
                self.assertEqual(len(result['local_assignments']), 2 if selector else 1)
                self.assertEqual(result['case_observations'][0]['supplied_intrinsic_selector'], selector)
        mutants = []
        for value in (-1, 4294967296, True, 0.0, None):
            p = sup_payload(); p['event_time_40518'] = value; mutants.append(p)
            p = minimal_sup_payload(); p['literal_inputs']['42462'] = value; mutants.append(p)
        for value in ([False] * 28, [False] * 30, [0] * 29):
            p = sup_payload(); p['local_reads']['47137'] = value; mutants.append(p)
        for value in (0, None, 'True'):
            p = sup_payload(); p['intrinsic_inputs']['19594'] = value; mutants.append(p)
        for index, value in ((4, 0), (1, 65536), (0, [0.0] * 6), (10, {'bytes_hex': 'ff'})):
            p = sup_payload(); p['new_value'][index] = value; mutants.append(p)
        p = sup_payload(); p['reference_bindings']['31390']['stored_URI_bytes']['bytes_hex'] += '00'; mutants.append(p)
        p = sup_payload(); p['literal_inputs']['35281']['bytes_hex'] += '00'; mutants.append(p)
        p = sup_payload(); p['native_boundaries']['32048']['outputs']['32661']['code'] = 2**31; mutants.append(p)
        p = sup_payload(); p['native_boundaries']['32048']['outputs']['32661']['status'] = 0; mutants.append(p)
        p = sup_payload(); del p['unwired_inputs']['32658']; mutants.append(p)
        for report in (['32048', '32048'], ['47154']):
            p = sup_payload(); p['completed_sinks'] = report; mutants.append(p)
        for flag in sup_payload()['unqualified_boundaries']:
            p = sup_payload(); p['unqualified_boundaries'][flag] = True; mutants.append(p)
        for p in mutants: self.replay(SUP_PATH, p, 400)

    def test_exact_source_identity_and_no_execution_extension(self):
        for path, factory in ((ACQ_PATH, acq_payload), (SUP_PATH, sup_payload)):
            for key in ('source_id', 'source_version', 'event_uid', 'frame_uid'):
                p = factory(); p[key] = 'wrong'; self.replay(path, p, 400)
            p = factory(); p['execute_native'] = True; self.replay(path, p, 400)

    def test_authentication_nonce_signature_and_path_binding(self):
        request = self.request(SUP_PATH, sup_payload())
        self.assertEqual(self.endpoint.dispatch(request)['status'], 200)
        self.assertEqual(self.endpoint.dispatch(request)['status'], 401)
        request = self.request(SUP_PATH, sup_payload()); request['path'] = ACQ_PATH
        self.assertEqual(self.endpoint.dispatch(request)['status'], 401)
        request = self.request(SUP_PATH, sup_payload()); request['signature'] = '0' * 64
        self.assertEqual(self.endpoint.dispatch(request)['status'], 401)

    def test_allowed_opaque_carriers_and_measured_signed_response_cap(self):
        p = oversized_sup_payload()
        self.assertEqual(p['literal_inputs'], sup_payload()['literal_inputs'])
        self.assertLessEqual(len(json_bytes(p)), MAX_BYTES)
        result = sup.replay_saved_sup_event_47072(p)
        body = dict(schema_version=1, execution_allowed=False, hardware_writes=False, physical_status='NOT_EXECUTED', result=result)
        self.assertGreater(len(json_bytes(body)), MAX_BYTES)
        refused = self.response(SUP_PATH, p, 400)
        self.assertEqual(refused['error'], 'Supervision response exceeds 65536 bytes')
        self.assertIs(refused['accepted'], False)
        p['native_boundaries']['28270']['outputs'] = ['X' * 8192] * 8
        self.assertGreater(len(json_bytes(p)), MAX_BYTES)
        with self.assertRaises(ValueError): self.endpoint.dispatch(self.request(SUP_PATH, p))


if __name__ == '__main__': unittest.main()
