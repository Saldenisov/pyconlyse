"""Fresh48846 independent source expectations; portable inline supplied fixtures."""
import copy,importlib.machinery,json,os,unittest
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
m=importlib.machinery.SourceFileLoader('fresh48846core',os.path.join(ROOT,'elyse_agent','saved_acq_event_48846.py')).load_module()
COUNTS=dict(core_calls=0,accepted=0,refused=0,completed_true=0,prefixes=0,false=0,adapter_calls=0,adapter_accepted=0,adapter_refused=0)
def fixture():
 s={u:tuple(i%3==offset for i in range(n))for u,n,offset in(('54039',32,0),('54110',32,1),('54186',77,1),('54210',29,2),('35726',29,0),('47280',77,2),('47323',32,1))}
 r={u:{e:m.ErrorValue(True,-i,'supplied-'+u),ref:object()}for i,(u,e,ref)in enumerate((('47263','47274','47268'),('47306','47317','47311'),('47349','47360','47354')),1)}
 r.update({'54053':{'54055':4294967295},'50582':{'50585':0},'47366':{'47369':False,'47372':-9,'47384':'message','47387':m.ErrorValue(True,31,'unused-handler-error'),'47390':'details'}})
 u={'47271':m.ErrorValue(True,43,'supplied-first-error'),'47375':object(),'47378':7,'47381':'explicit handler text','47393':2}
 refs={uid:dict(constant_uid=uid,saved_uri='ni.var.psp://10.20.30.2/SUPERVISION/'+name,native_ref=object())for uid,name in(('47245','DPS'),('47290','EPS'),('47333','C4_OUT_DIO96'))}
 return dict(snapshots=s,leaf_returns=r,unwired_inputs=u,reference_bindings=refs)
def schedule():
 return(m.Step('54039'),m.Step('54029'),m.Step('54021'),m.Step('54045'),m.LeafCall('54053'),m.LeafReturn('54053'),m.StageComplete('53995'),
  m.Step('54110'),m.Step('54100'),m.Step('54094'),m.StageComplete('54078'),
  m.Step('54186'),m.Step('54170'),m.Step('54162'),m.Step('54210'),m.Step('54200'),m.Step('54192'),m.StageComplete('54126'),
  m.Step('35726'),m.LeafCall('47263'),m.LeafReturn('47263'),m.Step('47280'),m.LeafCall('47306'),m.LeafReturn('47306'),
  m.Step('47323'),m.LeafCall('47349'),m.LeafReturn('47349'),m.LeafCall('47366'),m.LeafReturn('47366'),m.StageComplete('54238'),
  m.LeafCall('50582'),m.LeafReturn('50582'),m.StageComplete('50555'))
def core(new=True,tokens=None,data=None):
 COUNTS['core_calls']+=1
 try:r=m.replay_event(new,schedule()if tokens is None else tokens,**(fixture()if data is None else data))
 except(TypeError,ValueError):COUNTS['refused']+=1;raise
 COUNTS['accepted']+=1;COUNTS['false'if not new else'completed_true'if r['selected_body_completed']else'prefixes']+=1;return r
def payload():
 f=fixture();p=dict(source_id='APP-00',source_version='57E1B106EEB57D70124D21CC3FEE775BCADFBF47081F02ED9335A28BAFBC9DD5',event_uid='43',frame_uid='48846',new_value=True,
  schedule=[dict(kind={m.Step:'step',m.LeafCall:'leaf_call',m.LeafReturn:'leaf_return',m.StageComplete:'stage_complete'}[type(t)],uid=t.frame_uid if type(t)is m.StageComplete else t.node_uid)for t in schedule()],snapshots={u:list(v)for u,v in f['snapshots'].items()},leaf_returns=f['leaf_returns'],unwired_inputs=f['unwired_inputs'],reference_bindings=f['reference_bindings'])
 p['unwired_inputs']['47271']=dict(p['unwired_inputs']['47271']._asdict());p['unwired_inputs']['47375']={'opaque':'supplied-Void-47375'}
 for u,e,r in(('47263','47274','47268'),('47306','47317','47311'),('47349','47360','47354')):
  p['leaf_returns'][u][e]=dict(p['leaf_returns'][u][e]._asdict());p['leaf_returns'][u][r]={'opaque':'unused-'+r}
 p['leaf_returns']['47366']['47387']=dict(p['leaf_returns']['47366']['47387']._asdict())
 for u in p['reference_bindings']:p['reference_bindings'][u]['native_ref']={'opaque':'supplied-'+u}
 return p
def adapter(p):
 COUNTS['adapter_calls']+=1
 try:r=m.replay_saved_acq_event_48846(p)
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
class SavedAcq48846Tests(unittest.TestCase):
 def expect(self,r,f):
  first=list(f['snapshots']['54039']);first[18]=True;second=list(f['snapshots']['54110']);second[18]=False;eps=list(f['snapshots']['54186']);eps[49]=False;eps[45]=True;dps=list(f['snapshots']['54210']);dps[15]=False
  self.assertEqual({w['node_uid']:w['value']for w in r['writes']},{'54021':tuple(first),'54045':True,'54094':tuple(second),'54162':tuple(eps),'54192':tuple(dps)})
  calls={c['node_uid']:c['input_ports']for c in r['leaf_calls']}
  for uid,face,read in(('47263','47277','35726'),('47306','47320','47280'),('47349','47363','47323')):self.assertIs(calls[uid][face],f['snapshots'][read])
  self.assertEqual(calls['54053'],{'54058':150});self.assertEqual(calls['50582'],{'50592':100})
 def test_full_five_stages_all_fresh_fields(self):
  f=fixture();r=core(data=f);self.expect(r,f);self.assertEqual(r['completed_stages'],['53995','54078','54126','54238','50555']);self.assertTrue(r['selected_body_completed']);self.assertEqual(len(schedule()),33)
 def test_every_snapshot_Boolean_position(self):
  for uid,n in(('54039',32),('54110',32),('54186',77),('54210',29),('35726',29),('47280',77),('47323',32)):
   for i in range(n):
    f=fixture();v=[False]*n;v[i]=True;f['snapshots'][uid]=tuple(v);self.expect(core(data=f),f)
 def test_fresh_C4_EPS_DPS_adjacent_fields(self):
  f=fixture();f['snapshots']['54039']=tuple([False]*32);f['snapshots']['54110']=tuple([True]*32);f['snapshots']['54186']=tuple([True]*77);f['snapshots']['54210']=tuple([True]*29);r=core(data=f);self.expect(r,f)
  w={x['node_uid']:x['value']for x in r['writes']};self.assertEqual(w['54021'][17:20],(False,True,False));self.assertEqual(w['54094'][17:20],(True,False,True));self.assertEqual(w['54192'][14:17],(True,False,True));self.assertIs(w['54162'][49],False);self.assertIs(w['54162'][45],True);self.assertIs(w['54162'][48],True)
 def test_sixty_stage0_orders_with_Wait_overlap(self):
  base=schedule();n=0
  for ab in interleave((0,1,2),(3,)):
   for order in interleave(ab,(4,5)):
    f=fixture();self.expect(core(tokens=tuple(base[i]for i in order)+base[6:],data=f),f);n+=1
  self.assertEqual(n,60)
 def test_twenty_independent_EPS_DPS_stage2_orders(self):
  base=schedule();n=0
  for order in interleave((0,1,2),(3,4,5)):
   f=fixture();self.expect(core(tokens=base[:11]+tuple(base[11+i]for i in order)+base[17:],data=f),f);n+=1
  self.assertEqual(n,20)
 def test_twenty_eight_publication_read_orders(self):
  base=schedule();n=0
  for reads in((3,6),(6,3)):
   for order in interleave((0,1,2,4,5,7,8,9,10),reads):
    if order.index(3)>order.index(4)or order.index(6)>order.index(7):continue
    f=fixture();self.expect(core(tokens=base[:18]+tuple(base[18+i]for i in order)+base[29:],data=f),f);n+=1
  self.assertEqual(n,28)
 def test_all_canonical_prefixes(self):
  for n in range(34):
   r=core(tokens=schedule()[:n]);self.assertEqual(r['selected_body_completed'],n==33);self.assertEqual(len(r['completed_stages']),sum(i<n for i in(6,10,17,29,32)))
 def test_six_inflight_leaves(self):
  for i,t in enumerate(schedule()):
   if type(t)is m.LeafCall:
    r=core(tokens=schedule()[:i+1]);self.assertIn(t.node_uid,r['pending_leaf_uids']);self.assertFalse(r['selected_body_completed'])
 def test_false_and_empty_nonaccess(self):
  for p in(Poison(),None,{'bad':object()}):
   r=core(False,tokens=p,data=dict(snapshots=p,leaf_returns=p,unwired_inputs=p,reference_bindings=p));self.assertEqual(r['leaf_calls'],[]);self.assertEqual(r['writes'],[]);self.assertEqual(r['selected_case_frame'],'53972');self.assertFalse(any(x['kind']=='border_transfer'for x in r['log']))
  r=core(tokens=(),data=dict(snapshots=Poison(),leaf_returns=Poison(),unwired_inputs=Poison(),reference_bindings=Poison()));self.assertEqual(r['active_stage'],'53995');self.assertEqual(len([x for x in r['log']if x['kind']=='border_transfer']),5)
 def test_error_and_reference_identity_order(self):
  f=fixture();r=core(data=f);calls={x['node_uid']:x['input_ports']for x in r['leaf_calls']}
  for uid,face,p,o in(('47306','47314','47263','47274'),('47349','47357','47306','47317'),('47366','47396','47349','47360')):self.assertIs(calls[uid][face],f['leaf_returns'][p][o])
  for uid,face,ref in(('47263','47265','47245'),('47306','47308','47290'),('47349','47351','47333')):self.assertIs(calls[uid][face],f['reference_bindings'][ref]['native_ref'])
  self.assertIs(calls['47263']['47271'],f['unwired_inputs']['47271']);self.assertIs(calls['47366']['47375'],f['unwired_inputs']['47375']);self.assertEqual([c['node_uid']for c in r['leaf_calls']],['54053','47263','47306','47349','47366','50582'])
 def test_seven_fresh_snapshots_not_write_caches(self):
  f=fixture()
  for u,n in(('54039',32),('54186',77),('54210',29)):f['snapshots'][u]=tuple([True]*n)
  for u,n in(('54110',32),('35726',29),('47280',77),('47323',32)):f['snapshots'][u]=tuple([False]*n)
  r=core(data=f);self.expect(r,f);w={x['node_uid']:x['value']for x in r['writes']}
  self.assertNotEqual(w['54021'],w['54094']);self.assertNotEqual(w['54162'],f['snapshots']['47280']);self.assertNotEqual(w['54192'],f['snapshots']['35726'])
 def test_consumed_outer150_exact_border_path(self):
  r=core();path=[x['source_path']for x in r['log']if x['kind']=='border_transfer']
  self.assertEqual(path,[('wire','54357','54357','53958','53965','54370'),('paired','53958','53965','53969','53966'),('wire','53958','53969','53984','53986','54352'),('paired','53984','53986','53989','53987'),('wire','53984','53989','54053','54058','54063')]);self.assertEqual(r['unconsumed_sequence_input_faces'],('53990','53991','53992','50574'));self.assertEqual(r['event_data_consumed_ports'],('53951',))
 def test_nonzero_unused_errors_not_stage_gates(self):
  for uid,e in(('47263','47274'),('47306','47317'),('47349','47360'),('47366','47387')):
   f=fixture();error=m.ErrorValue(True,-2147483648,'fault');f['leaf_returns'][uid][e]=error;r=core(data=f);self.assertTrue(r['selected_body_completed']);self.assertIs(next(x for x in r['leaf_returns']if x['node_uid']==uid)['output_ports'][e],error)
  f=fixture()
  for uid,face in(('47263','47268'),('47306','47311'),('47349','47354')):f['leaf_returns'][uid][face]=Poison()
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
 def test_invalid_dependencies_and_foreign_UID(self):
  base=schedule();bad=[(m.StageComplete('53995'),),(m.Step('54029'),),(m.Step('54021'),),(m.LeafReturn('54053'),),(m.LeafCall('47263'),),(m.Step('33106'),),base+(m.Step('54039'),),base[:1]+(m.Step('54039'),),base[:7]+(m.StageComplete('54078'),),base[:11]+(m.Step('54162'),),base[:13]+(m.StageComplete('54126'),),base[:20]+(m.LeafCall('47306'),),base[:30]+(m.StageComplete('50555'),),base[:30]+(m.LeafReturn('50582'),),list(base),('Step',),(m.Step(54039),)]
  for tokens in bad:
   with self.assertRaises((TypeError,ValueError)):core(tokens=tokens)
 def test_typed_Boolean_integer_error_boundaries(self):
  for new in(0,1,None,'True'):
   with self.assertRaises(TypeError):core(new)
  for uid,n in(('54039',32),('54110',32),('54186',77),('54210',29),('35726',29),('47280',77),('47323',32)):
   for value in(tuple([False]*(n-1)),tuple([False]*n+[True]),tuple([0]*n)):
    f=fixture();f['snapshots'][uid]=value
    with self.assertRaises(TypeError):core(data=f)
  for uid,face in(('54053','54055'),('50582','50585')):
   for value in(-1,4294967296,True,1.0):
    f=fixture();f['leaf_returns'][uid][face]=value
    with self.assertRaises(TypeError):core(data=f)
  for face,value in(('47378',2147483648),('47393',-1),('47393',65536),('47381',1),('47271',m.ErrorValue(1,0,'x')),('47271',m.ErrorValue(False,2147483648,'x'))):
   f=fixture();f['unwired_inputs'][face]=value
   with self.assertRaises(TypeError):core(data=f)
 def test_exact_URI_and_return_keys(self):
  for uid in('47245','47290','47333'):
   f=fixture();f['reference_bindings'][uid]['saved_uri']='other'
   with self.assertRaises(ValueError):core(data=f)
  f=fixture();f['leaf_returns']['54053']['extra']=0
  with self.assertRaises(ValueError):core(data=f)
 def test_JSON_full_false_prefix(self):
  p=payload();r=adapter(p);self.assertTrue(r['selected_body_completed']);w={x['node_uid']:x['value']for x in r['writes']};self.assertIs(w['54021'][18],True);self.assertIs(w['54094'][18],False);self.assertIs(w['54162'][49],False);self.assertIs(w['54162'][45],True);self.assertIs(w['54192'][15],False);self.assertEqual(r['leaf_calls'][0]['input_ports'],{'54058':150})
  p=payload();p.update(new_value=False,schedule=Poison(),snapshots=Poison(),leaf_returns=Poison(),unwired_inputs=Poison(),reference_bindings=Poison());self.assertEqual(adapter(p)['writes'],[])
  p=payload();p['schedule']=p['schedule'][:5];r=adapter(p);self.assertEqual(r['pending_leaf_uids'],['54053']);self.assertEqual(r['completed_stages'],[])
 def test_JSON_identity_schema_finite_domains(self):
  changes=[lambda p:p.update(source_version='other'),lambda p:p.pop('source_version'),lambda p:p.update(frame_uid='31552'),lambda p:p.update(event_uid='44'),lambda p:p.update(source_id='APP-01'),lambda p:p.update(extra=1),lambda p:p.update(new_value=1),lambda p:p['schedule'][0].update(extra=1),lambda p:p['schedule'][0].update(uid='33106'),lambda p:p['snapshots'].update(other=[]),lambda p:p['snapshots']['54039'].__setitem__(0,1),lambda p:p['reference_bindings']['47245'].update(native_ref=float('nan')),lambda p:p['unwired_inputs'].update({'47375':object()}),lambda p:p['leaf_returns']['54053'].update({'54055':-1})]
  for change in changes:
   p=payload();change(p)
   with self.assertRaises((TypeError,ValueError)):adapter(p)
 def test_native_whole_default_limits_false(self):
  r=core()
  for k in m.LIMITS:self.assertIs(r[k],False)
if __name__=='__main__':unittest.main()
