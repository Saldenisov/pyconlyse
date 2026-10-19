import copy,hashlib,itertools,json,os,sys,unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from elyse_agent import saved_acq_event_35942 as m
COUNTS=dict(accepted=0,refused=0,checks=0);WITNESS=[]
def check(v):
 COUNTS['checks']+=1
 if not v:raise AssertionError('independent35942 source expectation failed')
def accepted(p):
 r=m.replay_saved_acq_event_35942(p);COUNTS['accepted']+=1;return r
def refused(p):
 try:m.replay_saved_acq_event_35942(p)
 except(ValueError,TypeError,KeyError,IndexError):COUNTS['refused']+=1;return
 raise AssertionError('bounded domain must refuse')
def args(p):
 classes={'step':m.Step,'leaf_call':m.LeafCall,'leaf_return':m.LeafReturn,'stage_complete':m.StageComplete}
 def err(v):return m.ErrorValue(v['status'],v['code'],v['source'])
 r=dict(snapshots={u:tuple(v)for u,v in p['snapshots'].items()},leaf_returns=copy.deepcopy(p['leaf_returns']),unwired_inputs=copy.deepcopy(p['unwired_inputs']),reference_bindings=copy.deepcopy(p['reference_bindings']),literal_inputs=dict(p['literal_inputs']))
 r['unwired_inputs']['36501']=err(r['unwired_inputs']['36501']);r['leaf_returns']['36493']['36504']=err(r['leaf_returns']['36493']['36504']);r['leaf_returns']['36510']['36532']=err(r['leaf_returns']['36510']['36532'])
 return tuple(classes[x['kind']](x['uid'])for x in p['schedule']),r
class Poison:
 def __getitem__(self,k):raise AssertionError('unselected body accessed')
 def __iter__(self):raise AssertionError('unselected body iterated')
FULL={'event_uid': '43',
 'frame_uid': '35942',
 'leaf_returns': {'36081': {'36083': 101},
                  '36181': {'36183': 102},
                  '36232': {'36235': 103},
                  '36322': {'36324': 104},
                  '36479': {'36481': 105},
                  '36493': {'36498': {'opaque': 'explicit returned DPS ref'},
                            '36504': {'code': -9, 'source': 'explicit supplied fault -9', 'status': True}},
                  '36510': {'36513': True,
                            '36516': 2147483647,
                            '36529': 'supplied handler source',
                            '36532': {'code': -10, 'source': 'explicit supplied fault -10', 'status': True},
                            '36535': 'unused supplied message'}},
 'literal_inputs': {'36121': False, '36261': False, '36340': False, '36360': False, '42575': False},
 'new_value': True,
 'reference_bindings': {'36461': {'constant_uid': '36461',
                                  'native_ref': {'opaque_supplied_ref': 'DPS'},
                                  'saved_uri': 'ni.var.psp://10.20.30.2/SUPERVISION/DPS'}},
 'schedule': [{'kind': 'step', 'uid': '36067'},
              {'kind': 'step', 'uid': '36057'},
              {'kind': 'step', 'uid': '36049'},
              {'kind': 'step', 'uid': '36073'},
              {'kind': 'leaf_call', 'uid': '36081'},
              {'kind': 'leaf_return', 'uid': '36081'},
              {'kind': 'stage_complete', 'uid': '36023'},
              {'kind': 'step', 'uid': '36147'},
              {'kind': 'step', 'uid': '36137'},
              {'kind': 'step', 'uid': '36131'},
              {'kind': 'stage_complete', 'uid': '36115'},
              {'kind': 'leaf_call', 'uid': '36181'},
              {'kind': 'leaf_return', 'uid': '36181'},
              {'kind': 'stage_complete', 'uid': '36163'},
              {'kind': 'leaf_call', 'uid': '36232'},
              {'kind': 'step', 'uid': '36226'},
              {'kind': 'step', 'uid': '36215'},
              {'kind': 'step', 'uid': '36209'},
              {'kind': 'leaf_return', 'uid': '36232'},
              {'kind': 'stage_complete', 'uid': '36193'},
              {'kind': 'step', 'uid': '36287'},
              {'kind': 'step', 'uid': '36277'},
              {'kind': 'step', 'uid': '36271'},
              {'kind': 'stage_complete', 'uid': '36255'},
              {'kind': 'leaf_call', 'uid': '36322'},
              {'kind': 'leaf_return', 'uid': '36322'},
              {'kind': 'stage_complete', 'uid': '36304'},
              {'kind': 'step', 'uid': '36415'},
              {'kind': 'step', 'uid': '36405'},
              {'kind': 'step', 'uid': '36397'},
              {'kind': 'step', 'uid': '36391'},
              {'kind': 'step', 'uid': '36378'},
              {'kind': 'step', 'uid': '36370'},
              {'kind': 'stage_complete', 'uid': '36334'},
              {'kind': 'step', 'uid': '36487'},
              {'kind': 'leaf_call', 'uid': '36493'},
              {'kind': 'leaf_call', 'uid': '36479'},
              {'kind': 'leaf_return', 'uid': '36493'},
              {'kind': 'leaf_call', 'uid': '36510'},
              {'kind': 'leaf_return', 'uid': '36510'},
              {'kind': 'leaf_return', 'uid': '36479'},
              {'kind': 'stage_complete', 'uid': '36443'}],
 'snapshots': {'36067': [True,
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
               '36147': [False,
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
               '36226': [False,
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
               '36287': [True,
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
               '36391': [False,
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
               '36415': [False,
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
               '36487': [True,
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
 'unwired_inputs': {'36501': {'code': 5, 'source': 'explicit supplied fault 5', 'status': True},
                    '36520': {'opaque': 'explicit Void argument'},
                    '36523': -2147483648,
                    '36526': 'explicit unwired String',
                    '36538': 65535}}
class NewSourceCases(unittest.TestCase):
 def verify(self,p,r):
  expected={}
  for read,write,index,value in(('36067','36049',16,True),('36147','36131',16,False),('36226','36209',2,True),('36287','36271',2,False),('36415','36397',8,False)):
   v=list(p['snapshots'][read]);v[index]=value;expected[write]=v
  v=list(p['snapshots']['36391']);v[29]=False;v[26]=True;v[24]=False;expected['36370']=v;expected['36073']=True
  check({x['node_uid']:x['value']for x in r['writes']}==expected)
  check(r['completed_stages']==['36023','36115','36163','36193','36255','36304','36334','36443']);check(r['selected_body_completed']);check(not r['pending_leaf_uids'])
  calls={x['node_uid']:x['input_ports']for x in r['leaf_calls']}
  check([calls[u][f]for u,f in(('36081','36086'),('36181','36186'),('36232','36238'),('36322','36327'),('36479','36484'))]==[150,500,150,250,100])
  check(calls['36493']['36507']==p['snapshots']['36487']);check(calls['36510']['36541']==p['leaf_returns']['36493']['36504'])
  for k in m.LIMITS:check(r[k]is False)
 def test_full_and_independent_reads(self):
  for seed in range(12):
   p=copy.deepcopy(FULL)
   for j,u in enumerate(sorted(p['snapshots'])):p['snapshots'][u]=[(i+seed+j)%2==0 for i in range(len(p['snapshots'][u]))]
   r=accepted(p);self.verify(p,r)
  tokens,a=args(FULL);r=m.replay_event(True,tokens,**a);COUNTS['accepted']+=1
  calls={x['node_uid']:x['input_ports']for x in r['leaf_calls']}
  check(calls['36493']['36507']is a['snapshots']['36487']);check(calls['36493']['36495']is a['reference_bindings']['36461']['native_ref']);check(calls['36493']['36501']is a['unwired_inputs']['36501']);check(calls['36510']['36541']is a['leaf_returns']['36493']['36504'])
  check(r['leaf_returns'][-1]['output_ports']is a['leaf_returns']['36479']);check(a['snapshots']['36415']!=a['snapshots']['36487'])
  for x in r['writes']:
   if x['node_uid']!='36073':check(type(x['value'])is tuple)
  WITNESS.append(['full','fields16TrueFalse2TrueFalseEPS29False26True24FalseDPS8False',r['completed_stages']])
 def test_source_orders_prefixes_and_inflight(self):
  specs=[(0,6,(('step','36067'),('step','36057'),('step','36049')),(('step','36073'),),(('leaf_call','36081'),('leaf_return','36081'))),
         (14,5,(('step','36226'),('step','36215'),('step','36209')),(('leaf_call','36232'),('leaf_return','36232')))]
  for spec in specs:
   start,length=spec[:2];chains=spec[2:];items=[x for c in chains for x in c]
   for order in itertools.permutations(items):
    if any([order.index(x)for x in c]!=sorted(order.index(x)for x in c)for c in chains):continue
    p=copy.deepcopy(FULL);p['schedule'][start:start+length]=[dict(kind=k,uid=u)for k,u in order];self.verify(p,accepted(p))
  # Two fresh reads/writes in stage6 share no physical source wire.
  a=[('step','36415'),('step','36405'),('step','36397')];b=[('step','36391'),('step','36378'),('step','36370')]
  for pos in itertools.combinations(range(6),3):
   ia=iter(a);ib=iter(b);order=[next(ia)if i in pos else next(ib)for i in range(6)];p=copy.deepcopy(FULL);p['schedule'][27:33]=[dict(kind=k,uid=u)for k,u in order];self.verify(p,accepted(p))
  a=[('step','36487'),('leaf_call','36493'),('leaf_return','36493'),('leaf_call','36510'),('leaf_return','36510')];b=[('leaf_call','36479'),('leaf_return','36479')]
  for pos in itertools.combinations(range(7),2):
   ia=iter(a);ib=iter(b);order=[next(ib)if i in pos else next(ia)for i in range(7)];p=copy.deepcopy(FULL);p['schedule'][-8:-1]=[dict(kind=k,uid=u)for k,u in order];self.verify(p,accepted(p))
  for n in range(43):
   p=copy.deepcopy(FULL);p['schedule']=p['schedule'][:n];r=accepted(p);check(r['selected_body_completed']==(n==42));check(len(r['completed_stages'])==sum(x['kind']=='stage_complete'for x in p['schedule']))
  p=copy.deepcopy(FULL);p['schedule']=p['schedule'][:5];p['leaf_returns']={};r=accepted(p);check(r['pending_leaf_uids']==['36081']);check(r['completed_stages']==[])
  WITNESS.append(['independent-stages','8','prefixes42'])
 def test_false_nonaccess(self):
  z=Poison();r=m.replay_event(False,z,snapshots=z,leaf_returns=z,unwired_inputs=z,reference_bindings=z,literal_inputs=z);COUNTS['accepted']+=1
  check(r['selected_case_frame']=='35996');check(not r['writes']);check(not r['leaf_calls']);check(r['selected_body_completed'])
  p=copy.deepcopy(FULL);p.update(new_value=False,schedule=z,snapshots=z,leaf_returns=z,unwired_inputs=z,reference_bindings=z,literal_inputs=z);check(not accepted(p)['leaf_calls'])
  for v in(0,1,None,'True',[]):p=copy.deepcopy(FULL);p['new_value']=v;refused(p)
 def test_typed_domains_and_carriers(self):
  for u in FULL['snapshots']:
   for v in(None,True,{},FULL['snapshots'][u][:-1],FULL['snapshots'][u]+[False],[0]*len(FULL['snapshots'][u])):p=copy.deepcopy(FULL);p['snapshots'][u]=v;refused(p)
  for u in('36067','36147','36226','36287'):
   p=copy.deepcopy(FULL);p['snapshots'][u]=[False]*40;refused(p)
  for u in FULL['literal_inputs']:
   for v in(None,0,True,'False',[],float('nan')):p=copy.deepcopy(FULL);p['literal_inputs'][u]=v;refused(p)
   p=copy.deepcopy(FULL);del p['literal_inputs'][u];refused(p)
  for uid,port,bad in(('36081','36083',-1),('36181','36183',4294967296),('36232','36235',True),('36322','36324',True),('36479','36481',1.0),('36510','36513',1),('36510','36516',2147483648),('36510','36529',None),('36510','36535',[])):
   p=copy.deepcopy(FULL);p['leaf_returns'][uid][port]=bad;refused(p)
  for face,bad in(('36523',True),('36523',-2147483649),('36526',42),('36538',65536),('36538',-1)):
   p=copy.deepcopy(FULL);p['unwired_inputs'][face]=bad;refused(p)
  for field,bad in(('status',1),('code',True),('code',2147483648),('source',None)):
   p=copy.deepcopy(FULL);p['leaf_returns']['36493']['36504'][field]=bad;refused(p)
  p=copy.deepcopy(FULL);p['reference_bindings']['36461']['saved_uri']='wrong';refused(p)
  p=copy.deepcopy(FULL);p['reference_bindings']['36461']['constant_uid']='wrong';refused(p)
 def test_schedule_refusals(self):
  for k,u in(('step','36057'),('step','36049'),('leaf_return','36081'),('stage_complete','36023'),('step','36487')):
   p=copy.deepcopy(FULL);p['schedule']=[dict(kind=k,uid=u)];refused(p)
  # Removing each completion or step that a complete saved schedule needs must refuse.
  for i in(0,1,6,7,10,13,19,23,26,30,33,34,37,38,40):
   p=copy.deepcopy(FULL);p['schedule']=p['schedule'][:i]+p['schedule'][i+1:];refused(p)
  p=copy.deepcopy(FULL);p['schedule']=p['schedule'][:-1];check(not accepted(p)['selected_body_completed'])
  p=copy.deepcopy(FULL);p['schedule'].append(dict(kind='step',uid='36067'));refused(p)
  p=copy.deepcopy(FULL);p['schedule'][0]['kind']='callback';refused(p)
  WITNESS.append(['schedule-refusals',COUNTS['refused']])
 def test_envelope_and_finite_json(self):
  for k in('source_id','source_version','event_uid','frame_uid'):
   p=copy.deepcopy(FULL);p[k]='wrong';refused(p);p=copy.deepcopy(FULL);del p[k];refused(p)
  for k in('native_execution','field_index_bindings','whole_event_equivalence'):p=copy.deepcopy(FULL);p[k]=False;refused(p)
  for k in('snapshots','leaf_returns','unwired_inputs','reference_bindings','literal_inputs'):
   p=copy.deepcopy(FULL);p[k]['unknown']='x';refused(p)
  for v in(object(),float('inf'),{1:False}):p=copy.deepcopy(FULL);p['unwired_inputs']['36520']=v;refused(p)
  p=copy.deepcopy(FULL);p['leaf_returns']['36493']['foreign']=object();refused(p)
  p=copy.deepcopy(FULL);p['schedule'][0]['extra']=0;refused(p)
  for b in(False,True):
   p=copy.deepcopy(FULL);p['leaf_returns']['36493']['36504']['status']=b;check(accepted(p)['selected_body_completed'])
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(NewSourceCases));out=dict(status='PASS'if result.wasSuccessful()else'FAIL',python_version=sys.version,methods=result.testsRun,counts=COUNTS,witness_sha256=hashlib.sha256(json.dumps(WITNESS,sort_keys=True,separators=(',',':')).encode('ascii')).hexdigest().upper())
 if len(sys.argv)>1:
  with open(sys.argv[1],'w')as f:json.dump(out,f,sort_keys=True,indent=2)
 print(json.dumps(out,sort_keys=True));sys.exit(0 if result.wasSuccessful()else 1)
