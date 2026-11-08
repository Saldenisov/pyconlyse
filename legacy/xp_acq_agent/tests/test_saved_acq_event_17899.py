import copy,hashlib,itertools,json,os,sys,unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from elyse_agent import saved_acq_event_17899 as m
COUNTS=dict(accepted=0,refused=0,checks=0);WITNESS=[]
def check(v):
 COUNTS['checks']+=1
 if not v:raise AssertionError('independent source expectation failed')
def accepted(p):
 r=m.replay_saved_acq_event_17899(p);COUNTS['accepted']+=1;return r
def refused(p):
 try:m.replay_saved_acq_event_17899(p)
 except(ValueError,TypeError,KeyError,IndexError):COUNTS['refused']+=1;return
 raise AssertionError('bounded domain must refuse')
def args(p):
 classes={'step':m.Step,'leaf_call':m.LeafCall,'leaf_return':m.LeafReturn,'stage_complete':m.StageComplete}
 def err(v):return m.ErrorValue(v['status'],v['code'],v['source'])
 r=dict(snapshots={u:tuple(x)for u,x in p['snapshots'].items()},leaf_returns=copy.deepcopy(p['leaf_returns']),unwired_inputs=copy.deepcopy(p['unwired_inputs']),reference_bindings=copy.deepcopy(p['reference_bindings']),literal_inputs=dict(p['literal_inputs']))
 r['unwired_inputs']['23185']=err(r['unwired_inputs']['23185']);r['leaf_returns']['23177']['23188']=err(r['leaf_returns']['23177']['23188']);r['leaf_returns']['23194']['23226']=err(r['leaf_returns']['23194']['23226'])
 return tuple(classes[x['kind']](x['uid'])for x in p['schedule']),r
class Poison:
 def __getitem__(self,key):raise AssertionError('unselected body accessed')
 def __iter__(self):raise AssertionError('unselected body iterated')
FULL={'event_uid': '43',
 'frame_uid': '17899',
 'leaf_returns': {'16362': {'16403': 101},
                  '21625': {'21633': 102},
                  '21990': {'22004': 103},
                  '22147': {'22153': 104},
                  '23162': {'23165': 105},
                  '23177': {'23182': {'opaque': 'explicit returned DPS ref'},
                            '23188': {'code': -9, 'source': 'explicit supplied fault -9', 'status': True}},
                  '23194': {'23197': True,
                            '23201': 2147483647,
                            '23217': 'supplied handler source',
                            '23226': {'code': -10, 'source': 'explicit supplied fault -10', 'status': True},
                            '23229': 'unused supplied message'}},
 'literal_inputs': {'21733': False, '22885': False, '22900': False, '22921': False, '22931': False, '7970': False},
 'new_value': True,
 'reference_bindings': {'23135': {'constant_uid': '23135',
                                  'native_ref': {'opaque_supplied_ref': 'DPS'},
                                  'saved_uri': 'ni.var.psp://10.20.30.2/SUPERVISION/DPS'}},
 'schedule': [{'kind': 'step', 'uid': '13611'},
              {'kind': 'step', 'uid': '11019'},
              {'kind': 'step', 'uid': '10838'},
              {'kind': 'step', 'uid': '16177'},
              {'kind': 'leaf_call', 'uid': '16362'},
              {'kind': 'leaf_return', 'uid': '16362'},
              {'kind': 'stage_complete', 'uid': '7963'},
              {'kind': 'step', 'uid': '20437'},
              {'kind': 'step', 'uid': '20420'},
              {'kind': 'step', 'uid': '20410'},
              {'kind': 'stage_complete', 'uid': '18101'},
              {'kind': 'leaf_call', 'uid': '21625'},
              {'kind': 'leaf_return', 'uid': '21625'},
              {'kind': 'stage_complete', 'uid': '21010'},
              {'kind': 'leaf_call', 'uid': '21990'},
              {'kind': 'step', 'uid': '21967'},
              {'kind': 'step', 'uid': '21826'},
              {'kind': 'step', 'uid': '21773'},
              {'kind': 'leaf_return', 'uid': '21990'},
              {'kind': 'stage_complete', 'uid': '21712'},
              {'kind': 'step', 'uid': '22138'},
              {'kind': 'leaf_call', 'uid': '22147'},
              {'kind': 'step', 'uid': '22115'},
              {'kind': 'leaf_return', 'uid': '22147'},
              {'kind': 'step', 'uid': '22098'},
              {'kind': 'stage_complete', 'uid': '22060'},
              {'kind': 'step', 'uid': '23076'},
              {'kind': 'step', 'uid': '23043'},
              {'kind': 'step', 'uid': '23005'},
              {'kind': 'step', 'uid': '22985'},
              {'kind': 'step', 'uid': '22959'},
              {'kind': 'step', 'uid': '22951'},
              {'kind': 'stage_complete', 'uid': '22878'},
              {'kind': 'step', 'uid': '23171'},
              {'kind': 'leaf_call', 'uid': '23177'},
              {'kind': 'leaf_call', 'uid': '23162'},
              {'kind': 'leaf_return', 'uid': '23177'},
              {'kind': 'leaf_call', 'uid': '23194'},
              {'kind': 'leaf_return', 'uid': '23194'},
              {'kind': 'leaf_return', 'uid': '23162'},
              {'kind': 'stage_complete', 'uid': '23117'}],
 'snapshots': {'13611': [True,
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
               '20437': [False,
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
                         False],
               '21967': [False,
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
                         False],
               '22138': [True,
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
               '22985': [False,
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
                         True,
                         False,
                         False],
               '23076': [False,
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
               '23171': [True,
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
 'source_id': 'APP-00',
 'source_version': '57E1B106EEB57D70124D21CC3FEE775BCADFBF47081F02ED9335A28BAFBC9DD5',
 'unwired_inputs': {'23185': {'code': 5, 'source': 'explicit supplied fault 5', 'status': True},
                    '23204': {'opaque': 'explicit Void argument'},
                    '23209': -2147483648,
                    '23213': 'explicit unwired String',
                    '23232': 65535}}
class NewSourceCases(unittest.TestCase):
 def verify(self,p,r):
  expected=[]
  # Independent concrete source mutations, no module plan-derived expectation.
  for read,write,index,value in(('13611','10838',1,False),('20437','20410',1,True),('21967','21773',4,False),('22138','22098',4,True),('23076','23005',1,False)):
   x=list(p['snapshots'][read]);x[index]=value;expected.append((write,x))
  x=list(p['snapshots']['22985']);x[3]=False;x[2]=False;x[5]=True;x[1]=False;expected.append(('22951',x));expected.append(('16177',True))
  actual={x['node_uid']:x['value']for x in r['writes']};check(actual==dict(expected));check(r['completed_stages']==['7963','18101','21010','21712','22060','22878','23117']);check(r['selected_body_completed']);check(not r['pending_leaf_uids'])
  calls={x['node_uid']:x['input_ports']for x in r['leaf_calls']};check([calls[u][f]for u,f in(('16362','16413'),('21625','21640'),('21990','22010'),('22147','22162'),('23162','23168'))]==[150,400,150,150,100]);check(calls['23177']['23191']==p['snapshots']['23171']);check(calls['23194']['23236']==p['leaf_returns']['23177']['23188'])
  for k in m.LIMITS:check(r[k]is False)
 def test_full_and_fresh_reads(self):
  for seed in range(12):
   p=copy.deepcopy(FULL)
   for j,u in enumerate(sorted(p['snapshots'])):p['snapshots'][u]=[(i+seed+j)%2==0 for i in range(len(p['snapshots'][u]))]
   r=accepted(p);self.verify(p,r)
  p=copy.deepcopy(FULL);tokens,a=args(p);r=m.replay_event(True,tokens,**a);COUNTS['accepted']+=1
  calls={x['node_uid']:x['input_ports']for x in r['leaf_calls']};check(calls['23177']['23191']is a['snapshots']['23171']);check(calls['23177']['23179']is a['reference_bindings']['23135']['native_ref']);check(calls['23177']['23185']is a['unwired_inputs']['23185']);check(calls['23194']['23236']is a['leaf_returns']['23177']['23188']);check(r['leaf_returns'][-1]['output_ports']is a['leaf_returns']['23162'])
  WITNESS.append(['full',r['completed_stages'],[x['node_uid']for x in r['writes']]])
 def test_partial_orders_and_inflight(self):
  # Independent source chain order, unrelated Wait/ACTION may interleave.
  stages=[(0,6,(('step','13611'),('step','11019'),('step','10838')), (('step','16177'),),(('leaf_call','16362'),('leaf_return','16362'))),
          (14,5,(('step','21967'),('step','21826'),('step','21773')), (('leaf_call','21990'),('leaf_return','21990'))),
          (20,5,(('step','22138'),('step','22115'),('step','22098')), (('leaf_call','22147'),('leaf_return','22147')))]
  for spec in stages:
   start,length=spec[:2];chains=spec[2:];items=[x for c in chains for x in c]
   for order in itertools.permutations(items):
    if not all([order.index(x)for x in c]==sorted(order.index(x)for x in c)for c in chains):continue
    p=copy.deepcopy(FULL);p['schedule'][start:start+length]=[dict(kind=k,uid=u)for k,u in order];r=accepted(p);self.verify(p,r)
  # Stage6 Wait remains independent from the snapshot->PSP->handler chain.
  a=[('step','23171'),('leaf_call','23177'),('leaf_return','23177'),('leaf_call','23194'),('leaf_return','23194')];b=[('leaf_call','23162'),('leaf_return','23162')]
  for pos in itertools.combinations(range(7),2):
   ia=iter(a);ib=iter(b);order=[next(ib)if i in pos else next(ia)for i in range(7)];p=copy.deepcopy(FULL);p['schedule'][-8:-1]=[dict(kind=k,uid=u)for k,u in order];r=accepted(p);self.verify(p,r)
  for n in range(42):
   p=copy.deepcopy(FULL);p['schedule']=p['schedule'][:n];r=accepted(p);check(r['selected_body_completed']==(n==41));check(len(r['completed_stages'])==sum(x['kind']=='stage_complete'for x in p['schedule']))
  p=copy.deepcopy(FULL);p['schedule']=p['schedule'][:5];p['leaf_returns']={};r=accepted(p);check(r['pending_leaf_uids']==['16362']);check(r['completed_stages']==[])
  WITNESS.append(['orders-prefixes','source-owned'])
 def test_false_nonaccess(self):
  z=Poison();r=m.replay_event(False,z,snapshots=z,leaf_returns=z,unwired_inputs=z,reference_bindings=z,literal_inputs=z);COUNTS['accepted']+=1;check(r['selected_case_frame']=='17964');check(not r['writes']);check(not r['leaf_calls']);check(r['selected_body_completed'])
  p=copy.deepcopy(FULL);p.update(new_value=False,schedule=z,snapshots=z,leaf_returns=z,unwired_inputs=z,reference_bindings=z,literal_inputs=z);r=accepted(p);check(not r['leaf_calls'])
  for v in(0,1,None,'True',[]):p=copy.deepcopy(FULL);p['new_value']=v;refused(p)
 def test_typed_domains_and_snapshots(self):
  for u in FULL['snapshots']:
   for v in(None,True,{},FULL['snapshots'][u][:-1],FULL['snapshots'][u]+[False],[0]*len(FULL['snapshots'][u])):p=copy.deepcopy(FULL);p['snapshots'][u]=v;refused(p)
  for u in('13611','20437','21967','22138'):
   p=copy.deepcopy(FULL);p['snapshots'][u]=[False]*32;refused(p)
  for u in FULL['literal_inputs']:
   for v in(None,0,True,'False',[],float('nan')):p=copy.deepcopy(FULL);p['literal_inputs'][u]=v;refused(p)
   p=copy.deepcopy(FULL);del p['literal_inputs'][u];refused(p)
  for uid,port,bad in(('16362','16403',-1),('21625','21633',4294967296),('21990','22004',True),('22147','22153',True),('23162','23165',1.0),('23194','23197',1),('23194','23201',2147483648),('23194','23217',None),('23194','23229',[])):
   p=copy.deepcopy(FULL);p['leaf_returns'][uid][port]=bad;refused(p)
  for face,bad in(('23209',True),('23209',-2147483649),('23213',42),('23232',65536),('23232',-1)):
   p=copy.deepcopy(FULL);p['unwired_inputs'][face]=bad;refused(p)
  for field,bad in(('status',1),('code',True),('code',2147483648),('source',None)):
   p=copy.deepcopy(FULL);p['leaf_returns']['23177']['23188'][field]=bad;refused(p)
  p=copy.deepcopy(FULL);p['reference_bindings']['23135']['saved_uri']='wrong';refused(p)
  p=copy.deepcopy(FULL);p['reference_bindings']['23135']['constant_uid']='wrong';refused(p)
 def test_schedule_dependency_refusals(self):
  bad=[[],[dict(kind='step',uid='11019')],[dict(kind='step',uid='10838')],[dict(kind='leaf_return',uid='16362')],[dict(kind='stage_complete',uid='7963')],[dict(kind='step',uid='23171')]]
  # Empty is accepted prefix, separate from incomplete invalid joins.
  p=copy.deepcopy(FULL);p['schedule']=bad.pop(0);check(not accepted(p)['selected_body_completed'])
  for rows in bad:p=copy.deepcopy(FULL);p['schedule']=rows;refused(p)
  for i in(0,1,6,7,13,19,23,30):
   p=copy.deepcopy(FULL);p['schedule']=p['schedule'][:i]+p['schedule'][i+1:];refused(p)
  p=copy.deepcopy(FULL);p['schedule']=p['schedule'][:-1];check(not accepted(p)['selected_body_completed'])
  p=copy.deepcopy(FULL);p['schedule'].append(dict(kind='step',uid='13611'));refused(p)
  p=copy.deepcopy(FULL);p['schedule'][0]['kind']='callback';refused(p)
  p=copy.deepcopy(FULL);p['schedule'][0]['uid']='11019';refused(p)
  WITNESS.append(['refusals',COUNTS['refused']])
 def test_identity_envelope_and_json(self):
  for k in('source_id','source_version','event_uid','frame_uid'):
   p=copy.deepcopy(FULL);p[k]='wrong';refused(p);p=copy.deepcopy(FULL);del p[k];refused(p)
  for k in('native_execution','field_index_bindings','whole_event_equivalence'):p=copy.deepcopy(FULL);p[k]=False;refused(p)
  for k in('snapshots','leaf_returns','unwired_inputs','reference_bindings','literal_inputs'):
   p=copy.deepcopy(FULL);p[k]['unknown']='x';refused(p)
  for k,v in(('23204',object()),('23204',float('inf')),('23204',{1:False})):
   p=copy.deepcopy(FULL);p['unwired_inputs'][k]=v;refused(p)
  p=copy.deepcopy(FULL);p['leaf_returns']['23177']['38647']=object();refused(p)
  p=copy.deepcopy(FULL);p['schedule'][0]['extra']=0;refused(p)
  # Supplied errors never imply success or gate any stage.
  for b in(False,True):
   p=copy.deepcopy(FULL);p['leaf_returns']['23177']['23188']['status']=b;r=accepted(p);check(r['selected_body_completed'])
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(NewSourceCases));out=dict(status='PASS'if result.wasSuccessful()else'FAIL',python_version=sys.version,methods=result.testsRun,counts=COUNTS,witness_sha256=hashlib.sha256(json.dumps(WITNESS,sort_keys=True,separators=(',',':')).encode('ascii')).hexdigest().upper())
 if len(sys.argv)>1:
  with open(sys.argv[1],'w')as f:json.dump(out,f,sort_keys=True,indent=2)
 print(json.dumps(out,sort_keys=True));sys.exit(0 if result.wasSuccessful()else 1)
