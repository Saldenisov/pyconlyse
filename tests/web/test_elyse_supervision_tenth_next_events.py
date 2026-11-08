"""G71 source-specific web integration tests; provider/native tripwires."""
import copy
import importlib
import json
from pathlib import Path
import sys
import pytest
from flask import Flask
from flask_jwt_extended import JWTManager
REPO=next(p for p in Path(__file__).resolve().parents if(p/'legacy/xp_acq_agent').is_dir()and(p/'web/backend').is_dir())
sys.path.insert(0,str(REPO/'web/backend'));sys.path.insert(0,str(REPO/'legacy/xp_acq_agent/tests'));sys.path.insert(0,str(Path(__file__).resolve().parent))
from tenth_next_event_fixtures import (acq_payload,false_acq_payload,inflight_acq_payload,
    sup_payload,minimal_sup_payload,sparse_sup_payload,sup_mask_payload)
api=importlib.import_module('elyse_supervision_api')

def unusable_provider(*args,**kwargs):raise AssertionError('Stateless replay accessed provider/business/native runtime')
@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('PYCONLYSE_PRODUCTION','false');monkeypatch.setenv('PYCONLYSE_ENFORCE_DEVICE_AUTH','false')
    monkeypatch.setattr(api,'configured_acq',unusable_provider);monkeypatch.setattr(api,'business',unusable_provider)
    app=Flask(__name__);app.config.update(TESTING=True,JWT_SECRET_KEY='G71-software-only-source-web-key');JWTManager(app);app.register_blueprint(api.elyse_supervision_api);return app.test_client()
def post(client,operation,payload):return client.post('/api/elyse/supervision/replay',json=dict(operation=operation,inputs=payload))

def test_exact_shared_core_function_identity():
    from DeviceServers.control.elyse_acq.vi_simulation import acquisition_event_23113 as acq,supervision_event_5847 as sup
    from legacy.xp_acq_agent.elyse_agent import saved_acq_event_23113,saved_sup_event_5847
    assert acq.replay_event is saved_acq_event_23113.replay_event
    assert acq.replay_saved_acq_event_23113 is saved_acq_event_23113.replay_saved_acq_event_23113
    assert sup.project_event_5847 is saved_sup_event_5847.project_event_5847
    assert sup.replay_saved_sup_event_5847 is saved_sup_event_5847.replay_saved_sup_event_5847

@pytest.mark.parametrize('operation,factory',[
    ('saved_acq_event_23113',acq_payload),('saved_acq_event_23113',false_acq_payload),('saved_acq_event_23113',inflight_acq_payload),
    ('saved_sup_event_5847',sup_payload),('saved_sup_event_5847',minimal_sup_payload),('saved_sup_event_5847',sparse_sup_payload)])
def test_exact_current_examples_same_pure_adapter_and_safe_envelope(client,operation,factory):
    from legacy.xp_acq_agent.elyse_agent.saved_acq_event_23113 import replay_saved_acq_event_23113
    from legacy.xp_acq_agent.elyse_agent.saved_sup_event_5847 import replay_saved_sup_event_5847
    p=factory();before=copy.deepcopy(p);response=post(client,operation,p);assert response.status_code==200
    body=response.get_json();assert body['execution_allowed'] is False and body['physical_status']=='NOT_EXECUTED'and body['input_origin']=='OPERATOR_SUPPLIED_REPLAY'
    adapter=replay_saved_acq_event_23113 if operation=='saved_acq_event_23113'else replay_saved_sup_event_5847
    assert body['result']==adapter(p);assert p==before
    assert tuple(body['result'][k]for k in('source_id','source_version','event_uid','frame_uid'))==tuple(p[k]for k in('source_id','source_version','event_uid','frame_uid'))
    assert len(json.dumps(body,separators=(',',':')).encode('utf-8'))<=65536
    if operation=='saved_sup_event_5847':assert all(v is False for v in body['result']['boundary_scope'].values())
    else:assert body['result']['whole_event_equivalence'] is False

def test_acq_fresh_fields_and_hierarchical_diagram_joins(client):
    p=acq_payload();p['snapshots']['54862'][2]=True;p['snapshots']['23811'][2]=False
    response=post(client,'saved_acq_event_23113',p);assert response.status_code==200;r=response.get_json()['result']
    c0=list(p['snapshots']['54862']);c0[8]=False;c1=list(p['snapshots']['23811']);c1[8]=True
    eps=list(p['snapshots']['23961']);eps[32]=False;eps[33]=False;eps[35]=True;dps=list(p['snapshots']['24025']);dps[11]=False
    assert {x['node_uid']:x['value']for x in r['writes']}=={'23740':True,'54844':c0,'23792':c1,'23916':eps,'23980':dps}
    assert r['completed_stages']==['23518','54833','23774','23880','24054']and r['completed_nested_stages']==['57312','47864']
    rows=[x for x in r['log']if x['kind']=='nested_stage_complete']
    assert[(x['frame_uid'],x['sequence_frame_container_uid'])for x in rows]==[('57312','57299'),('47864','47855')]

def test_acq_originalcallee_and_publication_error_ports_four_carriers(client):
    p=acq_payload();p['snapshots']['24155'][11]=True;response=post(client,'saved_acq_event_23113',p);assert response.status_code==200
    r=response.get_json()['result'];calls={x['node_uid']:x for x in r['leaf_calls']};assert calls['23625']['original_subvi_boundary'] is True
    for f in('23730','23735','23757','23771','31059','31068'):assert calls['23625']['input_ports'][f]==p['unwired_inputs'][f]
    assert calls['46521']['input_ports']['46559']==p['leaf_returns']['23625']['23726']
    assert calls['24178']['input_ports']['24208']==p['leaf_returns']['24161']['24172']
    assert calls['24161']['input_ports']['24175']==p['snapshots']['24155']
    assert calls['24161']['input_ports']['24169']==p['unwired_inputs']['24169']
    assert calls['24161']['input_ports']['24163']==p['reference_bindings']['24129']['native_ref']
    for uid,f,value in(('23748','23754',150),('54877','54889',150),('48835','48844',500),('24147','24152',100)):assert calls[uid]['input_ports']=={f:value}
    assert len([x for x in r['log']if x['kind']=='border_transfer'])==7
    assert r['selected_body_completed'] is True
    for flag in('native_callee_equivalence','wait_units_or_pulse_duration_qualified','snapshot_equality_qualified','scheduler_qualified'):assert r[flag] is False

def test_acq_false_nonaccess_and_overlapping_nested_inflight(client):
    p=false_acq_payload()
    for k in('schedule','snapshots','leaf_returns','unwired_inputs','reference_bindings'):p[k]=None
    response=post(client,'saved_acq_event_23113',p);assert response.status_code==200;r=response.get_json()['result']
    assert r['selected_case_frame']=='23493'and r['leaf_calls']==r['writes']==r['completed_stages']==[]
    p=inflight_acq_payload();response=post(client,'saved_acq_event_23113',p);assert response.status_code==200;r=response.get_json()['result']
    assert r['pending_leaf_uids']==['23625','23748']and r['active_stage']=='23518'and r['active_nested_stage']=='57312'
    assert r['selected_body_completed'] is False
    p['schedule'].append(dict(kind='stage_complete',uid='57299'));assert post(client,'saved_acq_event_23113',p).status_code==400

@pytest.mark.parametrize('mask,index,base,small,large,operation,arithmetic_uid',[
    (128,0,0.0,0.1,1.0,'Subtract','9004'),(128,1,60.0,1.0,10.0,'Subtract','8838'),
    (128,2,180.0,5.0,50.0,'Subtract','8928'),(128,3,0.0,0.1,1.0,'Subtract','7706'),
    (256,0,0.0,0.01,0.1,'Subtract','17182'),(256,1,60.0,0.1,1.0,'Subtract','16930'),
    (256,2,180.0,1.0,5.0,'Subtract','17056'),(256,3,0.0,0.01,0.1,'Subtract','17308'),
    (512,0,0.0,0.01,0.1,'Add','7536'),(512,1,60.0,0.1,1.0,'Add','7493'),
    (512,2,180.0,1.0,5.0,'Add','6083'),(512,3,0.0,0.01,0.1,'Add','7558'),
    (1024,0,0.0,0.1,1.0,'Add','5965'),(1024,1,60.0,1.0,10.0,'Add','5971'),
    (1024,2,180.0,5.0,50.0,'Add','6147'),(1024,3,0.0,0.1,1.0,'Add','6230')])
def test_sup_fresh_sixteen_arithmetic_paths_and_select_inputs(client,mask,index,base,small,large,operation,arithmetic_uid):
    for x10,step in((False,small),(True,large)):
        p=sup_mask_payload(mask,index,x10);response=post(client,'saved_sup_event_5847',p);assert response.status_code==200
        r=response.get_json()['result'];expected=base-step if operation=='Subtract'else base+step
        assert r['loop_count']==11 and(r['maximum_mask'],r['maximum_index'])==(mask,index)
        a=r['arithmetic_trace'][0];assert(a['arithmetic_uid'],a['source_slot1'],a['source_slot2'],a['result'])==(arithmetic_uid,step,base,expected)
        assert r['property_value'][5]==expected and r['property_value'][6]==17.25 and r['property_value'][7:]==[False]*4
        assert r['boundary_scope']['native_float_bitwise_equivalence'] is False and r['boundary_scope']['native_range_mode_qualified'] is False

def test_sup_loop1937_mask_unique_and_hypothetical_tie_policy(client):
    p=sup_mask_payload(1,3);p['new_value'][0][5]=9.0;p['new_value'][0][6]=3.0
    response=post(client,'saved_sup_event_5847',p);assert response.status_code==200;r=response.get_json()['result']
    assert r['masks']==[0,0,0,1,0,0,0,0,0,0,0]and r['loop_count']==11
    p['new_value'][4][0]=True;assert post(client,'saved_sup_event_5847',p).status_code==400
    p['max_index_7844']=4;response=post(client,'saved_sup_event_5847',p);assert response.status_code==200
    assert response.get_json()['result']['maximum_index']==4
    p['max_index_7844']=2;assert post(client,'saved_sup_event_5847',p).status_code==400

def test_sup_independent_phase_carriers_publications_and_no_errorcase(client):
    p=sup_payload();p['local_reads']['15459'][3][5]=113.0;response=post(client,'saved_sup_event_5847',p);assert response.status_code==200
    r=response.get_json()['result'];a={x['node_uid']:x['data']for x in r['local_assignments']}
    for read,write,changes in(('15529','6122',((0,3),(1,4),(2,5),(3,6),(4,9),(5,10))),('9302','8562',((8,0),(5,1),(0,7),(1,8))),('15570','7702',((5,2),))):
        expected=list(p['local_reads'][read])
        for dst,src in changes:expected[dst]=p['local_reads']['15459'][src][5]
        assert a[write]==expected
    leaves={x['node_uid']:x for x in r['leaf_observations']}
    for read,writer,face,handler,handler_face,error_face in(('8032','12969','13013','8654','9120','13010'),('9134','13145','13269','9315','9407','13261'),('9426','13838','13919','10185','10590','13916'),('10599','13981','14001','11287','11568','13998')):
        assert leaves[writer]['inputs'][face]==p['local_reads'][read]
        assert leaves[handler]['inputs'][handler_face]==p['native_boundaries'][writer]['outputs'][error_face]
    assert leaves['8480']['inputs']=={'8485':70}and leaves['26814']['inputs']=={'26829':100}
    assert r['boundary_scope']['native_error_case_present'] is False
    p=sparse_sup_payload();response=post(client,'saved_sup_event_5847',p);assert response.status_code==200;r=response.get_json()['result']
    assert r['local_assignments']==[]and[x['node_uid']for x in r['local_reads']]==['8032','9134','9426','10599']

def test_sup_completion_observations_do_not_claim_source_trace_or_error_success(client):
    p=sup_payload();p['completed_sinks']=['26814','12969','6122','8025'];p['native_boundaries']['8025']['outputs']['8036']['status']=False
    response=post(client,'saved_sup_event_5847',p);assert response.status_code==200;r=response.get_json()['result']
    assert r['completed_sinks']==p['completed_sinks']and r['boundary_scope']['completion_observations_are_feasible_trace'] is False
    p['completed_sinks']=['8025','8025'];assert post(client,'saved_sup_event_5847',p).status_code==400

@pytest.mark.parametrize('operation,factory', [('saved_acq_event_23113',acq_payload),('saved_sup_event_5847',sup_payload)])
@pytest.mark.parametrize('mutation',['source','version','missing_version','event','frame','native','defaults','hardware'])
def test_exact_current_saved_identity_and_forbidden_native_fields(client,operation,factory,mutation):
    p=factory()
    if mutation=='missing_version':p.pop('source_version')
    else:
        k,v={'source':('source_id','APP-02'),'version':('source_version','0'*64),'event':('event_uid','44'),'frame':('frame_uid','8896'),'native':('native_execution',True),'defaults':('native_defaults_qualified',True),'hardware':('hardware_execution',True)}[mutation];p[k]=v
    assert post(client,operation,p).status_code==400

@pytest.mark.parametrize('mutation',['composite','endpoint','shape','Bool','DBL','prototype','reset','lower','ErrorI32','hex','Variant','propertyrefs'])
def test_sup_fresh_domain_storage_and_explicit_boundary_refusals(client,mutation):
    p=sup_mask_payload(128,1)
    if mutation=='composite':p=sup_mask_payload(129,3)
    elif mutation=='endpoint':p=sup_mask_payload(128,0,True);p['native_boundaries']['65015']['outputs']['65045'][5]=-15.0
    elif mutation=='shape':p['old_value'][0].pop()
    elif mutation=='Bool':p['new_value'][0][0]=1
    elif mutation=='DBL':p['new_value'][0][5]=0
    elif mutation=='prototype':p['literal_inputs']['7855'].pop()
    elif mutation=='reset':p['literal_inputs']['8521']=0
    elif mutation=='lower':p['literal_inputs']['7607']=0
    elif mutation=='ErrorI32':p['native_boundaries']['7985']['outputs']['7990']['code']=2**31
    elif mutation=='hex':p['native_boundaries']['7985']['outputs']['7990']['source_hex']='ab'
    elif mutation=='Variant':p['native_boundaries']['65015']['outputs']['65045'].pop()
    else:p['native_boundaries']['7957']['outputs']['7971'].pop()
    assert post(client,'saved_sup_event_5847',p).status_code==400

def test_outer_duplicate_nonfinite_native_and_request_cap_refusals(client):
    path='/api/elyse/supervision/replay'
    assert client.post(path,json=dict(operation='saved_acq_event_23113',inputs=acq_payload(),execute_native=True)).status_code==400
    raw='{"operation":"saved_acq_event_23113","operation":"saved_sup_event_5847","inputs":'+json.dumps(acq_payload())+'}'
    assert client.post(path,data=raw,content_type='application/json').status_code==400
    p=sup_payload();p['new_value'][0][5]=float('nan')
    assert client.post(path,data=json.dumps(dict(operation='saved_sup_event_5847',inputs=p)),content_type='application/json').status_code==400
    response=client.post(path,data=b' '*65537,content_type='application/json');assert response.status_code==413
    assert response.get_json()['error']=='Replay body exceeds 65536 bytes'
