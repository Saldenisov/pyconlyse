"""G77 current signed stateless routes; supplied data never proves native execution."""
import copy
import time
import unittest
import uuid
from elyse_agent.supervision_rpc import SupervisionEndpoint
from elyse_agent.supervision_wire import MAX_BYTES, json_bytes, request_mac, response_mac
from elyse_agent import saved_acq_event_40079 as acq, saved_sup_event_53656 as sup
from sixteenth_next_event_fixtures import (
    acq_payload, false_acq_payload, inflight_acq_payload,
    sup_payload, minimal_sup_payload, sparse_sup_payload, oversized_sup_payload)

ACQ_PATH = '/v1/replay/acquisition-event-40079'
SUP_PATH = '/v1/replay/supervision-event-53656'
CONTRACT_NAME = 'saved_sixteenth_next_event_slices_contract.json'
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
    expected = {('APP-00', '43', '40079', 'saved_acq_event_40079.py'): acq.SOURCE_VERSION,
                ('APP-17', '5909', '53656', 'saved_sup_event_53656.py'): sup.SOURCE_VERSION}
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
    names = ('check_saved_sixteenth_next_event_slices_contract', '_check_saved_event_slices_contract')
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


class SavedSixteenthNextEventsRpcTests(unittest.TestCase):
    def setUp(self):
        self.key = b'G77-software-only-current-source-key'
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
            (ACQ_PATH, acq_payload, acq.replay_saved_acq_event_40079),
            (ACQ_PATH, false_acq_payload, acq.replay_saved_acq_event_40079),
            (ACQ_PATH, inflight_acq_payload, acq.replay_saved_acq_event_40079),
            (SUP_PATH, sup_payload, sup.replay_saved_sup_event_53656),
            (SUP_PATH, minimal_sup_payload, sup.replay_saved_sup_event_53656),
            (SUP_PATH, sparse_sup_payload, sup.replay_saved_sup_event_53656)):
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
                         {('APP-00', '43', '40079'), ('APP-17', '5909', '53656')})
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

    def test_acq_hierarchical_source_phases_and_independent_publication_read(self):
        p = acq_payload(); result = self.replay(ACQ_PATH, p)
        writes = {row['node_uid']: row['value'] for row in result['writes']}
        expected = {}
        for uid, read, fields in (('40188', '40206', {7: True}), ('40261', '40277', {7: False}),
                ('40339', '40355', {2: True}), ('40399', '40415', {2: False}),
                ('40499', '40520', {35: False, 32: True, 30: False}), ('40526', '40544', {10: False})):
            carrier = list(p['snapshots'][read])
            for index, value in fields.items(): carrier[index] = value
            expected[uid] = carrier
        expected['40212'] = True
        self.assertEqual(writes, expected)
        self.assertEqual(result['completed_stages'], ['40162', '40245', '46840', '48404', '49054', '40293', '40323', '40383', '40432', '40463', '40573'])
        self.assertEqual(result['completed_main_stages'], ['40162', '40245', '40293', '40323', '40383', '40432', '40463', '40573'])
        self.assertEqual(result['completed_nested_stages'], ['46840', '48404', '49054'])
        calls = {row['node_uid']: row['input_ports'] for row in result['leaf_calls']}
        self.assertEqual(calls['40623']['40637'], p['snapshots']['40617'])
        self.assertNotEqual(calls['40623']['40637'], writes['40526'])
        self.assertEqual(calls['40640']['40670'], p['leaf_returns']['40623']['40634'])
        self.assertEqual(calls['50796']['50912'], p['leaf_returns']['38600']['45219'])
        self.assertEqual(calls['38600'], {uid: p['unwired_inputs'][uid] for uid in ('45228', '45233', '45236', '45240', '45243', '45247')})
        for uid, ports in (('40220', {'40225': 150}), ('40311', {'40316': 29000}),
                ('50176', {'50185': 1500}), ('40361', {'40366': 150}), ('40451', {'40456': 250}), ('40609', {'40614': 100})):
            self.assertEqual(calls[uid], ports)
        self.assertEqual(calls['40623']['40625'], p['reference_bindings']['40591']['native_ref'])
        self.assertEqual(result['event_data_consumed_ports'], ['40114'])
        self.assertTrue(result['selected_body_completed'])
        for flag in ('scheduler_qualified', 'native_callee_equivalence', 'native_literal_serializer_qualified'):
            self.assertIs(result[flag], False)

    def test_acq_four_exact_false_literal_hypotheses_and_eleven_keys(self):
        self.assertEqual(acq_payload()['literal_inputs'], dict.fromkeys(('40251', '40389', '40469', '40489'), False))
        for uid in ('40251', '40389', '40469', '40489'):
            for value in (True, 0, None, 'False', 0.0):
                p = acq_payload(); p['literal_inputs'][uid] = value; self.replay(ACQ_PATH, p, 400)
            p = acq_payload(); del p['literal_inputs'][uid]; self.replay(ACQ_PATH, p, 400)
        p = acq_payload(); p['field_index_bindings'] = {}; self.replay(ACQ_PATH, p, 400)
        p = acq_payload(); p['reference_bindings']['40591']['saved_uri'] += '/other'; self.replay(ACQ_PATH, p, 400)
        p = acq_payload(); p['leaf_returns']['38600']['45219']['status'] = 0; self.replay(ACQ_PATH, p, 400)
        p = acq_payload(); p['unwired_inputs']['50904'] = 65536; self.replay(ACQ_PATH, p, 400)

    def test_acq_false_and_nested_inflight_dependency_boundaries(self):
        result = self.replay(ACQ_PATH, false_acq_payload())
        self.assertEqual(result['selected_case_frame'], '40135')
        self.assertEqual(result['writes'], []); self.assertEqual(result['leaf_calls'], [])
        p = inflight_acq_payload(); result = self.replay(ACQ_PATH, p)
        self.assertEqual(result['pending_leaf_uids'], ['38600'])
        self.assertEqual(result['active_stage'], '48404')
        self.assertEqual(result['completed_main_stages'], ['40162', '40245'])
        self.assertEqual(result['completed_nested_stages'], ['46840'])
        self.assertIs(result['selected_body_completed'], False)
        p['schedule'].append(dict(kind='stage_complete', uid='48404')); self.replay(ACQ_PATH, p, 400)
        p = acq_payload(); p['schedule'][0] = dict(kind='step', uid='40202'); self.replay(ACQ_PATH, p, 400)

    def test_sup_u16_two_nonempty_source_arms_and_independent_field_copies(self):
        arm_rows = (
            (sup_payload, '76439', '77973', ['77981', '81258', '85997'], 22,
             (('53890', '53881', '53908', '53934', '79753', '54139', '53910', '54213', '70702', '53930'),
              ('86012', '86004', '86028', '86042', '86078', '86088', '86030', '86045', '86075', '86039')), '81888', '81908'),
            (sparse_sup_payload, '56504', '56518', ['56523', '56742', '56785'], 26,
             (('56568', '56560', '56584', '56647', '56550', '56529', '56586', '56650', '56706', '56644'),
              ('56833', '56827', '56849', '56867', '56817', '56792', '56851', '56870', '56900', '56864')), '56768', '56779'))
        for factory, frame, sequence, diagrams, field, pairs, wait, wait_port in arm_rows:
            p = factory(); result = self.replay(SUP_PATH, p)
            self.assertEqual(result['source_case_uid'], '76431')
            self.assertEqual(result['source_selector_terminal_uid'], '76455')
            self.assertEqual(result['source_NewVal_terminal_uid'], '53859')
            self.assertEqual(result['selected_case_frame'], frame)
            self.assertEqual(result['sequence_uid'], sequence)
            self.assertEqual(result['source_sequence_actual_diagram_uids'], diagrams)
            calls = {row['node_uid']: row for row in result['leaf_observations']}
            self.assertEqual(len(result['local_assignments']), 2)
            self.assertEqual([row['sequence_phase'] for row in result['leaf_observations']], [0, 0, 1, 2, 2])
            for index, (read, write, writer, data, literal, ref, refport, handler, errorport, errorout) in enumerate(pairs):
                expected = list(p['local_reads'][read]); expected[field] = p['literal_inputs'][literal]
                self.assertEqual(result['local_assignments'][index]['node_uid'], write)
                self.assertEqual(result['local_assignments'][index]['value'], expected)
                self.assertEqual(calls[writer]['inputs'][data], expected)
                self.assertEqual(calls[writer]['inputs'][refport], p['reference_bindings'][ref]['native_reference'])
                self.assertEqual(calls[handler]['inputs'][errorport], p['native_boundaries'][writer]['outputs'][errorout])
                self.assertEqual(result['field_updates'][index]['raw_flattened_field_index'], field)
                self.assertEqual(result['field_updates'][index]['typed_position_path'], [field])
                self.assertEqual(result['local_assignments'][index]['explicit_paramIdx'], 26)
                self.assertEqual(result['local_assignments'][index]['control_terminal_uid'], '66821')
            self.assertNotEqual(result['local_assignments'][0]['value'], result['local_assignments'][1]['value'])
            self.assertEqual(calls[wait]['inputs'], {wait_port: 1000})
            self.assertIs(result['native_field_index_selection_qualified'], False)
            self.assertIs(result['native_default_policy_qualified'], False)
        result = self.replay(SUP_PATH, minimal_sup_payload())
        self.assertEqual(result['selected_case_frame'], '76439')
        self.assertEqual(len(result['leaf_observations']), 5)
        self.assertEqual(len(result['local_assignments']), 2)

    def test_sup_hypothetical_bool_literals_reports_and_inactive_json_nonaccess(self):
        for first in (False, True):
            for last in (False, True):
                p = sup_payload(); p['literal_inputs'] = {'79753': first, '86078': last}
                p['completed_sinks'] = ['86045', '53881']
                # Known inactive keys carry inert wrong-domain values without source access.
                p['local_reads'].update({'56568': 'inactive', '56833': None})
                p['literal_inputs'].update({'56550': None, '56817': 'inactive'})
                p['reference_bindings'].update({'56529': None, '56792': 'inactive'})
                p['native_boundaries'].update({uid: None for uid in ('56584', '56650', '56768', '56849', '56870')})
                result = self.replay(SUP_PATH, p)
                self.assertEqual([row['value'][22] for row in result['local_assignments']], [first, last])
                self.assertEqual([row['node_uid'] for row in result['local_reads']], ['53890', '86012'])
                self.assertEqual(result['completed_sinks'], p['completed_sinks'])
                self.assertIs(result['completion_observations_are_feasible_trace'], False)
                self.assertIs(result['completion_observations_prove_success'], False)

    def test_sup_strict_u16_carrier_literal_error_reference_boundary_refusals(self):
        for value in (False, True, -1, 2, 65535, 65536, 0.0, None, '0'):
            p = sup_payload(); p['new_value'] = value; self.replay(SUP_PATH, p, 400)
        for uid in ('53890', '86012'):
            for value in ([False] * 39, [False] * 41, [0] * 40):
                p = sup_payload(); p['local_reads'][uid] = value; self.replay(SUP_PATH, p, 400)
        for uid in ('79753', '86078'):
            p = sup_payload(); p['literal_inputs'][uid] = 0; self.replay(SUP_PATH, p, 400)
            p = sup_payload(); del p['literal_inputs'][uid]; self.replay(SUP_PATH, p, 400)
        p = sup_payload(); p['reference_bindings']['54139']['stored_URI_bytes']['bytes_hex'] += '00'; self.replay(SUP_PATH, p, 400)
        p = sup_payload(); p['native_boundaries']['53908']['outputs']['53930']['status'] = 0; self.replay(SUP_PATH, p, 400)
        p = sup_payload(); p['native_boundaries']['86028']['outputs']['86039']['code'] = 2**31; self.replay(SUP_PATH, p, 400)
        p = sup_payload(); del p['unwired_inputs']['53918']; self.replay(SUP_PATH, p, 400)
        p = sup_payload(); p['unwired_inputs']['70699'] = 65536; self.replay(SUP_PATH, p, 400)
        for report in (['53908', '53908'], ['63056'], ['56584']):
            p = sup_payload(); p['completed_sinks'] = report; self.replay(SUP_PATH, p, 400)
        for flag in sup_payload()['unqualified_boundaries']:
            p = sup_payload(); p['unqualified_boundaries'][flag] = True; self.replay(SUP_PATH, p, 400)
        p = sup_payload(); p['unwired_inputs']['70685'] = {'bytes_hex': '00FF'}
        self.assertEqual(self.replay(SUP_PATH, p)['leaf_observations'][1]['inputs']['70685'], {'bytes_hex': '00FF'})
        p['unwired_inputs']['70685'] = {'bytes_hex': 'ff'}; self.replay(SUP_PATH, p, 400)

    def test_exact_source_identity_and_no_execution_extension(self):
        for path, factory in ((ACQ_PATH, acq_payload), (SUP_PATH, sup_payload)):
            for key in ('source_id', 'source_version', 'event_uid', 'frame_uid'):
                p = factory(); p[key] = 'wrong'; self.replay(path, p, 400)
            p = factory(); p['execute_native'] = True; self.replay(path, p, 400)
        p = acq_payload(); p['snapshots']['40206'][0] = 1; self.replay(ACQ_PATH, p, 400)

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
        result = sup.replay_saved_sup_event_53656(p)
        body = dict(schema_version=1, execution_allowed=False, hardware_writes=False, physical_status='NOT_EXECUTED', result=result)
        self.assertGreater(len(json_bytes(body)), MAX_BYTES)
        refused = self.response(SUP_PATH, p, 400)
        self.assertEqual(refused['error'], 'Supervision response exceeds 65536 bytes')
        self.assertIs(refused['accepted'], False)
        p['event_outputs'] = 'X' * 8192
        p['native_boundaries']['81888']['outputs'] = ['X' * 8192] * 8
        with self.assertRaises(ValueError): self.endpoint.dispatch(self.request(SUP_PATH, p))


if __name__ == '__main__': unittest.main()
