"""Fresh34531 source-directed bounded tests; portable embedded fixture."""
import copy,hashlib,json,os,sys,unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from elyse_agent import saved_acq_event_34531 as k
_FULL={'event_uid': '43',
 'field_index_bindings': {'34732': 0, '34942': 0},
 'frame_uid': '34531',
 'leaf_returns': {'29271': {'29299': 103},
                  '32023': {'32025': 104},
                  '34786': {'34789': 100},
                  '35031': {'35033': 101},
                  '35081': {'35083': 102},
                  '35606': {'35608': 105},
                  '35620': {'35625': {'opaque_supplied_return_ref': 'DPS'},
                            '35631': {'code': -7, 'source': 'explicit supplied fault -7', 'status': True}},
                  '35637': {'35640': True,
                            '35643': -8,
                            '35655': 'supplied handler text',
                            '35658': {'code': -9, 'source': 'explicit supplied fault -9', 'status': True},
                            '35661': 'unused supplied handler message'}},
 'literal_inputs': {'25728': False,
                    '32614': False,
                    '33267': False,
                    '34877': False,
                    '35419': False,
                    '35459': False},
 'new_value': True,
 'reference_bindings': {'35588': {'constant_uid': '35588',
                                  'native_ref': {'opaque_supplied_ref': 'DPS'},
                                  'saved_uri': 'ni.var.psp://10.20.30.2/SUPERVISION/DPS'}},
 'schedule': [{'kind': 'step', 'uid': '34742'},
              {'kind': 'step', 'uid': '34714'},
              {'kind': 'step', 'uid': '34688'},
              {'kind': 'step', 'uid': '34760'},
              {'kind': 'leaf_call', 'uid': '34786'},
              {'kind': 'leaf_return', 'uid': '34786'},
              {'kind': 'stage_complete', 'uid': '34617'},
              {'kind': 'step', 'uid': '34957'},
              {'kind': 'step', 'uid': '34924'},
              {'kind': 'step', 'uid': '34906'},
              {'kind': 'stage_complete', 'uid': '34859'},
              {'kind': 'leaf_call', 'uid': '35031'},
              {'kind': 'leaf_return', 'uid': '35031'},
              {'kind': 'stage_complete', 'uid': '35005'},
              {'kind': 'leaf_call', 'uid': '35081'},
              {'kind': 'step', 'uid': '35075'},
              {'kind': 'step', 'uid': '35065'},
              {'kind': 'step', 'uid': '35059'},
              {'kind': 'leaf_return', 'uid': '35081'},
              {'kind': 'stage_complete', 'uid': '35043'},
              {'kind': 'step', 'uid': '25217'},
              {'kind': 'step', 'uid': '25168'},
              {'kind': 'step', 'uid': '25108'},
              {'kind': 'stage_complete', 'uid': '25037'},
              {'kind': 'leaf_call', 'uid': '29271'},
              {'kind': 'leaf_return', 'uid': '29271'},
              {'kind': 'stage_complete', 'uid': '29225'},
              {'kind': 'step', 'uid': '32017'},
              {'kind': 'step', 'uid': '32007'},
              {'kind': 'step', 'uid': '31999'},
              {'kind': 'leaf_call', 'uid': '32023'},
              {'kind': 'leaf_return', 'uid': '32023'},
              {'kind': 'stage_complete', 'uid': '31989'},
              {'kind': 'step', 'uid': '33251'},
              {'kind': 'step', 'uid': '33241'},
              {'kind': 'step', 'uid': '33233'},
              {'kind': 'stage_complete', 'uid': '33223'},
              {'kind': 'step', 'uid': '35509'},
              {'kind': 'step', 'uid': '35487'},
              {'kind': 'step', 'uid': '35479'},
              {'kind': 'step', 'uid': '35533'},
              {'kind': 'step', 'uid': '35523'},
              {'kind': 'step', 'uid': '35515'},
              {'kind': 'stage_complete', 'uid': '35413'},
              {'kind': 'leaf_call', 'uid': '35606'},
              {'kind': 'step', 'uid': '35614'},
              {'kind': 'leaf_call', 'uid': '35620'},
              {'kind': 'leaf_return', 'uid': '35620'},
              {'kind': 'leaf_call', 'uid': '35637'},
              {'kind': 'leaf_return', 'uid': '35606'},
              {'kind': 'leaf_return', 'uid': '35637'},
              {'kind': 'stage_complete', 'uid': '35570'}],
 'snapshots': {'25217': [True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
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
               '32017': [False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
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
               '33251': [False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
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
               '34742': [True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
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
               '34957': [False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
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
               '35075': [False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
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
               '35509': [True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
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
               '35533': [False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
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
               '35614': [False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True,
                         False,
                         False,
                         True]},
 'source_id': 'APP-00',
 'source_version': '57E1B106EEB57D70124D21CC3FEE775BCADFBF47081F02ED9335A28BAFBC9DD5',
 'unwired_inputs': {'35628': {'code': -1, 'source': 'explicit supplied fault -1', 'status': True},
                    '35646': {'opaque': 'handler Void'},
                    '35649': -2147483648,
                    '35652': 'explicit unwired String',
                    '35664': 65535}}
COUNTS=dict(accepted=0,refused=0,checks=0);WITNESS=[]
STAGES=('34617','34859','35005','35043','25037','29225','31989','33223','35413','35570')
# Independent source-oracle rows, not read from kernel plans.
UPDATES=(('34688','34742',((0,True),)),('34906','34957',((0,False),)),('35059','35075',((2,True),)),('25108','25217',((2,False),)),('31999','32017',((2,True),)),('33233','33251',((2,False),)),('35479','35509',((11,False),(8,True),(6,False))),('35515','35533',((2,False),)))
def check(v):
 COUNTS['checks']+=1
 if not v:raise AssertionError('independent source expectation failed')
def accept(p,label):
 r=k.replay_saved_acq_event_34531(p);COUNTS['accepted']+=1;WITNESS.append(dict(label=label,completed=r['completed_stages'],writes=[(x['node_uid'],x['value'])for x in r['writes']],pending=r['pending_leaf_uids']));return r
def refuse(p,label):
 try:k.replay_saved_acq_event_34531(p)
 except(TypeError,ValueError,KeyError):COUNTS['refused']+=1;WITNESS.append(dict(refused=label));return
 raise AssertionError('invalid source-domain sample admitted:'+label)
def pure_args(p):
 classes={'step':k.Step,'leaf_call':k.LeafCall,'leaf_return':k.LeafReturn,'stage_complete':k.StageComplete}
 def error(v):return k.ErrorValue(v['status'],v['code'],v['source'])
 tokens=tuple(classes[x['kind']](x['uid'])for x in p['schedule']);snapshots={u:tuple(v)for u,v in p['snapshots'].items()};returns=copy.deepcopy(p['leaf_returns']);unwired=copy.deepcopy(p['unwired_inputs'])
 returns['35620']['35631']=error(returns['35620']['35631']);returns['35637']['35658']=error(returns['35637']['35658']);unwired['35628']=error(unwired['35628'])
 return tokens,dict(snapshots=snapshots,leaf_returns=returns,unwired_inputs=unwired,reference_bindings=copy.deepcopy(p['reference_bindings']),field_index_bindings=copy.deepcopy(p['field_index_bindings']),literal_inputs=copy.deepcopy(p['literal_inputs']))
class Poison(dict):
 def __getitem__(self,key):raise AssertionError('unselected body boundary accessed')
class Tests(unittest.TestCase):
 def test_source_fields_and_fresh_reads(self):
  for bits in range(64):
   p=copy.deepcopy(_FULL)
   for j,u in enumerate(('34742','34957','35075','25217','32017','33251')):p['snapshots'][u]=[bool(bits&(1<<j))]*32
   for mode in range(2):
    p['snapshots']['35509']=[bool(mode)]*77;p['snapshots']['35533']=[not bool(mode)]*29;p['snapshots']['35614']=[bool((i+bits+mode)%2)for i in range(29)]
    r=accept(p,'fields-'+str(bits)+'-'+str(mode));by={x['node_uid']:x['value']for x in r['writes']}
    for writer,read,fields in UPDATES:
     expected=list(p['snapshots'][read])
     for i,v in fields:expected[i]=v
     check(by[writer]==expected)
    check(by['34760']is True);calls={x['node_uid']:x for x in r['leaf_calls']};check(calls['35620']['input_ports']['35634']==p['snapshots']['35614']);check(calls['35620']['input_ports']['35634']!=by['35515']or p['snapshots']['35614']==by['35515'])
    check([calls[u]['input_ports'][face]for u,face in(('34786','34798'),('35081','35086'),('32023','32028'),('35031','35036'),('29271','29308'),('35606','35611'))]==[150,150,150,1000,1000,100]);check(r['completed_stages']==list(STAGES))
 def test_prefixes_and_independent_schedules(self):
  for n in range(53):
   p=copy.deepcopy(_FULL);p['schedule']=p['schedule'][:n];r=accept(p,'prefix-'+str(n));check(r['selected_body_completed']==(n==52));check(len(r['completed_stages'])==sum(x['kind']=='stage_complete'for x in p['schedule']))
  p=copy.deepcopy(_FULL);s=p['schedule'];first=s[:7];s[:7]=first[4:6]+first[:4]+first[6:]
  r=accept(p,'Wait-before-local0');check(r['completed_stages']==list(STAGES))
  p=copy.deepcopy(_FULL);s=p['schedule'];s[44:]=[s[45],s[46],s[47],s[48],s[50],s[44],s[49],s[51]]
  r=accept(p,'publication-before-Wait9');check(r['selected_body_completed']is True)
  p=copy.deepcopy(_FULL);p['schedule']=p['schedule'][:47];p['leaf_returns'].pop('35606');p['leaf_returns'].pop('35620');r=accept(p,'two-leaves-inflight');check(set(r['pending_leaf_uids'])=={'35606','35620'});check(r['active_stage']=='35570')
 def test_reference_error_identity_and_false_nonaccess(self):
  tokens,args=pure_args(_FULL);r=k.replay_event(True,tokens,**args);COUNTS['accepted']+=1
  calls={x['node_uid']:x for x in r['leaf_calls']};reads={x['node_uid']:x for x in r['log']if x['kind']=='local_read'}
  check(calls['35620']['input_ports']['35634']is args['snapshots']['35614']);check(calls['35620']['input_ports']['35622']is args['reference_bindings']['35588']['native_ref']);check(calls['35620']['input_ports']['35628']is args['unwired_inputs']['35628']);check(calls['35637']['input_ports']['35667']is args['leaf_returns']['35620']['35631'])
  check(reads['35614']['value']is args['snapshots']['35614']);check(r['selected_body_completed']is True)
  for status in(False,True):
   p=copy.deepcopy(_FULL);p['leaf_returns']['35620']['35631']['status']=status;p['leaf_returns']['35637']['35658']['status']=not status;r=accept(p,'fault-status-'+str(status));check(r['selected_body_completed']is True)
  for poison in(None,Poison()):
   r=k.replay_event(False,poison,snapshots=poison,leaf_returns=poison,unwired_inputs=poison,reference_bindings=poison,field_index_bindings=poison,literal_inputs=poison);COUNTS['accepted']+=1;check(not r['writes']and not r['leaf_calls']and not r['completed_stages'])
  p=copy.deepcopy(_FULL);p.update(new_value=False,schedule=None,snapshots=None,leaf_returns=None,unwired_inputs=None,reference_bindings=None,field_index_bindings=None,literal_inputs=None);r=accept(p,'JSON-False');check(r['selected_case_frame']=='34585')
 def test_schedule_refusals(self):
  variants=[]
  for label,index,value in(('foreignUID',0,'42457'),('wrongstage',6,'34859'),('selectorasStep',0,'34573')):
   p=copy.deepcopy(_FULL);p['schedule'][index]['uid']=value;variants.append((label,p))
  p=copy.deepcopy(_FULL);p['schedule'][0:2]=p['schedule'][1::-1];variants.append(('bundle-before-read',p))
  p=copy.deepcopy(_FULL);p['schedule'][0:2]=[p['schedule'][0],p['schedule'][0]];variants.append(('duplicate-read',p))
  p=copy.deepcopy(_FULL);p['schedule'][4:6]=p['schedule'][5:3:-1];variants.append(('return-before-call',p))
  p=copy.deepcopy(_FULL);p['schedule'].pop(5);variants.append(('join-with-pending-Wait',p))
  p=copy.deepcopy(_FULL);p['schedule'][48],p['schedule'][47]=p['schedule'][47],p['schedule'][48];variants.append(('handler-before-PSP-return',p))
  p=copy.deepcopy(_FULL);p['schedule'].append(p['schedule'][-1]);variants.append(('after-lastjoin',p))
  p=copy.deepcopy(_FULL);p['schedule'][0]['extra']=0;variants.append(('token-extra',p))
  for label,p in variants:refuse(p,label)
 def test_typed_and_JSON_domains(self):
  for u,n in(('34742',32),('34957',32),('35075',32),('25217',32),('32017',32),('33251',32),('35509',77),('35533',29),('35614',29)):
   for mode in('missing','short','long','integer','nonfinite'):
    p=copy.deepcopy(_FULL)
    if mode=='missing':p['snapshots'].pop(u)
    elif mode=='short':p['snapshots'][u]=[False]*(n-1)
    elif mode=='long':p['snapshots'][u]=[False]*(n+1)
    elif mode=='integer':p['snapshots'][u][0]=0
    else:p['snapshots'][u][0]=float('nan')
    refuse(p,u+'-'+mode)
  for uid in('34732','34942'):
   for bad in(None,False,-1,1,32):
    p=copy.deepcopy(_FULL);p['field_index_bindings'][uid]=bad;refuse(p,'index-'+uid+'-'+repr(bad))
  for uid in('25728','32614','33267','34877','35419','35459'):
   for bad in(True,0,None):
    p=copy.deepcopy(_FULL);p['literal_inputs'][uid]=bad;refuse(p,'storage-'+uid+'-'+repr(bad))
  for key,bad in(('source_version','0'*64),('frame_uid','34571'),('event_uid','34573'),('source_id','APP-17'),('new_value',1)):
   p=copy.deepcopy(_FULL);p[key]=bad;refuse(p,key)
  p=copy.deepcopy(_FULL);p.pop('source_version');refuse(p,'missing-version')
  p=copy.deepcopy(_FULL);p['native_execution']=True;refuse(p,'native-flag-extra')
  p=copy.deepcopy(_FULL);p['reference_bindings']['35588']['saved_uri']='wrong';refuse(p,'wrongURI')
  p=copy.deepcopy(_FULL);p['leaf_returns']['35620']['35631']['status']=1;refuse(p,'error-status-int')
  p=copy.deepcopy(_FULL);p['leaf_returns']['35620']['35631']['code']=2147483648;refuse(p,'error-I32-overflow')
  p=copy.deepcopy(_FULL);p['unwired_inputs']['35649']=True;refuse(p,'unwired-I32-bool')
  p=copy.deepcopy(_FULL);p['unwired_inputs']['35664']=65536;refuse(p,'unwired-U16-overflow')
  p=copy.deepcopy(_FULL);p['leaf_returns']['34786']['34789']=-1;refuse(p,'Wait-U32-negative')
  p=copy.deepcopy(_FULL);p['leaf_returns']['35620']['35625']=object();refuse(p,'JSON-opaque-object')
 def test_source_boundary_nonaccess_prefix(self):
  p=copy.deepcopy(_FULL);p['schedule']=p['schedule'][:7]
  for u in('34957','35075','25217','32017','33251','35509','35533','35614'):p['snapshots'][u]=object()
  p['leaf_returns'].pop('35620');p['leaf_returns'].pop('35637');p['unwired_inputs']={};p['reference_bindings']={}
  r=accept(p,'unused-later-boundaries');check(r['active_stage']=='34859')
  p=copy.deepcopy(_FULL);p['schedule']=[];p['field_index_bindings']={};p['leaf_returns']={};p['snapshots']={};p['unwired_inputs']={};p['reference_bindings']={};p['literal_inputs']={};r=accept(p,'empty-True-prefix');check(r['active_stage']=='34617')
  tokens,args=pure_args(_FULL);args['unwired_inputs']=Poison();args['reference_bindings']=Poison();args['leaf_returns']=Poison();args['snapshots']=Poison();args['field_index_bindings']=Poison();args['literal_inputs']=Poison()
  r=k.replay_event(True,(),**args);COUNTS['accepted']+=1;check(r['active_stage']=='34617')
if __name__=='__main__':
 suite=unittest.defaultTestLoader.loadTestsFromTestCase(Tests);result=unittest.TextTestRunner(verbosity=2).run(suite)
 if not result.wasSuccessful():sys.exit(1)
 receipt=dict(status='PASS',python_version=sys.version,methods=result.testsRun,counts=COUNTS,witness_sha256=hashlib.sha256(json.dumps(WITNESS,sort_keys=True,separators=(',',':'),allow_nan=False).encode('ascii')).hexdigest().upper(),source_or_native_execution=False,whole_frame_closure=False)
 if len(sys.argv)>1:
  with open(sys.argv[1],'w')as stream:json.dump(receipt,stream,sort_keys=True,indent=2)
 print(json.dumps(receipt,sort_keys=True))
