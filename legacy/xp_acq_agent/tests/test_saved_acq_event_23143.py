import copy,hashlib,itertools,json,os,sys,unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from elyse_agent import saved_acq_event_23143 as m
COUNTS=dict(accepted=0,refused=0,checks=0);WITNESS=[]
def check(v):
 COUNTS['checks']+=1
 if not v:raise AssertionError('independent23143 source expectation failed')
def accepted(p):
 r=m.replay_saved_acq_event_23143(p);COUNTS['accepted']+=1;return r
def refused(p):
 try:m.replay_saved_acq_event_23143(p)
 except(ValueError,TypeError,KeyError,IndexError):COUNTS['refused']+=1;return
 raise AssertionError('bounded domain must refuse')
def args(p):
 classes={'step':m.Step,'leaf_call':m.LeafCall,'leaf_return':m.LeafReturn,'stage_complete':m.StageComplete}
 def err(v):return m.ErrorValue(v['status'],v['code'],v['source'])
 r=dict(snapshots={u:tuple(v)for u,v in p['snapshots'].items()},leaf_returns=copy.deepcopy(p['leaf_returns']),unwired_inputs=copy.deepcopy(p['unwired_inputs']),reference_bindings=copy.deepcopy(p['reference_bindings']),literal_inputs=dict(p['literal_inputs']))
 r['unwired_inputs']['29505']=err(r['unwired_inputs']['29505']);r['leaf_returns']['29442']['29560']=err(r['leaf_returns']['29442']['29560']);r['leaf_returns']['29616']['29706']=err(r['leaf_returns']['29616']['29706'])
 return tuple(classes[x['kind']](x['uid'])for x in p['schedule']),r
class Poison:
 def __getitem__(self,k):raise AssertionError('unselected body accessed')
 def __iter__(self):raise AssertionError('unselected body iterated')
FULL={'event_uid': '43',
 'frame_uid': '23143',
 'leaf_returns': {'24789': {'24802': 101},
                  '28736': {'28756': 102},
                  '28924': {'28926': 103},
                  '29013': {'29015': 104},
                  '29398': {'29406': 105},
                  '29442': {'29478': {'opaque': 'explicit returned DPS ref'},
                            '29560': {'code': -9, 'source': 'explicit supplied fault -9', 'status': True}},
                  '29616': {'29652': True,
                            '29661': 2147483647,
                            '29697': 'supplied handler source',
                            '29706': {'code': -10, 'source': 'explicit supplied fault -10', 'status': True},
                            '29715': 'unused supplied message'}},
 'literal_inputs': {'25991': False, '28952': False, '29031': False, '29052': False, '40005': False},
 'new_value': True,
 'reference_bindings': {'29221': {'constant_uid': '29221',
                                  'native_ref': {'opaque_supplied_ref': 'DPS'},
                                  'saved_uri': 'ni.var.psp://10.20.30.2/SUPERVISION/DPS'}},
 'schedule': [{'kind': 'step', 'uid': '24474'},
              {'kind': 'step', 'uid': '24433'},
              {'kind': 'step', 'uid': '24413'},
              {'kind': 'step', 'uid': '24495'},
              {'kind': 'leaf_call', 'uid': '24789'},
              {'kind': 'leaf_return', 'uid': '24789'},
              {'kind': 'stage_complete', 'uid': '24338'},
              {'kind': 'step', 'uid': '27893'},
              {'kind': 'step', 'uid': '26303'},
              {'kind': 'step', 'uid': '26145'},
              {'kind': 'stage_complete', 'uid': '25366'},
              {'kind': 'leaf_call', 'uid': '28736'},
              {'kind': 'leaf_return', 'uid': '28736'},
              {'kind': 'stage_complete', 'uid': '28640'},
              {'kind': 'leaf_call', 'uid': '28924'},
              {'kind': 'step', 'uid': '28916'},
              {'kind': 'step', 'uid': '28895'},
              {'kind': 'step', 'uid': '28881'},
              {'kind': 'leaf_return', 'uid': '28924'},
              {'kind': 'stage_complete', 'uid': '28837'},
              {'kind': 'step', 'uid': '28978'},
              {'kind': 'step', 'uid': '28968'},
              {'kind': 'step', 'uid': '28962'},
              {'kind': 'stage_complete', 'uid': '28946'},
              {'kind': 'leaf_call', 'uid': '29013'},
              {'kind': 'leaf_return', 'uid': '29013'},
              {'kind': 'stage_complete', 'uid': '28995'},
              {'kind': 'step', 'uid': '29175'},
              {'kind': 'step', 'uid': '29162'},
              {'kind': 'step', 'uid': '29094'},
              {'kind': 'step', 'uid': '29087'},
              {'kind': 'step', 'uid': '29073'},
              {'kind': 'step', 'uid': '29062'},
              {'kind': 'stage_complete', 'uid': '29025'},
              {'kind': 'step', 'uid': '29424'},
              {'kind': 'leaf_call', 'uid': '29442'},
              {'kind': 'leaf_call', 'uid': '29398'},
              {'kind': 'leaf_return', 'uid': '29442'},
              {'kind': 'leaf_call', 'uid': '29616'},
              {'kind': 'leaf_return', 'uid': '29616'},
              {'kind': 'leaf_return', 'uid': '29398'},
              {'kind': 'stage_complete', 'uid': '29203'}],
 'snapshots': {'24474': [True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
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
               '27893': [False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
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
               '28916': [False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
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
               '28978': [True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
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
               '29087': [False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
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
               '29175': [False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
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
               '29424': [True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
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
 'unwired_inputs': {'29505': {'code': 5, 'source': 'explicit supplied fault 5', 'status': True},
                    '29670': {'opaque': 'explicit Void argument'},
                    '29679': -2147483648,
                    '29688': 'explicit unwired String',
                    '29723': 65535}}
class NewSourceCases(unittest.TestCase):
 def verify(self,p,r):
  expected={}
  for read,write,index,value in(('24474','24413',5,True),('27893','26145',5,False),('28916','28881',2,True),('28978','28962',2,False),('29175','29094',6,False)):
   v=list(p['snapshots'][read]);v[index]=value;expected[write]=v
  v=list(p['snapshots']['29087']);v[23]=False;v[20]=True;v[18]=False;expected['29062']=v;expected['24495']=True
  check({x['node_uid']:x['value']for x in r['writes']}==expected)
  check(r['completed_stages']==['24338','25366','28640','28837','28946','28995','29025','29203']);check(r['selected_body_completed']);check(not r['pending_leaf_uids'])
  calls={x['node_uid']:x['input_ports']for x in r['leaf_calls']}
  check([calls[u][f]for u,f in(('24789','24815'),('28736','28820'),('28924','28929'),('29013','29018'),('29398','29415'))]==[150,500,150,250,100])
  check(calls['29442']['29569']==p['snapshots']['29424']);check(calls['29616']['29732']==p['leaf_returns']['29442']['29560'])
  for k in m.LIMITS:check(r[k]is False)
 def test_full_and_independent_reads(self):
  for seed in range(12):
   p=copy.deepcopy(FULL)
   for j,u in enumerate(sorted(p['snapshots'])):p['snapshots'][u]=[(i+seed+j)%2==0 for i in range(len(p['snapshots'][u]))]
   r=accepted(p);self.verify(p,r)
  tokens,a=args(FULL);r=m.replay_event(True,tokens,**a);COUNTS['accepted']+=1
  calls={x['node_uid']:x['input_ports']for x in r['leaf_calls']}
  check(calls['29442']['29569']is a['snapshots']['29424']);check(calls['29442']['29445']is a['reference_bindings']['29221']['native_ref']);check(calls['29442']['29505']is a['unwired_inputs']['29505']);check(calls['29616']['29732']is a['leaf_returns']['29442']['29560'])
  check(r['leaf_returns'][-1]['output_ports']is a['leaf_returns']['29398']);check(a['snapshots']['29175']!=a['snapshots']['29424'])
  for x in r['writes']:
   if x['node_uid']!='24495':check(type(x['value'])is tuple)
  WITNESS.append(['full','fields5TrueFalse2TrueFalseEPS23False20True18FalseDPS6False',r['completed_stages']])
 def test_source_orders_prefixes_and_inflight(self):
  specs=[(0,6,(('step','24474'),('step','24433'),('step','24413')),(('step','24495'),),(('leaf_call','24789'),('leaf_return','24789'))),
         (14,5,(('step','28916'),('step','28895'),('step','28881')),(('leaf_call','28924'),('leaf_return','28924')))]
  for spec in specs:
   start,length=spec[:2];chains=spec[2:];items=[x for c in chains for x in c]
   for order in itertools.permutations(items):
    if any([order.index(x)for x in c]!=sorted(order.index(x)for x in c)for c in chains):continue
    p=copy.deepcopy(FULL);p['schedule'][start:start+length]=[dict(kind=k,uid=u)for k,u in order];self.verify(p,accepted(p))
  # Two fresh reads/writes in stage6 share no physical source wire.
  a=[('step','29175'),('step','29162'),('step','29094')];b=[('step','29087'),('step','29073'),('step','29062')]
  for pos in itertools.combinations(range(6),3):
   ia=iter(a);ib=iter(b);order=[next(ia)if i in pos else next(ib)for i in range(6)];p=copy.deepcopy(FULL);p['schedule'][27:33]=[dict(kind=k,uid=u)for k,u in order];self.verify(p,accepted(p))
  a=[('step','29424'),('leaf_call','29442'),('leaf_return','29442'),('leaf_call','29616'),('leaf_return','29616')];b=[('leaf_call','29398'),('leaf_return','29398')]
  for pos in itertools.combinations(range(7),2):
   ia=iter(a);ib=iter(b);order=[next(ib)if i in pos else next(ia)for i in range(7)];p=copy.deepcopy(FULL);p['schedule'][-8:-1]=[dict(kind=k,uid=u)for k,u in order];self.verify(p,accepted(p))
  for n in range(43):
   p=copy.deepcopy(FULL);p['schedule']=p['schedule'][:n];r=accepted(p);check(r['selected_body_completed']==(n==42));check(len(r['completed_stages'])==sum(x['kind']=='stage_complete'for x in p['schedule']))
  p=copy.deepcopy(FULL);p['schedule']=p['schedule'][:5];p['leaf_returns']={};r=accepted(p);check(r['pending_leaf_uids']==['24789']);check(r['completed_stages']==[])
  WITNESS.append(['independent-stages','8','prefixes42'])
 def test_false_nonaccess(self):
  z=Poison();r=m.replay_event(False,z,snapshots=z,leaf_returns=z,unwired_inputs=z,reference_bindings=z,literal_inputs=z);COUNTS['accepted']+=1
  check(r['selected_case_frame']=='24286');check(not r['writes']);check(not r['leaf_calls']);check(r['selected_body_completed'])
  p=copy.deepcopy(FULL);p.update(new_value=False,schedule=z,snapshots=z,leaf_returns=z,unwired_inputs=z,reference_bindings=z,literal_inputs=z);check(not accepted(p)['leaf_calls'])
  for v in(0,1,None,'True',[]):p=copy.deepcopy(FULL);p['new_value']=v;refused(p)
 def test_typed_domains_and_carriers(self):
  for u in FULL['snapshots']:
   for v in(None,True,{},FULL['snapshots'][u][:-1],FULL['snapshots'][u]+[False],[0]*len(FULL['snapshots'][u])):p=copy.deepcopy(FULL);p['snapshots'][u]=v;refused(p)
  for u in('24474','27893','28916','28978'):
   p=copy.deepcopy(FULL);p['snapshots'][u]=[False]*40;refused(p)
  for u in FULL['literal_inputs']:
   for v in(None,0,True,'False',[],float('nan')):p=copy.deepcopy(FULL);p['literal_inputs'][u]=v;refused(p)
   p=copy.deepcopy(FULL);del p['literal_inputs'][u];refused(p)
  for uid,port,bad in(('24789','24802',-1),('28736','28756',4294967296),('28924','28926',True),('29013','29015',True),('29398','29406',1.0),('29616','29652',1),('29616','29661',2147483648),('29616','29697',None),('29616','29715',[])):
   p=copy.deepcopy(FULL);p['leaf_returns'][uid][port]=bad;refused(p)
  for face,bad in(('29679',True),('29679',-2147483649),('29688',42),('29723',65536),('29723',-1)):
   p=copy.deepcopy(FULL);p['unwired_inputs'][face]=bad;refused(p)
  for field,bad in(('status',1),('code',True),('code',2147483648),('source',None)):
   p=copy.deepcopy(FULL);p['leaf_returns']['29442']['29560'][field]=bad;refused(p)
  p=copy.deepcopy(FULL);p['reference_bindings']['29221']['saved_uri']='wrong';refused(p)
  p=copy.deepcopy(FULL);p['reference_bindings']['29221']['constant_uid']='wrong';refused(p)
 def test_schedule_refusals(self):
  for k,u in(('step','24433'),('step','24413'),('leaf_return','24789'),('stage_complete','24338'),('step','29424')):
   p=copy.deepcopy(FULL);p['schedule']=[dict(kind=k,uid=u)];refused(p)
  # Removing each completion or step that a complete saved schedule needs must refuse.
  for i in(0,1,6,7,10,13,19,23,26,30,33,34,37,38,40):
   p=copy.deepcopy(FULL);p['schedule']=p['schedule'][:i]+p['schedule'][i+1:];refused(p)
  p=copy.deepcopy(FULL);p['schedule']=p['schedule'][:-1];check(not accepted(p)['selected_body_completed'])
  p=copy.deepcopy(FULL);p['schedule'].append(dict(kind='step',uid='24474'));refused(p)
  p=copy.deepcopy(FULL);p['schedule'][0]['kind']='callback';refused(p)
  WITNESS.append(['schedule-refusals',COUNTS['refused']])
 def test_envelope_and_finite_json(self):
  for k in('source_id','source_version','event_uid','frame_uid'):
   p=copy.deepcopy(FULL);p[k]='wrong';refused(p);p=copy.deepcopy(FULL);del p[k];refused(p)
  for k in('native_execution','field_index_bindings','whole_event_equivalence'):p=copy.deepcopy(FULL);p[k]=False;refused(p)
  for k in('snapshots','leaf_returns','unwired_inputs','reference_bindings','literal_inputs'):
   p=copy.deepcopy(FULL);p[k]['unknown']='x';refused(p)
  for v in(object(),float('inf'),{1:False}):p=copy.deepcopy(FULL);p['unwired_inputs']['29670']=v;refused(p)
  p=copy.deepcopy(FULL);p['leaf_returns']['29442']['foreign']=object();refused(p)
  p=copy.deepcopy(FULL);p['schedule'][0]['extra']=0;refused(p)
  for b in(False,True):
   p=copy.deepcopy(FULL);p['leaf_returns']['29442']['29560']['status']=b;check(accepted(p)['selected_body_completed'])
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(NewSourceCases));out=dict(status='PASS'if result.wasSuccessful()else'FAIL',python_version=sys.version,methods=result.testsRun,counts=COUNTS,witness_sha256=hashlib.sha256(json.dumps(WITNESS,sort_keys=True,separators=(',',':')).encode('ascii')).hexdigest().upper())
 if len(sys.argv)>1:
  with open(sys.argv[1],'w')as f:json.dump(out,f,sort_keys=True,indent=2)
 print(json.dumps(out,sort_keys=True));sys.exit(0 if result.wasSuccessful()else 1)
