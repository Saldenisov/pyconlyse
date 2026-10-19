"""Fresh34191 independent saved expectations and portable inline Py3.4 fixtures."""
import copy,importlib.machinery,json,os,unittest
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
m=importlib.machinery.SourceFileLoader('new34191core',os.path.join(ROOT,'elyse_agent','saved_acq_event_34191.py')).load_module()
COUNTS=dict(core_calls=0,accepted=0,refused=0,completed_true=0,prefixes=0,false=0,adapter_calls=0,adapter_accepted=0,adapter_refused=0)
def fixture():
    snapshots={u:tuple(i%3==s for i in range(n))for u,n,s in(('34377',32,0),('35778',77,1),('35802',29,2),('35878',29,0),('49466',77,2),('52019',32,1))}
    returns={u:{face:m.ErrorValue(True,-i,'supplied-'+u),ref:object()}for i,(u,face,ref)in enumerate((('35884','35895','35889'),('49501','49512','49506'),('52054','52065','52059')),1)}
    returns['52071']={'52074':False,'52077':-9,'52089':'message','52092':m.ErrorValue(False,31,'unused-handler-error'),'52095':'details'}
    returns['35870']={'35872':4294967295}
    unwired={'35892':m.ErrorValue(True,43,'supplied-DPS-error'),'52080':object(),'52083':7,'52086':'explicit handler message','52098':2}
    refs={u:dict(constant_uid=u,saved_uri='ni.var.psp://10.20.30.2/SUPERVISION/'+name,native_ref=object())for u,name in(('35851','DPS'),('49483','EPS'),('52036','C4_OUT_DIO96'))}
    return dict(snapshots=snapshots,leaf_returns=returns,unwired_inputs=unwired,reference_bindings=refs)
def schedule():
    return(m.Step('34377'),m.Step('34350'),m.Step('34333'),m.Step('34383'),m.StageComplete('34284'),
        m.Step('35802'),m.Step('35792'),m.Step('35784'),m.Step('35778'),m.Step('35761'),m.Step('35744'),m.StageComplete('35506'),
        m.Step('35878'),m.LeafCall('35884'),m.LeafReturn('35884'),m.Step('49466'),m.LeafCall('49501'),m.LeafReturn('49501'),
        m.Step('52019'),m.LeafCall('52054'),m.LeafReturn('52054'),m.LeafCall('52071'),m.LeafReturn('52071'),m.StageComplete('35833'),
        m.LeafCall('35870'),m.LeafReturn('35870'),m.StageComplete('35244'))
def core(new=True,tokens=None,data=None):
    COUNTS['core_calls']+=1
    try:r=m.replay_event(new,schedule()if tokens is None else tokens,**(fixture()if data is None else data))
    except(TypeError,ValueError):COUNTS['refused']+=1;raise
    COUNTS['accepted']+=1;COUNTS['false'if not new else'completed_true'if r['selected_body_completed']else'prefixes']+=1;return r
def payload():
    f=fixture();p=dict(source_id='APP-00',source_version='57E1B106EEB57D70124D21CC3FEE775BCADFBF47081F02ED9335A28BAFBC9DD5',event_uid='43',frame_uid='34191',new_value=True,
        schedule=[dict(kind={m.Step:'step',m.LeafCall:'leaf_call',m.LeafReturn:'leaf_return',m.StageComplete:'stage_complete'}[type(t)],uid=t.frame_uid if type(t)is m.StageComplete else t.node_uid)for t in schedule()],
        snapshots={u:list(v)for u,v in f['snapshots'].items()},leaf_returns=f['leaf_returns'],unwired_inputs=f['unwired_inputs'],reference_bindings=f['reference_bindings'])
    p['unwired_inputs']['35892']=dict(p['unwired_inputs']['35892']._asdict());p['unwired_inputs']['52080']={'opaque':'supplied-Void-52080'}
    for u,e,r in(('35884','35895','35889'),('49501','49512','49506'),('52054','52065','52059')):
        p['leaf_returns'][u][e]=dict(p['leaf_returns'][u][e]._asdict());p['leaf_returns'][u][r]={'opaque':'unused-'+r}
    p['leaf_returns']['52071']['52092']=dict(p['leaf_returns']['52071']['52092']._asdict())
    for u in p['reference_bindings']:p['reference_bindings'][u]['native_ref']={'opaque':'provided-'+u}
    return p
def adapter(p):
    COUNTS['adapter_calls']+=1
    try:r=m.replay_saved_acq_event_34191(p)
    except(TypeError,ValueError):COUNTS['adapter_refused']+=1;raise
    COUNTS['adapter_accepted']+=1;return r
def interleave(a,b):
    if not a:yield tuple(b);return
    if not b:yield tuple(a);return
    for t in interleave(a[1:],b):yield(a[0],)+t
    for t in interleave(a,b[1:]):yield(b[0],)+t
class Poison:
    def __iter__(self):raise AssertionError('unselected body input accessed')
    def __getitem__(self,k):raise AssertionError('unselected body input accessed')
    def __len__(self):raise AssertionError('unselected body input accessed')
class SavedAcq34191Tests(unittest.TestCase):
    def expect(self,r,f):
        c=list(f['snapshots']['34377']);c[29]=True;e=list(f['snapshots']['35778']);e[42]=False;e[39]=True;d=list(f['snapshots']['35802']);d[13]=False
        self.assertEqual({w['node_uid']:w['value']for w in r['writes']},{'34333':tuple(c),'34383':True,'35744':tuple(e),'35784':tuple(d)})
        calls={x['node_uid']:x['input_ports']for x in r['leaf_calls']}
        for uid,face,read in(('35884','35898','35878'),('49501','49515','49466'),('52054','52068','52019')):self.assertIs(calls[uid][face],f['snapshots'][read])
    def test_full_saved_body_and_new_fields(self):
        f=fixture();r=core(data=f);self.expect(r,f);self.assertEqual(r['completed_stages'],['34284','35506','35833','35244']);self.assertTrue(r['selected_body_completed'])
    def test_every_Boolean_snapshot_position(self):
        for uid,n in(('34377',32),('35778',77),('35802',29),('35878',29),('49466',77),('52019',32)):
            for i in range(n):
                f=fixture();v=[False]*n;v[i]=True;f['snapshots'][uid]=tuple(v);self.expect(core(data=f),f)
    def test_all_bounded_stage0_and_stage1_orders(self):
        base=schedule();counts=[]
        for start,end,a,b in((0,4,(0,1,2),(3,)),(5,11,(0,1,2),(3,4,5))):
            n=0
            for order in interleave(a,b):
                f=fixture();self.expect(core(tokens=base[:start]+tuple(base[start+i]for i in order)+base[end:],data=f),f);n+=1
            counts.append(n)
        self.assertEqual(counts,[4,20])
    def test_three_fresh_stage2_read_partial_orders(self):
        base=schedule();n=0
        for reads in((3,6),(6,3)):
            for order in interleave((0,1,2,4,5,7,8,9,10),reads):
                if order.index(3)>order.index(4)or order.index(6)>order.index(7):continue
                f=fixture();self.expect(core(tokens=base[:12]+tuple(base[12+i]for i in order)+base[23:],data=f),f);n+=1
        self.assertEqual(n,28)
    def test_all_canonical_prefixes(self):
        for n in range(28):
            r=core(tokens=schedule()[:n]);self.assertEqual(r['selected_body_completed'],n==27);self.assertEqual(len(r['completed_stages']),sum(i<n for i in(4,11,23,26)))
    def test_all_five_leaf_inflight_boundaries(self):
        for i,t in enumerate(schedule()):
            if type(t)is m.LeafCall:
                r=core(tokens=schedule()[:i+1]);self.assertIn(t.node_uid,r['pending_leaf_uids']);self.assertFalse(r['selected_body_completed'])
    def test_false_no_body_access(self):
        for p in(Poison(),None,{'wrong':object()}):
            r=core(False,tokens=p,data=dict(snapshots=p,leaf_returns=p,unwired_inputs=p,reference_bindings=p));self.assertEqual(r['writes'],[]);self.assertEqual(r['leaf_calls'],[]);self.assertEqual(r['selected_case_frame'],'34255')
    def test_empty_true_no_future_access(self):
        r=core(tokens=(),data=dict(snapshots=Poison(),leaf_returns=Poison(),unwired_inputs=Poison(),reference_bindings=Poison()));self.assertEqual(r['active_stage'],'34284');self.assertEqual(r['leaf_calls'],[])
    def test_exact_three_error_ref_and_fresh_read_identities(self):
        f=fixture();r=core(data=f);self.expect(r,f);calls={x['node_uid']:x['input_ports']for x in r['leaf_calls']}
        for c,i,p,o in(('49501','49509','35884','35895'),('52054','52062','49501','49512'),('52071','52101','52054','52065')):self.assertIs(calls[c][i],f['leaf_returns'][p][o])
        self.assertIs(calls['35884']['35892'],f['unwired_inputs']['35892']);self.assertIs(calls['52071']['52080'],f['unwired_inputs']['52080'])
        for uid,face,constant in(('35884','35886','35851'),('49501','49503','49483'),('52054','52056','52036')):self.assertIs(calls[uid][face],f['reference_bindings'][constant]['native_ref'])
    def test_nonzero_errors_unused_outputs_do_not_gate(self):
        for uid,face in(('35884','35895'),('49501','49512'),('52054','52065'),('52071','52092')):
            f=fixture();e=m.ErrorValue(True,-2147483648,'supplied-fault');f['leaf_returns'][uid][face]=e;r=core(data=f);self.assertTrue(r['selected_body_completed']);self.assertIs(next(x for x in r['leaf_returns']if x['node_uid']==uid)['output_ports'][face],e)
        f=fixture()
        for uid,face in(('35884','35889'),('49501','49506'),('52054','52059')):f['leaf_returns'][uid][face]=Poison()
        self.assertTrue(core(data=f)['selected_body_completed'])
    def test_fresh_snapshots_are_not_replaced_by_written_values(self):
        f=fixture()
        for uid,n in(('34377',32),('35778',77),('35802',29)):f['snapshots'][uid]=tuple([True]*n)
        for uid,n in(('35878',29),('49466',77),('52019',32)):f['snapshots'][uid]=tuple([False]*n)
        r=core(data=f);self.expect(r,f);w={x['node_uid']:x['value']for x in r['writes']};calls={x['node_uid']:x['input_ports']for x in r['leaf_calls']}
        self.assertNotEqual(w['34333'],calls['52054']['52068']);self.assertNotEqual(w['35744'],calls['49501']['49515']);self.assertNotEqual(w['35784'],calls['35884']['35898'])
    def test_Wait100_outer150_unused_EventData_boundary(self):
        r=core();self.assertEqual(next(x for x in r['leaf_calls']if x['node_uid']=='35870')['input_ports'],{'35875':100});self.assertEqual(sum(x.get('value')==150 for x in r['log']if x['kind']=='constant'),1)
        self.assertEqual(r['event_data_consumed_ports'],('34227',));self.assertEqual(r['event_data_unconsumed_ports'],('34215','34218','34221','34224'));self.assertEqual(r['unconsumed_sequence_input_faces'],('34272','34280','34281','35251'))
    def test_every_five_unwired_and_twelve_return_ports_required(self):
        f=fixture();self.assertEqual(len(f['unwired_inputs']),5);self.assertEqual(sum(len(v)for v in f['leaf_returns'].values()),12)
        for face in f['unwired_inputs']:
            g=fixture();g['unwired_inputs'].pop(face)
            with self.assertRaises(ValueError):core(data=g)
        for uid,ports in f['leaf_returns'].items():
            for face in ports:
                g=fixture();g['leaf_returns'][uid].pop(face)
                with self.assertRaises(ValueError):core(data=g)
    def test_wire_stage_duplicate_and_return_order_refusals(self):
        for t in((m.Step('34350'),),(m.Step('34333'),),(m.StageComplete('34284'),),(m.Step('35778'),),schedule()[:12]+(m.LeafCall('35884'),),schedule()[:15]+(m.LeafCall('49501'),),schedule()[:18]+(m.LeafCall('52054'),),schedule()[:19]+(m.LeafCall('52071'),),(m.LeafReturn('35884'),),(m.Step('34377'),m.Step('34377')),schedule()+(m.Step('34377'),)):
            with self.assertRaises(ValueError):core(tokens=t)
    def test_snapshot_boolean_and_token_domain_refusals(self):
        for uid,bad in(('34377',tuple([False]*31)),('35778',tuple([False]*76)),('35802',tuple([0]*29)),('52019',[False]*32),('49466',tuple([None]*77))):
            f=fixture();f['snapshots'][uid]=bad
            with self.assertRaises(TypeError):core(data=f)
        for v in(0,1,None,'True'):
            with self.assertRaises(TypeError):core(new=v)
        for t in(list(schedule()),(object(),),(m.Step(34377),),(m.Step('other'),),(m.Step('34301'),)):
            with self.assertRaises((TypeError,ValueError)):core(tokens=t)
    def test_native_typed_input_and_return_domains(self):
        for uid,face,bad in(('35884','35895',{'status':False,'code':0,'source':''}),('49501','49512',m.ErrorValue(0,0,'')),('52054','52065',m.ErrorValue(False,2147483648,'')),('52071','52074',0),('52071','52077',-2147483649),('52071','52089',None),('35870','35872',-1),('35870','35872',True)):
            f=fixture();f['leaf_returns'][uid][face]=bad
            with self.assertRaises(TypeError):core(data=f)
        for face,bad in(('35892',None),('52083',True),('52086',None),('52098',65536)):
            f=fixture();f['unwired_inputs'][face]=bad
            with self.assertRaises(TypeError):core(data=f)
    def test_all_three_exact_saved_URI_binding_gates(self):
        for uid in('35851','49483','52036'):
            for bad in('missing','wrong_uri','wrong_uid','extra'):
                f=fixture()
                if bad=='missing':f['reference_bindings'].pop(uid)
                elif bad=='wrong_uri':f['reference_bindings'][uid]['saved_uri']='other'
                elif bad=='wrong_uid':f['reference_bindings'][uid]['constant_uid']='52019'
                else:f['reference_bindings'][uid]['extra']=None
                with self.assertRaises(ValueError):core(data=f)
    def test_JSON_full_false_and_DPS_inflight(self):
        p=payload();before=copy.deepcopy(p);r=adapter(p);self.assertEqual(p,before);self.assertTrue(r['selected_body_completed']);w={x['node_uid']:x['value']for x in r['writes']};self.assertIs(w['34333'][29],True);self.assertIs(w['35744'][42],False);self.assertIs(w['35744'][39],True);self.assertIs(w['35784'][13],False)
        p=payload();p.update(new_value=False,schedule=Poison(),snapshots=Poison(),leaf_returns=Poison(),unwired_inputs=Poison(),reference_bindings=Poison());self.assertEqual(adapter(p)['leaf_calls'],[])
        p=payload();p['schedule']=p['schedule'][:14];self.assertEqual(adapter(p)['pending_leaf_uids'],['35884'])
    def test_JSON_exact_version_identity_finite_input_refusals(self):
        for change in(lambda p:p.pop('source_version'),lambda p:p.update(source_version='other'),lambda p:p.update(extra=0),lambda p:p.update(frame_uid='45123'),lambda p:p.update(source_id='APP-02'),lambda p:p.update(new_value=1),lambda p:p['schedule'][0].update(extra=0),lambda p:p['schedule'][0].update(kind='callback'),lambda p:p['snapshots'].update(unknown=[]),lambda p:p['snapshots']['34377'].__setitem__(0,object()),lambda p:p['snapshots']['35878'].__setitem__(0,float('nan')),lambda p:p['unwired_inputs'].update(extra=None),lambda p:p['unwired_inputs'].__setitem__('52080',float('inf')),lambda p:p['reference_bindings']['52036'].update(native_ref=float('-inf'))):
            p=payload();change(p)
            with self.assertRaises((TypeError,ValueError)):adapter(p)
    def test_all_native_default_scheduler_and_whole_gates_false(self):
        r=core()
        for k in('execution_allowed','external_calls_executed','hardware_writes','native_runtime_equivalence','native_callee_equivalence','whole_event_equivalence','whole_vi_equivalence','native_default_qualified','native_ref_interpretation_qualified','native_task_reference_qualified','psp_delivery_qualified','wait_units_or_pulse_duration_qualified','snapshot_equality_qualified','scheduler_qualified','event_selection_qualified','event_acknowledgement_qualified','native_cluster_decode_qualified'):self.assertIs(r[k],False)
if __name__=='__main__':unittest.main()
