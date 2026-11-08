import copy,hashlib,itertools,json,os,sys,unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from elyse_agent import saved_acq_event_37991 as m
COUNTS=dict(accepted=0,refused=0,checks=0);WITNESS=[]
def check(v):
 COUNTS['checks']+=1
 if not v:raise AssertionError('independent source expectation failed')
def accepted(p):
 r=m.replay_saved_acq_event_37991(p);COUNTS['accepted']+=1;return r
def refused(p):
 try:m.replay_saved_acq_event_37991(p)
 except(ValueError,TypeError,KeyError,IndexError):COUNTS['refused']+=1;return
 raise AssertionError('bounded domain must refuse')
def args(p):
 classes={'step':m.Step,'leaf_call':m.LeafCall,'leaf_return':m.LeafReturn,'stage_complete':m.StageComplete}
 def err(v):return m.ErrorValue(v['status'],v['code'],v['source'])
 r=dict(snapshots={u:tuple(x)for u,x in p['snapshots'].items()},leaf_returns=copy.deepcopy(p['leaf_returns']),unwired_inputs=copy.deepcopy(p['unwired_inputs']),reference_bindings=copy.deepcopy(p['reference_bindings']),literal_inputs=dict(p['literal_inputs']))
 r['unwired_inputs']['38650']=err(r['unwired_inputs']['38650']);r['leaf_returns']['38642']['38653']=err(r['leaf_returns']['38642']['38653']);r['leaf_returns']['38659']['38680']=err(r['leaf_returns']['38659']['38680'])
 return tuple(classes[x['kind']](x['uid'])for x in p['schedule']),r
class Poison:
 def __getitem__(self,key):raise AssertionError('unselected body accessed')
 def __iter__(self):raise AssertionError('unselected body iterated')
FULL={'event_uid': '43',
 'frame_uid': '37991',
 'leaf_returns': {'38132': {'38134': 101},
                  '38223': {'38225': 102},
                  '38273': {'38275': 103},
                  '38628': {'38630': 104},
                  '38642': {'38647': {'opaque': 'explicit returned DPS ref'},
                            '38653': {'code': -9, 'source': 'explicit supplied fault -9', 'status': True}},
                  '38659': {'38662': True,
                            '38665': 2147483647,
                            '38677': 'supplied handler source',
                            '38680': {'code': -10, 'source': 'explicit supplied fault -10', 'status': True},
                            '38683': 'unused supplied message'}},
 'literal_inputs': {'37359': False, '38163': False, '38301': False, '38489': False, '38509': False},
 'new_value': True,
 'reference_bindings': {'38610': {'constant_uid': '38610',
                                  'native_ref': {'opaque_supplied_ref': 'DPS'},
                                  'saved_uri': 'ni.var.psp://10.20.30.2/SUPERVISION/DPS'}},
 'schedule': [{'kind': 'step', 'uid': '38118'},
              {'kind': 'step', 'uid': '38108'},
              {'kind': 'step', 'uid': '38100'},
              {'kind': 'step', 'uid': '38124'},
              {'kind': 'leaf_call', 'uid': '38132'},
              {'kind': 'leaf_return', 'uid': '38132'},
              {'kind': 'stage_complete', 'uid': '38074'},
              {'kind': 'step', 'uid': '38189'},
              {'kind': 'step', 'uid': '38179'},
              {'kind': 'step', 'uid': '38173'},
              {'kind': 'stage_complete', 'uid': '38157'},
              {'kind': 'leaf_call', 'uid': '38223'},
              {'kind': 'leaf_return', 'uid': '38223'},
              {'kind': 'stage_complete', 'uid': '38205'},
              {'kind': 'leaf_call', 'uid': '38273'},
              {'kind': 'step', 'uid': '38267'},
              {'kind': 'step', 'uid': '38257'},
              {'kind': 'step', 'uid': '38251'},
              {'kind': 'leaf_return', 'uid': '38273'},
              {'kind': 'stage_complete', 'uid': '38235'},
              {'kind': 'step', 'uid': '38327'},
              {'kind': 'step', 'uid': '38317'},
              {'kind': 'step', 'uid': '38311'},
              {'kind': 'stage_complete', 'uid': '38295'},
              {'kind': 'step', 'uid': '38564'},
              {'kind': 'step', 'uid': '38554'},
              {'kind': 'step', 'uid': '38546'},
              {'kind': 'step', 'uid': '38540'},
              {'kind': 'step', 'uid': '38527'},
              {'kind': 'step', 'uid': '38519'},
              {'kind': 'stage_complete', 'uid': '38483'},
              {'kind': 'step', 'uid': '38636'},
              {'kind': 'leaf_call', 'uid': '38642'},
              {'kind': 'leaf_call', 'uid': '38628'},
              {'kind': 'leaf_return', 'uid': '38642'},
              {'kind': 'leaf_call', 'uid': '38659'},
              {'kind': 'leaf_return', 'uid': '38659'},
              {'kind': 'leaf_return', 'uid': '38628'},
              {'kind': 'stage_complete', 'uid': '38592'}],
 'snapshots': {'38118': [True,
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
               '38189': [False,
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
               '38267': [False,
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
               '38327': [True,
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
               '38540': [False,
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
               '38564': [False,
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
               '38636': [True,
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
 'unwired_inputs': {'38650': {'code': 5, 'source': 'explicit supplied fault 5', 'status': True},
                    '38668': {'opaque': 'explicit Void argument'},
                    '38671': -2147483648,
                    '38674': 'explicit unwired String',
                    '38686': 65535}}
class NewSourceCases(unittest.TestCase):
 def verify(self,p,r):
  expected=[]
  # Independent concrete source mutations, no module plan-derived expectation.
  for read,write,index,value in(('38118','38100',3,True),('38189','38173',3,False),('38267','38251',2,True),('38327','38311',2,False),('38564','38546',4,False)):
   x=list(p['snapshots'][read]);x[index]=value;expected.append((write,x))
  x=list(p['snapshots']['38540']);x[17]=False;x[14]=True;x[12]=False;expected.append(('38519',x));expected.append(('38124',True))
  actual={x['node_uid']:x['value']for x in r['writes']};check(actual==dict(expected));check(r['completed_stages']==['38074','38157','38205','38235','38295','38483','38592']);check(r['selected_body_completed']);check(not r['pending_leaf_uids'])
  calls={x['node_uid']:x['input_ports']for x in r['leaf_calls']};check([calls[u][f]for u,f in(('38132','38137'),('38223','38228'),('38273','38278'),('38628','38633'))]==[150,3000,150,100]);check(calls['38642']['38656']==p['snapshots']['38636']);check(calls['38659']['38689']==p['leaf_returns']['38642']['38653'])
  for k in m.LIMITS:check(r[k]is False)
 def test_full_and_fresh_reads(self):
  for seed in range(12):
   p=copy.deepcopy(FULL)
   for j,u in enumerate(sorted(p['snapshots'])):p['snapshots'][u]=[(i+seed+j)%2==0 for i in range(len(p['snapshots'][u]))]
   r=accepted(p);self.verify(p,r)
  p=copy.deepcopy(FULL);tokens,a=args(p);r=m.replay_event(True,tokens,**a);COUNTS['accepted']+=1
  calls={x['node_uid']:x['input_ports']for x in r['leaf_calls']};check(calls['38642']['38656']is a['snapshots']['38636']);check(calls['38642']['38644']is a['reference_bindings']['38610']['native_ref']);check(calls['38642']['38650']is a['unwired_inputs']['38650']);check(calls['38659']['38689']is a['leaf_returns']['38642']['38653']);check(r['leaf_returns'][-1]['output_ports']is a['leaf_returns']['38628'])
  WITNESS.append(['full',r['completed_stages'],[x['node_uid']for x in r['writes']]])
 def test_partial_orders_and_inflight(self):
  # Independent source chain order, unrelated Wait/ACTION may interleave.
  stages=[(0,6,(('step','38118'),('step','38108'),('step','38100')), (('step','38124'),),(('leaf_call','38132'),('leaf_return','38132'))),
          (14,5,(('step','38267'),('step','38257'),('step','38251')), (('leaf_call','38273'),('leaf_return','38273')))]
  for spec in stages:
   start,length=spec[:2];chains=spec[2:];items=[x for c in chains for x in c]
   for order in itertools.permutations(items):
    if not all([order.index(x)for x in c]==sorted(order.index(x)for x in c)for c in chains):continue
    p=copy.deepcopy(FULL);p['schedule'][start:start+length]=[dict(kind=k,uid=u)for k,u in order];r=accepted(p);self.verify(p,r)
  # Stage6 Wait remains independent from the snapshot->PSP->handler chain.
  a=[('step','38636'),('leaf_call','38642'),('leaf_return','38642'),('leaf_call','38659'),('leaf_return','38659')];b=[('leaf_call','38628'),('leaf_return','38628')]
  for pos in itertools.combinations(range(7),2):
   ia=iter(a);ib=iter(b);order=[next(ib)if i in pos else next(ia)for i in range(7)];p=copy.deepcopy(FULL);p['schedule'][-8:-1]=[dict(kind=k,uid=u)for k,u in order];r=accepted(p);self.verify(p,r)
  for n in range(40):
   p=copy.deepcopy(FULL);p['schedule']=p['schedule'][:n];r=accepted(p);check(r['selected_body_completed']==(n==39));check(len(r['completed_stages'])==sum(x['kind']=='stage_complete'for x in p['schedule']))
  p=copy.deepcopy(FULL);p['schedule']=p['schedule'][:5];p['leaf_returns']={};r=accepted(p);check(r['pending_leaf_uids']==['38132']);check(r['completed_stages']==[])
  WITNESS.append(['orders-prefixes','source-owned'])
 def test_false_nonaccess(self):
  z=Poison();r=m.replay_event(False,z,snapshots=z,leaf_returns=z,unwired_inputs=z,reference_bindings=z,literal_inputs=z);COUNTS['accepted']+=1;check(r['selected_case_frame']=='38045');check(not r['writes']);check(not r['leaf_calls']);check(r['selected_body_completed'])
  p=copy.deepcopy(FULL);p.update(new_value=False,schedule=z,snapshots=z,leaf_returns=z,unwired_inputs=z,reference_bindings=z,literal_inputs=z);r=accepted(p);check(not r['leaf_calls'])
  for v in(0,1,None,'True',[]):p=copy.deepcopy(FULL);p['new_value']=v;refused(p)
 def test_typed_domains_and_snapshots(self):
  for u in FULL['snapshots']:
   for v in(None,True,{},FULL['snapshots'][u][:-1],FULL['snapshots'][u]+[False],[0]*len(FULL['snapshots'][u])):p=copy.deepcopy(FULL);p['snapshots'][u]=v;refused(p)
  for u in FULL['literal_inputs']:
   for v in(None,0,True,'False',[],float('nan')):p=copy.deepcopy(FULL);p['literal_inputs'][u]=v;refused(p)
   p=copy.deepcopy(FULL);del p['literal_inputs'][u];refused(p)
  for uid,port,bad in(('38132','38134',-1),('38223','38225',4294967296),('38273','38275',True),('38628','38630',1.0),('38659','38662',1),('38659','38665',2147483648),('38659','38677',None),('38659','38683',[])):
   p=copy.deepcopy(FULL);p['leaf_returns'][uid][port]=bad;refused(p)
  for face,bad in(('38671',True),('38671',-2147483649),('38674',42),('38686',65536),('38686',-1)):
   p=copy.deepcopy(FULL);p['unwired_inputs'][face]=bad;refused(p)
  for field,bad in(('status',1),('code',True),('code',2147483648),('source',None)):
   p=copy.deepcopy(FULL);p['leaf_returns']['38642']['38653'][field]=bad;refused(p)
  p=copy.deepcopy(FULL);p['reference_bindings']['38610']['saved_uri']='wrong';refused(p)
  p=copy.deepcopy(FULL);p['reference_bindings']['38610']['constant_uid']='wrong';refused(p)
 def test_schedule_dependency_refusals(self):
  bad=[[],[dict(kind='step',uid='38108')],[dict(kind='step',uid='38100')],[dict(kind='leaf_return',uid='38132')],[dict(kind='stage_complete',uid='38074')],[dict(kind='step',uid='38636')]]
  # Empty is accepted prefix, separate from incomplete invalid joins.
  p=copy.deepcopy(FULL);p['schedule']=bad.pop(0);check(not accepted(p)['selected_body_completed'])
  for rows in bad:p=copy.deepcopy(FULL);p['schedule']=rows;refused(p)
  for i in(0,1,6,7,13,19,23,30):
   p=copy.deepcopy(FULL);p['schedule']=p['schedule'][:i]+p['schedule'][i+1:];refused(p)
  p=copy.deepcopy(FULL);p['schedule']=p['schedule'][:-1];check(not accepted(p)['selected_body_completed'])
  p=copy.deepcopy(FULL);p['schedule'].append(dict(kind='step',uid='38118'));refused(p)
  p=copy.deepcopy(FULL);p['schedule'][0]['kind']='callback';refused(p)
  p=copy.deepcopy(FULL);p['schedule'][0]['uid']='38108';refused(p)
  WITNESS.append(['refusals',COUNTS['refused']])
 def test_identity_envelope_and_json(self):
  for k in('source_id','source_version','event_uid','frame_uid'):
   p=copy.deepcopy(FULL);p[k]='wrong';refused(p);p=copy.deepcopy(FULL);del p[k];refused(p)
  for k in('native_execution','field_index_bindings','whole_event_equivalence'):p=copy.deepcopy(FULL);p[k]=False;refused(p)
  for k in('snapshots','leaf_returns','unwired_inputs','reference_bindings','literal_inputs'):
   p=copy.deepcopy(FULL);p[k]['unknown']='x';refused(p)
  for k,v in(('38668',object()),('38668',float('inf')),('38668',{1:False})):
   p=copy.deepcopy(FULL);p['unwired_inputs'][k]=v;refused(p)
  p=copy.deepcopy(FULL);p['leaf_returns']['38642']['38647']=object();refused(p)
  p=copy.deepcopy(FULL);p['schedule'][0]['extra']=0;refused(p)
  # Supplied errors never imply success or gate any stage.
  for b in(False,True):
   p=copy.deepcopy(FULL);p['leaf_returns']['38642']['38653']['status']=b;r=accepted(p);check(r['selected_body_completed'])
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(NewSourceCases));out=dict(status='PASS'if result.wasSuccessful()else'FAIL',python_version=sys.version,methods=result.testsRun,counts=COUNTS,witness_sha256=hashlib.sha256(json.dumps(WITNESS,sort_keys=True,separators=(',',':')).encode('ascii')).hexdigest().upper())
 if len(sys.argv)>1:
  with open(sys.argv[1],'w')as f:json.dump(out,f,sort_keys=True,indent=2)
 print(json.dumps(out,sort_keys=True));sys.exit(0 if result.wasSuccessful()else 1)
