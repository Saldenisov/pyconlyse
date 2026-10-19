"""G70 signed stateless supplied-body tests. Run only after approved promotion."""
import copy
import time
import unittest
import uuid
from elyse_agent.supervision_rpc import SupervisionEndpoint
from elyse_agent.supervision_wire import MAX_BYTES, json_bytes, request_mac, response_mac
from elyse_agent import saved_acq_event_8896 as acq, saved_sup_event_38707 as sup
import sup_event_38707_fixtures as sup_source_fixture
from ninth_next_event_fixtures import (acq_payload, false_acq_payload, inflight_acq_payload,
    sup_payload, minimum_sup_payload, sparse_sup_payload, request_sup_payload, oversized_sup_payload)

ACQ_PATH='/v1/replay/acquisition-event-8896'
SUP_PATH='/v1/replay/supervision-event-38707'
SOURCE_ARMS=(
    (1,12,0,9.0,'39775','39641','41414','39649','39771','41480','41485'),
    (2,12,0,10.0-0.1,'70856','70801','70975','70809','70852','70927','70932'),
    (4,12,0,10.0+0.1,'60664','60583','60776','60592','60656','60722','60727'),
    (8,12,0,11.0,'75471','75427','75573','75435','75467','75522','75527'),
    (16,18,6,295.0,'49338','49251','78639','49259','49334','78590','78595'),
    (32,18,6,299.0,'69227','69172','69327','69180','69223','69278','69284'),
    (64,18,6,301.0,'72059','72004','72158','72012','72055','72110','72115'),
    (128,18,6,305.0,'73555','72042','73660','73519','73551','73612','73617'))


class UnusableRuntime(object):
    def __getattribute__(self,name):
        raise AssertionError('Stateless replay accessed live runtime: '+name)


class Tripwire(object):
    def __iter__(self):raise AssertionError('Inactive body value accessed')
    def __bool__(self):raise AssertionError('Inactive body value accessed')
    def __getitem__(self,key):raise AssertionError('Inactive body value accessed')


class SavedNinthNextEventsRpcTests(unittest.TestCase):
    def setUp(self):
        self.key=b'G70-software-only-stateless-replay-key'
        self.endpoint=SupervisionEndpoint(UnusableRuntime(),self.key)

    def request(self,path,payload,method='POST'):
        stamp,nonce=str(int(time.time())),uuid.uuid4().hex
        raw=b'' if method=='GET' else json_bytes(payload)
        return dict(method=method,path=path,payload=payload,timestamp=stamp,nonce=nonce,
            signature=request_mac(self.key,'RPC/'+method,path,stamp,nonce,raw))

    def response(self,path,payload,status=200):
        req=self.request(path,payload);before=copy.deepcopy(payload)
        response=self.endpoint.dispatch(req);self.assertEqual(response['status'],status)
        body=response['body'];raw=json_bytes(body)
        self.assertLessEqual(len(raw),65536)
        self.assertFalse(body['execution_allowed']);self.assertFalse(body['hardware_writes'])
        self.assertEqual(body['physical_status'],'NOT_EXECUTED')
        self.assertEqual(response['signature'],response_mac(self.key,'RPC/POST',path,req['nonce'],status,raw))
        self.assertEqual(payload,before)
        return body

    def replay(self,path,payload,status=200):return self.response(path,payload,status).get('result')

    def test_signed_cap_and_exact_current_portable_examples(self):
        self.assertEqual(MAX_BYTES,65536)
        for path,factory,adapter in (
            (ACQ_PATH,acq_payload,acq.replay_saved_acq_event_8896),
            (ACQ_PATH,false_acq_payload,acq.replay_saved_acq_event_8896),
            (ACQ_PATH,inflight_acq_payload,acq.replay_saved_acq_event_8896),
            (SUP_PATH,sup_payload,sup.replay_saved_sup_event_38707),
            (SUP_PATH,minimum_sup_payload,sup.replay_saved_sup_event_38707),
            (SUP_PATH,sparse_sup_payload,sup.replay_saved_sup_event_38707)):
            p=factory();r=self.replay(path,p);self.assertEqual(r,adapter(p))
            self.assertLessEqual(len(json_bytes(p)),65536)
            self.assertEqual(tuple(r[k]for k in('source_id','source_version','event_uid','frame_uid')),
                             tuple(p[k]for k in('source_id','source_version','event_uid','frame_uid')))
            flags=('external_calls_executed','native_default_qualified','native_runtime_equivalence',
                'wait_units_or_pulse_duration_qualified','whole_event_equivalence','whole_vi_equivalence')if path==ACQ_PATH else(
                'native_execution','PSP_execution','native_range_mode_qualified','native_storage_serializer_qualified',
                'native_defaults_qualified','native_property_modes_qualified','native_error_selector_projection_qualified',
                'source_schedule_qualified','whole_event_equivalence','whole_VI_equivalence')
            for flag in flags:self.assertIs(r[flag],False)

    def test_acq_fresh_positions_independent_reads_and_five_joins(self):
        p=acq_payload();p['snapshots']['31799'][3]=True;p['snapshots']['32107'][3]=False
        r=self.replay(ACQ_PATH,p);w={x['node_uid']:x['value']for x in r['writes']}
        c0=list(p['snapshots']['31799']);c0[19]=False
        c1=list(p['snapshots']['32107']);c1[19]=True
        eps=list(p['snapshots']['32180']);eps[45]=False;eps[49]=True
        dps=list(p['snapshots']['32260']);dps[17]=False
        self.assertEqual(w,{'31763':c0,'31847':True,'31905':c1,'32159':eps,'32186':dps})
        self.assertEqual(r['completed_stages'],['31696','31883','32123','32374','32729'])
        self.assertTrue(r['selected_body_completed'])

    def test_acq_publication_snapshot_error_and_reference_ports(self):
        p=acq_payload();p['snapshots']['32534'][17]=True
        p['snapshots']['32559'][45]=True;p['snapshots']['32642'][19]=False
        r=self.replay(ACQ_PATH,p);calls={x['node_uid']:x['input_ports']for x in r['leaf_calls']}
        for uid,face,read in(('32541','32556','32534'),('32625','32639','32559'),('32649','32663','32642')):
            self.assertEqual(calls[uid][face],p['snapshots'][read])
        for uid,face,producer,out in(('32625','32633','32541','32553'),('32649','32657','32625','32636'),('32666','32696','32649','32660')):
            self.assertEqual(calls[uid][face],p['leaf_returns'][producer][out])
            self.assertTrue(calls[uid][face]['status'])
        for uid,face,const in(('32541','32543','32380'),('32625','32627','32495'),('32649','32651','32515')):
            self.assertEqual(calls[uid][face],p['reference_bindings'][const]['native_ref'])
        self.assertEqual(calls['32541']['32549'],p['unwired_inputs']['32549'])
        self.assertTrue(r['selected_body_completed'])
        self.assertEqual(calls['31856'],{'31863':150});self.assertEqual(calls['32747'],{'32752':100})
        transfers=[x for x in r['log']if x['kind']=='border_transfer']
        self.assertEqual(len(transfers),5)

    def test_acq_pure_object_identity_and_false_poison_nonaccess(self):
        p=acq_payload();classes={'step':acq.Step,'leaf_call':acq.LeafCall,'leaf_return':acq.LeafReturn,'stage_complete':acq.StageComplete}
        tokens=tuple(classes[x['kind']](x['uid'])for x in p['schedule'])
        snapshots={u:tuple(v)for u,v in p['snapshots'].items()};returns=copy.deepcopy(p['leaf_returns'])
        for uid,face in(('32541','32553'),('32625','32636'),('32649','32660'),('32666','32687')):
            e=returns[uid][face];returns[uid][face]=acq.ErrorValue(e['status'],e['code'],e['source'])
        unwired=copy.deepcopy(p['unwired_inputs']);e=unwired['32549'];unwired['32549']=acq.ErrorValue(e['status'],e['code'],e['source'])
        refs=p['reference_bindings'];r=acq.replay_event(True,tokens,snapshots=snapshots,
            leaf_returns=returns,unwired_inputs=unwired,reference_bindings=refs)
        calls={x['node_uid']:x['input_ports']for x in r['leaf_calls']}
        for uid,face,read in(('32541','32556','32534'),('32625','32639','32559'),('32649','32663','32642')):
            self.assertIs(calls[uid][face],snapshots[read])
        for uid,face,producer,out in(('32625','32633','32541','32553'),('32649','32657','32625','32636'),('32666','32696','32649','32660')):
            self.assertIs(calls[uid][face],returns[producer][out])
        for uid,face,const in(('32541','32543','32380'),('32625','32627','32495'),('32649','32651','32515')):
            self.assertIs(calls[uid][face],refs[const]['native_ref'])
        opaque=Tripwire();r=acq.replay_event(False,opaque,snapshots=opaque,leaf_returns=opaque,unwired_inputs=opaque,reference_bindings=opaque)
        self.assertEqual((r['writes'],r['leaf_calls']),([],[]))

    def test_acq_false_and_inflight_have_no_invented_completion(self):
        p=false_acq_payload()
        for key in('schedule','snapshots','leaf_returns','unwired_inputs','reference_bindings'):p[key]=None
        r=self.replay(ACQ_PATH,p);self.assertEqual(r['selected_case_frame'],'31627')
        self.assertEqual((r['writes'],r['leaf_calls'],r['completed_stages']),([],[],[]))
        p=inflight_acq_payload();r=self.replay(ACQ_PATH,p)
        self.assertEqual(r['pending_leaf_uids'],['31856']);self.assertEqual(r['active_stage'],'31696')
        self.assertEqual(r['completed_stages'],[]);self.assertFalse(r['selected_body_completed'])
        p['schedule'].append(dict(kind='stage_complete',uid='31696'));self.replay(ACQ_PATH,p,400)

    def test_sup_all_eight_actual_arithmetic_and_carrier_paths(self):
        for mask,pos,dst,expected,read,write,page_write,writer,face,wait,wait_face in SOURCE_ARMS:
            p=request_sup_payload(mask);r=self.replay(SUP_PATH,p)
            self.assertEqual(r['request_mask'],mask);self.assertEqual(r['arithmetic_trace'][0]['result'],expected)
            a={x['node_uid']:x['data']for x in r['local_assignments']}
            copied=list(p['local_reads'][read]);copied[dst]=expected;self.assertEqual(a[write],copied)
            page=list(p['event_returns']['38726']['38743']);page[pos]=expected
            for i in(15,13,14,16,21,19,20,22):page[i]=False
            self.assertEqual(a[page_write],page)
            leaves={x['node_uid']:x for x in r['leaf_observations']}
            self.assertEqual(leaves[wait]['inputs'],{wait_face:17})
            field=next(x for x in r['field_projections']if x['terminal_uid']==face)
            self.assertEqual(field['typed_position_path'],[dst])
            if mask in(1,2,4,8):self.assertIsNone(field['raw_flattened_field_index'])
            self.assertEqual(r['Error_result']['status'],True)
            self.assertFalse(r['writer_success_gates_assignment'])

    def test_sup_no_request_dps_boolean_paths_and_eight_properties(self):
        p=request_sup_payload(0,stop=True,start=True)
        p['event_returns']['38726']['38743'][9:12]=[True,False,True]
        r=self.replay(SUP_PATH,p);a={x['node_uid']:x['data']for x in r['local_assignments']}
        expected=list(p['local_reads']['38750'])
        for dst,src in((15,10),(17,11),(16,9),(18,25),(19,24)):expected[dst]=p['event_returns']['38726']['38743'][src]
        self.assertEqual(a['38967'],expected)
        leaves=r['leaf_observations'];self.assertEqual(len(leaves),9)
        self.assertEqual(leaves[0]['node_uid'],'38989');self.assertEqual(leaves[0]['inputs']['39003'],expected)
        for row in leaves[1:5]:self.assertEqual(row['inputs'][sup.PROPERTY_PORTS[row['node_uid']]['4']],1)
        for row in leaves[5:]:self.assertEqual(row['inputs'][sup.PROPERTY_PORTS[row['node_uid']]['4']],23)
        self.assertFalse(r['native_UnitUInt8_coercion_qualified'])

    def test_sup_busy_any_bit_request_and_inactive_sparse_nonaccess(self):
        p=request_sup_payload(4);p['local_reads']['38750'][7]=True
        r=self.replay(SUP_PATH,p);self.assertTrue(r['DPS_busy']);self.assertEqual(r['request_mask'],4)
        p=request_sup_payload(0,busy=True);r=self.replay(SUP_PATH,p)
        self.assertEqual(r['leaf_observations'],[]);self.assertEqual([x['node_uid']for x in r['local_reads']],['38750'])
        self.assertEqual(r['error_prefix_hex'],p['literal_inputs']['39257'])
        self.assertEqual(r['error_message_hex'],p['literal_inputs']['39257']+p['literal_inputs']['39271']['source_hex'])
        r=self.replay(SUP_PATH,sparse_sup_payload());self.assertEqual(r['request_mask'],2)
        self.assertEqual([x['node_uid']for x in r['local_reads']],['38750','70856'])
        self.assertEqual([x['node_uid']for x in r['leaf_observations']],['70809','70927'])
        p=minimum_sup_payload();r=self.replay(SUP_PATH,p)
        self.assertFalse(r['outer_case_selector']);self.assertEqual([x['node_uid']for x in r['leaf_observations']],['38989'])

    def test_sup_pure_error_ref_carrier_identity_and_inactive_poison(self):
        args=sup_source_fixture.pure_inputs(request_sup_payload(128));before=args[1]['73555'];wr=args[2].writers['73519']
        r=sup.project_event_38707(*args);self.assertIs(r.Error_result,wr.error_out)
        self.assertIsNot(r.local_assignments[0].data,before)
        self.assertIs(r.local_assignments[0].data,r.leaf_observations[0].inputs['73533'])
        self.assertIs(r.leaf_observations[0].inputs['73521'],args[4]['73706'])
        self.assertIs(r.leaf_observations[0].supplied_outputs['73524'],wr.reference_out)
        for i in range(10):
            if i!=6:self.assertIs(r.local_assignments[0].data[i],before[i])
        args=sup_source_fixture.pure_inputs(request_sup_payload(1));opaque=Tripwire()
        for uid in args[1]:
            if uid not in('38750','39775'):args[1][uid]=opaque
        for mapping,active in((args[2].writers,'39649'),(args[2].waits,'41480')):
            for uid in mapping:
                if uid!=active:mapping[uid]=opaque
        for uid in args[2].properties:args[2].properties[uid]=opaque
        for uid in args[4]:
            if uid not in('39565','41470'):args[4][uid]=opaque
        self.assertEqual(sup.project_event_38707(*args).request_mask,1)

    def test_sup_error_intrinsic_report_order_independent_of_status(self):
        p=request_sup_payload(1);p['native_returns']['39649']['39698']['status']=False
        p['completed_sinks']=['41201','41414','39649'];r=self.replay(SUP_PATH,p)
        self.assertEqual(r['error_message_hex'],r['error_prefix_hex']+p['native_returns']['39649']['39698']['source_hex'])
        self.assertEqual(r['completed_sinks'],p['completed_sinks'])
        self.assertIn('not source-feasible trace/prefix/success',r['completion_semantics'])
        p['intrinsic_outputs']['41026']=False;p['completed_sinks']=['39649']
        p['native_returns']['39649']['39698']['status']=True
        self.assertIsNone(self.replay(SUP_PATH,p)['error_message_hex'])
        self.assertFalse(r['completion_feasibility_qualified'])

    def test_sup_composite_strict_range_storage_and_boundary_refusals(self):
        for mask in(3,5,129,255):self.replay(SUP_PATH,request_sup_payload(mask),400)
        for mask,value in((1,7.0),(1,21.0),(16,205.0),(128,395.0)):
            p=request_sup_payload(mask);p['event_returns']['38726']['38743'][12 if mask<16 else 18]=value
            self.replay(SUP_PATH,p,400)
        for kind in('shape','errorI32','reset','borderBool','selector','completion','hex','literalU32'):
            p=request_sup_payload(0,start=True)if kind=='literalU32'else sup_payload()
            if kind=='shape':p['local_reads']['39775'].pop()
            elif kind=='errorI32':p['native_returns']['39649']['39698']['code']=2**31
            elif kind=='reset':p['literal_inputs']['41470']=1
            elif kind=='borderBool':p['border_inputs']['38714']=True
            elif kind=='selector':p['intrinsic_outputs']['41026']=1
            elif kind=='completion':p['completed_sinks']=['foreign']
            elif kind=='hex':p['native_returns']['39649']['39698']['source_hex']='ff'
            else:p['literal_inputs']['84932']=256
            self.replay(SUP_PATH,p,400)

    def test_acq_typed_domains_wrong_structure_and_reference_refusals(self):
        for kind in('shape','Bool','early','ref','I32','U16','U32','wrongtoken'):
            p=acq_payload()
            if kind=='shape':p['snapshots']['31799'].pop()
            elif kind=='Bool':p['snapshots']['32180'][0]=1
            elif kind=='early':p['schedule'].insert(0,dict(kind='stage_complete',uid='31696'))
            elif kind=='ref':p['reference_bindings']['32380']['saved_uri']='ni.var.psp://wrong'
            elif kind=='I32':p['unwired_inputs']['32678']=2**31
            elif kind=='U16':p['unwired_inputs']['32693']=True
            elif kind=='U32':p['leaf_returns']['31856']['31860']=-1
            else:p['schedule'][0]['uid']='54039'
            self.replay(ACQ_PATH,p,400)

    def test_exact_envelopes_authentication_and_route_binding(self):
        for path,factory in((ACQ_PATH,acq_payload),(SUP_PATH,sup_payload)):
            for key,value in(('source_id','APP-02'),('source_version','0'*64),('event_uid','44'),('frame_uid','48846'),
                              ('native_execution',True),('hardware_execution',True),('native_defaults_qualified',True)):
                p=factory();p[key]=value;self.replay(path,p,400)
            p=factory();p.pop('source_version');self.replay(path,p,400)
            req=self.request(path,factory());req['signature']='0'*64
            self.assertEqual(self.endpoint.dispatch(req)['status'],401)
            req=self.request(path,factory());self.assertEqual(self.endpoint.dispatch(req)['status'],200)
            self.assertEqual(self.endpoint.dispatch(req)['status'],401)
            req=self.request(path,factory());req['path']=SUP_PATH if path==ACQ_PATH else ACQ_PATH
            self.assertEqual(self.endpoint.dispatch(req)['status'],401)
            self.assertEqual(self.endpoint.dispatch(self.request(path,None,'GET'))['status'],404)
            req=self.request(path,factory());req['execute_native']=True
            with self.assertRaises(ValueError):self.endpoint.dispatch(req)

    def test_valid_supplied_outputs_can_exceed_signed_response_cap(self):
        p=oversized_sup_payload();self.assertEqual(p['literal_inputs'],sup_payload()['literal_inputs'])
        self.assertLessEqual(len(json_bytes(p)),65536)
        pure=sup.replay_saved_sup_event_38707(p)
        body=dict(schema_version=1,execution_allowed=False,hardware_writes=False,physical_status='NOT_EXECUTED',result=pure)
        self.assertGreater(len(json_bytes(body)),65536)
        refusal=self.response(SUP_PATH,p,400)
        self.assertEqual(refusal['error'],'Supervision response exceeds 65536 bytes');self.assertFalse(refusal['accepted'])
        p=sup_payload();p['event_returns']['38726']['38737']=['Q'*1200 for unused in range(64)]
        with self.assertRaises(ValueError):self.endpoint.dispatch(self.request(SUP_PATH,p))
        p=sup_payload();p['event_returns']['38726']['38743'][12]=float('nan')
        with self.assertRaises(ValueError):self.request(SUP_PATH,p)


if __name__=='__main__':unittest.main()
