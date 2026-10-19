"""G73 current signed stateless routes; supplied data never proves native execution."""
import copy
import time
import unittest
import uuid
from elyse_agent.supervision_rpc import SupervisionEndpoint
from elyse_agent.supervision_wire import MAX_BYTES, json_bytes, request_mac, response_mac
from elyse_agent import saved_acq_event_37991 as acq, saved_sup_event_23880 as sup
from twelfth_next_event_fixtures import (
    acq_payload, false_acq_payload, inflight_acq_payload,
    sup_payload, minimal_sup_payload, sparse_sup_payload, oversized_sup_payload)

ACQ_PATH = '/v1/replay/acquisition-event-37991'
SUP_PATH = '/v1/replay/supervision-event-23880'
CONTRACT_NAME = 'saved_twelfth_next_event_slices_contract.json'
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
    expected = {('APP-00', '43', '37991', 'saved_acq_event_37991.py'): acq.SOURCE_VERSION,
                ('APP-17', '5909', '23880', 'saved_sup_event_23880.py'): sup.SOURCE_VERSION}
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
    names = ('check_saved_twelfth_next_event_slices_contract', '_check_saved_event_slices_contract')
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


class SavedTwelfthNextEventsRpcTests(unittest.TestCase):
    def setUp(self):
        self.key = b'G73-software-only-current-source-key'
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
            (ACQ_PATH, acq_payload, acq.replay_saved_acq_event_37991),
            (ACQ_PATH, false_acq_payload, acq.replay_saved_acq_event_37991),
            (ACQ_PATH, inflight_acq_payload, acq.replay_saved_acq_event_37991),
            (SUP_PATH, sup_payload, sup.replay_saved_sup_event_23880),
            (SUP_PATH, minimal_sup_payload, sup.replay_saved_sup_event_23880),
            (SUP_PATH, sparse_sup_payload, sup.replay_saved_sup_event_23880)):
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
                         {('APP-00', '43', '37991'), ('APP-17', '5909', '23880')})
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
            for key, value in (('source_version', '0' * 64), ('frame_uid', '37992'),
                               ('implementation_sha256', '0' * 64), ('boundary_scope', 'WHOLE')):
                item = copy.deepcopy(valid); item['sources'][0][key] = value; mutants.append(item)
            for key, value in (('bytes', True), ('sha256', 'X' * 64), ('path', '')):
                item = copy.deepcopy(valid); item['sources'][0]['source_proof'][key] = value; mutants.append(item)
            for item in mutants:
                save(item)
                with self.assertRaises((ValueError, KeyError)):
                    _portable_contract_metadata(folder)

    def test_acq_seven_stages_seven_assignments_independent_snapshots(self):
        payload = acq_payload(); result = self.replay(ACQ_PATH, payload)
        writes = {r['node_uid']: r['value'] for r in result['writes']}
        expected = {}
        for uid, read, fields in (
            ('38100', '38118', {3: True}), ('38173', '38189', {3: False}),
            ('38251', '38267', {2: True}), ('38311', '38327', {2: False}),
            ('38519', '38540', {17: False, 14: True, 12: False}), ('38546', '38564', {4: False})):
            carrier = list(payload['snapshots'][read])
            for index, value in fields.items():
                carrier[index] = value
            expected[uid] = carrier
        expected['38124'] = True
        self.assertEqual(writes, expected)
        self.assertEqual(result['completed_stages'], ['38074', '38157', '38205', '38235', '38295', '38483', '38592'])
        calls = {r['node_uid']: r['input_ports'] for r in result['leaf_calls']}
        self.assertEqual(calls['38642']['38656'], payload['snapshots']['38636'])
        self.assertNotEqual(calls['38642']['38656'], writes['38546'])
        self.assertEqual(calls['38642']['38644'], payload['reference_bindings']['38610']['native_ref'])
        self.assertEqual(calls['38659']['38689'], payload['leaf_returns']['38642']['38653'])
        self.assertTrue(calls['38659']['38689']['status'])
        for uid, expected in (('38132', {'38137': 150}), ('38223', {'38228': 3000}),
                              ('38273', {'38278': 150}), ('38628', {'38633': 100})):
            self.assertEqual(calls[uid], expected)
        self.assertFalse(result['wait_units_or_pulse_duration_qualified'])
        self.assertFalse(result['native_callee_equivalence'])
        self.assertFalse(result['scheduler_qualified'])

    def test_acq_five_false_literal_policy_and_exact_adapter_keys(self):
        payload = acq_payload()
        self.assertEqual(payload['literal_inputs'], {u: False for u in ('37359', '38163', '38301', '38489', '38509')})
        self.replay(ACQ_PATH, payload)
        for uid in payload['literal_inputs']:
            for value in (True, 0, None, 'False', 0.0):
                item = acq_payload(); item['literal_inputs'][uid] = value
                self.replay(ACQ_PATH, item, 400)
            item = acq_payload(); del item['literal_inputs'][uid]
            self.replay(ACQ_PATH, item, 400)
        payload = acq_payload(); payload['field_index_bindings'] = {}
        self.replay(ACQ_PATH, payload, 400)
        payload = acq_payload(); del payload['literal_inputs']
        self.replay(ACQ_PATH, payload, 400)

    def test_acq_false_nonaccess_and_inflight_completion_refusal(self):
        result = self.replay(ACQ_PATH, false_acq_payload())
        self.assertEqual(result['selected_case_frame'], '38045')
        self.assertEqual(result['writes'], [])
        self.assertEqual(result['leaf_calls'], [])
        trap = Tripwire()
        pure = acq.replay_event(False, trap, snapshots=trap, leaf_returns=trap,
                                unwired_inputs=trap, reference_bindings=trap, literal_inputs=trap)
        self.assertEqual(pure['writes'], [])
        payload = inflight_acq_payload(); result = self.replay(ACQ_PATH, payload)
        self.assertEqual(result['pending_leaf_uids'], ['38132'])
        self.assertEqual(result['active_stage'], '38074')
        self.assertFalse(result['selected_body_completed'])
        payload['schedule'].append(dict(kind='stage_complete', uid='38074'))
        self.replay(ACQ_PATH, payload, 400)

    def test_sup_supplied_literal_selector_and_direct_error_reference_chains(self):
        for first in (False, True):
            payload = sup_payload(); payload['literal_inputs']['17326'] = first
            result = self.replay(SUP_PATH, payload)
            self.assertEqual(result['selected_case_frame'], '25142')
            self.assertIs(result['selector_literal_interpretation_is_hypothetical'], True)
            calls = {r['node_uid']: r['inputs'] for r in result['leaf_observations']}
            self.assertIs(calls['17431']['17465'], first)
            self.assertEqual(calls['17431']['17475'], 9600)
            self.assertEqual(calls['17431']['17478'], payload['literal_inputs']['17367'])
            for uid, face, producer, output in (
                ('17485','17519','17431','17440'), ('17485','17528','17431','17453'),
                ('17531','17558','17485','17491'), ('17531','17571','17485','17500'),
                ('17574','17614','17531','17534'), ('17574','17624','17531','17543'),
                ('17627','17654','17574','17577'), ('17627','17663','17574','17587'),
                ('28756','28794','17627','17630')):
                self.assertEqual(calls[uid][face], payload['native_boundaries'][producer]['outputs'][output])
            self.assertEqual(calls['17666'], {'17677': 50})
            self.assertEqual([(r['node_uid'], r['explicit_paramIdx'], r['value']) for r in result['local_assignments']],
                             [('34747', 90, payload['native_boundaries']['17531']['outputs']['17540']),
                              ('30337', 89, payload['native_boundaries']['17574']['outputs']['17584'])])
            self.assertFalse(result['native_callee_equivalence_qualified'])
            self.assertFalse(result['native_coercion_qualified'])

    def test_sup_u16_to_i32_supplied_integer_domains_and_storage_refusals(self):
        for value in (0, 65535):
            for returned in (-(2 ** 31), 2 ** 31 - 1):
                payload = sup_payload(); payload['local_reads']['31193'] = value
                payload['native_boundaries']['17531']['outputs']['17540'] = returned
                result = self.replay(SUP_PATH, payload)
                self.assertEqual(result['leaf_observations'][1]['inputs']['17525'], value)
                self.assertEqual(result['local_assignments'][0]['value'], returned)
        for value in (-1, 65536, True, 1.0):
            payload = sup_payload(); payload['local_reads']['31193'] = value
            self.replay(SUP_PATH, payload, 400)
        for value in (-(2 ** 31)-1, 2 ** 31, True, 1.0):
            payload = sup_payload(); payload['native_boundaries']['17531']['outputs']['17540'] = value
            self.replay(SUP_PATH, payload, 400)
        for uid, value in (('25668', 0), ('17326', 0), ('17367', {'bytes_hex': '00'})):
            payload = sup_payload(); payload['literal_inputs'][uid] = value
            self.replay(SUP_PATH, payload, 400)
            payload = sup_payload(); del payload['literal_inputs'][uid]
            self.replay(SUP_PATH, payload, 400)

    def test_sup_false_case_unused_event_returns_and_completion_reports(self):
        result = self.replay(SUP_PATH, minimal_sup_payload())
        self.assertEqual(result['selected_case_frame'], '25108')
        self.assertEqual(result['leaf_observations'], [])
        self.assertEqual(result['local_assignments'], [])
        trap = Tripwire()
        pure = sup.project_event_23880({'25668':False,'17326':trap,'17367':trap}, trap, trap, trap, trap)
        self.assertIs(pure['supplied_unused_event_outputs'], trap)
        payload = sup_payload(); payload['completed_sinks'] = ['28756', '17431', '30337']
        result = self.replay(SUP_PATH, payload)
        self.assertEqual(result['completed_sinks'], payload['completed_sinks'])
        self.assertFalse(result['completion_observations_are_feasible_trace'])
        self.assertFalse(result['completion_observations_prove_success'])
        for reports in (['17431','17431'], ['25142'], ['17668']):
            payload = sup_payload(); payload['completed_sinks'] = reports
            self.replay(SUP_PATH, payload, 400)
        payload = minimal_sup_payload(); payload['completed_sinks'] = ['17431']
        self.replay(SUP_PATH, payload, 400)

    def test_sup_byte_error_unwired_native_and_boundary_guard(self):
        for raw in ('', '00FF', 'AB' * 4096):
            payload = sup_payload(); payload['native_boundaries']['17574']['outputs']['17584'] = {'bytes_hex':raw}
            result = self.replay(SUP_PATH, payload)
            self.assertEqual(result['local_assignments'][1]['value'], {'bytes_hex':raw})
        for raw in ('0', 'ff', 'GG', 'AB' * 4097):
            payload = sup_payload(); payload['native_boundaries']['17574']['outputs']['17584'] = {'bytes_hex':raw}
            self.replay(SUP_PATH, payload, 400)
        for flag in sup.UNQUALIFIED_FLAGS:
            payload = sup_payload(); payload['unqualified_boundaries'][flag] = True
            self.replay(SUP_PATH, payload, 400)
        payload = sup_payload(); del payload['unwired_inputs']['17471']
        self.replay(SUP_PATH, payload, 400)
        payload = sup_payload(); payload['native_boundaries']['17431']['outputs']['17440']['status'] = 0
        self.replay(SUP_PATH, payload, 400)

    def test_exact_source_identity_no_execute_and_wrong_typed_snapshot(self):
        for path, factory in ((ACQ_PATH, acq_payload), (SUP_PATH, sup_payload)):
            for key in ('source_id','source_version','event_uid','frame_uid'):
                payload = factory(); payload[key] = 'wrong'
                self.replay(path, payload, 400)
            payload = factory(); payload['execute_native'] = True
            self.replay(path, payload, 400)
        payload = acq_payload(); payload['snapshots']['38118'][0] = 1
        self.replay(ACQ_PATH, payload, 400)

    def test_authentication_nonce_signature_and_path_binding(self):
        request = self.request(SUP_PATH, sup_payload())
        self.assertEqual(self.endpoint.dispatch(request)['status'], 200)
        self.assertEqual(self.endpoint.dispatch(request)['status'], 401)
        request = self.request(SUP_PATH, sup_payload()); request['path'] = ACQ_PATH
        self.assertEqual(self.endpoint.dispatch(request)['status'], 401)
        request = self.request(SUP_PATH, sup_payload()); request['signature'] = '0' * 64
        self.assertEqual(self.endpoint.dispatch(request)['status'], 401)

    def test_pure_allowed_opaque_refs_and_actual_signed_response_cap(self):
        payload = oversized_sup_payload()
        self.assertEqual(payload['literal_inputs'], sup_payload()['literal_inputs'])
        self.assertLessEqual(len(json_bytes(payload)), MAX_BYTES)
        result = sup.replay_saved_sup_event_23880(payload)
        body = dict(schema_version=1, execution_allowed=False, hardware_writes=False, physical_status='NOT_EXECUTED', result=result)
        self.assertGreater(len(json_bytes(body)), MAX_BYTES)
        refused = self.response(SUP_PATH, payload, 400)
        self.assertEqual(refused['error'], 'Supervision response exceeds 65536 bytes')
        self.assertFalse(refused['accepted'])
        payload = oversized_sup_payload(); payload['event_outputs'] = 'X' * 8192
        payload['native_boundaries']['17666']['outputs'] = ['X' * 8192] * 8
        with self.assertRaises(ValueError):
            self.endpoint.dispatch(self.request(SUP_PATH, payload))


if __name__ == '__main__':
    unittest.main()
