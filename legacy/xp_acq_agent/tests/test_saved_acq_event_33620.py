"""Independent expected values and source partial orders; Python3.4 stdlib."""
import copy
import itertools
import unittest
from elyse_agent import saved_acq_event_33620 as core


def fixture():
    # Different snapshots deliberately prevent an implicit shared-store model.
    snapshots = {
        '33741': tuple(i % 3 == 0 for i in range(32)),
        '33812': tuple(i % 3 == 1 for i in range(32)),
        '33958': tuple(i % 2 == 0 for i in range(29)),
        '34353': tuple(i % 5 == 0 for i in range(77)),
        '34030': tuple(i % 2 == 1 for i in range(29)),
    }
    error_in = core.ErrorValue(False, 31, 'supplied PSP input')
    error_out = core.ErrorValue(True, -72, 'supplied PSP output')
    returns = {
        '33755': {'33757': 4294967295},
        '34022': {'34024': 0},
        '34036': {'34041': object(), '34047': error_out},
        '34076': {'34079': True, '34082': -8, '34094': 'unused1',
            '34097': core.ErrorValue(True, 93, 'unused handler error'), '34100': 'unused2'},
    }
    defaults = {'34044': error_in, '34085': object(), '34088': -4,
                '34091': 'explicit unwired argument', '34103': 65535}
    binding = dict(constant_uid='34004', saved_uri='ni.var.psp://10.20.30.2/SUPERVISION/DPS', native_ref=object())
    return dict(snapshots=snapshots, leaf_returns=returns,
                unwired_inputs=defaults, reference_binding=binding)


def stages():
    # These expectations are literal source UID chains, not imported core maps.
    return (
        (core.Step('33741'), core.Step('33731'), core.Step('33723'), core.Step('33747'),
         core.LeafCall('33755'), core.LeafReturn('33755')),
        (core.Step('33812'), core.Step('33802'), core.Step('33796')),
        (core.Step('33958'), core.Step('33905'), core.Step('33891'),
         core.Step('34353'), core.Step('34337'), core.Step('34320')),
        (core.Step('34030'), core.LeafCall('34036'), core.LeafReturn('34036'),
         core.LeafCall('34076'), core.LeafReturn('34076'),
         core.LeafCall('34022'), core.LeafReturn('34022')),
    )


def full_schedule(parts=None):
    parts = stages() if parts is None else parts
    return tuple(token for part, frame in zip(parts, ('33697', '33780', '33828', '33986'))
                 for token in tuple(part) + (core.StageComplete(frame),))


def replay(schedule=None, data=None):
    return core.replay_event(True, full_schedule() if schedule is None else schedule,
                             **(fixture() if data is None else data))


def interleave(*chains):
    # Enumerate linear extensions of independently specified source chains.
    if not any(chains):
        yield ()
    for index, chain in enumerate(chains):
        if chain:
            rest = list(chains)
            rest[index] = chain[1:]
            for suffix in interleave(*rest):
                yield (chain[0],) + suffix


def expected_writes(snapshots):
    return {
        '33723': tuple(True if i == 2 else bit for i, bit in enumerate(snapshots['33741'])),
        '33747': True,
        '33796': tuple(False if i == 2 else bit for i, bit in enumerate(snapshots['33812'])),
        '33891': tuple(False if i == 12 else bit for i, bit in enumerate(snapshots['33958'])),
        '34320': tuple(False if i == 36 else bit for i, bit in enumerate(snapshots['34353'])),
    }


def json_payload():
    data = fixture()
    data['reference_binding']['native_ref'] = {'supplied_handle_representation': 17}
    data['unwired_inputs']['34085'] = {'opaque_void_argument': 'explicit'}
    data['leaf_returns']['34036']['34041'] = {'unused_ref_representation': 42}
    def j(value):
        if type(value) is core.ErrorValue:
            return dict(status=value.status, code=value.code, source=value.source)
        if type(value) is tuple:
            return list(value)
        if type(value) is dict:
            return {key: j(item) for key, item in value.items()}
        return value
    names = {core.Step: 'step', core.LeafCall: 'leaf_call',
             core.LeafReturn: 'leaf_return', core.StageComplete: 'stage_complete'}
    result = dict(source_id='APP-00', event_uid='43', frame_uid='33620', new_value=True,
        schedule=[dict(kind=names[type(t)], uid=t[0]) for t in full_schedule()])
    result.update(j(data))
    return result


class Poison(object):
    def __iter__(self):
        raise AssertionError('unselected input iterated')
    def __getitem__(self, key):
        raise AssertionError('unselected input read')
    def __len__(self):
        raise AssertionError('unselected input measured')


class SavedAcqEventTests(unittest.TestCase):
    def assert_complete(self, result, data):
        self.assertIs(result['selected_body_completed'], True)
        self.assertEqual(result['completed_stages'], ['33697', '33780', '33828', '33986'])
        self.assertEqual({row['node_uid']: row['value'] for row in result['writes']}, expected_writes(data['snapshots']))
        calls = {row['node_uid']: row['input_ports'] for row in result['leaf_calls']}
        self.assertEqual(calls['33755'], {'33760': 150})
        self.assertEqual(calls['34022'], {'34027': 100})
        self.assertIs(calls['34036']['34038'], data['reference_binding']['native_ref'])
        self.assertIs(calls['34036']['34044'], data['unwired_inputs']['34044'])
        self.assertIs(calls['34036']['34060'], data['snapshots']['34030'])
        self.assertIs(calls['34076']['34106'], data['leaf_returns']['34036']['34047'])
        self.assertIs(calls['34076']['34085'], data['unwired_inputs']['34085'])
        self.assertEqual(result['pending_leaf_uids'], ())
        self.assertEqual(result['remaining_node_uids'], ())
        self.assertEqual({row['node_uid'] for row in result['log'] if 'node_uid' in row},
            {'33636','33660','33686','33703','33713','33723','33731','33741','33747','33755',
             '33786','33796','33802','33812','33854','33891','33905','33958','33992','34004',
             '34022','34030','34036','34076','34128','34320','34337','34353','34361'})

    def test_complete_direct_body_and_identity(self):
        data = fixture()
        original_banks = dict(data['snapshots'])
        self.assert_complete(replay(data=data), data)
        self.assertEqual(data['snapshots'], original_banks)

    def test_false_arm_accesses_zero_body_inputs(self):
        result = core.replay_event(False, Poison(), snapshots=Poison(), leaf_returns=Poison(),
                                  unwired_inputs=Poison(), reference_binding=Poison())
        self.assertTrue(result['selected_body_completed'])
        self.assertEqual(result['selected_case_frame'], '33674')
        self.assertEqual(result['writes'], [])
        self.assertEqual(result['leaf_calls'], [])
        self.assertEqual([x['node_uid'] for x in result['log']], ['33636','34128','33660'])

    def test_false_json_body_values_are_unaccessed(self):
        data = json_payload()
        data['new_value'] = False
        for key in ('schedule','snapshots','leaf_returns','unwired_inputs','reference_binding'):
            data[key] = Poison()
        self.assertEqual(core.replay_saved_acq_event_33620(data)['writes'], [])

    def test_all_stage0_linear_extensions(self):
        rows = list(interleave(stages()[0][:3], (core.Step('33747'),), stages()[0][4:]))
        self.assertEqual(len(rows), 60)
        for row in rows:
            parts = list(stages()); parts[0] = row
            data = fixture(); self.assert_complete(replay(full_schedule(parts), data), data)

    def test_all_independent_reset_linear_extensions(self):
        rows = list(interleave(stages()[2][:3], stages()[2][3:]))
        self.assertEqual(len(rows), 20)
        for row in rows:
            parts = list(stages()); parts[2] = row
            data = fixture(); self.assert_complete(replay(full_schedule(parts), data), data)

    def test_all_publication_wait_linear_extensions(self):
        rows = list(interleave(stages()[3][:5], stages()[3][5:]))
        self.assertEqual(len(rows), 21)
        for row in rows:
            parts = list(stages()); parts[3] = row
            data = fixture(); self.assert_complete(replay(full_schedule(parts), data), data)

    def test_all_canonical_prefixes(self):
        schedule = full_schedule()
        for count in range(27):
            prefix = schedule[:count]
            result = replay(prefix)
            self.assertEqual(result['selected_body_completed'], count == 26)
            expected = [t.frame_uid for t in prefix if type(t) is core.StageComplete]
            self.assertEqual(result['completed_stages'], expected)
            pending = {t.node_uid for t in prefix if type(t) is core.LeafCall} - {
                t.node_uid for t in prefix if type(t) is core.LeafReturn}
            self.assertEqual(set(result['pending_leaf_uids']), pending)

    def test_prefix_does_not_read_future_values(self):
        data = dict(snapshots={'33741': (False,)*32, '33812': Poison()},
            leaf_returns=Poison(), unwired_inputs=Poison(), reference_binding=Poison())
        result = replay((core.Step('33741'), core.Step('33731')), data)
        self.assertEqual(result['writes'], [])
        data = json_payload(); data['schedule'] = []
        data['snapshots']['33741'] = Poison(); data['leaf_returns']['34036'] = Poison()
        data['reference_binding'] = Poison()
        self.assertEqual(core.replay_saved_acq_event_33620(data)['writes'], [])

    def test_single_hot_banks_all_fields_and_separate_publication(self):
        for uid, count in (('33741',32),('33812',32),('33958',29),('34353',77),('34030',29)):
            for index in range(count):
                data = fixture(); data['snapshots'][uid] = tuple(i == index for i in range(count))
                self.assert_complete(replay(data=data), data)

    def test_failed_leaf_outputs_do_not_gate_completion(self):
        data = fixture()
        data['leaf_returns']['34076']['34079'] = False
        data['leaf_returns']['34076']['34082'] = 2147483647
        data['leaf_returns']['34076']['34097'] = core.ErrorValue(True, -2147483648, 'failure supplied')
        self.assert_complete(replay(data=data), data)

    def test_every_unused_return_is_recorded_without_gating(self):
        data = fixture(); result = replay(data=data)
        for row in result['leaf_returns']:
            self.assertIs(row['output_ports'], data['leaf_returns'][row['node_uid']])
            self.assertEqual(row['consumed_output_ports'], ('34047',) if row['node_uid']=='34036' else ())

    def test_every_limit_remains_false(self):
        for new_value in (False, True):
            result = core.replay_event(new_value, (), **fixture())
            for key in ('execution_allowed','external_calls_executed','hardware_writes',
                'whole_event_equivalence','whole_vi_equivalence','native_runtime_equivalence',
                'native_default_qualified','native_ref_interpretation_qualified','psp_delivery_qualified',
                'wait_units_or_pulse_duration_qualified','snapshot_equality_qualified',
                'scheduler_qualified','event_selection_qualified','event_acknowledgement_qualified',
                'native_cluster_decode_qualified'):
                self.assertIs(result[key], False)

    def test_bad_newval_and_schedule_refuse(self):
        for value in (0, 1, None, 'True'):
            self.assertRaises(TypeError, core.replay_event, value, (), **fixture())
        for schedule in ([], (core.Step('33741'),)*27):
            self.assertRaises(ValueError, replay, schedule)
        for token in (object(), core.Step(33741)):
            self.assertRaises(TypeError, replay, (token,))

    def test_unknown_wrong_stage_early_dependency_refuse(self):
        for token in (core.Step('999'), core.Step('33812'), core.Step('33731'), core.Step('33723'),
                      core.LeafCall('34022'), core.LeafReturn('33755'), core.StageComplete('33697'),
                      core.StageComplete('0')):
            self.assertRaises(ValueError, replay, (token,))

    def test_duplicate_node_call_return_refuse(self):
        for prefix in ((core.Step('33741'),)*2,
            (core.LeafCall('33755'),)*2,
            (core.LeafCall('33755'),core.LeafReturn('33755'),core.LeafReturn('33755'))):
            self.assertRaises(ValueError, replay, prefix)

    def test_stage_join_requires_wait_completion(self):
        self.assertRaises(ValueError, replay, stages()[0][:-1]+(core.StageComplete('33697'),))

    def test_handler_requires_wired_psp_return(self):
        schedule = full_schedule()[:18] + (core.Step('34030'),core.LeafCall('34036'),core.LeafCall('34076'))
        self.assertRaises(ValueError, replay, schedule)

    def test_bank_domain_refusals(self):
        for value in ([False]*32, (False,)*31, (False,)*33, (False,)*31+(0,), None):
            data = fixture(); data['snapshots']['33741'] = value
            self.assertRaises(TypeError, replay, (core.Step('33741'),), data)
        data = fixture(); del data['snapshots']['33741']
        self.assertRaises(ValueError, replay, (core.Step('33741'),), data)

    def test_leaf_output_and_error_domain_refusals(self):
        for value in ({}, {'33757':True}, {'33757':-1}, {'33757':4294967296}, {'33757':0,'extra':0}):
            data=fixture();data['leaf_returns']['33755']=value
            self.assertRaises((TypeError,ValueError),replay,(core.LeafCall('33755'),core.LeafReturn('33755')),data)
        for value in (core.ErrorValue(1,0,''),core.ErrorValue(False,True,''),
                      core.ErrorValue(False,2147483648,''),core.ErrorValue(False,0,None)):
            data=fixture();data['leaf_returns']['34036']['34047']=value
            self.assertRaises(TypeError,replay,None,data)

    def test_explicit_unwired_and_ref_binding_required(self):
        for key in ('34044','34085','34088','34091','34103'):
            data=fixture();del data['unwired_inputs'][key]
            self.assertRaises(ValueError,replay,None,data)
        for key in ('constant_uid','saved_uri','native_ref'):
            data=fixture();del data['reference_binding'][key]
            self.assertRaises(ValueError,replay,None,data)
        for key,value in (('constant_uid','34005'),('saved_uri','different')):
            data=fixture();data['reference_binding'][key]=value
            self.assertRaises(ValueError,replay,None,data)
        for key,value in (('34088',True),('34103',65536),('34091',None)):
            data=fixture();data['unwired_inputs'][key]=value
            self.assertRaises(TypeError,replay,None,data)

    def test_json_complete_and_input_unchanged(self):
        data=json_payload();before=copy.deepcopy(data)
        result=core.replay_saved_acq_event_33620(data)
        self.assertTrue(result['selected_body_completed'])
        self.assertEqual(data,before)
        calls={r['node_uid']:r['input_ports'] for r in result['leaf_calls']}
        self.assertEqual(calls['34036']['34060'],data['snapshots']['34030'])
        self.assertEqual(calls['34076']['34106'],data['leaf_returns']['34036']['34047'])

    def test_json_schema_and_source_identity_refusals(self):
        for key,value in (('source_id','APP-17'),('event_uid','33620'),('frame_uid','11'),('new_value',1)):
            data=json_payload();data[key]=value
            self.assertRaises((ValueError,TypeError),core.replay_saved_acq_event_33620,data)
        for change in ('missing','extra','token_extra','token_unknown','unknown_snapshot','snapshot_tuple'):
            data=json_payload()
            if change=='missing':del data['new_value']
            elif change=='extra':data['extra']=True
            elif change=='token_extra':data['schedule'][0]['extra']=0
            elif change=='token_unknown':data['schedule'][0]['kind']='callback'
            elif change=='unknown_snapshot':data['snapshots']['21731']=[]
            else:data['snapshots']['33741']=tuple(data['snapshots']['33741'])
            self.assertRaises((ValueError,TypeError),core.replay_saved_acq_event_33620,data)

    def test_json_native_representation_refusals(self):
        for value in (float('nan'),float('inf'),object(),{1:'bad-key'}):
            data=json_payload();data['reference_binding']['native_ref']=value
            self.assertRaises((ValueError,TypeError),core.replay_saved_acq_event_33620,data)
        data=json_payload();data['leaf_returns']['34036']['34047']['extra']=0
        self.assertRaises(ValueError,core.replay_saved_acq_event_33620,data)


if __name__ == '__main__':
    unittest.main()
