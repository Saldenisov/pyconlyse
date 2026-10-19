"""New original40079 expectations; only isolated current pure core executes."""
import copy,hashlib,itertools,json,os,sys,unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from elyse_agent import saved_acq_event_40079 as m
COUNTS=dict(accepted=0,refused=0,checks=0);WITNESS=[]
def check(v):
 COUNTS['checks']+=1
 if not v:raise AssertionError('independent40079 source expectation failed')
def accepted(p):r=m.replay_saved_acq_event_40079(p);COUNTS['accepted']+=1;return r
def refused(p):
 try:m.replay_saved_acq_event_40079(p)
 except(ValueError,TypeError,KeyError,IndexError):COUNTS['refused']+=1;return
 raise AssertionError('bounded domain must refuse')
def args(p):
 classes={'step':m.Step,'leaf_call':m.LeafCall,'leaf_return':m.LeafReturn,'stage_complete':m.StageComplete};r=dict(snapshots={u:tuple(v)for u,v in p['snapshots'].items()},leaf_returns=copy.deepcopy(p['leaf_returns']),unwired_inputs=copy.deepcopy(p['unwired_inputs']),reference_bindings=copy.deepcopy(p['reference_bindings']),literal_inputs=dict(p['literal_inputs']))
 for u,f in(('38600','45219'),('50796','50887'),('40623','40634'),('40640','40661')):
  v=r['leaf_returns'][u][f];r['leaf_returns'][u][f]=m.ErrorValue(v['status'],v['code'],v['source'])
 v=r['unwired_inputs']['40631'];r['unwired_inputs']['40631']=m.ErrorValue(v['status'],v['code'],v['source'])
 return tuple(classes[x['kind']](x['uid'])for x in p['schedule']),r
def span(p,frame):
 end=next(i for i,x in enumerate(p['schedule'])if x==dict(kind='stage_complete',uid=frame));start=max([-1]+[i for i,x in enumerate(p['schedule'][:end])if x['kind']=='stage_complete'])+1;return start,end
class Poison:
 def __getitem__(self,k):raise AssertionError('unselected body accessed')
 def __iter__(self):raise AssertionError('unselected body iterated')
FULL={'event_uid': '43',
 'frame_uid': '40079',
 'leaf_returns': {'38600': {'45219': {'code': -11, 'source': 'explicit supplied fault -11', 'status': True}},
                  '40220': {'40222': 101},
                  '40311': {'40313': 102},
                  '40361': {'40363': 103},
                  '40451': {'40453': 104},
                  '40609': {'40611': 105},
                  '40623': {'40628': {'opaque': 'explicit returned DPS ref'},
                            '40634': {'code': -9, 'source': 'explicit supplied fault -9', 'status': True}},
                  '40640': {'40643': True,
                            '40646': 2147483647,
                            '40658': 'supplied handler source',
                            '40661': {'code': -10, 'source': 'explicit supplied fault -10', 'status': True},
                            '40664': 'unused supplied message'},
                  '50176': {'50182': 106},
                  '50796': {'50836': True,
                            '50844': 2147483647,
                            '50881': 'supplied handler source',
                            '50887': {'code': -12, 'source': 'explicit supplied fault -12', 'status': True},
                            '50895': 'unused supplied message'}},
 'literal_inputs': {'40251': False, '40389': False, '40469': False, '40489': False},
 'new_value': True,
 'reference_bindings': {'40591': {'constant_uid': '40591',
                                  'native_ref': {'opaque_supplied_ref': 'DPS'},
                                  'saved_uri': 'ni.var.psp://10.20.30.2/SUPERVISION/DPS'}},
 'schedule': [{'kind': 'step', 'uid': '40206'},
              {'kind': 'step', 'uid': '40196'},
              {'kind': 'step', 'uid': '40188'},
              {'kind': 'step', 'uid': '40212'},
              {'kind': 'leaf_call', 'uid': '40220'},
              {'kind': 'leaf_return', 'uid': '40220'},
              {'kind': 'stage_complete', 'uid': '40162'},
              {'kind': 'step', 'uid': '40277'},
              {'kind': 'step', 'uid': '40267'},
              {'kind': 'step', 'uid': '40261'},
              {'kind': 'stage_complete', 'uid': '40245'},
              {'kind': 'leaf_call', 'uid': '40311'},
              {'kind': 'leaf_return', 'uid': '40311'},
              {'kind': 'stage_complete', 'uid': '46840'},
              {'kind': 'leaf_call', 'uid': '38600'},
              {'kind': 'leaf_return', 'uid': '38600'},
              {'kind': 'leaf_call', 'uid': '50796'},
              {'kind': 'leaf_return', 'uid': '50796'},
              {'kind': 'stage_complete', 'uid': '48404'},
              {'kind': 'leaf_call', 'uid': '50176'},
              {'kind': 'leaf_return', 'uid': '50176'},
              {'kind': 'stage_complete', 'uid': '49054'},
              {'kind': 'stage_complete', 'uid': '40293'},
              {'kind': 'leaf_call', 'uid': '40361'},
              {'kind': 'step', 'uid': '40355'},
              {'kind': 'step', 'uid': '40345'},
              {'kind': 'step', 'uid': '40339'},
              {'kind': 'leaf_return', 'uid': '40361'},
              {'kind': 'stage_complete', 'uid': '40323'},
              {'kind': 'step', 'uid': '40415'},
              {'kind': 'step', 'uid': '40405'},
              {'kind': 'step', 'uid': '40399'},
              {'kind': 'stage_complete', 'uid': '40383'},
              {'kind': 'leaf_call', 'uid': '40451'},
              {'kind': 'leaf_return', 'uid': '40451'},
              {'kind': 'stage_complete', 'uid': '40432'},
              {'kind': 'step', 'uid': '40544'},
              {'kind': 'step', 'uid': '40534'},
              {'kind': 'step', 'uid': '40526'},
              {'kind': 'step', 'uid': '40520'},
              {'kind': 'step', 'uid': '40507'},
              {'kind': 'step', 'uid': '40499'},
              {'kind': 'stage_complete', 'uid': '40463'},
              {'kind': 'step', 'uid': '40617'},
              {'kind': 'leaf_call', 'uid': '40623'},
              {'kind': 'leaf_call', 'uid': '40609'},
              {'kind': 'leaf_return', 'uid': '40623'},
              {'kind': 'leaf_call', 'uid': '40640'},
              {'kind': 'leaf_return', 'uid': '40640'},
              {'kind': 'leaf_return', 'uid': '40609'},
              {'kind': 'stage_complete', 'uid': '40573'}],
 'snapshots': {'40206': [True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
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
               '40277': [False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
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
               '40355': [False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
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
               '40415': [True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
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
               '40520': [False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
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
               '40544': [False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
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
               '40617': [True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
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
 'unwired_inputs': {'40631': {'code': 5, 'source': 'explicit supplied fault 5', 'status': True},
                    '40649': {'opaque': 'explicit Void argument'},
                    '40652': -2147483648,
                    '40655': 'explicit unwired String',
                    '40667': 65535,
                    '45228': {'opaque_focal_argument': '45228'},
                    '45233': {'opaque_focal_argument': '45233'},
                    '45236': {'opaque_focal_argument': '45236'},
                    '45240': {'opaque_focal_argument': '45240'},
                    '45243': {'opaque_focal_argument': '45243'},
                    '45247': {'opaque_focal_argument': '45247'},
                    '50852': {'opaque': 'nested Void'},
                    '50860': -1,
                    '50873': 'nested explicit String',
                    '50904': 0}}
class NewSourceCases(unittest.TestCase):
 def verify(self,p,r):
  expected={}
  for read,write,index,value in(('40206','40188',7,True),('40277','40261',7,False),('40355','40339',2,True),('40415','40399',2,False),('40544','40526',10,False)):
   v=list(p['snapshots'][read]);v[index]=value;expected[write]=v
  v=list(p['snapshots']['40520']);v[35]=False;v[32]=True;v[30]=False;expected['40499']=v;expected['40212']=True
  check({x['node_uid']:x['value']for x in r['writes']}==expected)
  check(r['completed_main_stages']==['40162','40245','40293','40323','40383','40432','40463','40573'])
  check(r['completed_nested_stages']==['46840','48404','49054']);check(r['selected_body_completed']);check(not r['pending_leaf_uids'])
  calls={x['node_uid']:x['input_ports']for x in r['leaf_calls']}
  check([calls[u][f]for u,f in(('40220','40225'),('40311','40316'),('50176','50185'),('40361','40366'),('40451','40456'),('40609','40614'))]==[150,29000,1500,150,250,100])
  check(calls['50796']['50912']==p['leaf_returns']['38600']['45219']);check(calls['40623']['40637']==p['snapshots']['40617']);check(calls['40640']['40670']==p['leaf_returns']['40623']['40634'])
  check([x['sequence_uid']for x in r['log']if x['kind']=='stage_complete']==['40147','40147','46815','46815','46815','40147','40147','40147','40147','40147','40147'])
  for k in m.LIMITS:check(r[k]is False)
 def test_full_fresh_reads_identity(self):
  for seed in range(12):
   p=copy.deepcopy(FULL)
   for j,u in enumerate(sorted(p['snapshots'])):p['snapshots'][u]=[(i+seed+j)%2==0 for i in range(len(p['snapshots'][u]))]
   self.verify(p,accepted(p))
  tokens,a=args(FULL);r=m.replay_event(True,tokens,**a);COUNTS['accepted']+=1;calls={x['node_uid']:x['input_ports']for x in r['leaf_calls']}
  check(calls['50796']['50912']is a['leaf_returns']['38600']['45219']);check(calls['40640']['40670']is a['leaf_returns']['40623']['40634'])
  check(calls['40623']['40637']is a['snapshots']['40617']);check(calls['40623']['40625']is a['reference_bindings']['40591']['native_ref']);check(calls['40623']['40631']is a['unwired_inputs']['40631'])
  for f in('45228','45233','45236','45240','45243','45247'):check(calls['38600'][f]is a['unwired_inputs'][f])
  for x in r['leaf_returns']:check(x['output_ports']is a['leaf_returns'][x['node_uid']])
  check(a['snapshots']['40544']!=a['snapshots']['40617']);WITNESS.append(['fresh','7TrueFalse2TrueFalseEPS35False32True30FalseDPS10False',r['completed_stages']])
 def test_partial_orders_and_prefixes(self):
  for frame,chains in(('40162',((('step','40206'),('step','40196'),('step','40188')),(('step','40212'),),(('leaf_call','40220'),('leaf_return','40220')))),('40323',((('step','40355'),('step','40345'),('step','40339')),(('leaf_call','40361'),('leaf_return','40361'))))):
   items=[x for c in chains for x in c]
   for order in itertools.permutations(items):
    if any([order.index(x)for x in c]!=sorted(order.index(x)for x in c)for c in chains):continue
    p=copy.deepcopy(FULL);start,end=span(p,frame);p['schedule'][start:end]=[dict(kind=k,uid=u)for k,u in order];self.verify(p,accepted(p))
  for frame,a,b in(('40463',[('step','40544'),('step','40534'),('step','40526')],[('step','40520'),('step','40507'),('step','40499')]),('40573',[('step','40617'),('leaf_call','40623'),('leaf_return','40623'),('leaf_call','40640'),('leaf_return','40640')],[('leaf_call','40609'),('leaf_return','40609')])):
   for pos in itertools.combinations(range(len(a)+len(b)),len(b)):
    ia=iter(a);ib=iter(b);order=[next(ib)if i in pos else next(ia)for i in range(len(a)+len(b))];p=copy.deepcopy(FULL);start,end=span(p,frame);p['schedule'][start:end]=[dict(kind=k,uid=u)for k,u in order];self.verify(p,accepted(p))
  for n in range(52):
   p=copy.deepcopy(FULL);p['schedule']=p['schedule'][:n];r=accepted(p);check(r['selected_body_completed']==(n==51));check(len(r['completed_stages'])==sum(x['kind']=='stage_complete'for x in p['schedule']))
  p=copy.deepcopy(FULL);p['schedule']=p['schedule'][:15];p['leaf_returns'].pop('38600');r=accepted(p);check(r['pending_leaf_uids']==['38600']);check(r['active_stage']=='48404')
  WITNESS.append(['hierarchical','51tokens','11sourcejoins','52prefixes'])
 def test_hierarchy_and_error_independence(self):
  for focal in(False,True):
   for psp in(False,True):
    p=copy.deepcopy(FULL);p['leaf_returns']['38600']['45219']['status']=focal;p['leaf_returns']['40623']['40634']['status']=psp;self.verify(p,accepted(p))
  for uid in('46840','48404','49054','40293'):
   p=copy.deepcopy(FULL);i=next(i for i,x in enumerate(p['schedule'])if x==dict(kind='stage_complete',uid=uid));del p['schedule'][i];refused(p)
  for token in(dict(kind='leaf_call',uid='50796'),dict(kind='stage_complete',uid='46836'),dict(kind='stage_complete',uid='48400'),dict(kind='stage_complete',uid='49050'),dict(kind='stage_complete',uid='40293')):
   p=copy.deepcopy(FULL);p['schedule']=p['schedule'][:14]+[token];refused(p)
  for u in('38600','50796','50176'):
   p=copy.deepcopy(FULL);i=next(i for i,x in enumerate(p['schedule'])if x==dict(kind='leaf_return',uid=u));del p['schedule'][i];refused(p)
 def test_false_nonaccess(self):
  z=Poison();r=m.replay_event(False,z,snapshots=z,leaf_returns=z,unwired_inputs=z,reference_bindings=z,literal_inputs=z);COUNTS['accepted']+=1;check(r['selected_case_frame']=='40135');check(not r['writes']);check(not r['leaf_calls'])
  p=copy.deepcopy(FULL);p.update(new_value=False,schedule=z,snapshots=z,leaf_returns=z,unwired_inputs=z,reference_bindings=z,literal_inputs=z);check(not accepted(p)['leaf_calls'])
  for v in(0,1,None,'True',[]):p=copy.deepcopy(FULL);p['new_value']=v;refused(p)
 def test_typed_domains(self):
  for u in FULL['snapshots']:
   for v in(None,True,{},FULL['snapshots'][u][:-1],FULL['snapshots'][u]+[False],[0]*len(FULL['snapshots'][u])):p=copy.deepcopy(FULL);p['snapshots'][u]=v;refused(p)
  for u in FULL['literal_inputs']:
   for v in(None,0,True,'False',[],float('nan')):p=copy.deepcopy(FULL);p['literal_inputs'][u]=v;refused(p)
   p=copy.deepcopy(FULL);del p['literal_inputs'][u];refused(p)
  for u,f in(('40220','40222'),('40311','40313'),('40361','40363'),('40451','40453'),('40609','40611'),('50176','50182')):
   for v in(-1,4294967296,True):p=copy.deepcopy(FULL);p['leaf_returns'][u][f]=v;refused(p)
  for u,f in(('38600','45219'),('50796','50887'),('40623','40634'),('40640','40661')):
   for key,v in(('status',1),('code',True),('code',2147483648),('source',None)):p=copy.deepcopy(FULL);p['leaf_returns'][u][f][key]=v;refused(p)
  for f,v in(('40652',True),('50860',-2147483649),('40655',42),('50873',None),('40667',65536),('50904',-1)):p=copy.deepcopy(FULL);p['unwired_inputs'][f]=v;refused(p)
  for key in('constant_uid','saved_uri'):p=copy.deepcopy(FULL);p['reference_bindings']['40591'][key]='wrong';refused(p)
 def test_schedule_and_envelope(self):
  for k,u in(('step','40196'),('step','40188'),('leaf_return','40220'),('stage_complete','40162'),('step','40617')):p=copy.deepcopy(FULL);p['schedule']=[dict(kind=k,uid=u)];refused(p)
  p=copy.deepcopy(FULL);p['schedule'].append(dict(kind='step',uid='40206'));refused(p)
  p=copy.deepcopy(FULL);p['schedule'][0]['kind']='callback';refused(p)
  for k in('source_id','source_version','event_uid','frame_uid'):
   p=copy.deepcopy(FULL);p[k]='wrong';refused(p);p=copy.deepcopy(FULL);del p[k];refused(p)
  for k in('native_execution','field_index_bindings','whole_event_equivalence'):p=copy.deepcopy(FULL);p[k]=False;refused(p)
  for k in('snapshots','leaf_returns','unwired_inputs','reference_bindings','literal_inputs'):p=copy.deepcopy(FULL);p[k]['unknown']='x';refused(p)
  for v in(object(),float('inf'),{1:False}):p=copy.deepcopy(FULL);p['unwired_inputs']['45228']=v;refused(p)
  p=copy.deepcopy(FULL);p['schedule'][0]['extra']=0;refused(p)
  WITNESS.append(['domain',COUNTS['refused']])
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(NewSourceCases));out=dict(status='PASS'if result.wasSuccessful()else'FAIL',python_version=sys.version,methods=result.testsRun,counts=COUNTS,witness_sha256=hashlib.sha256(json.dumps(WITNESS,sort_keys=True,separators=(',',':')).encode('ascii')).hexdigest().upper())
 if len(sys.argv)>1:
  with open(sys.argv[1],'w')as f:json.dump(out,f,sort_keys=True,indent=2)
 print(json.dumps(out,sort_keys=True));sys.exit(0 if result.wasSuccessful()else 1)
