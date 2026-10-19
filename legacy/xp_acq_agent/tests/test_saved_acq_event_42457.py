"""Independent fresh42457 original-source expectations; isolated pure kernel only."""
import copy,hashlib,itertools,json,os,sys,unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from elyse_agent import saved_acq_event_42457 as m
COUNTS=dict(accepted=0,refused=0,checks=0);WITNESS=[]
C3_FIELDS=(9,11,15,17,21,23,25,27,29,31,32,33,34,35,36,37,38,39)
ERROR_PORTS={'41020':'41031','41037':'41048','39791':'39802','43112':'43124','31968':'31979','40987':'41008','31985':'32073'}
def check(v):
 COUNTS['checks']+=1
 if not v:raise AssertionError('independent42457 source expectation failed')
def accepted(p):r=m.replay_saved_acq_event_42457(p);COUNTS['accepted']+=1;return r
def refused(p):
 try:m.replay_saved_acq_event_42457(p)
 except(ValueError,TypeError,KeyError,IndexError):COUNTS['refused']+=1;return
 raise AssertionError('bounded domain must refuse')
def args(p):
 classes={'step':m.Step,'leaf_call':m.LeafCall,'leaf_return':m.LeafReturn,'stage_complete':m.StageComplete};a=dict(snapshots={u:tuple(v)for u,v in p['snapshots'].items()},leaf_returns=copy.deepcopy(p['leaf_returns']),unwired_inputs=copy.deepcopy(p['unwired_inputs']),reference_bindings=copy.deepcopy(p['reference_bindings']),field_index_bindings=dict(p['field_index_bindings']),literal_inputs=dict(p['literal_inputs']))
 for u,f in ERROR_PORTS.items():
  v=a['leaf_returns'][u][f];a['leaf_returns'][u][f]=m.ErrorValue(v['status'],v['code'],v['source'])
 for f in('41028','39799'):
  v=a['unwired_inputs'][f];a['unwired_inputs'][f]=m.ErrorValue(v['status'],v['code'],v['source'])
 return tuple(classes[x['kind']](x['uid'])for x in p['schedule']),a
def span(p,frame):
 end=next(i for i,x in enumerate(p['schedule'])if x==dict(kind='stage_complete',uid=frame));start=max([-1]+[i for i,x in enumerate(p['schedule'][:end])if x['kind']=='stage_complete'])+1;return start,end
def interleavings(chains):
 def walk(rest,out):
  if not any(rest):yield out;return
  for i,c in enumerate(rest):
   if c:
    nexts=list(rest);nexts[i]=c[1:]
    for row in walk(nexts,out+[c[0]]):yield row
 return walk([list(x)for x in chains],[])
class Poison:
 def __getitem__(self,k):raise AssertionError('unselected body accessed')
 def __iter__(self):raise AssertionError('unselected body iterated')
FULL={'event_uid': '43',
 'field_index_bindings': {'42589': 0, '51321': 0},
 'frame_uid': '42457',
 'leaf_returns': {'31968': {'31973': {'opaque_supplied_return_ref': '31968'},
                            '31979': {'code': -14, 'source': 'explicit supplied fault -14', 'status': True}},
                  '31985': {'31998': True,
                            '32055': -1,
                            '32070': 'supplied handler text',
                            '32073': {'code': -21, 'source': 'explicit supplied fault -21', 'status': True},
                            '32076': 'unused supplied handler message'},
                  '39791': {'39796': {'opaque_supplied_return_ref': '39791'},
                            '39802': {'code': -12, 'source': 'explicit supplied fault -12', 'status': True}},
                  '40868': {'40874': 102},
                  '40987': {'40990': True,
                            '40993': -1,
                            '41005': 'supplied handler text',
                            '41008': {'code': -20, 'source': 'explicit supplied fault -20', 'status': True},
                            '41011': 'unused supplied handler message'},
                  '41020': {'41025': {'opaque_supplied_return_ref': '41020'},
                            '41031': {'code': -10, 'source': 'explicit supplied fault -10', 'status': True}},
                  '41037': {'41042': {'opaque_supplied_return_ref': '41037'},
                            '41048': {'code': -11, 'source': 'explicit supplied fault -11', 'status': True}},
                  '42649': {'42651': 101},
                  '43112': {'43118': {'opaque_supplied_return_ref': '43112'},
                            '43124': {'code': -13, 'source': 'explicit supplied fault -13', 'status': True}}},
 'literal_inputs': {'31686': False,
                    '40767': 0.0,
                    '42907': False,
                    '42917': False,
                    '42927': False,
                    '42947': False,
                    '42957': False},
 'new_value': True,
 'reference_bindings': {'31950': {'constant_uid': '31950',
                                  'native_ref': {'opaque_supplied_ref': 'EPS'},
                                  'saved_uri': 'ni.var.psp://10.20.30.2/SUPERVISION/EPS'},
                        '39773': {'constant_uid': '39773',
                                  'native_ref': {'opaque_supplied_ref': 'C3_OUT_DIO96'},
                                  'saved_uri': 'ni.var.psp://10.20.30.2/SUPERVISION/C3_OUT_DIO96'},
                        '40910': {'constant_uid': '40910',
                                  'native_ref': {'opaque_supplied_ref': 'C6NI6703'},
                                  'saved_uri': 'ni.var.psp://10.20.30.2/SUPERVISION/C6NI6703'},
                        '40930': {'constant_uid': '40930',
                                  'native_ref': {'opaque_supplied_ref': 'C7NI6703'},
                                  'saved_uri': 'ni.var.psp://10.20.30.2/SUPERVISION/C7NI6703'},
                        '43080': {'constant_uid': '43080',
                                  'native_ref': {'opaque_supplied_ref': 'DPS'},
                                  'saved_uri': 'ni.var.psp://10.20.30.2/SUPERVISION/DPS'}},
 'schedule': [{'kind': 'step', 'uid': '42602'},
              {'kind': 'step', 'uid': '42583'},
              {'kind': 'step', 'uid': '42565'},
              {'kind': 'step', 'uid': '51349'},
              {'kind': 'step', 'uid': '51315'},
              {'kind': 'step', 'uid': '51300'},
              {'kind': 'step', 'uid': '42608'},
              {'kind': 'stage_complete', 'uid': '42539'},
              {'kind': 'step', 'uid': '40872'},
              {'kind': 'leaf_call', 'uid': '41020'},
              {'kind': 'step', 'uid': '40979'},
              {'kind': 'leaf_return', 'uid': '41020'},
              {'kind': 'leaf_call', 'uid': '41037'},
              {'kind': 'leaf_return', 'uid': '41037'},
              {'kind': 'leaf_call', 'uid': '40987'},
              {'kind': 'leaf_return', 'uid': '40987'},
              {'kind': 'stage_complete', 'uid': '39882'},
              {'kind': 'leaf_call', 'uid': '42649'},
              {'kind': 'leaf_return', 'uid': '42649'},
              {'kind': 'stage_complete', 'uid': '35750'},
              {'kind': 'step', 'uid': '30243'},
              {'kind': 'step', 'uid': '8899'},
              {'kind': 'step', 'uid': '1953'},
              {'kind': 'stage_complete', 'uid': '1926'},
              {'kind': 'step', 'uid': '42997'},
              {'kind': 'step', 'uid': '42975'},
              {'kind': 'step', 'uid': '42967'},
              {'kind': 'step', 'uid': '43022'},
              {'kind': 'step', 'uid': '43011'},
              {'kind': 'step', 'uid': '43003'},
              {'kind': 'stage_complete', 'uid': '42901'},
              {'kind': 'step', 'uid': '39762'},
              {'kind': 'leaf_call', 'uid': '39791'},
              {'kind': 'step', 'uid': '43106'},
              {'kind': 'step', 'uid': '31683'},
              {'kind': 'leaf_return', 'uid': '39791'},
              {'kind': 'leaf_call', 'uid': '43112'},
              {'kind': 'leaf_return', 'uid': '43112'},
              {'kind': 'leaf_call', 'uid': '31968'},
              {'kind': 'leaf_return', 'uid': '31968'},
              {'kind': 'leaf_call', 'uid': '31985'},
              {'kind': 'leaf_return', 'uid': '31985'},
              {'kind': 'stage_complete', 'uid': '41314'},
              {'kind': 'leaf_call', 'uid': '40868'},
              {'kind': 'leaf_return', 'uid': '40868'},
              {'kind': 'stage_complete', 'uid': '44333'}],
 'snapshots': {'30243': [True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
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
               '31683': [True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
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
               '39762': [False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
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
               '40872': [3.0,
                         3.142857142857143,
                         3.2857142857142856,
                         3.4285714285714284,
                         3.5714285714285716,
                         3.7142857142857144,
                         3.857142857142857,
                         4.0,
                         4.142857142857143,
                         4.285714285714286],
               '40979': [4.428571428571429,
                         4.571428571428571,
                         4.714285714285714,
                         4.857142857142857,
                         5.0,
                         5.142857142857143,
                         5.285714285714286,
                         5.428571428571429,
                         5.571428571428571,
                         5.714285714285714],
               '42602': [0.14285714285714285,
                         0.2857142857142857,
                         0.42857142857142855,
                         0.5714285714285714,
                         0.7142857142857143,
                         0.8571428571428571,
                         1.0,
                         1.1428571428571428,
                         1.2857142857142858,
                         1.4285714285714286],
               '42997': [False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
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
               '43022': [False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
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
               '43106': [True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
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
               '51349': [1.5714285714285714,
                         1.7142857142857142,
                         1.8571428571428572,
                         2.0,
                         2.142857142857143,
                         2.2857142857142856,
                         2.4285714285714284,
                         2.5714285714285716,
                         2.7142857142857144,
                         2.857142857142857]},
 'source_id': 'APP-00',
 'source_version': '57E1B106EEB57D70124D21CC3FEE775BCADFBF47081F02ED9335A28BAFBC9DD5',
 'unwired_inputs': {'32060': {'opaque': 'second handler Void'},
                    '32064': 2147483647,
                    '32067': 'other unwired String',
                    '32079': 0,
                    '39799': {'code': 2, 'source': 'explicit supplied fault 2', 'status': True},
                    '40996': {'opaque': 'handler Void'},
                    '40999': -2147483648,
                    '41002': 'explicit unwired String',
                    '41014': 65535,
                    '41028': {'code': 1, 'source': 'explicit supplied fault 1', 'status': True}}}
class NewSourceCases(unittest.TestCase):
 def verify(self,p,r):
  expected={}
  for read,write,indices,value in(('42602','42565',(0,1,2,3,4,5,6,7,9),0.0),('51349','51300',(0,1,3,4,5,6,7,8,9),0.0),('30243','1953',C3_FIELDS,False),('43022','43003',(23,),False)):
   v=list(p['snapshots'][read])
   for i in indices:v[i]=value
   expected[write]=v
  v=list(p['snapshots']['42997'])
  for i,bit in((65,False),(58,False),(64,False),(67,True),(61,False)):v[i]=bit
  expected['42967']=v;expected['42608']=True
  check({x['node_uid']:x['value']for x in r['writes']}==expected)
  check(r['completed_stages']==['42539','39882','35750','1926','42901','41314','44333']);check(r['selected_body_completed']);check(not r['pending_leaf_uids'])
  calls={x['node_uid']:x['input_ports']for x in r['leaf_calls']}
  check(calls['42649']['42654']==1000);check(calls['40868']['40877']==200)
  for u,f,read in(('41020','41034','40872'),('41037','41051','40979'),('39791','39805','39762'),('43112','43127','43106'),('31968','31982','31683')):check(calls[u][f]==p['snapshots'][read])
  for u,f,producer,pf in(('41037','41045','41020','41031'),('40987','41017','41037','41048'),('43112','43121','39791','39802'),('31968','31976','43112','43124'),('31985','32082','31968','31979')):check(calls[u][f]==p['leaf_returns'][producer][pf])
  check(not any(x['kind']=='leaf_call'and 150 in x['input_ports'].values()for x in r['log']))
  check([x['node_uid']for x in r['log']if x['kind']=='unused_outer_carrier']==['43183'])
  for k in m.LIMITS:check(r[k]is False)
 def test_fresh_source_values_and_identity(self):
  for seed in range(12):
   p=copy.deepcopy(FULL)
   for j,u in enumerate(sorted(p['snapshots'])):
    p['snapshots'][u]=[float(i+seed+j+1)/11 for i in range(10)]if u in('42602','51349','40872','40979')else[(i+seed+j)%2==0 for i in range(len(p['snapshots'][u]))]
   self.verify(p,accepted(p))
  tokens,a=args(FULL);r=m.replay_event(True,tokens,**a);COUNTS['accepted']+=1;calls={x['node_uid']:x['input_ports']for x in r['leaf_calls']}
  for u,f,read in(('41020','41034','40872'),('41037','41051','40979'),('39791','39805','39762'),('43112','43127','43106'),('31968','31982','31683')):check(calls[u][f]is a['snapshots'][read])
  for u,f,producer,pf in(('41037','41045','41020','41031'),('40987','41017','41037','41048'),('43112','43121','39791','39802'),('31968','31976','43112','43124'),('31985','32082','31968','31979')):check(calls[u][f]is a['leaf_returns'][producer][pf])
  for u,f,c in(('41020','41022','40910'),('41037','41039','40930'),('39791','39793','39773'),('43112','43114','43080'),('31968','31970','31950')):check(calls[u][f]is a['reference_bindings'][c]['native_ref'])
  for u,f in(('41020','41028'),('39791','39799'),('40987','40996'),('31985','32060')):check(calls[u][f]is a['unwired_inputs'][f])
  for x in r['leaf_returns']:check(x['output_ports']is a['leaf_returns'][x['node_uid']])
  check(a['snapshots']['42602']!=a['snapshots']['40872']);check(a['snapshots']['51349']!=a['snapshots']['40979']);check(a['snapshots']['30243']!=a['snapshots']['39762']);check(a['snapshots']['42997']!=a['snapshots']['31683']);check(a['snapshots']['43022']!=a['snapshots']['43106'])
  WITNESS.append(['fresh','C6keep8C7keep2','C3exact18False','EPS65F58F64F67T61FDPS23F'])
 def test_partial_orders_and_prefixes(self):
  for frame,chains in(('42539',((('step','42602'),('step','42583'),('step','42565')),(('step','51349'),('step','51315'),('step','51300')),(('step','42608'),))),('42901',((('step','42997'),('step','42975'),('step','42967')),(('step','43022'),('step','43011'),('step','43003'))))):
   for order in interleavings(chains):
    p=copy.deepcopy(FULL);a,b=span(p,frame);p['schedule'][a:b]=[dict(kind=k,uid=u)for k,u in order];self.verify(p,accepted(p))
  for n in range(47):
   p=copy.deepcopy(FULL);p['schedule']=p['schedule'][:n];r=accepted(p);check(r['selected_body_completed']==(n==46));check(len(r['completed_stages'])==sum(x['kind']=='stage_complete'for x in p['schedule']))
  p=copy.deepcopy(FULL);p['schedule']=p['schedule'][:10];p['leaf_returns'].pop('41020');r=accepted(p);check(r['pending_leaf_uids']==['41020']);check(r['active_stage']=='39882')
  WITNESS.append(['orders','46tokens','47prefixes'])
 def test_completion_and_error_independence(self):
  for status in(False,True):
   p=copy.deepcopy(FULL)
   for u,f in ERROR_PORTS.items():p['leaf_returns'][u][f]['status']=status
   self.verify(p,accepted(p))
  for frame in('42539','39882','35750','1926','42901','41314','44333'):
   p=copy.deepcopy(FULL);i=next(i for i,x in enumerate(p['schedule'])if x==dict(kind='stage_complete',uid=frame));del p['schedule'][i];refused(p)if frame!='44333'else check(not accepted(p)['selected_body_completed'])
  for uid in('41020','41037','39791','43112','31968','40987','31985','42649','40868'):
   p=copy.deepcopy(FULL);i=next(i for i,x in enumerate(p['schedule'])if x==dict(kind='leaf_return',uid=uid));del p['schedule'][i];refused(p)
  for k,u in(('leaf_call','41037'),('leaf_call','40987'),('leaf_call','43112'),('leaf_call','31968'),('leaf_call','31985')):
   p=copy.deepcopy(FULL);p['schedule']=[dict(kind=k,uid=u)];refused(p)
 def test_false_and_unused_nonaccess(self):
  z=Poison();r=m.replay_event(False,z,snapshots=z,leaf_returns=z,unwired_inputs=z,reference_bindings=z,field_index_bindings=z,literal_inputs=z);COUNTS['accepted']+=1;check(r['selected_case_frame']=='42511');check(not r['writes']);check(not r['leaf_calls'])
  p=copy.deepcopy(FULL);p.update(new_value=False,schedule=z,snapshots=z,leaf_returns=z,unwired_inputs=z,reference_bindings=z,field_index_bindings=z,literal_inputs=z);check(not accepted(p)['leaf_calls'])
  for v in(0,1,None,'True',[]):p=copy.deepcopy(FULL);p['new_value']=v;refused(p)
  p=copy.deepcopy(FULL);p['schedule']=p['schedule'][:1];p['leaf_returns']={};p['unwired_inputs']={};p['reference_bindings']={};p['field_index_bindings']={};check(not accepted(p)['leaf_calls'])
 def test_typed_domains(self):
  for u in FULL['snapshots']:
   for v in(None,True,{},FULL['snapshots'][u][:-1],FULL['snapshots'][u]+[False],[0]*len(FULL['snapshots'][u])):p=copy.deepcopy(FULL);p['snapshots'][u]=v;refused(p)
  for u in('42602','51349','40872','40979'):
   for v in(float('inf'),float('-inf'),float('nan'),True):p=copy.deepcopy(FULL);p['snapshots'][u][0]=v;refused(p)
  for u in FULL['literal_inputs']:
   vals=(None,0,True,'False',[],float('nan'))if u!='40767'else(None,0,False,-0.0,1.0,float('inf'))
   for v in vals:p=copy.deepcopy(FULL);p['literal_inputs'][u]=v;refused(p)
   p=copy.deepcopy(FULL);del p['literal_inputs'][u];refused(p)
  for f in('42589','51321'):
   for v in(None,False,1,-1):p=copy.deepcopy(FULL);p['field_index_bindings'][f]=v;refused(p)
   p=copy.deepcopy(FULL);del p['field_index_bindings'][f];refused(p)
  for u,f in ERROR_PORTS.items():
   for k,v in(('status',1),('code',True),('code',2147483648),('source',None)):p=copy.deepcopy(FULL);p['leaf_returns'][u][f][k]=v;refused(p)
  for u,f in(('42649','42651'),('40868','40874')):
   for v in(-1,4294967296,True):p=copy.deepcopy(FULL);p['leaf_returns'][u][f]=v;refused(p)
  for f,v in(('40999',True),('32064',-2147483649),('41002',42),('32067',None),('41014',65536),('32079',-1)):p=copy.deepcopy(FULL);p['unwired_inputs'][f]=v;refused(p)
  for u in FULL['reference_bindings']:
   for key in('constant_uid','saved_uri'):p=copy.deepcopy(FULL);p['reference_bindings'][u][key]='wrong';refused(p)
 def test_schedule_and_envelope(self):
  for k,u in(('step','42583'),('step','42565'),('leaf_return','41020'),('stage_complete','42539'),('step','39762')):p=copy.deepcopy(FULL);p['schedule']=[dict(kind=k,uid=u)];refused(p)
  p=copy.deepcopy(FULL);p['schedule'].append(dict(kind='step',uid='42602'));refused(p)
  p=copy.deepcopy(FULL);p['schedule'][0]['kind']='callback';refused(p)
  for k in('source_id','source_version','event_uid','frame_uid'):
   p=copy.deepcopy(FULL);p[k]='wrong';refused(p);p=copy.deepcopy(FULL);del p[k];refused(p)
  for k in('native_execution','whole_event_equivalence'):p=copy.deepcopy(FULL);p[k]=False;refused(p)
  for k in('snapshots','leaf_returns','unwired_inputs','reference_bindings','field_index_bindings','literal_inputs'):p=copy.deepcopy(FULL);p[k]['unknown']='x';refused(p)
  for v in(object(),float('inf'),{1:False}):p=copy.deepcopy(FULL);p['unwired_inputs']['40996']=v;refused(p)
  p=copy.deepcopy(FULL);p['schedule'][0]['extra']=0;refused(p);WITNESS.append(['domain',COUNTS['refused']])
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(NewSourceCases));out=dict(status='PASS'if result.wasSuccessful()else'FAIL',python_version=sys.version,methods=result.testsRun,counts=COUNTS,witness_sha256=hashlib.sha256(json.dumps(WITNESS,sort_keys=True,separators=(',',':')).encode('ascii')).hexdigest().upper())
 if len(sys.argv)>1:
  with open(sys.argv[1],'w')as f:json.dump(out,f,sort_keys=True,indent=2)
 print(json.dumps(out,sort_keys=True));sys.exit(0 if result.wasSuccessful()else 1)
