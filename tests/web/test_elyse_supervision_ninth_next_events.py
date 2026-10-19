"""G70 web source-specific supplied-body tests; no provider/business access."""
import copy
import importlib
import json
from pathlib import Path
import sys
import pytest
from flask import Flask
from flask_jwt_extended import JWTManager

REPO=next(p for p in Path(__file__).resolve().parents
          if(p/'legacy/xp_acq_agent').is_dir()and(p/'web/backend').is_dir())
sys.path.insert(0,str(REPO/'web/backend'))
sys.path.insert(0,str(REPO/'legacy/xp_acq_agent/tests'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from ninth_next_event_fixtures import (acq_payload,false_acq_payload,inflight_acq_payload,
    sup_payload,minimum_sup_payload,sparse_sup_payload,request_sup_payload)
api=importlib.import_module('elyse_supervision_api')


def unusable_provider(*args,**kwargs):
    raise AssertionError('Stateless web replay attempted provider/business access')


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('PYCONLYSE_PRODUCTION','false')
    monkeypatch.setenv('PYCONLYSE_ENFORCE_DEVICE_AUTH','false')
    monkeypatch.setattr(api,'configured_acq',unusable_provider)
    monkeypatch.setattr(api,'business',unusable_provider)
    app=Flask(__name__)
    app.config.update(TESTING=True,JWT_SECRET_KEY='G70-software-only-pure-web-key')
    JWTManager(app);app.register_blueprint(api.elyse_supervision_api)
    return app.test_client()


def post(client,operation,payload):
    return client.post('/api/elyse/supervision/replay',json=dict(operation=operation,inputs=payload))


def test_exact_current_shared_core_function_identity():
    from DeviceServers.control.elyse_acq.vi_simulation import acquisition_event_8896 as acq,supervision_event_38707 as sup
    from legacy.xp_acq_agent.elyse_agent import saved_acq_event_8896,saved_sup_event_38707
    assert acq.replay_event is saved_acq_event_8896.replay_event
    assert acq.replay_saved_acq_event_8896 is saved_acq_event_8896.replay_saved_acq_event_8896
    assert sup.project_event_38707 is saved_sup_event_38707.project_event_38707
    assert sup.replay_saved_sup_event_38707 is saved_sup_event_38707.replay_saved_sup_event_38707


@pytest.mark.parametrize('operation,factory',[
    ('saved_acq_event_8896',acq_payload),('saved_acq_event_8896',false_acq_payload),
    ('saved_acq_event_8896',inflight_acq_payload),('saved_sup_event_38707',sup_payload),
    ('saved_sup_event_38707',minimum_sup_payload),('saved_sup_event_38707',sparse_sup_payload)])
def test_exact_source_example_same_pure_function_and_safe_envelope(client,operation,factory):
    from legacy.xp_acq_agent.elyse_agent.saved_acq_event_8896 import replay_saved_acq_event_8896
    from legacy.xp_acq_agent.elyse_agent.saved_sup_event_38707 import replay_saved_sup_event_38707
    p=factory();before=copy.deepcopy(p);response=post(client,operation,p)
    assert response.status_code==200
    body=response.get_json();assert body['execution_allowed'] is False
    assert body['physical_status']=='NOT_EXECUTED'and body['input_origin']=='OPERATOR_SUPPLIED_REPLAY'
    adapter=replay_saved_acq_event_8896 if operation=='saved_acq_event_8896'else replay_saved_sup_event_38707
    assert body['result']==adapter(p)
    assert body['result']['whole_event_equivalence'] is False
    assert tuple(body['result'][k]for k in('source_id','source_version','event_uid','frame_uid'))==tuple(p[k]for k in('source_id','source_version','event_uid','frame_uid'))
    assert len(json.dumps(body,separators=(',',':')).encode('utf-8'))<=65536
    assert p==before


def test_acq_fresh_fields_and_independent_publication_error_carriers(client):
    p=acq_payload();p['snapshots']['31799'][3]=True;p['snapshots']['32107'][3]=False
    p['snapshots']['32534'][17]=True;p['snapshots']['32559'][45]=True;p['snapshots']['32642'][19]=False
    response=post(client,'saved_acq_event_8896',p);assert response.status_code==200
    r=response.get_json()['result'];w={x['node_uid']:x['value']for x in r['writes']}
    c0=list(p['snapshots']['31799']);c0[19]=False
    c1=list(p['snapshots']['32107']);c1[19]=True
    eps=list(p['snapshots']['32180']);eps[45]=False;eps[49]=True
    dps=list(p['snapshots']['32260']);dps[17]=False
    assert w=={'31763':c0,'31847':True,'31905':c1,'32159':eps,'32186':dps}
    calls={x['node_uid']:x['input_ports']for x in r['leaf_calls']}
    for uid,face,read in(('32541','32556','32534'),('32625','32639','32559'),('32649','32663','32642')):
        assert calls[uid][face]==p['snapshots'][read]
    for uid,face,producer,out in(('32625','32633','32541','32553'),('32649','32657','32625','32636'),('32666','32696','32649','32660')):
        assert calls[uid][face]==p['leaf_returns'][producer][out]
    assert calls['31856']=={'31863':150}and calls['32747']=={'32752':100}
    assert r['completed_stages']==['31696','31883','32123','32374','32729']
    assert len([x for x in r['log']if x['kind']=='border_transfer'])==5
    for flag in('wait_units_or_pulse_duration_qualified','snapshot_equality_qualified','scheduler_qualified'):
        assert r[flag] is False


def test_acq_false_nonaccess_and_wait_inflight_without_join(client):
    p=false_acq_payload()
    for key in('schedule','snapshots','leaf_returns','unwired_inputs','reference_bindings'):p[key]=None
    response=post(client,'saved_acq_event_8896',p);assert response.status_code==200
    r=response.get_json()['result'];assert r['selected_case_frame']=='31627'
    assert r['leaf_calls']==r['writes']==r['completed_stages']==[]
    p=inflight_acq_payload();response=post(client,'saved_acq_event_8896',p);assert response.status_code==200
    r=response.get_json()['result'];assert r['pending_leaf_uids']==['31856']and r['completed_stages']==[]
    p['schedule'].append(dict(kind='stage_complete',uid='31696'))
    assert post(client,'saved_acq_event_8896',p).status_code==400


@pytest.mark.parametrize('mask,pos,dst,expected,read,write,page_write',[
    (1,12,0,9.0,'39775','39641','41414'),(2,12,0,10.0-0.1,'70856','70801','70975'),
    (4,12,0,10.0+0.1,'60664','60583','60776'),(8,12,0,11.0,'75471','75427','75573'),
    (16,18,6,295.0,'49338','49251','78639'),(32,18,6,299.0,'69227','69172','69327'),
    (64,18,6,301.0,'72059','72004','72158'),(128,18,6,305.0,'73555','72042','73660')])
def test_sup_eight_saved_arithmetic_masks_and_independent_carrier_snapshots(client,mask,pos,dst,expected,read,write,page_write):
    p=request_sup_payload(mask);response=post(client,'saved_sup_event_38707',p);assert response.status_code==200
    r=response.get_json()['result'];assert r['request_mask']==mask
    assert r['arithmetic_trace'][0]['result']==expected
    a={x['node_uid']:x['data']for x in r['local_assignments']}
    carrier=list(p['local_reads'][read]);carrier[dst]=expected;assert a[write]==carrier
    page=list(p['event_returns']['38726']['38743']);page[pos]=expected
    for i in(15,13,14,16,21,19,20,22):page[i]=False
    assert a[page_write]==page
    for flag in('native_range_mode_qualified','native_storage_serializer_qualified','source_schedule_qualified'):
        assert r[flag] is False


def test_sup_no_request_boolean_paths_property_values_and_dps_any_predicate(client):
    p=request_sup_payload(0,stop=True,start=True);p['event_returns']['38726']['38743'][9:12]=[True,False,True]
    response=post(client,'saved_sup_event_38707',p);assert response.status_code==200
    r=response.get_json()['result'];a={x['node_uid']:x['data']for x in r['local_assignments']}
    expected=list(p['local_reads']['38750'])
    for dst,src in((15,10),(17,11),(16,9),(18,25),(19,24)):expected[dst]=p['event_returns']['38726']['38743'][src]
    assert a['38967']==expected
    leaves={x['node_uid']:x for x in r['leaf_observations']};assert len(leaves)==9
    for uid,face in(('67577','67593'),('67619','67647'),('67657','67679'),('67698','67714')):
        assert leaves[uid]['inputs'][face]==1
    for uid,face in(('7002','7021'),('70250','70299'),('67505','67527'),('68962','68990')):
        assert leaves[uid]['inputs'][face]==23
    p=request_sup_payload(0,busy=True);p['local_reads']['38750']=[False]*29;p['local_reads']['38750'][7]=True
    response=post(client,'saved_sup_event_38707',p);assert response.status_code==200
    r=response.get_json()['result'];assert r['DPS_busy'] is True and r['leaf_observations']==[]
    p=request_sup_payload(4);p['local_reads']['38750'][7]=True
    response=post(client,'saved_sup_event_38707',p);assert response.status_code==200
    r=response.get_json()['result'];assert r['DPS_busy'] is True and r['request_mask']==4
    assert r['arithmetic_trace'][0]['result']==10.0+0.1


def test_sup_sparse_inactive_nonaccess_and_explicit_errorcase_completion_report(client):
    p=sparse_sup_payload();response=post(client,'saved_sup_event_38707',p);assert response.status_code==200
    r=response.get_json()['result'];assert [x['node_uid']for x in r['local_reads']]==['38750','70856']
    assert [x['node_uid']for x in r['leaf_observations']]==['70809','70927']
    field=next(x for x in r['field_projections']if x['terminal_uid']=='70852')
    assert field['raw_flattened_field_index'] is None and field['typed_position_path']==[0]
    p=sup_payload();p['native_returns']['39649']['39698']['status']=False
    p['completed_sinks']=['41201','41414','39649']
    response=post(client,'saved_sup_event_38707',p);assert response.status_code==200
    r=response.get_json()['result'];assert r['error_message_hex']==r['error_prefix_hex']+p['native_returns']['39649']['39698']['source_hex']
    assert r['completed_sinks']==p['completed_sinks'] and r['completion_feasibility_qualified'] is False
    p['intrinsic_outputs']['41026']=False;p['completed_sinks']=['39649']
    p['native_returns']['39649']['39698']['status']=True
    response=post(client,'saved_sup_event_38707',p);assert response.status_code==200
    assert response.get_json()['result']['error_message_hex'] is None


@pytest.mark.parametrize('operation,factory',[
    ('saved_acq_event_8896',acq_payload),('saved_sup_event_38707',sup_payload)])
@pytest.mark.parametrize('mutation',['source','version','missing_version','frame','event','native','defaults','hardware'])
def test_exact_saved_identity_and_native_flags_refused(client,operation,factory,mutation):
    p=factory()
    if mutation=='missing_version':p.pop('source_version')
    else:
        key,value={'source':('source_id','APP-02'),'version':('source_version','0'*64),
            'frame':('frame_uid','48846'),'event':('event_uid','44'),'native':('native_execution',True),
            'defaults':('native_defaults_qualified',True),'hardware':('hardware_execution',True)}[mutation]
        p[key]=value
    assert post(client,operation,p).status_code==400


@pytest.mark.parametrize('mutation',['composite','lower_endpoint','upper_endpoint','carrier','ErrorI32','reset','selector','borderBool','completion','hex','literalU32'])
def test_sup_actual_source_domain_refusals(client,mutation):
    p=request_sup_payload(0,start=True)if mutation=='literalU32'else sup_payload()
    if mutation=='composite':p['event_returns']['38726']['38743'][13]=True
    elif mutation=='lower_endpoint':p['event_returns']['38726']['38743'][12]=7.0
    elif mutation=='upper_endpoint':p['event_returns']['38726']['38743'][12]=21.0
    elif mutation=='carrier':p['local_reads']['39775'].pop()
    elif mutation=='ErrorI32':p['native_returns']['39649']['39698']['code']=2**31
    elif mutation=='reset':p['literal_inputs']['41470']=1
    elif mutation=='selector':p['intrinsic_outputs']['41026']=1
    elif mutation=='borderBool':p['border_inputs']['38714']=True
    elif mutation=='completion':p['completed_sinks']=['foreign']
    elif mutation=='hex':p['native_returns']['39649']['39698']['source_hex']='ff'
    else:p['literal_inputs']['84932']=256
    assert post(client,'saved_sup_event_38707',p).status_code==400


def test_outer_envelope_duplicate_nonfinite_and_request_cap_refusals(client):
    path='/api/elyse/supervision/replay'
    response=client.post(path,json=dict(operation='saved_acq_event_8896',inputs=acq_payload(),execute_native=True))
    assert response.status_code==400
    raw='{"operation":"saved_acq_event_8896","operation":"saved_sup_event_38707","inputs":'+json.dumps(acq_payload())+'}'
    assert client.post(path,data=raw,content_type='application/json').status_code==400
    p=sup_payload();p['event_returns']['38726']['38743'][12]=float('nan')
    assert client.post(path,data=json.dumps(dict(operation='saved_sup_event_38707',inputs=p)),content_type='application/json').status_code==400
    response=client.post(path,data=b' '*65537,content_type='application/json')
    assert response.status_code==413 and response.get_json()['error']=='Replay body exceeds 65536 bytes'
