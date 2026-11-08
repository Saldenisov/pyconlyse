"""G71 signed stateless current-source tests; run only after approved promotion."""
import copy
import time
import unittest
import uuid
from elyse_agent.supervision_rpc import SupervisionEndpoint
from elyse_agent.supervision_wire import MAX_BYTES,json_bytes,request_mac,response_mac
from elyse_agent import saved_acq_event_23113 as acq,saved_sup_event_5847 as sup
import sup_event_5847_fixtures as sup_source_fixture
from tenth_next_event_fixtures import (acq_payload,false_acq_payload,inflight_acq_payload,
    sup_payload,minimal_sup_payload,sparse_sup_payload,sup_mask_payload,oversized_sup_payload)

ACQ_PATH='/v1/replay/acquisition-event-23113'
SUP_PATH='/v1/replay/supervision-event-5847'
SELECTED_FALSE_FLAGS=('event_selection_qualified','native_property_or_reference_validity_qualified',
    'native_literal_serializer_qualified','native_range_mode_qualified','native_error_case_selection_qualified',
    'native_wait_units_or_timing_qualified','supplied_snapshots_are_acquired_data_qualified',
    'supplied_completion_is_feasible_native_trace','native_variant_conversion_qualified',
    'native_argmax_tie_or_empty_policy_qualified','native_loop_output_policy_qualified')
# Fresh saved arithmetic slot/order: (mask,index,source value,false-step,true-step,
# operation,arithmeticUID,actual innerdiagramUID). No native range/default claim.
ARMS=((128,0,0.0,0.1,1.0,'Subtract','9004','8960'),(128,1,60.0,1.0,10.0,'Subtract','8838','8754'),
    (128,2,180.0,5.0,50.0,'Subtract','8928','8884'),(128,3,0.0,0.1,1.0,'Subtract','7706','7672'),
    (256,0,0.0,0.01,0.1,'Subtract','17182','17114'),(256,1,60.0,0.1,1.0,'Subtract','16930','16862'),
    (256,2,180.0,1.0,5.0,'Subtract','17056','16988'),(256,3,0.0,0.01,0.1,'Subtract','17308','17240'),
    (512,0,0.0,0.01,0.1,'Add','7536','9058'),(512,1,60.0,0.1,1.0,'Add','7493','8550'),
    (512,2,180.0,1.0,5.0,'Add','6083','8741'),(512,3,0.0,0.01,0.1,'Add','7558','9375'),
    (1024,0,0.0,0.1,1.0,'Add','5965','11259'),(1024,1,60.0,1.0,10.0,'Add','5971','10683'),
    (1024,2,180.0,5.0,50.0,'Add','6147','11130'),(1024,3,0.0,0.1,1.0,'Add','6230','11385'))


class _ContractPath(object):
    """Test-only Python3.4 binary/UTF8 I/O carrier; no native/legacy claim."""
    def __init__(self,path):self.path=str(path)
    def __truediv__(self,part):
        import os
        return _ContractPath(os.path.join(self.path,part))
    def read_bytes(self):
        with open(self.path,'rb') as stream:return stream.read()
    def read_text(self,encoding='utf-8'):
        with open(self.path,'r',encoding=encoding) as stream:return stream.read()

class _JsonCompat(object):
    """Explicit UTF8 decoding for exact source checker json.loads(bytes) on3.4."""
    @staticmethod
    def loads(value):
        import json
        return json.loads(value.decode('utf-8') if isinstance(value,bytes) else value)

def _portable_contract_metadata(agent_root):
    """Local package identity/module hashes/proof metadata; no external proof I/O."""
    import hashlib,json,os,re
    with open(os.path.join(agent_root,'data','saved_tenth_next_event_slices_contract.json'),'r',encoding='utf-8') as stream:value=json.load(stream)
    flags=('native_execution','hardware_execution','PSP_execution','deployed','whole_event_equivalence','whole_business_scope_complete')
    if value.get('schema_version')!=1 or any(value.get(flag)is not False for flag in flags):raise ValueError('Bounded packaged event contract required')
    expected={('APP-00','43','23113','saved_acq_event_23113.py'):acq.SOURCE_VERSION if 'acq' in globals()else '57E1B106EEB57D70124D21CC3FEE775BCADFBF47081F02ED9335A28BAFBC9DD5',
              ('APP-17','5909','5847','saved_sup_event_5847.py'):sup.SOURCE_VERSION if 'sup' in globals()else 'D3356F86853E718BB80F5F874620E201CA635400025D35DF6DBC2629C14874A9'}
    rows=value.get('sources')
    if not isinstance(rows,list)or len(rows)!=2:raise ValueError('Exact two packaged event rows required')
    actual={(row['source_id'],row['event_uid'],row['frame_uid'],row['module'])for row in rows}
    if actual!=set(expected):raise ValueError('Exact current packaged source identities required')
    for row in rows:
        identity=tuple(row[key]for key in('source_id','event_uid','frame_uid','module'))
        if row.get('source_version')!=expected[identity]or row.get('scope')!='SUPPLIED_SELECTED_EVENT_BODY'or row.get('native_execution')is not False or row.get('whole_event_equivalence')is not False:raise ValueError('Bounded version-specific packaged row required')
        if row.get('boundary_scope')!='EXPLICIT_UNQUALIFIED_PROPERTY_VARIANT_STORAGE_ARGMAX_RANGE_LOOP_ERRORCASE_AND_NATIVE_LEAVES'or any(row.get(flag)is not False for flag in SELECTED_FALSE_FLAGS):raise ValueError('Eleven packaged open boundaries required')
        with open(os.path.join(agent_root,'elyse_agent',row['module']),'rb')as stream:data=stream.read()
        if hashlib.sha256(data).hexdigest().upper()!=row['implementation_sha256']:raise ValueError('Packaged implementation changed')
        proof=row.get('source_proof')
        if not isinstance(proof,dict)or set(proof)!=set(('path','bytes','sha256'))or not isinstance(proof['path'],str)or not proof['path']or type(proof['bytes'])is not int or proof['bytes']<0 or not isinstance(proof['sha256'],str)or re.match(r'^[0-9A-F]{64}\Z',proof['sha256'])is None:raise ValueError('Packaged source proof metadata required')
        # proof.path is deliberately NOT opened: package carries metadata only.
    return value

def check_current_saved_contract():
    """Source host: exact evidence checker. Extracted package: local metadata only."""
    import hashlib,os,re
    agent_root=os.path.dirname(os.path.abspath(__file__))
    while not(os.path.isfile(os.path.join(agent_root,'data','saved_tenth_next_event_slices_contract.json'))and os.path.isdir(os.path.join(agent_root,'elyse_agent'))):
        parent=os.path.dirname(agent_root)
        if parent==agent_root:raise ImportError('Current agent contract and modules required')
        agent_root=parent
    source_root=os.path.dirname(os.path.dirname(agent_root))
    builder=os.path.join(source_root,'tools','build_elyse_acq_supervision.py')
    is_source=(os.path.basename(agent_root)=='xp_acq_agent'and os.path.basename(os.path.dirname(agent_root))=='legacy'and os.path.isfile(builder))
    if not is_source:return _portable_contract_metadata(agent_root)
    with open(builder,'r',encoding='utf-8')as stream:source=stream.read()
    names=('check_saved_tenth_next_event_slices_contract','_check_saved_event_slices_contract');blocks=[]
    for name in names:
        matches=re.findall(r'^def '+re.escape(name)+r'\([^\n]*\):\n.*?(?=^def |\Z)',source,re.M|re.S)
        if len(matches)!=1:raise AssertionError('Exactly one current source checker required: '+name)
        blocks.append(matches[0])
    namespace={'hashlib':hashlib,'json':_JsonCompat,'AGENT':_ContractPath(agent_root),'Path':_ContractPath}
    exec(compile('\n'.join(blocks),builder,'exec'),namespace)
    return namespace[names[0]]()

class UnusableRuntime(object):
    def __getattribute__(self,name):raise AssertionError('Stateless replay accessed runtime: '+name)
class Tripwire(object):
    def __iter__(self):raise AssertionError('Inactive source branch input read')
    def __getitem__(self,key):raise AssertionError('Inactive source branch input read')
    def __bool__(self):raise AssertionError('Inactive source branch input read')

class SavedTenthNextEventsRpcTests(unittest.TestCase):
    def setUp(self):
        self.key=b'G71-software-only-current-source-key';self.endpoint=SupervisionEndpoint(UnusableRuntime(),self.key)
    def request(self,path,payload,method='POST'):
        stamp,nonce=str(int(time.time())),uuid.uuid4().hex;raw=b''if method=='GET'else json_bytes(payload)
        return dict(method=method,path=path,payload=payload,timestamp=stamp,nonce=nonce,signature=request_mac(self.key,'RPC/'+method,path,stamp,nonce,raw))
    def response(self,path,payload,status=200):
        req=self.request(path,payload);before=copy.deepcopy(payload);r=self.endpoint.dispatch(req);self.assertEqual(r['status'],status)
        b=r['body'];raw=json_bytes(b);self.assertLessEqual(len(raw),65536);self.assertFalse(b['execution_allowed']);self.assertFalse(b['hardware_writes']);self.assertEqual(b['physical_status'],'NOT_EXECUTED')
        self.assertEqual(r['signature'],response_mac(self.key,'RPC/POST',path,req['nonce'],status,raw));self.assertEqual(payload,before);return b
    def replay(self,path,payload,status=200):return self.response(path,payload,status).get('result')

    def test_exact_six_current_examples_cap_and_same_adapter(self):
        self.assertEqual(MAX_BYTES,65536)
        for path,factory,adapter in((ACQ_PATH,acq_payload,acq.replay_saved_acq_event_23113),
            (ACQ_PATH,false_acq_payload,acq.replay_saved_acq_event_23113),(ACQ_PATH,inflight_acq_payload,acq.replay_saved_acq_event_23113),
            (SUP_PATH,sup_payload,sup.replay_saved_sup_event_5847),(SUP_PATH,minimal_sup_payload,sup.replay_saved_sup_event_5847),(SUP_PATH,sparse_sup_payload,sup.replay_saved_sup_event_5847)):
            p=factory();r=self.replay(path,p);self.assertEqual(r,adapter(p));self.assertLessEqual(len(json_bytes(p)),65536)
            self.assertEqual(tuple(r[k]for k in('source_id','source_version','event_uid','frame_uid')),tuple(p[k]for k in('source_id','source_version','event_uid','frame_uid')))
            if path==ACQ_PATH:
                for k in('external_calls_executed','native_default_qualified','native_runtime_equivalence','whole_event_equivalence','whole_vi_equivalence','scheduler_qualified'):self.assertIs(r[k],False)
            else:
                for k,v in r['boundary_scope'].items():self.assertIs(v,False)
                self.assertIs(r['boundary_scope']['native_error_case_present'],False)

    def test_packaged_selected_scope_retains_eleven_false_flags(self):
        c=check_current_saved_contract();self.assertEqual(len(c['sources']),2)
        self.assertEqual({(r['source_id'],r['event_uid'],r['frame_uid'])for r in c['sources']},{('APP-00','43','23113'),('APP-17','5909','5847')})
        for row in c['sources']:
            for flag in SELECTED_FALSE_FLAGS:self.assertIs(row[flag],False)
            self.assertIs(row['native_execution'],False);self.assertIs(row['whole_event_equivalence'],False)

    def test_acq_current_fields_nested_and_main_joins(self):
        p=acq_payload();p['snapshots']['54862'][2]=True;p['snapshots']['23811'][2]=False
        r=self.replay(ACQ_PATH,p);w={x['node_uid']:x['value']for x in r['writes']}
        c0=list(p['snapshots']['54862']);c0[8]=False;c1=list(p['snapshots']['23811']);c1[8]=True
        eps=list(p['snapshots']['23961']);eps[32]=False;eps[33]=False;eps[35]=True;dps=list(p['snapshots']['24025']);dps[11]=False
        self.assertEqual(w,{'23740':True,'54844':c0,'23792':c1,'23916':eps,'23980':dps})
        self.assertEqual(r['completed_stages'],['23518','54833','23774','23880','24054']);self.assertEqual(r['completed_nested_stages'],['57312','47864'])
        nested=[x for x in r['log']if x['kind']=='nested_stage_complete']
        self.assertEqual([(x['frame_uid'],x['sequence_frame_container_uid'])for x in nested],[('57312','57299'),('47864','47855')])
        self.assertTrue(r['selected_body_completed'])

    def test_acq_callee_fresh_publication_error_reference_and_four_waits(self):
        p=acq_payload();p['snapshots']['24155'][11]=True;r=self.replay(ACQ_PATH,p);c={x['node_uid']:x for x in r['leaf_calls']}
        self.assertTrue(c['23625']['original_subvi_boundary'])
        for f in('23730','23735','23757','23771','31059','31068'):self.assertEqual(c['23625']['input_ports'][f],p['unwired_inputs'][f])
        for uid,f,producer,out in(('46521','46559','23625','23726'),('24178','24208','24161','24172')):
            self.assertEqual(c[uid]['input_ports'][f],p['leaf_returns'][producer][out]);self.assertTrue(c[uid]['input_ports'][f]['status'])
        self.assertEqual(c['24161']['input_ports']['24175'],p['snapshots']['24155']);self.assertEqual(c['24161']['input_ports']['24163'],p['reference_bindings']['24129']['native_ref']);self.assertEqual(c['24161']['input_ports']['24169'],p['unwired_inputs']['24169'])
        for uid,f,value in(('23748','23754',150),('54877','54889',150),('48835','48844',500),('24147','24152',100)):self.assertEqual(c[uid]['input_ports'],{f:value})
        self.assertEqual(len([x for x in r['log']if x['kind']=='border_transfer']),7)

    def test_acq_pure_identity_false_nonaccess_and_inflight(self):
        p=acq_payload();classes={'step':acq.Step,'leaf_call':acq.LeafCall,'leaf_return':acq.LeafReturn,'stage_complete':acq.StageComplete};tokens=tuple(classes[x['kind']](x['uid'])for x in p['schedule'])
        snapshots={u:tuple(v)for u,v in p['snapshots'].items()};returns=copy.deepcopy(p['leaf_returns'])
        for uid,f in(('23625','23726'),('46521','46548'),('24161','24172'),('24178','24199')):
            e=returns[uid][f];returns[uid][f]=acq.ErrorValue(e['status'],e['code'],e['source'])
        unwired=copy.deepcopy(p['unwired_inputs']);e=unwired['24169'];unwired['24169']=acq.ErrorValue(e['status'],e['code'],e['source'])
        r=acq.replay_event(True,tokens,snapshots=snapshots,leaf_returns=returns,unwired_inputs=unwired,reference_bindings=p['reference_bindings']);c={x['node_uid']:x['input_ports']for x in r['leaf_calls']}
        self.assertIs(c['46521']['46559'],returns['23625']['23726']);self.assertIs(c['24178']['24208'],returns['24161']['24172']);self.assertIs(c['24161']['24175'],snapshots['24155']);self.assertIs(c['24161']['24163'],p['reference_bindings']['24129']['native_ref'])
        z=Tripwire();r=acq.replay_event(False,z,snapshots=z,leaf_returns=z,unwired_inputs=z,reference_bindings=z);self.assertEqual((r['writes'],r['leaf_calls']),([],[]))
        r=self.replay(ACQ_PATH,false_acq_payload());self.assertEqual(r['selected_case_frame'],'23493');self.assertEqual(r['completed_stages'],[])
        p=inflight_acq_payload();r=self.replay(ACQ_PATH,p);self.assertEqual(r['pending_leaf_uids'],['23625','23748']);self.assertEqual(r['active_nested_stage'],'57312');self.assertFalse(r['selected_body_completed'])
        p['schedule'].append(dict(kind='stage_complete',uid='23518'));self.replay(ACQ_PATH,p,400)

    def test_sup_comparison_loop_mask_argmax_and_independent_variant(self):
        for mask in(1,16,128,256,512,1024):
            p=sup_mask_payload(mask,3);r=self.replay(SUP_PATH,p);self.assertEqual(r['loop_count'],11);self.assertEqual(r['masks'],[0,0,0,mask,0,0,0,0,0,0,0]);self.assertEqual((r['maximum_mask'],r['maximum_index']),(mask,3))
            self.assertIn('not_native_policy',r['maximum_index_scope']);self.assertEqual(r['property_value'][6],17.25)
        p=sup_mask_payload(0,0);r=self.replay(SUP_PATH,p);self.assertEqual(r['masks'],[0]*11);self.assertIn('hypothetical',r['maximum_index_scope'])
        p=sup_mask_payload(1,3);p['new_value'][0][5]=9.0;p['new_value'][0][6]=3.0;r=self.replay(SUP_PATH,p);self.assertEqual(r['masks'][0],0)
        p=sup_mask_payload(1,3);p['new_value'][4][0]=True;self.replay(SUP_PATH,p,400);p['max_index_7844']=4;r=self.replay(SUP_PATH,p);self.assertEqual(r['maximum_index'],4)
        p['max_index_7844']=2;self.replay(SUP_PATH,p,400)

    def test_sup_sixteen_source_arithmetic_families_with_explicit_select(self):
        for mask,index,value,small,large,op,uid,diagram in ARMS:
            for x10,step in((False,small),(True,large)):
                p=sup_mask_payload(mask,index,x10);r=self.replay(SUP_PATH,p);expected=value-step if op=='Subtract'else value+step
                self.assertEqual(len(r['arithmetic_trace']),1);a=r['arithmetic_trace'][0];self.assertEqual((a['arithmetic_uid'],a['operation'],a['source_slot1'],a['source_slot2'],a['result']),(uid,op,step,value,expected))
                self.assertIn(diagram,[x[1]for x in r['selected_frames']]);self.assertEqual(r['property_value'][5],expected)
                self.assertEqual(r['property_value'][7:],[False]*4);self.assertFalse(r['boundary_scope']['native_range_mode_qualified'])

    def test_sup_source_carrier_updates_and_fresh_four_publications(self):
        p=sup_payload();p['local_reads']['15459'][3][5]=113.0;r=self.replay(SUP_PATH,p);a={x['node_uid']:x['data']for x in r['local_assignments']}
        for read,write,updates in(('15529','6122',((0,3),(1,4),(2,5),(3,6),(4,9),(5,10))),('9302','8562',((8,0),(5,1),(0,7),(1,8))),('15570','7702',((5,2),))):
            expected=list(p['local_reads'][read])
            for dst,source in updates:expected[dst]=p['local_reads']['15459'][source][5]
            self.assertEqual(a[write],expected)
        leaves={x['node_uid']:x for x in r['leaf_observations']}
        for read,writer,face,ref_face,constant,error_face,handler,handler_face in(('8032','12969','13013','12981','11727','13010','8654','9120'),('9134','13145','13269','13214','11681','13261','9315','9407'),('9426','13838','13919','13886','11647','13916','10185','10590'),('10599','13981','14001','13989','11595','13998','11287','11568')):
            self.assertEqual(leaves[writer]['inputs'][face],p['local_reads'][read]);self.assertEqual(leaves[writer]['inputs'][ref_face],p['literal_inputs'][constant]);self.assertEqual(leaves[handler]['inputs'][handler_face],p['native_boundaries'][writer]['outputs'][error_face])
        self.assertEqual(leaves['8480']['inputs'],{'8485':70});self.assertEqual(leaves['26814']['inputs'],{'26829':100})

    def test_sup_reference_error_identity_and_inactive_phase_nonaccess(self):
        args=sup_source_fixture.pure_arguments(sup,sup_payload());r=sup.project_event_5847(**args);leaves={x.node_uid:x for x in r.leaf_observations}
        selected=args['native_boundaries']['7957']['outputs']['7971'][3]
        self.assertIs(leaves['8048'].inputs['8050'],selected);self.assertIs(leaves['8025'].inputs['8027'],selected);self.assertIs(leaves['8025'].inputs['8039'],r.property_value)
        for consumer,face,producer,out in(('7957','7965','7985','7990'),('8048','8060','7957','7968'),('65015','65019','8048','8064'),('8025','8033','65015','65023'),('16572','42572','8025','8036'),('8654','9120','12969','13010'),('9315','9407','13145','13261'),('10185','10590','13838','13916'),('11287','11568','13981','13998')):
            self.assertIs(leaves[consumer].inputs[face],args['native_boundaries'][producer]['outputs'][out])
        for read,writer,face in(('8032','12969','13013'),('9134','13145','13269'),('9426','13838','13919'),('10599','13981','14001')):self.assertIs(leaves[writer].inputs[face],args['local_reads'][read])
        args=sup_source_fixture.pure_arguments(sup,sup_mask_payload(1,3));z=Tripwire()
        for uid in('15459','15529','9302','15570'):args['local_reads'][uid]=z
        r=sup.project_event_5847(**args);self.assertEqual(r.local_assignments,());self.assertEqual([x.node_uid for x in r.local_reads],['8032','9134','9426','10599'])

    def test_sup_completion_reports_and_sparse_policy_no_errorcase(self):
        p=sup_payload();p['completed_sinks']=['26814','12969','6122','8025'];p['native_boundaries']['8025']['outputs']['8036']['status']=False;r=self.replay(SUP_PATH,p)
        self.assertEqual(r['completed_sinks'],p['completed_sinks']);self.assertFalse(r['boundary_scope']['completion_observations_are_feasible_trace']);self.assertFalse(r['boundary_scope']['native_error_case_present'])
        self.assertEqual(r['leaf_observations'][-1]['node_uid'],'26814')
        r=self.replay(SUP_PATH,sparse_sup_payload());self.assertEqual([x['node_uid']for x in r['local_reads']],['8032','9134','9426','10599']);self.assertEqual(r['local_assignments'],[])
        p['completed_sinks']=['8025','8025'];self.replay(SUP_PATH,p,400);p['completed_sinks']=['foreign'];self.replay(SUP_PATH,p,400)

    def test_current_domain_and_storage_boundary_refusals(self):
        for mask in(17,129,1920):self.replay(SUP_PATH,sup_mask_payload(mask),400)
        for kind in('subshape','Bool','DBL','propertyrefs','Variant','prototype','reset','lower','ErrorI32','hex'):
            p=sup_mask_payload(128,1)
            if kind=='subshape':p['old_value'][0].pop()
            elif kind=='Bool':p['new_value'][0][0]=1
            elif kind=='DBL':p['new_value'][0][5]=0
            elif kind=='propertyrefs':p['native_boundaries']['7957']['outputs']['7971'].pop()
            elif kind=='Variant':p['native_boundaries']['65015']['outputs']['65045'].pop()
            elif kind=='prototype':p['literal_inputs']['7855'].pop()
            elif kind=='reset':p['literal_inputs']['8521']=0
            elif kind=='lower':p['literal_inputs']['7607']=0
            elif kind=='ErrorI32':p['native_boundaries']['7985']['outputs']['7990']['code']=2**31
            else:p['native_boundaries']['7985']['outputs']['7990']['source_hex']='ab'
            self.replay(SUP_PATH,p,400)
        p=sup_mask_payload(128,0,True);p['native_boundaries']['65015']['outputs']['65045'][5]=-15.0;self.replay(SUP_PATH,p,400)
        for kind in('shape','Bool','early','container','ref','I32','U16','U32'):
            p=acq_payload()
            if kind=='shape':p['snapshots']['54862'].pop()
            elif kind=='Bool':p['snapshots']['23961'][0]=1
            elif kind=='early':p['schedule'].insert(0,dict(kind='stage_complete',uid='23518'))
            elif kind=='container':p['schedule'][6]['uid']='57299'
            elif kind=='ref':p['reference_bindings']['24129']['saved_uri']='ni.var.psp://wrong'
            elif kind=='I32':p['unwired_inputs']['46538']=2**31
            elif kind=='U16':p['unwired_inputs']['46555']=True
            else:p['leaf_returns']['48835']['48841']=-1
            self.replay(ACQ_PATH,p,400)

    def test_exact_envelopes_authentication_and_signed_route_binding(self):
        for path,factory in((ACQ_PATH,acq_payload),(SUP_PATH,sup_payload)):
            for key,value in(('source_id','APP-02'),('source_version','0'*64),('event_uid','44'),('frame_uid','8896'),('native_execution',True),('hardware_execution',True),('native_defaults_qualified',True)):
                p=factory();p[key]=value;self.replay(path,p,400)
            p=factory();p.pop('source_version');self.replay(path,p,400)
            req=self.request(path,factory());req['signature']='0'*64;self.assertEqual(self.endpoint.dispatch(req)['status'],401)
            req=self.request(path,factory());self.assertEqual(self.endpoint.dispatch(req)['status'],200);self.assertEqual(self.endpoint.dispatch(req)['status'],401)
            req=self.request(path,factory());req['path']=SUP_PATH if path==ACQ_PATH else ACQ_PATH;self.assertEqual(self.endpoint.dispatch(req)['status'],401)
            self.assertEqual(self.endpoint.dispatch(self.request(path,None,'GET'))['status'],404)
            req=self.request(path,factory());req['execute_native']=True
            with self.assertRaises(ValueError):self.endpoint.dispatch(req)

    def test_pure_accepted_opaque_observations_can_exceed_signed_response_cap(self):
        p=oversized_sup_payload();self.assertEqual(p['literal_inputs'],sup_payload()['literal_inputs']);self.assertLessEqual(len(json_bytes(p)),65536)
        result=sup.replay_saved_sup_event_5847(p);body=dict(schema_version=1,execution_allowed=False,hardware_writes=False,physical_status='NOT_EXECUTED',result=result)
        self.assertGreater(len(json_bytes(body)),65536);refusal=self.response(SUP_PATH,p,400);self.assertEqual(refusal['error'],'Supervision response exceeds 65536 bytes');self.assertFalse(refusal['accepted'])
        p=sup_payload();p['event_outputs']['5868']='X'*65537
        with self.assertRaises(ValueError):self.endpoint.dispatch(self.request(SUP_PATH,p))
        p=sup_payload();p['new_value'][0][5]=float('nan')
        with self.assertRaises(ValueError):self.request(SUP_PATH,p)

if __name__=='__main__':unittest.main()
