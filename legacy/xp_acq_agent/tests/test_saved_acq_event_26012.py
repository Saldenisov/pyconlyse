"""Independent bounded saved APP00/frame26012 expectations, Python3.4."""
import copy
import importlib.machinery
import itertools
import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE = os.path.join(ROOT, 'elyse_agent', 'saved_acq_event_26012.py')
m = importlib.machinery.SourceFileLoader('qualified_acq26012', CORE).load_module()
COUNTS = dict(core_calls=0, accepted=0, refused=0, completed_true=0, prefixes=0,
              false=0, adapter_calls=0, adapter_accepted=0, adapter_refused=0)


def fixture():
    snapshots = {'26290': tuple(i % 3 == 0 for i in range(32)),
        '26900': tuple(i % 3 == 1 for i in range(32)),
        '27807': tuple(i % 2 == 0 for i in range(29)),
        '27587': tuple(i % 3 == 2 for i in range(77)),
        '28294': tuple(i % 3 == 0 for i in range(29))}
    pin = m.ErrorValue(False, 0, 'supplied input')
    perr = m.ErrorValue(True, -7, 'supplied PSP error')
    herr = m.ErrorValue(True, 6, 'supplied handler error')
    ref, returned_ref, opaque = object(), object(), object()
    returns = {'26304': {'26306': 41}, '28273': {'28276': 99},
        '28312': {'28328': returned_ref, '28346': perr},
        '28364': {'28373': False, '28382': 6, '28418': 'handler output',
                  '28427': herr, '28436': 'details'}}
    unwired = {'28337': pin, '28391': opaque, '28400': 0,
               '28409': 'supplied message', '28445': 1}
    return dict(snapshots=snapshots, leaf_returns=returns, unwired_inputs=unwired,
                reference_binding={'constant_uid': '27965',
                    'saved_uri': 'ni.var.psp://10.20.30.2/SUPERVISION/DPS', 'native_ref': ref})


def schedule():
    return (m.Step('26290'), m.Step('26280'), m.Step('26272'), m.Step('26296'),
        m.LeafCall('26304'), m.LeafReturn('26304'), m.StageComplete('26246'),
        m.Step('26900'), m.Step('26577'), m.Step('26356'), m.StageComplete('26330'),
        m.Step('27807'), m.Step('27650'), m.Step('27605'), m.Step('27587'),
        m.Step('27544'), m.Step('27523'), m.StageComplete('26962'),
        m.Step('28294'), m.LeafCall('28312'), m.LeafReturn('28312'),
        m.LeafCall('28364'), m.LeafReturn('28364'), m.LeafCall('28273'),
        m.LeafReturn('28273'), m.StageComplete('27900'))


def core(value=True, tokens=None, data=None):
    COUNTS['core_calls'] += 1
    try:
        result = m.replay_event(value, schedule() if tokens is None else tokens,
                                **(fixture() if data is None else data))
    except (ValueError, TypeError):
        COUNTS['refused'] += 1
        raise
    COUNTS['accepted'] += 1
    COUNTS['false' if not value else ('completed_true' if result['selected_body_completed'] else 'prefixes')] += 1
    return result


def payload():
    f = fixture()
    x = dict(source_id='APP-00', event_uid='43', frame_uid='26012', new_value=True,
        schedule=[dict(kind={m.Step:'step',m.LeafCall:'leaf_call',m.LeafReturn:'leaf_return',
            m.StageComplete:'stage_complete'}[type(t)], uid=t.frame_uid if type(t) is m.StageComplete else t.node_uid)
            for t in schedule()], snapshots={u:list(v) for u,v in f['snapshots'].items()},
        leaf_returns=copy.deepcopy(f['leaf_returns']), unwired_inputs=dict(f['unwired_inputs']),
        reference_binding=dict(f['reference_binding']))
    x['reference_binding']['native_ref'] = {'opaque':'provided'}
    x['leaf_returns']['28312']['28328'] = {'opaque':'returned'}
    x['unwired_inputs']['28391'] = {'opaque':'Void'}
    for maps, uid, terminal in [(x['leaf_returns'],'28312','28346'),(x['leaf_returns'],'28364','28427')]:
        maps[uid][terminal] = dict(maps[uid][terminal]._asdict())
    x['unwired_inputs']['28337'] = dict(x['unwired_inputs']['28337']._asdict())
    return x


def adapter(x):
    COUNTS['adapter_calls'] += 1
    try:
        result = m.replay_saved_acq_event_26012(x)
    except (ValueError,TypeError):
        COUNTS['adapter_refused'] += 1
        raise
    COUNTS['adapter_accepted'] += 1
    return result


class Poison:
    def __iter__(self): raise AssertionError('unselected body input accessed')
    def __getitem__(self,key): raise AssertionError('unselected body input accessed')
    def __len__(self): raise AssertionError('unselected body input accessed')


class SavedAcq26012Tests(unittest.TestCase):
    def expect_writes(self, result, snapshots):
        # Independent source values; do not derive expected fields from core plans.
        expected = {}
        a=list(snapshots['26290']);a[6]=False;expected['26272']=tuple(a)
        expected['26296']=True
        a=list(snapshots['26900']);a[6]=True;expected['26356']=tuple(a)
        a=list(snapshots['27807']);a[7]=False;expected['27605']=tuple(a)
        a=list(snapshots['27587']);a[20]=False;a[21]=False;a[23]=True;expected['27523']=tuple(a)
        self.assertEqual({r['node_uid']:r['value'] for r in result['writes']},expected)

    def test_full_body_independent_source_assignments(self):
        f=fixture();r=core(data=f);self.expect_writes(r,f['snapshots'])
        self.assertEqual(r['completed_stages'],['26246','26330','26962','27900'])
        self.assertTrue(r['selected_body_completed']);self.assertEqual(r['pending_leaf_uids'],())
        self.assertEqual(r['source_version'],'57E1B106EEB57D70124D21CC3FEE775BCADFBF47081F02ED9335A28BAFBC9DD5')
        self.assertEqual(r['event_data_unconsumed_input_ports'],('26088',))
        self.assertEqual(r['event_data_unconsumed_ports'],('26096','26100','26109','26118'))

    def test_every_individual_snapshot_field(self):
        for uid,count in [('26290',32),('26900',32),('27807',29),('27587',77),('28294',29)]:
            for index in range(count):
                f=fixture();v=[False]*count;v[index]=True;f['snapshots'][uid]=tuple(v)
                r=core(data=f);self.expect_writes(r,f['snapshots'])
                p=next(x for x in r['leaf_calls'] if x['node_uid']=='28312')
                self.assertIs(p['input_ports']['28355'],f['snapshots']['28294'])

    def test_all_within_stage_partial_orders(self):
        base=schedule();observed=[]
        for start,end,chains in [(0,6,[(0,1,2),(4,5)]),(11,17,[(0,1,2),(3,4,5)]),
                                 (18,25,[(0,1,2,3,4),(5,6)])]:
            count=0
            for permutation in itertools.permutations(range(end-start)):
                positions={v:i for i,v in enumerate(permutation)}
                if any(any(positions[a]>=positions[b] for a,b in zip(chain,chain[1:])) for chain in chains):continue
                tokens=base[:start]+tuple(base[start+i] for i in permutation)+base[end:]
                f=fixture();r=core(tokens=tokens,data=f);self.expect_writes(r,f['snapshots']);count+=1
            observed.append(count)
        self.assertEqual(observed,[60,20,21])

    def test_all_canonical_prefixes(self):
        for length in range(27):
            r=core(tokens=schedule()[:length])
            self.assertEqual(r['selected_body_completed'],length==26)
            self.assertEqual(len(r['completed_stages']),sum(i<length for i in [6,10,17,25]))

    def test_inflight_native_leaf_not_invented(self):
        r=core(tokens=schedule()[:5]);self.assertEqual(r['pending_leaf_uids'],('26304',))
        self.assertEqual(r['leaf_returns'],[]);self.assertEqual(r['completed_stages'],[])
        self.assertFalse(r['schedule_complete'])

    def test_false_zero_body_access(self):
        for input_ in [Poison(),None,{'unexpected':object()}]:
            r=core(False,tokens=input_,data=dict(snapshots=input_,leaf_returns=input_,
                unwired_inputs=input_,reference_binding=input_))
            self.assertEqual(r['writes'],[]);self.assertEqual(r['leaf_calls'],[])
            self.assertEqual(r['selected_case_frame'],'26217')

    def test_ref_error_and_opaque_input_identity(self):
        f=fixture();r=core(data=f);calls={x['node_uid']:x for x in r['leaf_calls']}
        self.assertIs(calls['28312']['input_ports']['28319'],f['reference_binding']['native_ref'])
        self.assertIs(calls['28312']['input_ports']['28337'],f['unwired_inputs']['28337'])
        self.assertIs(calls['28364']['input_ports']['28454'],f['leaf_returns']['28312']['28346'])
        self.assertIs(calls['28364']['input_ports']['28391'],f['unwired_inputs']['28391'])
        self.assertIs(next(x for x in r['leaf_returns'] if x['node_uid']=='28312')['output_ports']['28328'],f['leaf_returns']['28312']['28328'])

    def test_errors_do_not_gate_sequence_completion(self):
        for error in [m.ErrorValue(False,0,''),m.ErrorValue(True,-2147483648,'fault'),m.ErrorValue(False,2147483647,'warning')]:
            f=fixture();f['leaf_returns']['28312']['28346']=error;r=core(data=f)
            self.assertTrue(r['selected_body_completed'])
            self.assertIs(next(c for c in r['leaf_calls'] if c['node_uid']=='28364')['input_ports']['28454'],error)

    def test_constants_fields_and_saved_reference_args(self):
        r=core();calls={x['node_uid']:x for x in r['leaf_calls']}
        self.assertEqual(calls['26304']['input_ports'],{'26309':150})
        self.assertEqual(calls['28273']['input_ports'],{'28285':100})
        eps=next(x for x in r['log'] if x.get('node_uid')=='27544' and x['kind']=='bundle')
        self.assertEqual([(x['terminal_uid'],x['field_index'],x['value'],x['constant_uid']) for x in eps['assignments']],
                         [('27568',20,False,'26980'),('27577',23,True,'27089'),('47743',21,False,'26980')])

    def test_empty_true_does_not_consume_future_values(self):
        r=core(tokens=(),data=dict(snapshots=Poison(),leaf_returns=Poison(),unwired_inputs=Poison(),reference_binding=Poison()))
        self.assertEqual(r['active_stage'],'26246');self.assertEqual(r['writes'],[])

    def test_snapshot_domains_refuse(self):
        for bad in [None,[False]*32,tuple([False]*31),tuple([False]*33),tuple([0]*32),tuple([True]*31+[1])]:
            f=fixture();f['snapshots']['26290']=bad
            with self.assertRaises((TypeError,ValueError)):core(data=f)

    def test_boolean_event_and_token_domains_refuse(self):
        for bad in [0,1,None,'True']:
            with self.assertRaises(TypeError):core(value=bad)
        for tokens in [list(schedule()),(object(),),(m.Step(26290),),(m.Step('unknown'),),schedule()+(m.Step('26290'),)]:
            with self.assertRaises((TypeError,ValueError)):core(tokens=tokens)

    def test_saved_dependencies_refuse(self):
        for tokens in [(m.Step('26280'),),(m.Step('26272'),),(m.Step('26900'),),
                       (m.LeafReturn('26304'),),(m.StageComplete('26246'),),
                       schedule()[:5]+(m.StageComplete('26246'),),
                       schedule()[:18]+(m.LeafCall('28312'),),
                       schedule()[:20]+(m.LeafCall('28364'),),
                       (m.Step('26290'),m.Step('26290')),
                       (m.LeafCall('26304'),m.LeafCall('26304'))]:
            with self.assertRaises(ValueError):core(tokens=tokens)

    def test_reference_and_unwired_domain_refusals(self):
        for modify in [lambda f:f.update(reference_binding=None),
            lambda f:f['reference_binding'].update(constant_uid='34004'),
            lambda f:f['reference_binding'].update(saved_uri='other'),
            lambda f:f['unwired_inputs'].pop('28337'),
            lambda f:f['unwired_inputs'].update(**{'28400':True}),
            lambda f:f['unwired_inputs'].update(**{'28445':65536}),
            lambda f:f['unwired_inputs'].update(**{'28409':None})]:
            f=fixture();modify(f)
            with self.assertRaises((ValueError,TypeError)):core(data=f)

    def test_native_return_domains_refuse(self):
        for uid,port,bad in [('26304','26306',-1),('28273','28276',True),
                            ('28312','28346',{'status':False,'code':0,'source':''}),
                            ('28364','28382',2147483648),('28364','28373',0)]:
            f=fixture();f['leaf_returns'][uid][port]=bad
            with self.assertRaises((ValueError,TypeError)):core(data=f)

    def test_json_full_false_inflight(self):
        x=payload();r=adapter(x);self.assertTrue(r['selected_body_completed'])
        self.assertEqual(r['writes'][0]['value'][6],False)
        self.assertEqual(r['writes'][2]['value'][6],True)
        x=payload();x.update(new_value=False,schedule=Poison(),snapshots=Poison(),
            leaf_returns=Poison(),unwired_inputs=Poison(),reference_binding=Poison())
        self.assertEqual(adapter(x)['leaf_calls'],[])
        x=payload();x['schedule']=x['schedule'][:5];self.assertEqual(adapter(x)['pending_leaf_uids'],['26304'])

    def test_json_strict_envelope_refuses(self):
        for modify in [lambda x:x.update(extra=0),lambda x:x.pop('snapshots'),
            lambda x:x.update(source_id='APP-02'),lambda x:x.update(frame_uid='33620'),
            lambda x:x.update(new_value=1),lambda x:x['schedule'][0].update(kind='callback'),
            lambda x:x['schedule'][0].update(extra=0),lambda x:x['snapshots'].update(unknown=[]),
            lambda x:x['snapshots'].update(**{'26290':[1]*32}),
            lambda x:x['reference_binding'].update(native_ref=float('nan')),
            lambda x:x['reference_binding'].update(native_ref=object()),
            lambda x:x['unwired_inputs'].update(**{'28391':float('inf')})]:
            x=payload();modify(x)
            with self.assertRaises((ValueError,TypeError)):adapter(x)

    def test_all_native_and_whole_claims_false(self):
        r=core()
        for key in ['execution_allowed','external_calls_executed','hardware_writes','native_runtime_equivalence',
            'whole_event_equivalence','whole_vi_equivalence','native_default_qualified',
            'native_ref_interpretation_qualified','psp_delivery_qualified',
            'wait_units_or_pulse_duration_qualified','snapshot_equality_qualified','scheduler_qualified',
            'event_selection_qualified','event_acknowledgement_qualified','native_cluster_decode_qualified']:
            self.assertIs(r[key],False)


if __name__=='__main__':
    unittest.main()
