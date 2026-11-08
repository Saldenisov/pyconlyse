"""Fresh original8896 source cases; portable inline boundaries, no native calls."""
import copy,importlib.machinery,itertools,json,os,unittest
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
k=importlib.machinery.SourceFileLoader('fresh8896core',os.path.join(ROOT,'elyse_agent','saved_acq_event_8896.py')).load_module()
_PAYLOAD={'source_id': 'APP-00',
 'source_version': '57E1B106EEB57D70124D21CC3FEE775BCADFBF47081F02ED9335A28BAFBC9DD5',
 'event_uid': '43',
 'frame_uid': '8896',
 'new_value': True,
 'schedule': [{'kind': 'step', 'uid': '31799'},
              {'kind': 'step', 'uid': '31771'},
              {'kind': 'step', 'uid': '31763'},
              {'kind': 'step', 'uid': '31847'},
              {'kind': 'leaf_call', 'uid': '31856'},
              {'kind': 'leaf_return', 'uid': '31856'},
              {'kind': 'stage_complete', 'uid': '31696'},
              {'kind': 'step', 'uid': '32107'},
              {'kind': 'step', 'uid': '32097'},
              {'kind': 'step', 'uid': '31905'},
              {'kind': 'stage_complete', 'uid': '31883'},
              {'kind': 'step', 'uid': '32180'},
              {'kind': 'step', 'uid': '32167'},
              {'kind': 'step', 'uid': '32159'},
              {'kind': 'step', 'uid': '32260'},
              {'kind': 'step', 'uid': '32194'},
              {'kind': 'step', 'uid': '32186'},
              {'kind': 'stage_complete', 'uid': '32123'},
              {'kind': 'step', 'uid': '32534'},
              {'kind': 'leaf_call', 'uid': '32541'},
              {'kind': 'leaf_return', 'uid': '32541'},
              {'kind': 'step', 'uid': '32559'},
              {'kind': 'leaf_call', 'uid': '32625'},
              {'kind': 'leaf_return', 'uid': '32625'},
              {'kind': 'step', 'uid': '32642'},
              {'kind': 'leaf_call', 'uid': '32649'},
              {'kind': 'leaf_return', 'uid': '32649'},
              {'kind': 'leaf_call', 'uid': '32666'},
              {'kind': 'leaf_return', 'uid': '32666'},
              {'kind': 'stage_complete', 'uid': '32374'},
              {'kind': 'leaf_call', 'uid': '32747'},
              {'kind': 'leaf_return', 'uid': '32747'},
              {'kind': 'stage_complete', 'uid': '32729'}],
 'snapshots': {'31799': [True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False],
               '32107': [False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False],
               '32180': [False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True],
               '32260': [True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False],
               '32534': [False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False],
               '32559': [False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True],
               '32642': [True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False]},
 'leaf_returns': {'31856': {'31860': 7},
                  '32541': {'32546': {'unused_native': 0},
                            '32553': {'status': True, 'code': -18, 'source': 'independent supplied error -18'}},
                  '32625': {'32630': {'unused_native': 0},
                            '32636': {'status': True, 'code': -18, 'source': 'independent supplied error -18'}},
                  '32649': {'32654': {'unused_native': 0},
                            '32660': {'status': True, 'code': -18, 'source': 'independent supplied error -18'}},
                  '32666': {'32669': False,
                            '32672': 8,
                            '32684': 'unwired string',
                            '32687': {'status': True, 'code': -20, 'source': 'independent supplied error -20'},
                            '32690': 'unwired string'},
                  '32747': {'32749': 7}},
 'unwired_inputs': {'32549': {'status': True, 'code': -18, 'source': 'independent supplied error -18'},
                    '32675': {'unused_native': 0},
                    '32678': 8,
                    '32681': 'unwired string',
                    '32693': 10},
 'reference_bindings': {'32380': {'constant_uid': '32380',
                                  'saved_uri': 'ni.var.psp://10.20.30.2/SUPERVISION/DPS',
                                  'native_ref': {'supplied_native_reference': '32380'}},
                        '32495': {'constant_uid': '32495',
                                  'saved_uri': 'ni.var.psp://10.20.30.2/SUPERVISION/EPS',
                                  'native_ref': {'supplied_native_reference': '32495'}},
                        '32515': {'constant_uid': '32515',
                                  'saved_uri': 'ni.var.psp://10.20.30.2/SUPERVISION/C4_OUT_DIO96',
                                  'native_ref': {'supplied_native_reference': '32515'}}}}

CALLS=dict(core_calls=0,accepted=0,refused=0,adapter_calls=0,adapter_accepted=0,adapter_refused=0)
def payload(new_value=True):
 p=copy.deepcopy(_PAYLOAD);p['new_value']=new_value;return p

def direct(p):
 mapping={'step':k.Step,'leaf_call':k.LeafCall,'leaf_return':k.LeafReturn,'stage_complete':k.StageComplete}
 schedule=tuple(mapping[r['kind']](r['uid'])for r in p['schedule'])
 def error(v):return k.ErrorValue(v['status'],v['code'],v['source'])
 returns={u:{f:error(x)if type(x)is dict and set(x)=={'status','code','source'}else x for f,x in v.items()}for u,v in p['leaf_returns'].items()}
 unwired={f:error(x)if type(x)is dict and set(x)=={'status','code','source'}else x for f,x in p['unwired_inputs'].items()}
 return schedule,dict(snapshots={u:tuple(x)for u,x in p['snapshots'].items()},leaf_returns=returns,unwired_inputs=unwired,reference_bindings=p['reference_bindings'])

def invoke(new,schedule,**kw):
 CALLS['core_calls']+=1
 try:r=k.replay_event(new,schedule,**kw)
 except Exception:CALLS['refused']+=1;raise
 CALLS['accepted']+=1;return r

def adapter(p):
 CALLS['adapter_calls']+=1
 try:r=k.replay_saved_acq_event_8896(p)
 except Exception:CALLS['adapter_refused']+=1;raise
 CALLS['adapter_accepted']+=1;return r

class Poison(object):
 def __getitem__(self,key):raise AssertionError('unaccessed boundary was read')
 def __iter__(self):raise AssertionError('unaccessed boundary was iterated')
 def __len__(self):raise AssertionError('unaccessed boundary length was read')

class SavedAcq8896Tests(unittest.TestCase):
 def run_body(self,p=None,schedule=None):
  p=payload()if p is None else p;s,kw=direct(p)
  return invoke(p['new_value'],s if schedule is None else schedule,**kw)
 def expected(self,p):
  a=tuple(False if i==19 else v for i,v in enumerate(p['snapshots']['31799']))
  b=tuple(True if i==19 else v for i,v in enumerate(p['snapshots']['32107']))
  e=tuple(False if i==45 else True if i==49 else v for i,v in enumerate(p['snapshots']['32180']))
  d=tuple(False if i==17 else v for i,v in enumerate(p['snapshots']['32260']))
  return {'31763':a,'31847':True,'31905':b,'32159':e,'32186':d}
 def assert_projection(self,r,p):
  self.assertEqual({w['node_uid']:w['value']for w in r['writes']},self.expected(p))
  self.assertEqual(r['completed_stages'],['31696','31883','32123','32374','32729']);self.assertTrue(r['selected_body_completed'])
 def test_full_source_fields_and_adjacent_unchanged_values(self):
  p=payload();p['snapshots']['31799'][2]=True;p['snapshots']['32107'][2]=False
  self.assert_projection(self.run_body(p),p)
 def test_every_position_in_seven_independent_snapshots(self):
  for uid,n in(('31799',32),('32107',32),('32180',77),('32260',29),('32534',29),('32559',77),('32642',32)):
   for i in range(n):
    p=payload();p['snapshots'][uid][i]=not p['snapshots'][uid][i];r=self.run_body(p);self.assert_projection(r,p)
    calls={c['node_uid']:c['input_ports']for c in r['leaf_calls']}
    for writer,face,read in(('32541','32556','32534'),('32625','32639','32559'),('32649','32663','32642')):self.assertEqual(calls[writer][face],tuple(p['snapshots'][read]))
 def test_fresh_read_reference_error_identities(self):
  p=payload();s,kw=direct(p);r=invoke(True,s,**kw);calls={x['node_uid']:x['input_ports']for x in r['leaf_calls']}
  for writer,face,read,ref,constant in(('32541','32556','32534','32543','32380'),('32625','32639','32559','32627','32495'),('32649','32663','32642','32651','32515')):
   self.assertIs(calls[writer][face],kw['snapshots'][read]);self.assertIs(calls[writer][ref],kw['reference_bindings'][constant]['native_ref'])
  for consumer,face,producer,out in(('32625','32633','32541','32553'),('32649','32657','32625','32636'),('32666','32696','32649','32660')):
   self.assertIs(calls[consumer][face],kw['leaf_returns'][producer][out]);self.assertTrue(calls[consumer][face].status)
  self.assertIs(calls['32541']['32549'],kw['unwired_inputs']['32549'])
  self.assertIs(r['log'][next(i for i,x in enumerate(r['log'])if x['kind']=='local_read'and x['node_uid']=='31799')]['value'],kw['snapshots']['31799'])
 def test_exact_150_border_forwarding_and_final100(self):
  r=self.run_body();c={x['node_uid']:x['input_ports']for x in r['leaf_calls']}
  self.assertEqual(c['31856'],{'31863':150});self.assertEqual(c['32747'],{'32752':100})
  paths=[x['source_path']for x in r['log']if x['kind']=='border_transfer']
  self.assertEqual([(x[0],x[1],x[2],x[3],x[4])for x in paths],[('wire','32764','32764','31612','31619'),('paired','31612','31619','31623','31620'),('wire','31612','31623','31655','31666'),('paired','31655','31666','31681','31671'),('wire','31655','31681','31856','31863')])
 def test_sixty_stage0_orders_with_wait_overlap(self):
  s,kw=direct(payload());tokens=s[:6];count=0
  for order in itertools.permutations(tokens):
   at={t.node_uid+(type(t).__name__):i for i,t in enumerate(order)}
   if not at['31799Step']<at['31771Step']<at['31763Step']or not at['31856LeafCall']<at['31856LeafReturn']:continue
   r=invoke(True,tuple(order)+s[6:],**kw);self.assert_projection(r,payload());count+=1
  self.assertEqual(count,60)
 def test_twenty_stage2_independent_chain_orders(self):
  s,kw=direct(payload());tokens=s[11:17];count=0
  for order in itertools.permutations(tokens):
   at={t.node_uid:i for i,t in enumerate(order)}
   if not at['32180']<at['32167']<at['32159']or not at['32260']<at['32194']<at['32186']:continue
   self.assert_projection(invoke(True,s[:11]+tuple(order)+s[17:],**kw),payload());count+=1
  self.assertEqual(count,20)
 def test_two_publication_read_orders_same_routed_error_chain(self):
  s,kw=direct(payload());alt=s[:18]+(k.Step('32534'),k.Step('32559'),k.Step('32642'),k.LeafCall('32541'),k.LeafReturn('32541'),k.LeafCall('32625'),k.LeafReturn('32625'),k.LeafCall('32649'),k.LeafReturn('32649'),k.LeafCall('32666'),k.LeafReturn('32666'),k.StageComplete('32374'))+s[30:]
  for schedule in(s,alt):self.assert_projection(invoke(True,schedule,**kw),payload())
 def test_all34_prefixes_and_six_inflight_leaves(self):
  s,kw=direct(payload())
  for n in range(34):
   r=invoke(True,s[:n],**kw);self.assertEqual(r['selected_body_completed'],n==33)
   self.assertEqual(len(r['log'])>=4,True)
  for uid in('31856','32541','32625','32649','32666','32747'):
   i=next(i for i,t in enumerate(s)if type(t)is k.LeafCall and t.node_uid==uid)
   r=invoke(True,s[:i+1],**kw);self.assertEqual(r['pending_leaf_uids'],(uid,));self.assertFalse(r['selected_body_completed'])
 def test_false_and_empty_body_nonaccess(self):
  poison=Poison()
  for schedule in(None,poison,('invalid',)):
   r=invoke(False,schedule,snapshots=poison,leaf_returns=poison,unwired_inputs=poison,reference_bindings=poison)
   self.assertEqual(r['selected_case_frame'],'31627');self.assertEqual((r['writes'],r['leaf_calls']),([],[]))
  r=invoke(True,(),snapshots=poison,leaf_returns=poison,unwired_inputs=poison,reference_bindings=poison)
  self.assertEqual(r['completed_stages'],[])
 def test_missing_each_used_boundary_and_wrong_scalar_types(self):
  for uid in('31799','32107','32180','32260','32534','32559','32642'):
   s,kw=direct(payload());kw['snapshots'].pop(uid)
   with self.assertRaises((ValueError,TypeError)):invoke(True,s,**kw)
  for uid in('31856','32541','32625','32649','32666','32747'):
   for face in list(payload()['leaf_returns'][uid]):
    s,kw=direct(payload());kw['leaf_returns'][uid].pop(face)
    with self.assertRaises((ValueError,TypeError)):invoke(True,s,**kw)
  for face in list(payload()['unwired_inputs']):
   s,kw=direct(payload());kw['unwired_inputs'].pop(face)
   with self.assertRaises((ValueError,TypeError)):invoke(True,s,**kw)
  for uid in('31799','32180','32260'):
   s,kw=direct(payload());v=list(kw['snapshots'][uid]);v[0]=1;kw['snapshots'][uid]=tuple(v)
   with self.assertRaises((ValueError,TypeError)):invoke(True,s,**kw)
 def test_dependency_stage_ref_identity_and_invalid_domains(self):
  s,kw=direct(payload())
  for schedule in((k.Step('31771'),),(k.StageComplete('31696'),),(k.LeafReturn('31856'),),(k.Step('32107'),),(k.Step('foreign'),),s+(k.Step('31799'),)):
   with self.assertRaises((ValueError,TypeError)):invoke(True,schedule,**kw)
  for value in(1,None,'True'):
   with self.assertRaises(TypeError):invoke(value,(),**kw)
  for face,value in(('32678',2**31),('32693',65536),('32681',None)):
   s,v=direct(payload());v['unwired_inputs'][face]=value
   with self.assertRaises((ValueError,TypeError)):invoke(True,s,**v)
  s,v=direct(payload());v['leaf_returns']['31856']['31860']=-1
  with self.assertRaises((ValueError,TypeError)):invoke(True,s,**v)
  s,v=direct(payload());v['reference_bindings']['32380']['saved_uri']='other'
  with self.assertRaises((ValueError,TypeError)):invoke(True,s,**v)
 def test_JSON_full_false_prefix_and_exact_version(self):
  p=payload();r=adapter(p);self.assertEqual(r['frame_uid'],'8896');self.assertEqual(r['writes'][0]['value'][19],False)
  f=payload(False)
  for key in('schedule','snapshots','leaf_returns','unwired_inputs','reference_bindings'):f[key]=None
  self.assertEqual(adapter(f)['leaf_calls'],[])
  p=payload();p['schedule']=p['schedule'][:5];self.assertEqual(adapter(p)['pending_leaf_uids'],['31856'])
  for key,value in(('source_version','bad'),('frame_uid','48846'),('event_uid',43),('new_value',1),('native_execution',True)):
   p=payload();p[key]=value
   with self.assertRaises((ValueError,TypeError)):adapter(p)
  p=payload();p.pop('source_version')
  with self.assertRaises((ValueError,TypeError)):adapter(p)
  for value in(float('nan'),float('inf'),object()):
   p=payload();p['reference_bindings']['32380']['native_ref']=value
   with self.assertRaises((ValueError,TypeError)):adapter(p)
 def test_native_default_units_event_whole_gates_remain_false(self):
  r=self.run_body()
  for flag in('external_calls_executed','native_runtime_equivalence','native_callee_equivalence','whole_event_equivalence','whole_vi_equivalence','native_default_qualified','native_ref_interpretation_qualified','native_task_reference_qualified','wait_units_or_pulse_duration_qualified','snapshot_equality_qualified','scheduler_qualified','event_selection_qualified'):self.assertIs(r[flag],False)

if __name__=='__main__':unittest.main()
