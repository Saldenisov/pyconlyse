"""G69 signed stateless new-body integration; pure supplied boundaries only."""
import copy
import time
import unittest
import uuid
from elyse_agent.supervision_rpc import SupervisionEndpoint
from elyse_agent.supervision_wire import MAX_BYTES, json_bytes, request_mac, response_mac
from elyse_agent.saved_acq_event_48846 import replay_saved_acq_event_48846
from elyse_agent.saved_sup_event_33463 import replay_saved_sup_event_33463
from eighth_next_event_fixtures import (acq_payload, sup_payload,
    minimum_sup_payload, sparse_sup_payload, oversized_sup_payload)

ACQ_PATH='/v1/replay/acquisition-event-48846'
SUP_PATH='/v1/replay/supervision-event-33463'
ERROR_PREFIX_HEX='45727265757220646520636F6D6D616E64652064616E73206C6520636C75737465722022566F69652064E97669E965222E20'


class UnusableRuntime(object):
    def __getattribute__(self,name):
        raise AssertionError('Stateless replay accessed live runtime: '+name)


class SavedEighthNextEventsRpcTests(unittest.TestCase):
    def setUp(self):
        self.key=b'G69-software-only-stateless-replay-test-key'
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

    def replay(self,path,payload,status=200):
        return self.response(path,payload,status).get('result')

    def test_cap_constant_and_same_exact_pure_results(self):
        self.assertEqual(MAX_BYTES,65536)
        for path,factory,adapter in ((ACQ_PATH,acq_payload,replay_saved_acq_event_48846),
                                    (SUP_PATH,sup_payload,replay_saved_sup_event_33463),
                                    (SUP_PATH,minimum_sup_payload,replay_saved_sup_event_33463),
                                    (SUP_PATH,sparse_sup_payload,replay_saved_sup_event_33463)):
            p=factory();r=self.replay(path,p)
            self.assertEqual(r,adapter(p))
            self.assertEqual((r['source_id'],r['source_version'],r['event_uid'],r['frame_uid']),
                tuple(p[k]for k in('source_id','source_version','event_uid','frame_uid')))
            flags=('external_calls_executed','hardware_writes','native_default_qualified','whole_event_equivalence','whole_vi_equivalence') if path==ACQ_PATH else ('native_execution','hardware_execution','PSP_execution','native_defaults_qualified','whole_event_equivalence','whole_VI_equivalence')
            for flag in flags:
                self.assertIs(r[flag],False)

    def test_acq_exact_fresh_fields_and_five_stage_completion(self):
        p=acq_payload();p['snapshots']['54039'][3]=True;p['snapshots']['54110'][3]=False
        r=self.replay(ACQ_PATH,p);w={x['node_uid']:x['value']for x in r['writes']}
        c0=list(p['snapshots']['54039']);c0[18]=True
        c1=list(p['snapshots']['54110']);c1[18]=False
        eps=list(p['snapshots']['54186']);eps[49]=False;eps[45]=True
        dps=list(p['snapshots']['54210']);dps[15]=False
        self.assertEqual(w,{'54021':c0,'54045':True,'54094':c1,'54162':eps,'54192':dps})
        self.assertEqual(r['completed_stages'],['53995','54078','54126','54238','50555'])
        self.assertTrue(r['selected_body_completed'])

    def test_acq_separate_publication_reads_and_error_chain(self):
        p=acq_payload()
        p['snapshots']['35726'][15]=True;p['snapshots']['47280'][49]=True;p['snapshots']['47323'][18]=True
        for node,face in(('47263','47274'),('47306','47317'),('47349','47360')):
            p['leaf_returns'][node][face]['status']=True
        r=self.replay(ACQ_PATH,p);calls={x['node_uid']:x['input_ports']for x in r['leaf_calls']}
        for node,face,read in(('47263','47277','35726'),('47306','47320','47280'),('47349','47363','47323')):
            self.assertEqual(calls[node][face],p['snapshots'][read])
        for node,face,producer,out in(('47306','47314','47263','47274'),('47349','47357','47306','47317'),('47366','47396','47349','47360')):
            self.assertEqual(calls[node][face],p['leaf_returns'][producer][out])
            self.assertTrue(calls[node][face]['status'])
        self.assertEqual(calls['47263']['47271'],p['unwired_inputs']['47271'])
        self.assertTrue(r['selected_body_completed'])

    def test_acq_outer150_carriers_and_final100_wait(self):
        r=self.replay(ACQ_PATH,acq_payload());calls={x['node_uid']:x['input_ports']for x in r['leaf_calls']}
        self.assertEqual(calls['54053'],{'54058':150});self.assertEqual(calls['50582'],{'50592':100})
        transfers=[x for x in r['log']if x['kind']=='border_transfer']
        self.assertEqual(len(transfers),5)
        self.assertIs(r['wait_units_or_pulse_duration_qualified'],False)

    def test_acq_false_does_not_access_body_boundaries(self):
        p=acq_payload(False)
        for name in('schedule','snapshots','leaf_returns','unwired_inputs','reference_bindings'):p[name]=None
        r=self.replay(ACQ_PATH,p)
        self.assertEqual(r['selected_case_frame'],'53972')
        self.assertEqual((r['writes'],r['leaf_calls'],r['completed_stages']),([],[],[]))

    def test_acq_inflight_wait_join_refusal(self):
        p=acq_payload();i=p['schedule'].index(dict(kind='leaf_call',uid='54053'))+1
        p['schedule']=p['schedule'][:i];r=self.replay(ACQ_PATH,p)
        self.assertEqual(r['pending_leaf_uids'],['54053']);self.assertEqual(r['active_stage'],'53995')
        self.assertEqual(r['completed_stages'],[]);self.assertFalse(r['selected_body_completed'])
        p['schedule'].append(dict(kind='stage_complete',uid='53995'));self.replay(ACQ_PATH,p,400)

    def test_sup_nine_masks_current_variant_and_select_slots(self):
        p=sup_payload();r=self.replay(SUP_PATH,p)
        self.assertEqual((r['loop_iteration_count'],r['selected_index'],r['max_mask']),(9,0,128))
        self.assertEqual(r['masks'],[128]+[0]*8)
        self.assertEqual(r['numeric_trace'][0]['selected_step'],0.1)
        self.assertEqual(r['numeric_trace'][0]['operation'],'subtract')
        self.assertEqual(r['updated_cluster'][5],0.5-0.1)
        self.assertEqual(r['updated_cluster'][7:],[False]*4)
        self.assertNotEqual(p['native_returns']['65169']['65191'],p['event_returns']['33480']['33497'][0])
        leaves={x['node_uid']:x for x in r['leaf_observations']}
        self.assertEqual(leaves['33935']['inputs']['33949'],r['updated_cluster'])
        self.assertFalse(r['native_variant_conversion_qualified'])

    def test_sup_phase2_copy_paths_and_four_independent_publications(self):
        p=sup_payload();r=self.replay(SUP_PATH,p);a={x['node_uid']:x['data']for x in r['local_assignments']}
        c6=list(p['local_reads']['46632']);c7=list(p['local_reads']['46671']);voie=p['local_reads']['46585']
        for dst,src in((6,4),(7,5),(9,8),(8,7)):c6[dst]=voie[src][5]
        for dst,src in((9,6),(6,0),(7,1),(3,2),(4,3)):c7[dst]=voie[src][5]
        self.assertEqual(a['46665'],c6);self.assertEqual(a['46698'],c7)
        leaves={x['node_uid']:x for x in r['leaf_observations']}
        for read,writer,face,handler,errorface,out in(
            ('46864','47022','47036','46870','46900','47033'),
            ('46903','47039','47053','46909','46939','47050'),
            ('46942','47056','47070','46948','46978','47067'),
            ('46981','47073','47087','46989','47019','47084')):
            self.assertEqual(leaves[writer]['inputs'][face],p['local_reads'][read])
            self.assertEqual(leaves[handler]['inputs'][errorface],p['native_returns'][writer][out])
        self.assertNotEqual(leaves['47022']['inputs']['47036'],c6)
        self.assertEqual(leaves['46420']['inputs'],{'46425':70})
        self.assertEqual(leaves['27840']['inputs'],{'27849':100})

    def test_sup_sparse_phase2_nonaccess_and_descriptor_absence(self):
        p=sparse_sup_payload();r=self.replay(SUP_PATH,p)
        self.assertEqual(r['max_mask'],1);self.assertEqual(r['local_assignments'],[])
        self.assertEqual([x['node_uid']for x in r['local_reads']],['46864','46903','46942','46981'])
        fields={x['terminal_uid']:x for x in r['field_projections']}
        for uid in('34033','34061'):
            self.assertIsNone(fields[uid]['raw_flattened_field_index'])
            self.assertEqual(fields[uid]['descriptor_projection_ordinal'],0)
            self.assertEqual(fields[uid]['typed_position_path'],[0])
        self.assertEqual(r['null_model_ports_preserved'],['28333','33657','33724'])
        self.assertFalse(r['null_ports_are_caller_inputs'])

    def test_sup_explicit_error_selector_and_report_order_not_schedule(self):
        p=sup_payload();p['native_returns']['33935']['33946']['status']=False
        p['completed_sinks']=['47073','33935','46665','48604']
        r=self.replay(SUP_PATH,p)
        self.assertEqual(r['error_message_hex'],ERROR_PREFIX_HEX+p['native_returns']['33935']['33946']['source_hex'])
        self.assertEqual(r['completed_sinks'],p['completed_sinks'])
        self.assertIn('not_source_schedule_prefix_or_success',r['completion_observation_semantics'])
        self.assertFalse(r['source_schedule_qualified']);self.assertFalse(r['writer_success_gates_assignment'])
        p['intrinsic_outputs']['48544']=False;p['completed_sinks'].remove('48604')
        self.assertIsNone(self.replay(SUP_PATH,p)['error_message_hex'])

    def test_sup_invalid_tie_composite_shape_and_endpoint(self):
        for kind in('tie','composite','shape','reference','completion','literal_type'):
            p=sup_payload()
            if kind=='tie':p['event_returns']['33480']['33497'][1][7]=True
            elif kind=='composite':p['event_returns']['33480']['33497'][0][0]=True
            elif kind=='shape':p['native_returns']['65169']['65191'].pop()
            elif kind=='reference':p['native_returns']['33859']['33889']=[]
            elif kind=='completion':p['completed_sinks']=['foreign']
            else:p['literal_inputs']['46410']=0
            self.replay(SUP_PATH,p,400)

    def test_exact_new_source_envelopes_and_no_native_flags(self):
        for path,factory in((ACQ_PATH,acq_payload),(SUP_PATH,sup_payload)):
            for key,value in(('source_id','APP-02'),('source_version','0'*64),('event_uid','44'),('frame_uid','31552'),('native_execution',True),('hardware_execution',True),('native_defaults_qualified',True)):
                p=factory();p[key]=value;self.replay(path,p,400)
            p=factory();p.pop('source_version');self.replay(path,p,400)

    def test_authentication_nonce_route_binding_and_exact_signed_envelope(self):
        for path,factory in((ACQ_PATH,acq_payload),(SUP_PATH,sup_payload)):
            req=self.request(path,factory());req['signature']='0'*64
            self.assertEqual(self.endpoint.dispatch(req)['status'],401)
            req=self.request(path,factory());self.assertEqual(self.endpoint.dispatch(req)['status'],200)
            self.assertEqual(self.endpoint.dispatch(req)['status'],401)
            req=self.request(path,factory());req['path']=SUP_PATH if path==ACQ_PATH else ACQ_PATH
            self.assertEqual(self.endpoint.dispatch(req)['status'],401)
            self.assertEqual(self.endpoint.dispatch(self.request(path,None,'GET'))['status'],404)
            req=self.request(path,factory());req['execute_native']=True
            with self.assertRaises(ValueError):self.endpoint.dispatch(req)

    def test_valid_supplied_opaque_refs_trigger_only_response_cap(self):
        p=oversized_sup_payload();self.assertEqual(p['literal_inputs'],minimum_sup_payload()['literal_inputs'])
        self.assertLessEqual(len(json_bytes(p)),65536)
        pure=replay_saved_sup_event_33463(p)
        body=dict(schema_version=1,execution_allowed=False,hardware_writes=False,physical_status='NOT_EXECUTED',result=pure)
        self.assertGreater(len(json_bytes(body)),65536)
        refusal=self.response(SUP_PATH,p,400)
        self.assertEqual(refusal['error'],'Supervision response exceeds 65536 bytes')
        self.assertFalse(refusal['accepted'])


if __name__=='__main__':unittest.main()
