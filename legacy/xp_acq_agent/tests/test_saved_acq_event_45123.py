"""Independent original45123 source expectations; inline portable Py3.4 fixtures."""
import copy,importlib.machinery,itertools,json,os,unittest
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
m=importlib.machinery.SourceFileLoader('qualified_acq45123',os.path.join(ROOT,'elyse_agent','saved_acq_event_45123.py')).load_module()
COUNTS=dict(core_calls=0,accepted=0,refused=0,completed_true=0,prefixes=0,false=0,adapter_calls=0,adapter_accepted=0,adapter_refused=0)
# Original saved source lists, independently authored; no core plan lookup.
VOID_PORTS=('46277','46280','46283','46289','46292','46295','46298','46301','46304','46310','46313','46316',
    '54884','54887','54890','54896','54899','54902','54905','54908','54911','54917','54920','54923',
    '52882','52885','52888','52894','52897','52900','20494','20501','20504','20513','20518','20521','45524')
ERROR_OUTPUTS={'46267':'46319','52872':'52879','54874':'54926','2548':'20485','45451':'45463','45475':'45486','45515':'45536'}
def fixture():
    snapshots={'50001':tuple(object()for i in range(8)),'45333':tuple(i%3==0 for i in range(77)),
        '45357':tuple(i%2==0 for i in range(29)),'45445':tuple(i%3==1 for i in range(29)),
        '45469':tuple(i%3==2 for i in range(77))}
    returns={uid:{face:m.ErrorValue(True,-n,'supplied-'+uid)}for n,(uid,face)in enumerate(sorted(ERROR_OUTPUTS.items()),1)}
    returns['46267']['46286']=object();returns['54874']['54893']=object()
    returns['45451']['45457']=object();returns['45475']['45480']=object()
    returns['45515'].update({'45518':False,'45521':9,'45533':'message','45539':'details'})
    returns['45594']={'45596':101}
    unwired={u:object()for u in VOID_PORTS};unwired.update({'46307':m.ErrorValue(False,42,'explicit-first-DAQ-error'),
        '45460':m.ErrorValue(True,43,'explicit-DPS-input-error'),'45527':7,'45530':'supplied handler message','45542':2})
    refs={uid:dict(constant_uid=uid,saved_uri='ni.var.psp://10.20.30.2/SUPERVISION/'+name,native_ref=object())
        for uid,name in(('45391','DPS'),('45409','EPS'))}
    return dict(snapshots=snapshots,leaf_returns=returns,unwired_inputs=unwired,reference_bindings=refs)
def schedule():
    return (m.Step('50001'),m.Step('49179'),m.LeafCall('46267'),m.LeafReturn('46267'),
        m.LeafCall('52872'),m.LeafReturn('52872'),m.LeafCall('54874'),m.LeafReturn('54874'),
        m.LeafCall('2548'),m.LeafReturn('2548'),m.Step('45254'),m.StageComplete('45203'),
        m.Step('45357'),m.Step('45347'),m.Step('45339'),m.Step('45333'),m.Step('45320'),m.Step('45312'),m.StageComplete('45276'),
        m.Step('45445'),m.LeafCall('45451'),m.LeafReturn('45451'),m.Step('45469'),
        m.LeafCall('45475'),m.LeafReturn('45475'),m.LeafCall('45515'),m.LeafReturn('45515'),m.StageComplete('45385'),
        m.LeafCall('45594'),m.LeafReturn('45594'),m.StageComplete('45576'))
def core(new=True,tokens=None,data=None):
    COUNTS['core_calls']+=1
    try:r=m.replay_event(new,schedule()if tokens is None else tokens,**(fixture()if data is None else data))
    except(TypeError,ValueError):COUNTS['refused']+=1;raise
    COUNTS['accepted']+=1;COUNTS['false'if not new else'completed_true'if r['selected_body_completed']else'prefixes']+=1;return r
def payload():
    f=fixture()
    p=dict(source_id='APP-00',source_version='57E1B106EEB57D70124D21CC3FEE775BCADFBF47081F02ED9335A28BAFBC9DD5',event_uid='43',frame_uid='45123',new_value=True,
        schedule=[dict(kind={m.Step:'step',m.LeafCall:'leaf_call',m.LeafReturn:'leaf_return',m.StageComplete:'stage_complete'}[type(t)],uid=t.frame_uid if type(t)is m.StageComplete else t.node_uid)for t in schedule()],
        snapshots={u:list(v)for u,v in f['snapshots'].items()},leaf_returns=f['leaf_returns'],unwired_inputs=f['unwired_inputs'],reference_bindings=f['reference_bindings'])
    p['snapshots']['50001']=[dict(opaque='task-field-'+str(i))for i in range(8)]
    for u in VOID_PORTS:p['unwired_inputs'][u]=dict(opaque='supplied-Void-'+u)
    for u in('46307','45460'):p['unwired_inputs'][u]=dict(p['unwired_inputs'][u]._asdict())
    for uid,face in ERROR_OUTPUTS.items():p['leaf_returns'][uid][face]=dict(p['leaf_returns'][uid][face]._asdict())
    for uid,face in(('46267','46286'),('54874','54893'),('45451','45457'),('45475','45480')):p['leaf_returns'][uid][face]=dict(opaque='unused-return-'+face)
    for uid in p['reference_bindings']:p['reference_bindings'][uid]['native_ref']=dict(opaque='provided-'+uid)
    return p
def adapter(p):
    COUNTS['adapter_calls']+=1
    try:r=m.replay_saved_acq_event_45123(p)
    except(TypeError,ValueError):COUNTS['adapter_refused']+=1;raise
    COUNTS['adapter_accepted']+=1;return r
def interleavings(a,b):
    if not a:yield tuple(b);return
    if not b:yield tuple(a);return
    for tail in interleavings(a[1:],b):yield(a[0],)+tail
    for tail in interleavings(a,b[1:]):yield(b[0],)+tail
class Poison:
    def __iter__(self):raise AssertionError('unselected input accessed')
    def __getitem__(self,k):raise AssertionError('unselected input accessed')
    def __len__(self):raise AssertionError('unselected input accessed')

class SavedAcq45123Tests(unittest.TestCase):
    def expect(self,r,f):
        d=list(f['snapshots']['45357']);d[18]=False
        e=list(f['snapshots']['45333']);e[55]=False;e[52]=True
        self.assertEqual({x['node_uid']:x['value']for x in r['writes']},{'45254':True,'45339':tuple(d),'45312':tuple(e)})
        calls={x['node_uid']:x['input_ports']for x in r['leaf_calls']}
        self.assertIs(calls['46267']['46274'],f['snapshots']['50001'][3]);self.assertIs(calls['54874']['54881'],f['snapshots']['50001'][4])
        self.assertIs(calls['45451']['45466'],f['snapshots']['45445']);self.assertIs(calls['45475']['45489'],f['snapshots']['45469'])
    def test_full_new_source_body(self):
        f=fixture();r=core(data=f);self.expect(r,f)
        self.assertEqual(r['completed_stages'],['45203','45276','45385','45576']);self.assertTrue(r['selected_body_completed'])
        self.assertEqual(r['source_version'],'57E1B106EEB57D70124D21CC3FEE775BCADFBF47081F02ED9335A28BAFBC9DD5')
    def test_every_Boolean_snapshot_position(self):
        for uid,count in(('45333',77),('45357',29),('45445',29),('45469',77)):
            for i in range(count):
                f=fixture();v=[False]*count;v[i]=True;f['snapshots'][uid]=tuple(v);self.expect(core(data=f),f)
    def test_reference_unbundle_positions_and_other_fields(self):
        for shift in range(8):
            f=fixture();refs=f['snapshots']['50001'];f['snapshots']['50001']=refs[shift:]+refs[:shift];self.expect(core(data=f),f)
        f=fixture();refs=list(f['snapshots']['50001'])
        for i in(0,1,2,5,6,7):refs[i]=Poison()
        f['snapshots']['50001']=tuple(refs);self.expect(core(data=f),f)
    def test_all_bounded_within_stage_orders(self):
        base=schedule();counts=[]
        for start,end,chains in((0,11,(tuple(range(10)),(10,))),
            (12,18,((0,1,2),(3,4,5))),(19,27,((0,1,2,4,5,6,7),(3,)))):
            n=0
            for order in interleavings(*chains):
                if start==19 and order.index(3)>order.index(4):continue
                f=fixture();self.expect(core(tokens=base[:start]+tuple(base[start+i]for i in order)+base[end:],data=f),f);n+=1
            counts.append(n)
        self.assertEqual(counts,[11,20,4])
    def test_all_canonical_prefixes(self):
        for n in range(32):
            r=core(tokens=schedule()[:n]);self.assertEqual(r['selected_body_completed'],n==31)
            self.assertEqual(len(r['completed_stages']),sum(i<n for i in(11,18,27,30)))
    def test_all_native_inflight_boundaries(self):
        for i,t in enumerate(schedule()):
            if type(t)is m.LeafCall:
                r=core(tokens=schedule()[:i+1]);self.assertIn(t.node_uid,r['pending_leaf_uids']);self.assertFalse(r['selected_body_completed'])
    def test_false_no_body_access(self):
        for p in(Poison(),None,{'unknown':object()}):
            r=core(False,tokens=p,data=dict(snapshots=p,leaf_returns=p,unwired_inputs=p,reference_bindings=p));self.assertEqual(r['writes'],[]);self.assertEqual(r['leaf_calls'],[]);self.assertEqual(r['selected_case_frame'],'45177')
    def test_empty_true_no_future_access(self):
        r=core(tokens=(),data=dict(snapshots=Poison(),leaf_returns=Poison(),unwired_inputs=Poison(),reference_bindings=Poison()));self.assertEqual(r['active_stage'],'45203');self.assertEqual(r['writes'],[])
    def test_exact_error_and_reference_routing(self):
        f=fixture();r=core(data=f);calls={x['node_uid']:x['input_ports']for x in r['leaf_calls']}
        for consumer,input_,producer,output in(('52872','52891','46267','46319'),('54874','54914','52872','52879'),('2548','20510','54874','54926'),('45475','45483','45451','45463'),('45515','45545','45475','45486')):
            self.assertIs(calls[consumer][input_],f['leaf_returns'][producer][output])
        for uid,face in(('46267','46307'),('45451','45460'),('45515','45524')):self.assertIs(calls[uid][face],f['unwired_inputs'][face])
        self.assertIs(calls['45451']['45453'],f['reference_bindings']['45391']['native_ref']);self.assertIs(calls['45475']['45477'],f['reference_bindings']['45409']['native_ref'])
        for uid,face in(('46267','46286'),('54874','54893'),('45451','45457'),('45475','45480')):
            self.assertIs(next(x for x in r['leaf_returns']if x['node_uid']==uid)['output_ports'][face],f['leaf_returns'][uid][face])
    def test_supplied_Clear_Errors_returns_are_not_inferred(self):
        for e in(m.ErrorValue(True,-2147483648,'not cleared'),m.ErrorValue(False,2147483647,'warning')):
            f=fixture();f['leaf_returns']['52872']['52879']=e;f['leaf_returns']['2548']['20485']=e;r=core(data=f)
            self.assertIs(next(x for x in r['leaf_calls']if x['node_uid']=='54874')['input_ports']['54914'],e);self.assertTrue(r['selected_body_completed'])
    def test_new_fields_preserve_other_positions_and_fresh_reads(self):
        f=fixture();f['snapshots']['45357']=tuple([True]*29);f['snapshots']['45333']=tuple([True]*77)
        f['snapshots']['45445']=tuple([False]*29);f['snapshots']['45469']=tuple([False]*77);r=core(data=f);self.expect(r,f)
        v={x['node_uid']:x['value']for x in r['writes']};self.assertEqual([i for i,x in enumerate(v['45339'])if not x],[18]);self.assertEqual([i for i,x in enumerate(v['45312'])if not x],[55])
        calls={x['node_uid']:x['input_ports']for x in r['leaf_calls']};self.assertNotEqual(calls['45451']['45466'],v['45339']);self.assertNotEqual(calls['45475']['45489'],v['45312'])
    def test_Wait_literal_and_unconsumed_outer150(self):
        r=core();self.assertEqual(next(x for x in r['leaf_calls']if x['node_uid']=='45594')['input_ports'],{'45599':100})
        self.assertEqual(sum(x.get('value')==150 for x in r['log']if x['kind']=='constant'),1)
        self.assertEqual(r['event_data_unconsumed_ports'],('45144','45147','45150','45153'));self.assertEqual(r['unconsumed_sequence_input_faces'],('45194','45195','45196','45197'))
    def test_every_unwired_argument_required(self):
        f=fixture();self.assertEqual(len(f['unwired_inputs']),42)
        for u in f['unwired_inputs']:
            g=fixture();g['unwired_inputs'].pop(u)
            with self.assertRaises(ValueError):core(data=g)
    def test_every_supplied_return_port_required(self):
        f=fixture();self.assertEqual(sum(len(p)for p in f['leaf_returns'].values()),16)
        for uid,ports in f['leaf_returns'].items():
            for face in ports:
                g=fixture();g['leaf_returns'][uid].pop(face)
                with self.assertRaises(ValueError):core(data=g)
    def test_error_wire_and_stage_dependencies_refuse(self):
        for tokens in((m.Step('49179'),),(m.LeafCall('46267'),),(m.LeafCall('52872'),),(m.LeafCall('54874'),),
            (m.LeafCall('2548'),),(m.StageComplete('45203'),),schedule()[:3]+(m.LeafCall('52872'),),
            schedule()[:19]+(m.LeafCall('45451'),),schedule()[:22]+(m.LeafCall('45475'),),
            schedule()[:24]+(m.LeafCall('45515'),),(m.LeafReturn('46267'),),
            (m.Step('50001'),m.Step('50001')),schedule()+(m.Step('50001'),)):
            with self.assertRaises(ValueError):core(tokens=tokens)
    def test_snapshot_and_token_domains_refuse(self):
        for uid,bad in(('50001',tuple([None]*7)),('50001',[None]*8),('45333',tuple([False]*76)),('45357',tuple([0]*29))):
            f=fixture();f['snapshots'][uid]=bad
            with self.assertRaises(TypeError):core(data=f)
        for v in(0,1,None,'True'):
            with self.assertRaises(TypeError):core(new=v)
        for tokens in(list(schedule()),(object(),),(m.Step(50001),),(m.Step('other'),),(m.Step('45611'),)):
            with self.assertRaises((TypeError,ValueError)):core(tokens=tokens)
    def test_native_typed_output_and_unwired_domains_refuse(self):
        for uid,face,bad in(('46267','46319',{'status':False,'code':0,'source':''}),('52872','52879',m.ErrorValue(0,0,'')),
            ('2548','20485',m.ErrorValue(False,2147483648,'')),('54874','54926',m.ErrorValue(False,0,None)),
            ('45515','45518',0),('45515','45521',2147483648),('45515','45533',None),('45594','45596',-1),('45594','45596',True)):
            f=fixture();f['leaf_returns'][uid][face]=bad
            with self.assertRaises(TypeError):core(data=f)
        for face,bad in(('46307',None),('45460',m.ErrorValue(True,-2147483649,'')),('45527',True),('45530',None),('45542',65536)):
            f=fixture();f['unwired_inputs'][face]=bad
            with self.assertRaises(TypeError):core(data=f)
    def test_reference_bindings_refuse(self):
        for uid in('45391','45409'):
            for change in('missing','wrong_uri','wrong_constant','extra'):
                f=fixture()
                if change=='missing':f['reference_bindings'].pop(uid)
                elif change=='wrong_uri':f['reference_bindings'][uid]['saved_uri']='other'
                elif change=='wrong_constant':f['reference_bindings'][uid]['constant_uid']='31500'
                else:f['reference_bindings'][uid]['extra']=None
                with self.assertRaises(ValueError):core(data=f)
    def test_JSON_full_false_and_native_inflight(self):
        p=payload();before=copy.deepcopy(p);r=adapter(p);self.assertEqual(p,before);self.assertTrue(r['selected_body_completed'])
        v={x['node_uid']:x['value']for x in r['writes']};self.assertIs(v['45339'][18],False);self.assertIs(v['45312'][55],False);self.assertIs(v['45312'][52],True)
        calls={x['node_uid']:x['input_ports']for x in r['leaf_calls']};self.assertEqual(calls['45475']['45483'],p['leaf_returns']['45451']['45463'])
        p=payload();p.update(new_value=False,schedule=Poison(),snapshots=Poison(),leaf_returns=Poison(),unwired_inputs=Poison(),reference_bindings=Poison());self.assertEqual(adapter(p)['leaf_calls'],[])
        p=payload();p['schedule']=p['schedule'][:3];self.assertEqual(adapter(p)['pending_leaf_uids'],['46267'])
    def test_JSON_strict_identity_finite_objects_refuse(self):
        for mutate in(lambda p:p.update(extra=0),lambda p:p.pop('source_version'),lambda p:p.update(source_version='other'),lambda p:p.pop('reference_bindings'),lambda p:p.update(frame_uid='23449'),
            lambda p:p.update(source_id='APP-02'),lambda p:p.update(new_value=1),lambda p:p['schedule'][0].update(extra=0),
            lambda p:p['schedule'][0].update(kind='callback'),lambda p:p['snapshots'].update(unknown=[]),
            lambda p:p['snapshots']['50001'].__setitem__(3,object()),lambda p:p['snapshots']['50001'].__setitem__(4,float('nan')),
            lambda p:p['unwired_inputs'].update(extra=None),lambda p:p['unwired_inputs'].__setitem__('20501',float('inf')),
            lambda p:p['reference_bindings']['45409'].update(native_ref=float('-inf'))):
            p=payload();mutate(p)
            with self.assertRaises((TypeError,ValueError)):adapter(p)
    def test_all_whole_native_and_callee_gates_false(self):
        r=core()
        for key in('execution_allowed','external_calls_executed','hardware_writes','native_runtime_equivalence','native_callee_equivalence',
            'whole_event_equivalence','whole_vi_equivalence','native_default_qualified','native_ref_interpretation_qualified',
            'native_task_reference_qualified','psp_delivery_qualified','wait_units_or_pulse_duration_qualified','snapshot_equality_qualified',
            'scheduler_qualified','event_selection_qualified','event_acknowledgement_qualified','native_cluster_decode_qualified'):self.assertIs(r[key],False)

if __name__=='__main__':unittest.main()
