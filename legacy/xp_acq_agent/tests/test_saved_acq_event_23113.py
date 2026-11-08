"""Fresh23113 independent saved-source expectations; portable stdlib3.4."""
import copy,itertools,json,unittest
try:
    from elyse_agent import saved_acq_event_23113 as m
except ImportError:
    import importlib.machinery,os
    m=importlib.machinery.SourceFileLoader('acq23113',os.path.join(os.path.dirname(__file__),'..','elyse_agent','saved_acq_event_23113.py')).load_module()
CALLS=dict(accepted=0,refused=0,identity_checks=0,prefixes=0)
def fixture():
    # Five fresh decoded banks; intentionally independent before/after reads.
    snapshots={'54862':tuple(i%3==0 for i in range(32)), '23811':tuple(i%4==1 for i in range(32)),
               '23961':tuple(i%5==2 for i in range(77)), '24025':tuple(i%3==1 for i in range(29)),
               '24155':tuple(i%2==0 for i in range(29))}
    e1=m.ErrorValue(True,-601,'focales supplied fault');e2=m.ErrorValue(True,17,'PSP supplied fault')
    leaf_returns={'23625':{'23726':e1},'46521':{'46528':True,'46532':-9,'46545':'decoded','46548':m.ErrorValue(False,8,'unused'),'46552':'unused'},
        '48835':{'48841':4000},'23748':{'23750':7},'54877':{'54880':9},'24161':{'24166':object(),'24172':e2},
        '24178':{'24181':False,'24184':11,'24196':'unused','24199':m.ErrorValue(True,4,'unused output'),'24202':'unused'},'24147':{'24149':50}}
    unwired={f:object()for f in ('23730','23735','23757','23771','31059','31068','46535','24187')}
    unwired.update({'46538':-5,'46542':'handler caller source','46555':65535,'24169':m.ErrorValue(True,-12,'unwired writer error'),
                    '24190':6,'24193':'handler caller source2','24205':4})
    bindings={'24129':{'constant_uid':'24129','saved_uri':'ni.var.psp://10.20.30.2/SUPERVISION/DPS','native_ref':object()}}
    # Mainstage0 branches overlap nested stages; second Wait starts only after
    # original actualdiag57312 completion, not container57299 identification.
    schedule=(m.LeafCall('23748'),m.LeafCall('23625'),m.Step('23740'),m.LeafReturn('23625'),m.LeafCall('46521'),m.LeafReturn('46521'),
        m.StageComplete('57312'),m.LeafCall('48835'),m.LeafReturn('23748'),m.LeafReturn('48835'),m.StageComplete('47864'),m.StageComplete('23518'),
        m.LeafCall('54877'),m.Step('54862'),m.Step('54852'),m.Step('54844'),m.LeafReturn('54877'),m.StageComplete('54833'),
        m.Step('23811'),m.Step('23800'),m.Step('23792'),m.StageComplete('23774'),
        m.Step('23961'),m.Step('23928'),m.Step('23916'),m.Step('24025'),m.Step('24001'),m.Step('23980'),m.StageComplete('23880'),
        m.LeafCall('24147'),m.Step('24155'),m.LeafCall('24161'),m.LeafReturn('24161'),m.LeafCall('24178'),m.LeafReturn('24178'),m.LeafReturn('24147'),m.StageComplete('24054'))
    return dict(new_value=True,schedule=schedule,snapshots=snapshots,leaf_returns=leaf_returns,unwired_inputs=unwired,reference_bindings=bindings)
def replay(f):
    r=m.replay_event(**f);CALLS['accepted']+=1;return r
def json_payload(f=None):
    f=fixture()if f is None else f
    def inert(v):
        if type(v)is m.ErrorValue:return dict(status=v.status,code=v.code,source=v.source)
        if type(v)is dict:return{k:inert(x)for k,x in v.items()}
        if type(v)in(tuple,list):return[inert(x)for x in v]
        if type(v)in(str,int,bool)or v is None:return v
        return {'supplied_opaque':'inert'}
    kinds={m.Step:'step',m.LeafCall:'leaf_call',m.LeafReturn:'leaf_return',m.StageComplete:'stage_complete'}
    p=dict(source_id='APP-00',source_version='57E1B106EEB57D70124D21CC3FEE775BCADFBF47081F02ED9335A28BAFBC9DD5',event_uid='43',frame_uid='23113',new_value=f['new_value'],
        schedule=[dict(kind=kinds[type(t)],uid=t[0])for t in f['schedule']])
    p.update({k:inert(f[k])for k in('snapshots','leaf_returns','unwired_inputs','reference_bindings')});return p
class Poison:
    def __iter__(self):raise AssertionError('unselected input read')
    def __getitem__(self,k):raise AssertionError('unselected input read')
class BodyTests(unittest.TestCase):
    def refuse(self,f):
        with self.assertRaises((ValueError,TypeError)):m.replay_event(**f)
        CALLS['refused']+=1
    def eq_identity(self,a,b):
        self.assertIs(a,b);CALLS['identity_checks']+=1
    def test_complete_exact_fresh_assignments(self):
        f=fixture();r=replay(f);self.assertTrue(r['schedule_complete']);self.assertEqual(r['completed_stages'],['23518','54833','23774','23880','24054']);self.assertEqual(r['completed_nested_stages'],['57312','47864'])
        writes={x['node_uid']:x['value']for x in r['writes']}
        self.assertIs(writes['23740'],True)
        for uid,read,changes in (('54844','54862',{8:False}),('23792','23811',{8:True}),('23916','23961',{32:False,33:False,35:True}),('23980','24025',{11:False})):
            expected=list(f['snapshots'][read])
            for i,b in changes.items():expected[i]=b
            self.assertEqual(writes[uid],tuple(expected));self.assertEqual(f['snapshots'][read],fixture()['snapshots'][read])
        calls={x['node_uid']:x for x in r['leaf_calls']}
        self.eq_identity(calls['46521']['input_ports']['46559'],f['leaf_returns']['23625']['23726'])
        self.eq_identity(calls['24178']['input_ports']['24208'],f['leaf_returns']['24161']['24172'])
        self.eq_identity(calls['24161']['input_ports']['24169'],f['unwired_inputs']['24169'])
        self.eq_identity(calls['24161']['input_ports']['24175'],f['snapshots']['24155'])
        self.eq_identity(calls['24161']['input_ports']['24163'],f['reference_bindings']['24129']['native_ref'])
        self.assertNotEqual(calls['24161']['input_ports']['24175'],writes['23980'])
        for uid,face,value in(('23748','23754',150),('54877','54889',150),('48835','48844',500),('24147','24152',100)):
            self.assertEqual(calls[uid]['input_ports'][face],value)
        self.assertTrue(calls['23625']['original_subvi_boundary'])
        for face in ('23730','23735','23757','23771','31059','31068'):self.eq_identity(calls['23625']['input_ports'][face],f['unwired_inputs'][face])
        for row in r['leaf_returns']:self.eq_identity(row['output_ports'],f['leaf_returns'][row['node_uid']])
        for key,value in m.LIMITS.items():self.assertIs(r[key],False)
    def test_false_zero_access(self):
        for value in(None,Poison(),object()):
            f=dict(new_value=False,schedule=value,snapshots=value,leaf_returns=value,unwired_inputs=value,reference_bindings=value);r=replay(f)
            self.assertEqual(r['writes'],[]);self.assertEqual(r['leaf_calls'],[]);self.assertTrue(r['selected_body_completed']);self.assertEqual(r['selected_case_frame'],'23493')
    def test_all_prefixes_and_inflight(self):
        f=fixture()
        for i in range(38):
            q=dict(f,schedule=f['schedule'][:i]);r=replay(q);CALLS['prefixes']+=1
            self.assertEqual(r['schedule_complete'],i==37)
            calls={t.node_uid for t in q['schedule']if type(t)is m.LeafCall};returns={t.node_uid for t in q['schedule']if type(t)is m.LeafReturn}
            self.assertEqual(set(r['pending_leaf_uids']),calls-returns)
        r=replay(dict(f,schedule=f['schedule'][:2]));self.assertEqual(r['active_stage'],'23518');self.assertEqual(r['active_nested_stage'],'57312');self.assertEqual(set(r['pending_leaf_uids']),{'23748','23625'})
    def test_stage0_nested_interleavings(self):
        f=fixture();nested=[m.LeafCall('23625'),m.LeafReturn('23625'),m.LeafCall('46521'),m.LeafReturn('46521'),m.StageComplete('57312'),m.LeafCall('48835'),m.LeafReturn('48835'),m.StageComplete('47864')]
        # All placements of ordered outerWaitcall/return plus independentAction
        # in ten-node stage0 followed by sourcejoins. No nativeorder claim.
        count=0
        for wait_positions in itertools.combinations(range(10),2):
            for action_pos in range(11):
                rows=[];n=iter(nested)
                for i in range(10):rows.append(m.LeafCall('23748')if i==wait_positions[0]else m.LeafReturn('23748')if i==wait_positions[1]else next(n))
                rows.insert(action_pos,m.Step('23740'));q=dict(f,schedule=tuple(rows)+(m.StageComplete('23518'),)+f['schedule'][12:]);r=replay(q)
                self.assertTrue(r['schedule_complete']);self.assertEqual(len(r['writes']),5);count+=1
        self.assertEqual(count,495)
    def test_parallel_eps_dps_and_wait_orders(self):
        f=fixture();a=[m.Step('23961'),m.Step('23928'),m.Step('23916')];b=[m.Step('24025'),m.Step('24001'),m.Step('23980')]
        for positions in itertools.combinations(range(6),3):
            ai=iter(a);bi=iter(b);rows=[next(ai)if i in positions else next(bi)for i in range(6)]
            r=replay(dict(f,schedule=f['schedule'][:22]+tuple(rows)+(m.StageComplete('23880'),)+f['schedule'][29:]));self.assertTrue(r['schedule_complete'])
        last=[m.Step('24155'),m.LeafCall('24161'),m.LeafReturn('24161'),m.LeafCall('24178'),m.LeafReturn('24178')]
        for positions in itertools.combinations(range(7),2):
            it=iter(last);rows=[m.LeafCall('24147')if i==positions[0]else m.LeafReturn('24147')if i==positions[1]else next(it)for i in range(7)]
            self.assertTrue(replay(dict(f,schedule=f['schedule'][:29]+tuple(rows)+(m.StageComplete('24054'),)))['schedule_complete'])
    def test_source_order_refusals(self):
        f=fixture()
        bad=[(m.StageComplete('23518'),),(m.StageComplete('57299'),),(m.StageComplete('47855'),),(m.LeafCall('48835'),),(m.LeafCall('46521'),),(m.LeafReturn('23625'),),(m.Step('54862'),),(m.StageComplete('57312'),),(m.Step('54852'),),(m.Step('foreign'),)]
        for schedule in bad:self.refuse(dict(f,schedule=schedule))
        self.refuse(dict(f,schedule=f['schedule']+(m.Step('23740'),)))
        self.refuse(dict(f,schedule=(m.Step('23740'),m.Step('23740'))))
        self.refuse(dict(f,schedule=f['schedule'][:6]+(m.StageComplete('47864'),)))
        self.refuse(dict(f,schedule=f['schedule'][:29]+(m.LeafCall('24161'),)))
    def test_types_domains_and_reference(self):
        f=fixture()
        for v in(1,None,'True'):self.refuse(dict(f,new_value=v))
        for v in([],tuple([m.Step('23740')]*38)):self.refuse(dict(f,schedule=v))
        for v in(list(f['snapshots']['54862']),tuple([False]*31),tuple([False]*31+[1])):
            q=copy.deepcopy(f);q['snapshots']['54862']=v;self.refuse(q)
        for key,v in(('46538',True),('46538',2147483648),('46555',-1),('46555',65536),('46542',False),('24169',m.ErrorValue(1,0,'')),('24169',m.ErrorValue(False,2147483648,''))):
            q=copy.deepcopy(f);q['unwired_inputs'][key]=v;self.refuse(q)
        for key,v in(('23750',True),('23750',-1),('23750',4294967296)):
            q=copy.deepcopy(f);q['leaf_returns']['23748'][key]=v;self.refuse(q)
        for key,v in(('constant_uid','foreign'),('saved_uri','ni.var.psp://other/DPS')):
            q=copy.deepcopy(f);q['reference_bindings']['24129'][key]=v;self.refuse(q)
        q=copy.deepcopy(f);del q['unwired_inputs']['31068'];self.refuse(q)
        q=copy.deepcopy(f);del q['leaf_returns']['46521']['46552'];self.refuse(q)
        q=copy.deepcopy(f);q['leaf_returns']['24161']['foreign']=None;self.refuse(q)
    def test_unused_error_outputs_do_not_gate(self):
        f=fixture();f['leaf_returns']['46521']['46548']=m.ErrorValue(True,-999,'unused');f['leaf_returns']['24178']['24199']=m.ErrorValue(True,-998,'unused')
        self.assertTrue(replay(f)['schedule_complete'])
    def test_json_exact_and_false_policy(self):
        p=json_payload();r=m.replay_saved_acq_event_23113(p);self.assertTrue(r['schedule_complete']);self.assertEqual(len(r['writes']),5);CALLS['accepted']+=1
        for i in (0,2,7,12,18,29,34):
            q=copy.deepcopy(p);q['schedule']=q['schedule'][:i];self.assertFalse(m.replay_saved_acq_event_23113(q)['schedule_complete']);CALLS['accepted']+=1
        q=dict(p,new_value=False,schedule=Poison(),snapshots=Poison(),leaf_returns=Poison(),unwired_inputs=Poison(),reference_bindings=Poison())
        self.assertTrue(m.replay_saved_acq_event_23113(q)['schedule_complete']);CALLS['accepted']+=1
        for key,v in(('source_id','APP-01'),('source_version','0'*64),('event_uid','44'),('frame_uid','8896'),('new_value',1)):
            q=copy.deepcopy(p);q[key]=v
            with self.assertRaises((ValueError,TypeError)):m.replay_saved_acq_event_23113(q)
            CALLS['refused']+=1
        for mutate in(lambda q:q.pop('source_version'),lambda q:q.__setitem__('native_execution',True),lambda q:q['schedule'][0].__setitem__('kind','callback'),lambda q:q['snapshots'].__setitem__('foreign',[]),lambda q:q['reference_bindings']['24129'].__setitem__('native_ref',float('nan')),lambda q:q['unwired_inputs'].__setitem__('23730',object())):
            q=copy.deepcopy(p);mutate(q)
            with self.assertRaises((ValueError,TypeError)):m.replay_saved_acq_event_23113(q)
            CALLS['refused']+=1
if __name__=='__main__':unittest.main()
