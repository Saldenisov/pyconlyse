"""Independent bounded saved APP00/frame22879 expectations, Python3.4."""
import copy
import importlib.machinery
import itertools
import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE = os.path.join(ROOT, 'elyse_agent', 'saved_acq_event_22879.py')
m = importlib.machinery.SourceFileLoader('qualified_acq22879', CORE).load_module()
COUNTS = dict(core_calls=0, accepted=0, refused=0, completed_true=0, prefixes=0,
              false=0, adapter_calls=0, adapter_accepted=0, adapter_refused=0)


def fixture():
    snapshots = {'23351': tuple(i % 3 == 0 for i in range(32)),
        '23424': tuple(i % 3 == 1 for i in range(32)),
        '25058': tuple(i % 2 == 0 for i in range(29)),
        '24858': tuple(i % 3 == 2 for i in range(77)),
        '25526': tuple(i % 3 == 0 for i in range(29))}
    pin = m.ErrorValue(False, 0, 'supplied input')
    perr = m.ErrorValue(True, -7, 'supplied PSP error')
    herr = m.ErrorValue(True, 6, 'supplied handler error')
    ref, returned_ref, opaque = object(), object(), object()
    returns = {'23365': {'23367': 41}, '25510': {'25512': 99},
        '25625': {'25683': returned_ref, '25697': perr},
        '25703': {'25706': False, '25709': 6, '25721': 'handler output',
                  '25724': herr, '25727': 'details'}}
    unwired = {'25694': pin, '25712': opaque, '25715': 0,
               '25718': 'supplied message', '25765': 1}
    return dict(snapshots=snapshots, leaf_returns=returns, unwired_inputs=unwired,
                reference_binding={'constant_uid': '25486',
                    'saved_uri': 'ni.var.psp://10.20.30.2/SUPERVISION/DPS', 'native_ref': ref})


def schedule():
    return (m.Step('23351'), m.Step('23340'), m.Step('23331'), m.Step('23357'),
        m.LeafCall('23365'), m.LeafReturn('23365'), m.StageComplete('23304'),
        m.Step('23424'), m.Step('23414'), m.Step('23408'), m.StageComplete('23392'),
        m.Step('25058'), m.Step('24908'), m.Step('24872'), m.Step('24858'),
        m.Step('24619'), m.Step('24589'), m.StageComplete('24497'),
        m.Step('25526'), m.LeafCall('25625'), m.LeafReturn('25625'),
        m.LeafCall('25703'), m.LeafReturn('25703'), m.LeafCall('25510'),
        m.LeafReturn('25510'), m.StageComplete('25430'))


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
    x = dict(source_id='APP-00', event_uid='43', frame_uid='22879', new_value=True,
        schedule=[dict(kind={m.Step:'step',m.LeafCall:'leaf_call',m.LeafReturn:'leaf_return',
            m.StageComplete:'stage_complete'}[type(t)], uid=t.frame_uid if type(t) is m.StageComplete else t.node_uid)
            for t in schedule()], snapshots={u:list(v) for u,v in f['snapshots'].items()},
        leaf_returns=copy.deepcopy(f['leaf_returns']), unwired_inputs=dict(f['unwired_inputs']),
        reference_binding=dict(f['reference_binding']))
    x['reference_binding']['native_ref'] = {'opaque':'provided'}
    x['leaf_returns']['25625']['25683'] = {'opaque':'returned'}
    x['unwired_inputs']['25712'] = {'opaque':'Void'}
    for maps, uid, terminal in [(x['leaf_returns'],'25625','25697'),(x['leaf_returns'],'25703','25724')]:
        maps[uid][terminal] = dict(maps[uid][terminal]._asdict())
    x['unwired_inputs']['25694'] = dict(x['unwired_inputs']['25694']._asdict())
    return x


def adapter(x):
    COUNTS['adapter_calls'] += 1
    try:
        result = m.replay_saved_acq_event_22879(x)
    except (ValueError,TypeError):
        COUNTS['adapter_refused'] += 1
        raise
    COUNTS['adapter_accepted'] += 1
    return result


class Poison:
    def __iter__(self): raise AssertionError('unselected body input accessed')
    def __getitem__(self,key): raise AssertionError('unselected body input accessed')
    def __len__(self): raise AssertionError('unselected body input accessed')


class SavedAcq22879Tests(unittest.TestCase):
    def expect_writes(self, result, snapshots):
        # Independent source values; do not derive expected fields from core plans.
        expected = {}
        a=list(snapshots['23351']);a[4]=False;expected['23331']=tuple(a)
        expected['23357']=True
        a=list(snapshots['23424']);a[4]=True;expected['23408']=tuple(a)
        a=list(snapshots['25058']);a[5]=False;expected['24872']=tuple(a)
        a=list(snapshots['24858']);a[14]=False;a[15]=False;a[17]=True;expected['24589']=tuple(a)
        self.assertEqual({r['node_uid']:r['value'] for r in result['writes']},expected)

    def test_full_body_independent_source_assignments(self):
        f=fixture();r=core(data=f);self.expect_writes(r,f['snapshots'])
        self.assertEqual(r['completed_stages'],['23304','23392','24497','25430'])
        self.assertTrue(r['selected_body_completed']);self.assertEqual(r['pending_leaf_uids'],())
        self.assertEqual(r['source_version'],'57E1B106EEB57D70124D21CC3FEE775BCADFBF47081F02ED9335A28BAFBC9DD5')
        self.assertEqual(r['event_data_unconsumed_input_ports'],('23164',))
        self.assertEqual(r['event_data_unconsumed_ports'],('23173','23181','23190','23200'))

    def test_every_individual_snapshot_field(self):
        for uid,count in [('23351',32),('23424',32),('25058',29),('24858',77),('25526',29)]:
            for index in range(count):
                f=fixture();v=[False]*count;v[index]=True;f['snapshots'][uid]=tuple(v)
                r=core(data=f);self.expect_writes(r,f['snapshots'])
                p=next(x for x in r['leaf_calls'] if x['node_uid']=='25625')
                self.assertIs(p['input_ports']['25700'],f['snapshots']['25526'])

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
        r=core(tokens=schedule()[:5]);self.assertEqual(r['pending_leaf_uids'],('23365',))
        self.assertEqual(r['leaf_returns'],[]);self.assertEqual(r['completed_stages'],[])
        self.assertFalse(r['schedule_complete'])

    def test_false_zero_body_access(self):
        for input_ in [Poison(),None,{'unexpected':object()}]:
            r=core(False,tokens=input_,data=dict(snapshots=input_,leaf_returns=input_,
                unwired_inputs=input_,reference_binding=input_))
            self.assertEqual(r['writes'],[]);self.assertEqual(r['leaf_calls'],[])
            self.assertEqual(r['selected_case_frame'],'23269')

    def test_ref_error_and_opaque_input_identity(self):
        f=fixture();r=core(data=f);calls={x['node_uid']:x for x in r['leaf_calls']}
        self.assertIs(calls['25625']['input_ports']['25676'],f['reference_binding']['native_ref'])
        self.assertIs(calls['25625']['input_ports']['25694'],f['unwired_inputs']['25694'])
        self.assertIs(calls['25703']['input_ports']['25887'],f['leaf_returns']['25625']['25697'])
        self.assertIs(calls['25703']['input_ports']['25712'],f['unwired_inputs']['25712'])
        self.assertIs(next(x for x in r['leaf_returns'] if x['node_uid']=='25625')['output_ports']['25683'],f['leaf_returns']['25625']['25683'])

    def test_errors_do_not_gate_sequence_completion(self):
        for error in [m.ErrorValue(False,0,''),m.ErrorValue(True,-2147483648,'fault'),m.ErrorValue(False,2147483647,'warning')]:
            f=fixture();f['leaf_returns']['25625']['25697']=error;r=core(data=f)
            self.assertTrue(r['selected_body_completed'])
            self.assertIs(next(c for c in r['leaf_calls'] if c['node_uid']=='25703')['input_ports']['25887'],error)

    def test_constants_fields_and_saved_reference_args(self):
        r=core();calls={x['node_uid']:x for x in r['leaf_calls']}
        self.assertEqual(calls['23365']['input_ports'],{'23370':150})
        self.assertEqual(calls['25510']['input_ports'],{'25516':100})
        eps=next(x for x in r['log'] if x.get('node_uid')=='24619' and x['kind']=='bundle')
        self.assertEqual([(x['terminal_uid'],x['field_index'],x['value'],x['constant_uid']) for x in eps['assignments']],
                         [('24655',14,False,'24511'),('24681',17,True,'24536'),('46337',15,False,'24511')])

    def test_empty_true_does_not_consume_future_values(self):
        r=core(tokens=(),data=dict(snapshots=Poison(),leaf_returns=Poison(),unwired_inputs=Poison(),reference_binding=Poison()))
        self.assertEqual(r['active_stage'],'23304');self.assertEqual(r['writes'],[])

    def test_snapshot_domains_refuse(self):
        for bad in [None,[False]*32,tuple([False]*31),tuple([False]*33),tuple([0]*32),tuple([True]*31+[1])]:
            f=fixture();f['snapshots']['23351']=bad
            with self.assertRaises((TypeError,ValueError)):core(data=f)

    def test_boolean_event_and_token_domains_refuse(self):
        for bad in [0,1,None,'True']:
            with self.assertRaises(TypeError):core(value=bad)
        for tokens in [list(schedule()),(object(),),(m.Step(23351),),(m.Step('unknown'),),schedule()+(m.Step('23351'),)]:
            with self.assertRaises((TypeError,ValueError)):core(tokens=tokens)

    def test_saved_dependencies_refuse(self):
        for tokens in [(m.Step('23340'),),(m.Step('23331'),),(m.Step('23424'),),
                       (m.LeafReturn('23365'),),(m.StageComplete('23304'),),
                       schedule()[:5]+(m.StageComplete('23304'),),
                       schedule()[:18]+(m.LeafCall('25625'),),
                       schedule()[:20]+(m.LeafCall('25703'),),
                       (m.Step('23351'),m.Step('23351')),
                       (m.LeafCall('23365'),m.LeafCall('23365'))]:
            with self.assertRaises(ValueError):core(tokens=tokens)

    def test_reference_and_unwired_domain_refusals(self):
        for modify in [lambda f:f.update(reference_binding=None),
            lambda f:f['reference_binding'].update(constant_uid='34004'),
            lambda f:f['reference_binding'].update(saved_uri='other'),
            lambda f:f['unwired_inputs'].pop('25694'),
            lambda f:f['unwired_inputs'].update(**{'25715':True}),
            lambda f:f['unwired_inputs'].update(**{'25765':65536}),
            lambda f:f['unwired_inputs'].update(**{'25718':None})]:
            f=fixture();modify(f)
            with self.assertRaises((ValueError,TypeError)):core(data=f)

    def test_native_return_domains_refuse(self):
        for uid,port,bad in [('23365','23367',-1),('25510','25512',True),
                            ('25625','25697',{'status':False,'code':0,'source':''}),
                            ('25703','25709',2147483648),('25703','25706',0)]:
            f=fixture();f['leaf_returns'][uid][port]=bad
            with self.assertRaises((ValueError,TypeError)):core(data=f)

    def test_json_full_false_inflight(self):
        x=payload();r=adapter(x);self.assertTrue(r['selected_body_completed'])
        self.assertEqual(r['writes'][0]['value'][4],False)
        self.assertEqual(r['writes'][2]['value'][4],True)
        x=payload();x.update(new_value=False,schedule=Poison(),snapshots=Poison(),
            leaf_returns=Poison(),unwired_inputs=Poison(),reference_binding=Poison())
        self.assertEqual(adapter(x)['leaf_calls'],[])
        x=payload();x['schedule']=x['schedule'][:5];self.assertEqual(adapter(x)['pending_leaf_uids'],['23365'])

    def test_json_strict_envelope_refuses(self):
        for modify in [lambda x:x.update(extra=0),lambda x:x.pop('snapshots'),
            lambda x:x.update(source_id='APP-02'),lambda x:x.update(frame_uid='33620'),
            lambda x:x.update(new_value=1),lambda x:x['schedule'][0].update(kind='callback'),
            lambda x:x['schedule'][0].update(extra=0),lambda x:x['snapshots'].update(unknown=[]),
            lambda x:x['snapshots'].update(**{'23351':[1]*32}),
            lambda x:x['reference_binding'].update(native_ref=float('nan')),
            lambda x:x['reference_binding'].update(native_ref=object()),
            lambda x:x['unwired_inputs'].update(**{'25712':float('inf')})]:
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
