"""Fresh31552 source expectations; portable inline supplied fixtures, no native calls."""
import copy,importlib.machinery,json,os,unittest
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
m=importlib.machinery.SourceFileLoader('fresh31552core',os.path.join(ROOT,'elyse_agent','saved_acq_event_31552.py')).load_module()
COUNTS=dict(core_calls=0,accepted=0,refused=0,completed_true=0,prefixes=0,false=0,adapter_calls=0,adapter_accepted=0,adapter_refused=0)
def fixture():
 s={u:tuple(i%3==offset for i in range(n))for u,n,offset in(('33106',32,0),('33201',32,1),('33410',29,2),('33499',29,0),('33571',77,2),('33594',32,1))}
 r={u:{e:m.ErrorValue(True,-i,'supplied-'+u),ref:object()}for i,(u,e,ref)in enumerate((('33509','33564','33544'),('33577','33588','33582'),('33600','33611','33605')),1)}
 r.update({'33144':{'33146':4294967295},'33985':{'34149':0},'33617':{'33626':False,'33631':-9,'33826':'message','33836':m.ErrorValue(True,31,'unused-handler-error'),'33839':'details'}})
 u={'33561':m.ErrorValue(True,43,'supplied-first-error'),'33635':object(),'33659':7,'33753':'explicit handler text','33842':2}
 refs={uid:dict(constant_uid=uid,saved_uri='ni.var.psp://10.20.30.2/SUPERVISION/'+name,native_ref=object())for uid,name in(('33444','DPS'),('33462','EPS'),('33481','C4_OUT_DIO96'))}
 return dict(snapshots=s,leaf_returns=r,unwired_inputs=u,reference_bindings=refs)
def schedule():
 return(m.Step('33106'),m.Step('33095'),m.Step('33041'),m.Step('33124'),m.LeafCall('33144'),m.LeafReturn('33144'),m.StageComplete('32931'),
  m.Step('33201'),m.Step('33191'),m.Step('33185'),m.StageComplete('33169'),
  m.Step('33410'),m.Step('33400'),m.Step('33392'),m.StageComplete('33217'),
  m.Step('33499'),m.LeafCall('33509'),m.LeafReturn('33509'),m.Step('33571'),m.LeafCall('33577'),m.LeafReturn('33577'),
  m.Step('33594'),m.LeafCall('33600'),m.LeafReturn('33600'),m.LeafCall('33617'),m.LeafReturn('33617'),m.StageComplete('33438'),
  m.LeafCall('33985'),m.LeafReturn('33985'),m.StageComplete('33886'))
def core(new=True,tokens=None,data=None):
 COUNTS['core_calls']+=1
 try:r=m.replay_event(new,schedule()if tokens is None else tokens,**(fixture()if data is None else data))
 except(TypeError,ValueError):COUNTS['refused']+=1;raise
 COUNTS['accepted']+=1;COUNTS['false'if not new else'completed_true'if r['selected_body_completed']else'prefixes']+=1;return r
def payload():
 f=fixture();p=dict(source_id='APP-00',source_version='57E1B106EEB57D70124D21CC3FEE775BCADFBF47081F02ED9335A28BAFBC9DD5',event_uid='43',frame_uid='31552',new_value=True,
  schedule=[dict(kind={m.Step:'step',m.LeafCall:'leaf_call',m.LeafReturn:'leaf_return',m.StageComplete:'stage_complete'}[type(t)],uid=t.frame_uid if type(t)is m.StageComplete else t.node_uid)for t in schedule()],snapshots={u:list(v)for u,v in f['snapshots'].items()},leaf_returns=f['leaf_returns'],unwired_inputs=f['unwired_inputs'],reference_bindings=f['reference_bindings'])
 p['unwired_inputs']['33561']=dict(p['unwired_inputs']['33561']._asdict());p['unwired_inputs']['33635']={'opaque':'supplied-Void-33635'}
 for u,e,r in(('33509','33564','33544'),('33577','33588','33582'),('33600','33611','33605')):
  p['leaf_returns'][u][e]=dict(p['leaf_returns'][u][e]._asdict());p['leaf_returns'][u][r]={'opaque':'unused-'+r}
 p['leaf_returns']['33617']['33836']=dict(p['leaf_returns']['33617']['33836']._asdict())
 for u in p['reference_bindings']:p['reference_bindings'][u]['native_ref']={'opaque':'supplied-'+u}
 return p
def adapter(p):
 COUNTS['adapter_calls']+=1
 try:r=m.replay_saved_acq_event_31552(p)
 except(TypeError,ValueError):COUNTS['adapter_refused']+=1;raise
 COUNTS['adapter_accepted']+=1;return r
def interleave(a,b):
 if not a:yield tuple(b);return
 if not b:yield tuple(a);return
 for t in interleave(a[1:],b):yield(a[0],)+t
 for t in interleave(a,b[1:]):yield(b[0],)+t
class Poison:
 def __iter__(self):raise AssertionError('unselected input read')
 def __len__(self):raise AssertionError('unselected input read')
 def __getitem__(self,k):raise AssertionError('unselected input read')
class SavedAcq31552Tests(unittest.TestCase):
 def expect(self,r,f):
  first=list(f['snapshots']['33106']);first[20]=True;second=list(f['snapshots']['33201']);second[20]=False;dps=list(f['snapshots']['33410']);dps[16]=False
  self.assertEqual({w['node_uid']:w['value']for w in r['writes']},{'33041':tuple(first),'33124':True,'33185':tuple(second),'33392':tuple(dps)})
  calls={c['node_uid']:c['input_ports']for c in r['leaf_calls']}
  for uid,face,read in(('33509','33568','33499'),('33577','33591','33571'),('33600','33614','33594')):self.assertIs(calls[uid][face],f['snapshots'][read])
  self.assertEqual(calls['33144'],{'33149':150});self.assertEqual(calls['33985'],{'34152':100})
 def test_full_five_stages_fresh_projections(self):
  f=fixture();r=core(data=f);self.expect(r,f);self.assertEqual(r['completed_stages'],['32931','33169','33217','33438','33886']);self.assertTrue(r['selected_body_completed']);self.assertEqual(len(schedule()),30)
 def test_every_snapshot_Boolean_position(self):
  for uid,n in(('33106',32),('33201',32),('33410',29),('33499',29),('33571',77),('33594',32)):
   for i in range(n):
    f=fixture();v=[False]*n;v[i]=True;f['snapshots'][uid]=tuple(v);self.expect(core(data=f),f)
 def test_C4_phase_and_DPS_adjacent_fields(self):
  f=fixture();f['snapshots']['33106']=tuple([False]*32);f['snapshots']['33201']=tuple([True]*32);f['snapshots']['33410']=tuple([True]*29);r=core(data=f);self.expect(r,f)
  w={x['node_uid']:x['value']for x in r['writes']};self.assertEqual(w['33041'][19:22],(False,True,False));self.assertEqual(w['33185'][19:22],(True,False,True));self.assertEqual(w['33392'][15:18],(True,False,True))
 def test_sixty_stage0_orders_with_Wait_overlap(self):
  base=schedule();n=0
  for ab in interleave((0,1,2),(3,)):
   for order in interleave(ab,(4,5)):
    f=fixture();self.expect(core(tokens=tuple(base[i]for i in order)+base[6:],data=f),f);n+=1
  self.assertEqual(n,60)
 def test_twenty_eight_publication_read_orders(self):
  base=schedule();n=0
  for reads in((3,6),(6,3)):
   for order in interleave((0,1,2,4,5,7,8,9,10),reads):
    if order.index(3)>order.index(4)or order.index(6)>order.index(7):continue
    f=fixture();self.expect(core(tokens=base[:15]+tuple(base[15+i]for i in order)+base[26:],data=f),f);n+=1
  self.assertEqual(n,28)
 def test_all_canonical_prefixes(self):
  for n in range(31):
   r=core(tokens=schedule()[:n]);self.assertEqual(r['selected_body_completed'],n==30);self.assertEqual(len(r['completed_stages']),sum(i<n for i in(6,10,14,26,29)))
 def test_six_inflight_leaves(self):
  for i,t in enumerate(schedule()):
   if type(t)is m.LeafCall:
    r=core(tokens=schedule()[:i+1]);self.assertIn(t.node_uid,r['pending_leaf_uids']);self.assertFalse(r['selected_body_completed'])
 def test_false_and_empty_nonaccess(self):
  for p in(Poison(),None,{'bad':object()}):
   r=core(False,tokens=p,data=dict(snapshots=p,leaf_returns=p,unwired_inputs=p,reference_bindings=p));self.assertEqual(r['leaf_calls'],[]);self.assertEqual(r['writes'],[]);self.assertEqual(r['selected_case_frame'],'32851');self.assertFalse(any(x['kind']=='border_transfer'for x in r['log']))
  r=core(tokens=(),data=dict(snapshots=Poison(),leaf_returns=Poison(),unwired_inputs=Poison(),reference_bindings=Poison()));self.assertEqual(r['active_stage'],'32931');self.assertEqual(len([x for x in r['log']if x['kind']=='border_transfer']),5)
 def test_error_and_reference_identity_order(self):
  f=fixture();r=core(data=f);calls={x['node_uid']:x['input_ports']for x in r['leaf_calls']}
  for uid,face,p,o in(('33577','33585','33509','33564'),('33600','33608','33577','33588'),('33617','33845','33600','33611')):self.assertIs(calls[uid][face],f['leaf_returns'][p][o])
  for uid,face,ref in(('33509','33512','33444'),('33577','33579','33462'),('33600','33602','33481')):self.assertIs(calls[uid][face],f['reference_bindings'][ref]['native_ref'])
  self.assertIs(calls['33509']['33561'],f['unwired_inputs']['33561']);self.assertIs(calls['33617']['33635'],f['unwired_inputs']['33635']);self.assertEqual([c['node_uid']for c in r['leaf_calls']],['33144','33509','33577','33600','33617','33985'])
 def test_fresh_snapshots_not_write_caches(self):
  f=fixture();f['snapshots']['33106']=tuple([False]*32);f['snapshots']['33201']=tuple([True]*32);f['snapshots']['33410']=tuple([True]*29);f['snapshots']['33499']=tuple([False]*29);f['snapshots']['33594']=tuple([False]*32);r=core(data=f);self.expect(r,f)
  self.assertNotEqual(r['writes'][0]['value'],r['writes'][2]['value']);self.assertNotEqual(r['writes'][3]['value'],f['snapshots']['33499'])
 def test_consumed_outer150_exact_border_path(self):
  r=core();path=[x['source_path']for x in r['log']if x['kind']=='border_transfer']
  self.assertEqual(path,[('wire','34171','34171','32837','32844','34198'),('paired','32837','32844','32848','32845'),('wire','32837','32848','32863','32872','34162'),('paired','32863','32872','32881','32873'),('wire','32863','32881','33144','33149','33154')]);self.assertEqual(r['unconsumed_sequence_input_faces'],('32900','32902','32903','32904'));self.assertEqual(r['event_data_consumed_ports'],('32807',))
 def test_nonzero_unused_errors_not_stage_gates(self):
  for uid,e in(('33509','33564'),('33577','33588'),('33600','33611'),('33617','33836')):
   f=fixture();error=m.ErrorValue(True,-2147483648,'fault');f['leaf_returns'][uid][e]=error;r=core(data=f);self.assertTrue(r['selected_body_completed']);self.assertIs(next(x for x in r['leaf_returns']if x['node_uid']==uid)['output_ports'][e],error)
  f=fixture()
  for uid,face in(('33509','33544'),('33577','33582'),('33600','33605')):f['leaf_returns'][uid][face]=Poison()
  self.assertTrue(core(data=f)['selected_body_completed'])
 def test_every_required_unwired_and_return_face(self):
  f=fixture();self.assertEqual(len(f['unwired_inputs']),5);self.assertEqual(sum(len(v)for v in f['leaf_returns'].values()),13)
  for face in f['unwired_inputs']:
   g=fixture();g['unwired_inputs'].pop(face)
   with self.assertRaises(ValueError):core(data=g)
  for uid,ports in f['leaf_returns'].items():
   for face in ports:
    g=fixture();g['leaf_returns'][uid].pop(face)
    with self.assertRaises(ValueError):core(data=g)
 def test_schedule_invalid_dependencies_and_old_frame(self):
  base=schedule();bad=[(m.StageComplete('32931'),),(m.Step('33095'),),(m.Step('33041'),),(m.LeafReturn('33144'),),(m.LeafCall('33509'),),(m.Step('43757'),),base+(m.Step('33106'),),base[:1]+(m.Step('33106'),),base[:7]+(m.StageComplete('33169'),),base[:17]+(m.LeafCall('33577'),),base[:27]+(m.StageComplete('33886'),),base[:27]+(m.LeafReturn('33985'),),list(base),('Step',),(m.Step(33106),)]
  for tokens in bad:
   with self.assertRaises((TypeError,ValueError)):core(tokens=tokens)
 def test_typed_Boolean_and_integer_error_boundaries(self):
  for new in(0,1,None,'True'):
   with self.assertRaises(TypeError):core(new)
  for uid,n in(('33106',32),('33201',32),('33410',29),('33499',29),('33571',77),('33594',32)):
   for value in(tuple([False]*(n-1)),tuple([False]*n+[True]),tuple([0]*n)):
    f=fixture();f['snapshots'][uid]=value
    with self.assertRaises(TypeError):core(data=f)
  for uid,face in(('33144','33146'),('33985','34149')):
   for value in(-1,4294967296,True,1.0):
    f=fixture();f['leaf_returns'][uid][face]=value
    with self.assertRaises(TypeError):core(data=f)
  for face,value in(('33659',2147483648),('33842',-1),('33842',65536),('33753',1),('33561',m.ErrorValue(1,0,'x')),('33561',m.ErrorValue(False,2147483648,'x'))):
   f=fixture();f['unwired_inputs'][face]=value
   with self.assertRaises(TypeError):core(data=f)
 def test_exact_saved_URI_and_return_keys(self):
  for uid in('33444','33462','33481'):
   f=fixture();f['reference_bindings'][uid]['saved_uri']='other'
   with self.assertRaises(ValueError):core(data=f)
  f=fixture();f['leaf_returns']['33144']['extra']=0
  with self.assertRaises(ValueError):core(data=f)
 def test_JSON_full_false_prefix_equivalence(self):
  p=payload();r=adapter(p);self.assertTrue(r['selected_body_completed']);self.assertEqual([x['value'][20]for x in r['writes']if x['node_uid']in('33041','33185')],[True,False]);self.assertEqual(r['leaf_calls'][0]['input_ports'],{'33149':150})
  p=payload();p.update(new_value=False,schedule=Poison(),snapshots=Poison(),leaf_returns=Poison(),unwired_inputs=Poison(),reference_bindings=Poison());self.assertEqual(adapter(p)['writes'],[])
  p=payload();p['schedule']=p['schedule'][:5];r=adapter(p);self.assertEqual(r['pending_leaf_uids'],['33144']);self.assertEqual(r['completed_stages'],[])
 def test_JSON_wrong_version_identity_schema_finite_domains(self):
  changes=[lambda p:p.update(source_version='other'),lambda p:p.pop('source_version'),lambda p:p.update(frame_uid='43634'),lambda p:p.update(event_uid='44'),lambda p:p.update(source_id='APP-01'),lambda p:p.update(extra=1),lambda p:p.update(new_value=1),lambda p:p['schedule'][0].update(extra=1),lambda p:p['schedule'][0].update(uid='43757'),lambda p:p['snapshots'].update(other=[]),lambda p:p['snapshots']['33106'].__setitem__(0,1),lambda p:p['reference_bindings']['33444'].update(native_ref=float('nan')),lambda p:p['unwired_inputs'].update({'33635':object()}),lambda p:p['leaf_returns']['33144'].update({'33146':-1})]
  for change in changes:
   p=payload();change(p)
   with self.assertRaises((TypeError,ValueError)):adapter(p)
 def test_all_native_whole_default_limits_false(self):
  r=core()
  for k in m.LIMITS:self.assertIs(r[k],False)
if __name__=='__main__':unittest.main()
