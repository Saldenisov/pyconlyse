"""Fresh43634 independent saved expectations and portable inline Py3.4 fixtures."""
import copy,importlib.machinery,json,os,unittest
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
m=importlib.machinery.SourceFileLoader('new43634core',os.path.join(ROOT,'elyse_agent','saved_acq_event_43634.py')).load_module()
COUNTS=dict(core_calls=0,accepted=0,refused=0,completed_true=0,prefixes=0,false=0,adapter_calls=0,adapter_accepted=0,adapter_refused=0)
def fixture():
    snapshots={u:tuple(i%3==s for i in range(n))for u,n,s in(('43757',32,0),('43842',77,1),('43866',29,2),('43956',29,0),('43979',77,2),('44002',32,1))}
    returns={u:{face:m.ErrorValue(True,-i,'supplied-'+u),ref:object()}for i,(u,face,ref)in enumerate((('43962','43973','43967'),('43985','43996','43990'),('44008','44019','44013')),1)}
    returns['44025']={'44028':False,'44031':-9,'44043':'message','44046':m.ErrorValue(False,31,'unused-handler-error'),'44049':'details'}
    returns['44107']={'44109':4294967295}
    unwired={'43970':m.ErrorValue(True,43,'supplied-DPS-error'),'44034':object(),'44037':7,'44040':'explicit handler message','44052':2}
    refs={u:dict(constant_uid=u,saved_uri='ni.var.psp://10.20.30.2/SUPERVISION/'+name,native_ref=object())for u,name in(('43902','DPS'),('43920','EPS'),('43938','C4_OUT_DIO96'))}
    return dict(snapshots=snapshots,leaf_returns=returns,unwired_inputs=unwired,reference_bindings=refs)
def schedule():
    return(m.Step('43757'),m.Step('43746'),m.Step('43738'),m.Step('43763'),m.StageComplete('43712'),
        m.Step('43866'),m.Step('43856'),m.Step('43848'),m.Step('43842'),m.Step('43829'),m.Step('43821'),m.StageComplete('43785'),
        m.Step('43956'),m.LeafCall('43962'),m.LeafReturn('43962'),m.Step('43979'),m.LeafCall('43985'),m.LeafReturn('43985'),
        m.Step('44002'),m.LeafCall('44008'),m.LeafReturn('44008'),m.LeafCall('44025'),m.LeafReturn('44025'),m.StageComplete('43894'),
        m.LeafCall('44107'),m.LeafReturn('44107'),m.StageComplete('44089'))
def core(new=True,tokens=None,data=None):
    COUNTS['core_calls']+=1
    try:r=m.replay_event(new,schedule()if tokens is None else tokens,**(fixture()if data is None else data))
    except(TypeError,ValueError):COUNTS['refused']+=1;raise
    COUNTS['accepted']+=1;COUNTS['false'if not new else'completed_true'if r['selected_body_completed']else'prefixes']+=1;return r
def payload():
    f=fixture();p=dict(source_id='APP-00',source_version='57E1B106EEB57D70124D21CC3FEE775BCADFBF47081F02ED9335A28BAFBC9DD5',event_uid='43',frame_uid='43634',new_value=True,
        schedule=[dict(kind={m.Step:'step',m.LeafCall:'leaf_call',m.LeafReturn:'leaf_return',m.StageComplete:'stage_complete'}[type(t)],uid=t.frame_uid if type(t)is m.StageComplete else t.node_uid)for t in schedule()],
        snapshots={u:list(v)for u,v in f['snapshots'].items()},leaf_returns=f['leaf_returns'],unwired_inputs=f['unwired_inputs'],reference_bindings=f['reference_bindings'])
    p['unwired_inputs']['43970']=dict(p['unwired_inputs']['43970']._asdict());p['unwired_inputs']['44034']={'opaque':'supplied-Void-44034'}
    for u,e,r in(('43962','43973','43967'),('43985','43996','43990'),('44008','44019','44013')):
        p['leaf_returns'][u][e]=dict(p['leaf_returns'][u][e]._asdict());p['leaf_returns'][u][r]={'opaque':'unused-'+r}
    p['leaf_returns']['44025']['44046']=dict(p['leaf_returns']['44025']['44046']._asdict())
    for u in p['reference_bindings']:p['reference_bindings'][u]['native_ref']={'opaque':'provided-'+u}
    return p
def adapter(p):
    COUNTS['adapter_calls']+=1
    try:r=m.replay_saved_acq_event_43634(p)
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
class SavedAcq43634Tests(unittest.TestCase):
    def expect(self,r,f):
        c=list(f['snapshots']['43757']);c[29]=False;e=list(f['snapshots']['43842']);e[42]=True;e[39]=False;d=list(f['snapshots']['43866']);d[14]=False
        self.assertEqual({w['node_uid']:w['value']for w in r['writes']},{'43738':tuple(c),'43763':True,'43821':tuple(e),'43848':tuple(d)})
        calls={x['node_uid']:x['input_ports']for x in r['leaf_calls']}
        for uid,face,read in(('43962','43976','43956'),('43985','43999','43979'),('44008','44022','44002')):self.assertIs(calls[uid][face],f['snapshots'][read])
    def test_full_saved_body_and_new_fields(self):
        f=fixture();r=core(data=f);self.expect(r,f);self.assertEqual(r['completed_stages'],['43712','43785','43894','44089']);self.assertTrue(r['selected_body_completed'])
    def test_original_false_C4_true_EPS_and_adjacent_DPS_field_preserved(self):
        f=fixture();f['snapshots']['43757']=tuple([True]*32);f['snapshots']['43842']=tuple([True]*77);f['snapshots']['43866']=tuple([True]*29)
        r=core(data=f);w={x['node_uid']:x['value']for x in r['writes']}
        self.assertIs(w['43738'][29],False);self.assertIs(w['43821'][42],True);self.assertIs(w['43821'][39],False)
        self.assertIs(w['43848'][14],False);self.assertIs(w['43848'][13],True);self.assertIs(w['43763'],True)
    def test_every_Boolean_snapshot_position(self):
        for uid,n in(('43757',32),('43842',77),('43866',29),('43956',29),('43979',77),('44002',32)):
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
            r=core(False,tokens=p,data=dict(snapshots=p,leaf_returns=p,unwired_inputs=p,reference_bindings=p));self.assertEqual(r['writes'],[]);self.assertEqual(r['leaf_calls'],[]);self.assertEqual(r['selected_case_frame'],'43689')
    def test_empty_true_no_future_access(self):
        r=core(tokens=(),data=dict(snapshots=Poison(),leaf_returns=Poison(),unwired_inputs=Poison(),reference_bindings=Poison()));self.assertEqual(r['active_stage'],'43712');self.assertEqual(r['leaf_calls'],[])
    def test_exact_three_error_ref_and_fresh_read_identities(self):
        f=fixture();r=core(data=f);self.expect(r,f);calls={x['node_uid']:x['input_ports']for x in r['leaf_calls']}
        for c,i,p,o in(('43985','43993','43962','43973'),('44008','44016','43985','43996'),('44025','44055','44008','44019')):self.assertIs(calls[c][i],f['leaf_returns'][p][o])
        self.assertIs(calls['43962']['43970'],f['unwired_inputs']['43970']);self.assertIs(calls['44025']['44034'],f['unwired_inputs']['44034'])
        for uid,face,constant in(('43962','43964','43902'),('43985','43987','43920'),('44008','44010','43938')):self.assertIs(calls[uid][face],f['reference_bindings'][constant]['native_ref'])
    def test_nonzero_errors_unused_outputs_do_not_gate(self):
        for uid,face in(('43962','43973'),('43985','43996'),('44008','44019'),('44025','44046')):
            f=fixture();e=m.ErrorValue(True,-2147483648,'supplied-fault');f['leaf_returns'][uid][face]=e;r=core(data=f);self.assertTrue(r['selected_body_completed']);self.assertIs(next(x for x in r['leaf_returns']if x['node_uid']==uid)['output_ports'][face],e)
        f=fixture()
        for uid,face in(('43962','43967'),('43985','43990'),('44008','44013')):f['leaf_returns'][uid][face]=Poison()
        self.assertTrue(core(data=f)['selected_body_completed'])
    def test_fresh_snapshots_are_not_replaced_by_written_values(self):
        f=fixture()
        for uid,n in(('43757',32),('43842',77),('43866',29)):f['snapshots'][uid]=tuple([True]*n)
        for uid,n in(('43956',29),('43979',77),('44002',32)):f['snapshots'][uid]=tuple([False]*n)
        r=core(data=f);self.expect(r,f);w={x['node_uid']:x['value']for x in r['writes']};calls={x['node_uid']:x['input_ports']for x in r['leaf_calls']}
        self.assertNotEqual(w['43738'],calls['44008']['44022']);self.assertNotEqual(w['43821'],calls['43985']['43999']);self.assertNotEqual(w['43848'],calls['43962']['43976'])
    def test_Wait100_outer150_unused_EventData_boundary(self):
        r=core();self.assertEqual(next(x for x in r['leaf_calls']if x['node_uid']=='44107')['input_ports'],{'44112':100});self.assertEqual(sum(x.get('value')==150 for x in r['log']if x['kind']=='constant'),1)
        self.assertEqual(r['event_data_consumed_ports'],('43668',));self.assertEqual(r['event_data_unconsumed_ports'],('43656','43659','43662','43665'));self.assertEqual(r['unconsumed_sequence_input_faces'],('43706','43707','43708','43709'))
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
        for t in((m.Step('43746'),),(m.Step('43738'),),(m.StageComplete('43712'),),(m.Step('43842'),),schedule()[:12]+(m.LeafCall('43962'),),schedule()[:15]+(m.LeafCall('43985'),),schedule()[:18]+(m.LeafCall('44008'),),schedule()[:19]+(m.LeafCall('44025'),),(m.LeafReturn('43962'),),(m.Step('43757'),m.Step('43757')),schedule()+(m.Step('43757'),)):
            with self.assertRaises(ValueError):core(tokens=t)
    def test_snapshot_boolean_and_token_domain_refusals(self):
        for uid,bad in(('43757',tuple([False]*31)),('43842',tuple([False]*76)),('43866',tuple([0]*29)),('44002',[False]*32),('43979',tuple([None]*77))):
            f=fixture();f['snapshots'][uid]=bad
            with self.assertRaises(TypeError):core(data=f)
        for v in(0,1,None,'True'):
            with self.assertRaises(TypeError):core(new=v)
        for t in(list(schedule()),(object(),),(m.Step(43757),),(m.Step('other'),),(m.Step('43718'),)):
            with self.assertRaises((TypeError,ValueError)):core(tokens=t)
    def test_native_typed_input_and_return_domains(self):
        for uid,face,bad in(('43962','43973',{'status':False,'code':0,'source':''}),('43985','43996',m.ErrorValue(0,0,'')),('44008','44019',m.ErrorValue(False,2147483648,'')),('44025','44028',0),('44025','44031',-2147483649),('44025','44043',None),('44107','44109',-1),('44107','44109',True)):
            f=fixture();f['leaf_returns'][uid][face]=bad
            with self.assertRaises(TypeError):core(data=f)
        for face,bad in(('43970',None),('44037',True),('44040',None),('44052',65536)):
            f=fixture();f['unwired_inputs'][face]=bad
            with self.assertRaises(TypeError):core(data=f)
    def test_all_three_exact_saved_URI_binding_gates(self):
        for uid in('43902','43920','43938'):
            for bad in('missing','wrong_uri','wrong_uid','extra'):
                f=fixture()
                if bad=='missing':f['reference_bindings'].pop(uid)
                elif bad=='wrong_uri':f['reference_bindings'][uid]['saved_uri']='other'
                elif bad=='wrong_uid':f['reference_bindings'][uid]['constant_uid']='44002'
                else:f['reference_bindings'][uid]['extra']=None
                with self.assertRaises(ValueError):core(data=f)
    def test_JSON_full_false_and_DPS_inflight(self):
        p=payload();before=copy.deepcopy(p);r=adapter(p);self.assertEqual(p,before);self.assertTrue(r['selected_body_completed']);w={x['node_uid']:x['value']for x in r['writes']};self.assertIs(w['43738'][29],False);self.assertIs(w['43821'][42],True);self.assertIs(w['43821'][39],False);self.assertIs(w['43848'][14],False)
        p=payload();p.update(new_value=False,schedule=Poison(),snapshots=Poison(),leaf_returns=Poison(),unwired_inputs=Poison(),reference_bindings=Poison());self.assertEqual(adapter(p)['leaf_calls'],[])
        p=payload();p['schedule']=p['schedule'][:14];self.assertEqual(adapter(p)['pending_leaf_uids'],['43962'])
    def test_JSON_exact_version_identity_finite_input_refusals(self):
        for change in(lambda p:p.pop('source_version'),lambda p:p.update(source_version='other'),lambda p:p.update(extra=0),lambda p:p.update(frame_uid='45123'),lambda p:p.update(source_id='APP-02'),lambda p:p.update(new_value=1),lambda p:p['schedule'][0].update(extra=0),lambda p:p['schedule'][0].update(kind='callback'),lambda p:p['snapshots'].update(unknown=[]),lambda p:p['snapshots']['43757'].__setitem__(0,object()),lambda p:p['snapshots']['43956'].__setitem__(0,float('nan')),lambda p:p['unwired_inputs'].update(extra=None),lambda p:p['unwired_inputs'].__setitem__('44034',float('inf')),lambda p:p['reference_bindings']['43938'].update(native_ref=float('-inf'))):
            p=payload();change(p)
            with self.assertRaises((TypeError,ValueError)):adapter(p)
    def test_all_native_default_scheduler_and_whole_gates_false(self):
        r=core()
        for k in('execution_allowed','external_calls_executed','hardware_writes','native_runtime_equivalence','native_callee_equivalence','whole_event_equivalence','whole_vi_equivalence','native_default_qualified','native_ref_interpretation_qualified','native_task_reference_qualified','psp_delivery_qualified','wait_units_or_pulse_duration_qualified','snapshot_equality_qualified','scheduler_qualified','event_selection_qualified','event_acknowledgement_qualified','native_cluster_decode_qualified'):self.assertIs(r[k],False)
if __name__=='__main__':unittest.main()
