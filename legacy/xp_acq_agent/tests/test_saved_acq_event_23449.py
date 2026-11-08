"""Independent bounded saved APP00/frame23449 expectations, Python3.4."""
import copy
import importlib.machinery
import itertools
import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE = os.path.join(ROOT, 'elyse_agent', 'saved_acq_event_23449.py')
m = importlib.machinery.SourceFileLoader('qualified_acq23449', CORE).load_module()
COUNTS = dict(core_calls=0, accepted=0, refused=0, completed_true=0, prefixes=0,
              false=0, adapter_calls=0, adapter_accepted=0, adapter_refused=0)


def fixture():
    snapshots = {'31100': tuple(i % 3 == 0 for i in range(32)),
        '31258': tuple(i % 3 == 1 for i in range(32)),
        '31454': tuple(i % 2 == 0 for i in range(29)),
        '31423': tuple(i % 3 == 2 for i in range(77)),
        '31526': tuple(i % 3 == 0 for i in range(29))}
    pin = m.ErrorValue(False, 0, 'supplied input')
    perr = m.ErrorValue(True, -7, 'supplied PSP error')
    herr = m.ErrorValue(True, 6, 'supplied handler error')
    ref, returned_ref, opaque = object(), object(), object()
    returns = {'31114': {'31116': 41}, '31518': {'31520': 99},
        '31532': {'31537': returned_ref, '31543': perr},
        '41569': {'41572': False, '41575': 6, '41587': 'handler output',
                  '41590': herr, '41593': 'details'}}
    unwired = {'31540': pin, '41578': opaque, '41581': 0,
               '41584': 'supplied message', '41596': 1}
    return dict(snapshots=snapshots, leaf_returns=returns, unwired_inputs=unwired,
                reference_binding={'constant_uid': '31500',
                    'saved_uri': 'ni.var.psp://10.20.30.2/SUPERVISION/DPS', 'native_ref': ref})


def schedule():
    return (m.Step('31100'), m.Step('31090'), m.Step('31082'), m.Step('31106'),
        m.LeafCall('31114'), m.LeafReturn('31114'), m.StageComplete('31017'),
        m.Step('31258'), m.Step('31243'), m.Step('31237'), m.StageComplete('31192'),
        m.Step('31454'), m.Step('31444'), m.Step('31433'), m.Step('31423'),
        m.Step('31404'), m.Step('31396'), m.StageComplete('31360'),
        m.Step('31526'), m.LeafCall('31532'), m.LeafReturn('31532'),
        m.LeafCall('41569'), m.LeafReturn('41569'), m.LeafCall('31518'),
        m.LeafReturn('31518'), m.StageComplete('31482'))


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
    x = dict(source_id='APP-00', event_uid='43', frame_uid='23449', new_value=True,
        schedule=[dict(kind={m.Step:'step',m.LeafCall:'leaf_call',m.LeafReturn:'leaf_return',
            m.StageComplete:'stage_complete'}[type(t)], uid=t.frame_uid if type(t) is m.StageComplete else t.node_uid)
            for t in schedule()], snapshots={u:list(v) for u,v in f['snapshots'].items()},
        leaf_returns=copy.deepcopy(f['leaf_returns']), unwired_inputs=dict(f['unwired_inputs']),
        reference_binding=dict(f['reference_binding']))
    x['reference_binding']['native_ref'] = {'opaque':'provided'}
    x['leaf_returns']['31532']['31537'] = {'opaque':'returned'}
    x['unwired_inputs']['41578'] = {'opaque':'Void'}
    for maps, uid, terminal in [(x['leaf_returns'],'31532','31543'),(x['leaf_returns'],'41569','41590')]:
        maps[uid][terminal] = dict(maps[uid][terminal]._asdict())
    x['unwired_inputs']['31540'] = dict(x['unwired_inputs']['31540']._asdict())
    return x


def adapter(x):
    COUNTS['adapter_calls'] += 1
    try:
        result = m.replay_saved_acq_event_23449(x)
    except (ValueError,TypeError):
        COUNTS['adapter_refused'] += 1
        raise
    COUNTS['adapter_accepted'] += 1
    return result


class Poison:
    def __iter__(self): raise AssertionError('unselected body input accessed')
    def __getitem__(self,key): raise AssertionError('unselected body input accessed')
    def __len__(self): raise AssertionError('unselected body input accessed')


class SavedAcq23449Tests(unittest.TestCase):
    def expect_writes(self, result, snapshots):
        # Independent source values; do not derive expected fields from core plans.
        expected = {}
        a=list(snapshots['31100']);a[17]=False;expected['31082']=tuple(a)
        expected['31106']=True
        a=list(snapshots['31258']);a[17]=True;expected['31237']=tuple(a)
        a=list(snapshots['31454']);a[9]=False;expected['31433']=tuple(a)
        a=list(snapshots['31423']);a[26]=False;a[27]=False;a[29]=True;expected['31396']=tuple(a)
        self.assertEqual({r['node_uid']:r['value'] for r in result['writes']},expected)

    def test_full_body_independent_source_assignments(self):
        f=fixture();r=core(data=f);self.expect_writes(r,f['snapshots'])
        self.assertEqual(r['completed_stages'],['31017','31192','31360','31482'])
        self.assertTrue(r['selected_body_completed']);self.assertEqual(r['pending_leaf_uids'],())
        self.assertEqual(r['source_version'],'57E1B106EEB57D70124D21CC3FEE775BCADFBF47081F02ED9335A28BAFBC9DD5')
        self.assertEqual(r['event_data_unconsumed_input_ports'],('23467',))
        self.assertEqual(r['event_data_unconsumed_ports'],('23471','23476','30637','30668'))

    def test_every_individual_snapshot_field(self):
        for uid,count in [('31100',32),('31258',32),('31454',29),('31423',77),('31526',29)]:
            for index in range(count):
                f=fixture();v=[False]*count;v[index]=True;f['snapshots'][uid]=tuple(v)
                r=core(data=f);self.expect_writes(r,f['snapshots'])
                p=next(x for x in r['leaf_calls'] if x['node_uid']=='31532')
                self.assertIs(p['input_ports']['31546'],f['snapshots']['31526'])

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
        r=core(tokens=schedule()[:5]);self.assertEqual(r['pending_leaf_uids'],('31114',))
        self.assertEqual(r['leaf_returns'],[]);self.assertEqual(r['completed_stages'],[])
        self.assertFalse(r['schedule_complete'])

    def test_false_zero_body_access(self):
        for input_ in [Poison(),None,{'unexpected':object()}]:
            r=core(False,tokens=input_,data=dict(snapshots=input_,leaf_returns=input_,
                unwired_inputs=input_,reference_binding=input_))
            self.assertEqual(r['writes'],[]);self.assertEqual(r['leaf_calls'],[])
            self.assertEqual(r['selected_case_frame'],'30947')

    def test_ref_error_and_opaque_input_identity(self):
        f=fixture();r=core(data=f);calls={x['node_uid']:x for x in r['leaf_calls']}
        self.assertIs(calls['31532']['input_ports']['31534'],f['reference_binding']['native_ref'])
        self.assertIs(calls['31532']['input_ports']['31540'],f['unwired_inputs']['31540'])
        self.assertIs(calls['41569']['input_ports']['41599'],f['leaf_returns']['31532']['31543'])
        self.assertIs(calls['41569']['input_ports']['41578'],f['unwired_inputs']['41578'])
        self.assertIs(next(x for x in r['leaf_returns'] if x['node_uid']=='31532')['output_ports']['31537'],f['leaf_returns']['31532']['31537'])

    def test_errors_do_not_gate_sequence_completion(self):
        for error in [m.ErrorValue(False,0,''),m.ErrorValue(True,-2147483648,'fault'),m.ErrorValue(False,2147483647,'warning')]:
            f=fixture();f['leaf_returns']['31532']['31543']=error;r=core(data=f)
            self.assertTrue(r['selected_body_completed'])
            self.assertIs(next(c for c in r['leaf_calls'] if c['node_uid']=='41569')['input_ports']['41599'],error)

    def test_constants_fields_and_saved_reference_args(self):
        r=core();calls={x['node_uid']:x for x in r['leaf_calls']}
        self.assertEqual(calls['31114']['input_ports'],{'31130':150})
        self.assertEqual(calls['31518']['input_ports'],{'31523':100})
        eps=next(x for x in r['log'] if x.get('node_uid')=='31404' and x['kind']=='bundle')
        self.assertEqual([(x['terminal_uid'],x['field_index'],x['value'],x['constant_uid']) for x in eps['assignments']],
                         [('31412',26,False,'31366'),('31415',29,True,'31376'),('49149',27,False,'31366')])

    def test_new_fields_preserve_other_positions(self):
        f=fixture()
        f['snapshots']['31100']=tuple([True]*32)
        f['snapshots']['31258']=tuple([False]*32)
        f['snapshots']['31454']=tuple([True]*29)
        f['snapshots']['31423']=tuple([True]*77)
        r=core(data=f);values={x['node_uid']:x['value'] for x in r['writes']}
        self.assertEqual([i for i,x in enumerate(values['31082']) if not x],[17])
        self.assertEqual([i for i,x in enumerate(values['31237']) if x],[17])
        self.assertEqual([i for i,x in enumerate(values['31433']) if not x],[9])
        self.assertEqual([i for i,x in enumerate(values['31396']) if not x],[26,27])
        self.assertTrue(values['31396'][29])
        for oldfield in (20,21,23):self.assertTrue(values['31396'][oldfield])

    def test_fresh_publication_snapshot_is_not_reset_write(self):
        f=fixture()
        f['snapshots']['31454']=tuple([True]*29)
        f['snapshots']['31526']=tuple([False]*29)
        r=core(data=f)
        reset=next(x['value'] for x in r['writes'] if x['node_uid']=='31433')
        sent=next(x['input_ports']['31546'] for x in r['leaf_calls'] if x['node_uid']=='31532')
        self.assertIs(sent,f['snapshots']['31526'])
        self.assertIsNot(sent,reset)
        self.assertNotEqual(sent,reset)
        self.assertEqual(sum(reset),28);self.assertEqual(sum(sent),0)

    def test_empty_true_does_not_consume_future_values(self):
        r=core(tokens=(),data=dict(snapshots=Poison(),leaf_returns=Poison(),unwired_inputs=Poison(),reference_binding=Poison()))
        self.assertEqual(r['active_stage'],'31017');self.assertEqual(r['writes'],[])

    def test_snapshot_domains_refuse(self):
        for bad in [None,[False]*32,tuple([False]*31),tuple([False]*33),tuple([0]*32),tuple([True]*31+[1])]:
            f=fixture();f['snapshots']['31100']=bad
            with self.assertRaises((TypeError,ValueError)):core(data=f)

    def test_boolean_event_and_token_domains_refuse(self):
        for bad in [0,1,None,'True']:
            with self.assertRaises(TypeError):core(value=bad)
        for tokens in [list(schedule()),(object(),),(m.Step(31100),),(m.Step('unknown'),),schedule()+(m.Step('31100'),)]:
            with self.assertRaises((TypeError,ValueError)):core(tokens=tokens)

    def test_saved_dependencies_refuse(self):
        for tokens in [(m.Step('31090'),),(m.Step('31082'),),(m.Step('31258'),),
                       (m.LeafReturn('31114'),),(m.StageComplete('31017'),),
                       schedule()[:5]+(m.StageComplete('31017'),),
                       schedule()[:18]+(m.LeafCall('31532'),),
                       schedule()[:20]+(m.LeafCall('41569'),),
                       (m.Step('31100'),m.Step('31100')),
                       (m.LeafCall('31114'),m.LeafCall('31114'))]:
            with self.assertRaises(ValueError):core(tokens=tokens)

    def test_reference_and_unwired_domain_refusals(self):
        for modify in [lambda f:f.update(reference_binding=None),
            lambda f:f['reference_binding'].update(constant_uid='34004'),
            lambda f:f['reference_binding'].update(saved_uri='other'),
            lambda f:f['unwired_inputs'].pop('31540'),
            lambda f:f['unwired_inputs'].update(**{'41581':True}),
            lambda f:f['unwired_inputs'].update(**{'41596':65536}),
            lambda f:f['unwired_inputs'].update(**{'41584':None})]:
            f=fixture();modify(f)
            with self.assertRaises((ValueError,TypeError)):core(data=f)

    def test_native_return_domains_refuse(self):
        for uid,port,bad in [('31114','31116',-1),('31518','31520',True),
                            ('31532','31543',{'status':False,'code':0,'source':''}),
                            ('41569','41575',2147483648),('41569','41572',0)]:
            f=fixture();f['leaf_returns'][uid][port]=bad
            with self.assertRaises((ValueError,TypeError)):core(data=f)

    def test_json_full_false_inflight(self):
        x=payload();r=adapter(x);self.assertTrue(r['selected_body_completed'])
        self.assertEqual(r['writes'][0]['value'][17],False)
        self.assertEqual(r['writes'][2]['value'][17],True)
        x=payload();x.update(new_value=False,schedule=Poison(),snapshots=Poison(),
            leaf_returns=Poison(),unwired_inputs=Poison(),reference_binding=Poison())
        self.assertEqual(adapter(x)['leaf_calls'],[])
        x=payload();x['schedule']=x['schedule'][:5];self.assertEqual(adapter(x)['pending_leaf_uids'],['31114'])

    def test_json_strict_envelope_refuses(self):
        for modify in [lambda x:x.update(extra=0),lambda x:x.pop('snapshots'),
            lambda x:x.update(source_id='APP-02'),lambda x:x.update(frame_uid='33620'),
            lambda x:x.update(new_value=1),lambda x:x['schedule'][0].update(kind='callback'),
            lambda x:x['schedule'][0].update(extra=0),lambda x:x['snapshots'].update(unknown=[]),
            lambda x:x['snapshots'].update(**{'31100':[1]*32}),
            lambda x:x['reference_binding'].update(native_ref=float('nan')),
            lambda x:x['reference_binding'].update(native_ref=object()),
            lambda x:x['unwired_inputs'].update(**{'41578':float('inf')})]:
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
