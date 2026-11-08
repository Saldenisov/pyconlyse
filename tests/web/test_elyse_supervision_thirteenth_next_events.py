"""G74 source-specific stateless web replays; no configured provider access."""
import copy
import importlib
import json
from pathlib import Path
import sys
import pytest
from flask import Flask
from flask_jwt_extended import JWTManager

REPO = next(p for p in Path(__file__).resolve().parents
            if (p / 'legacy/xp_acq_agent').is_dir() and (p / 'web/backend').is_dir())
sys.path.insert(0, str(REPO / 'web/backend'))
sys.path.insert(0, str(REPO / 'legacy/xp_acq_agent/tests'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from thirteenth_next_event_fixtures import (
    acq_payload, false_acq_payload, inflight_acq_payload,
    sup_payload, minimal_sup_payload, sparse_sup_payload, oversized_sup_payload)
api = importlib.import_module('elyse_supervision_api')


def unusable_provider(*args, **kwargs):
    raise AssertionError('Stateless replay accessed provider/business/native runtime')


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('PYCONLYSE_PRODUCTION', 'false')
    monkeypatch.setenv('PYCONLYSE_ENFORCE_DEVICE_AUTH', 'false')
    monkeypatch.setattr(api, 'configured_acq', unusable_provider)
    monkeypatch.setattr(api, 'business', unusable_provider)
    app = Flask(__name__)
    app.config.update(TESTING=True, JWT_SECRET_KEY='G74-software-only-current-source-web-key')
    JWTManager(app)
    app.register_blueprint(api.elyse_supervision_api)
    return app.test_client()


def post(client, operation, payload):
    return client.post('/api/elyse/supervision/replay', json=dict(operation=operation, inputs=payload))


def test_exact_shared_core_facade_function_identity():
    from DeviceServers.control.elyse_acq.vi_simulation import acquisition_event_17899 as acq
    from DeviceServers.control.elyse_acq.vi_simulation import supervision_event_53772 as sup
    from legacy.xp_acq_agent.elyse_agent import saved_acq_event_17899, saved_sup_event_53772
    assert acq.replay_event is saved_acq_event_17899.replay_event
    assert acq.replay_saved_acq_event_17899 is saved_acq_event_17899.replay_saved_acq_event_17899
    assert sup.project_event_53772 is saved_sup_event_53772.project_event_53772
    assert sup.replay_saved_sup_event_53772 is saved_sup_event_53772.replay_saved_sup_event_53772


@pytest.mark.parametrize('operation,factory', [
    ('saved_acq_event_17899', acq_payload), ('saved_acq_event_17899', false_acq_payload),
    ('saved_acq_event_17899', inflight_acq_payload), ('saved_sup_event_53772', sup_payload),
    ('saved_sup_event_53772', minimal_sup_payload), ('saved_sup_event_53772', sparse_sup_payload)])
def test_six_frozen_examples_adapter_identity_and_safe_envelope(client, operation, factory):
    from legacy.xp_acq_agent.elyse_agent.saved_acq_event_17899 import replay_saved_acq_event_17899
    from legacy.xp_acq_agent.elyse_agent.saved_sup_event_53772 import replay_saved_sup_event_53772
    payload = factory(); before = copy.deepcopy(payload)
    response = post(client, operation, payload)
    assert response.status_code == 200
    body = response.get_json()
    assert body['execution_allowed'] is False and body['physical_status'] == 'NOT_EXECUTED'
    assert body['input_origin'] == 'OPERATOR_SUPPLIED_REPLAY'
    adapter = replay_saved_acq_event_17899 if operation == 'saved_acq_event_17899' else replay_saved_sup_event_53772
    assert body['result'] == adapter(payload) and payload == before
    assert tuple(body['result'][k] for k in ('source_id', 'source_version', 'event_uid', 'frame_uid')) == tuple(
        payload[k] for k in ('source_id', 'source_version', 'event_uid', 'frame_uid'))
    assert body['result']['whole_event_equivalence'] is False


def test_acq_fresh_source_stages_and_independent_publication_read(client):
    p=acq_payload();response=post(client,'saved_acq_event_17899',p)
    assert response.status_code==200
    r=response.get_json()['result'];writes={x['node_uid']:x['value']for x in r['writes']}
    expected={}
    for uid,read,fields in (('10838','13611',{1:False}),('20410','20437',{1:True}),
        ('21773','21967',{4:False}),('22098','22138',{4:True}),
        ('22951','22985',{3:False,2:False,5:True,1:False}),('23005','23076',{1:False})):
        carrier=list(p['snapshots'][read])
        for i,v in fields.items():carrier[i]=v
        expected[uid]=carrier
    expected['16177']=True
    assert writes==expected
    assert r['completed_stages']==['7963','18101','21010','21712','22060','22878','23117']
    calls={x['node_uid']:x['input_ports']for x in r['leaf_calls']}
    assert calls['23177']['23191']==p['snapshots']['23171']!=writes['23005']
    assert calls['23194']['23236']==p['leaf_returns']['23177']['23188']
    for uid,ports in (('16362',{'16413':150}),('21625',{'21640':400}),('21990',{'22010':150}),('22147',{'22162':150}),('23162',{'23168':100})):
        assert calls[uid]==ports
    assert r['scheduler_qualified'] is False


@pytest.mark.parametrize('uid',['7970','21733','22885','22900','22921','22931'])
@pytest.mark.parametrize('value',[True,0,None,'False',0.0])
def test_acq_exact_false_carriers_refuse_hypothesis_expansion(client,uid,value):
    p=acq_payload();p['literal_inputs'][uid]=value
    assert post(client,'saved_acq_event_17899',p).status_code==400
    p=acq_payload();del p['literal_inputs'][uid]
    assert post(client,'saved_acq_event_17899',p).status_code==400


def test_acq_false_inflight_and_extra_keys_are_source_specific(client):
    response=post(client,'saved_acq_event_17899',false_acq_payload())
    assert response.status_code==200
    r=response.get_json()['result'];assert r['selected_case_frame']=='17964'and r['writes']==r['leaf_calls']==[]
    p=inflight_acq_payload();response=post(client,'saved_acq_event_17899',p)
    assert response.status_code==200
    r=response.get_json()['result'];assert r['pending_leaf_uids']==['16362']and r['active_stage']=='7963'
    assert r['selected_body_completed'] is False
    p['schedule'].append(dict(kind='stage_complete',uid='7963'))
    assert post(client,'saved_acq_event_17899',p).status_code==400
    p=acq_payload();p['field_index_bindings']={}
    assert post(client,'saved_acq_event_17899',p).status_code==400


@pytest.mark.parametrize('first',[False,True])
@pytest.mark.parametrize('second',[False,True])
@pytest.mark.parametrize('reset',[False,True])
def test_sup_two_independent_c5_carriers_three_phases_and_reset_fanout(client,first,second,reset):
    p=sup_payload();p['literal_inputs']={'54623':first,'55116':second,'76784':reset}
    response=post(client,'saved_sup_event_53772',p);assert response.status_code==200
    r=response.get_json()['result'];assert r['selected_case_frame']=='54569'
    assert r['source_sequence_actual_diagram_uids']==['54581','54873','54970']
    calls={x['node_uid']:x for x in r['leaf_observations']}
    assert [x['sequence_phase']for x in r['leaf_observations']]==[0,0,1,2,2]
    for index,read,writer,port,value in ((0,'54644','54669','54685',first),(1,'55216','55252','55299',second)):
        expected=list(p['local_reads'][read]);expected[23]=value
        assert r['local_assignments'][index]['value']==calls[writer]['inputs'][port]==expected
        assert r['field_updates'][index]['raw_flattened_field_index']==23
        assert r['field_updates'][index]['typed_position_path']==[23]
    assert r['local_assignments'][0]['value']!=r['local_assignments'][1]['value']
    assert calls['54669']['inputs']['54671']==p['reference_bindings']['54587']['native_reference']
    assert calls['55252']['inputs']['55258']==p['reference_bindings']['55046']['native_reference']
    assert calls['54688']['inputs']['54830']==p['native_boundaries']['54669']['outputs']['54682']
    assert calls['55317']['inputs']['55468']==p['native_boundaries']['55252']['outputs']['55281']
    assert calls['54943']['inputs']=={'54953':500}
    assert [(x['node_uid'],x['explicit_paramIdx'],x['value'])for x in r['local_assignments'][2:]]==[('76774',156,reset),('76731',10,reset),('76766',7,reset)]
    assert r['native_field_index_selection_qualified'] is False
    assert r['native_wait_units_or_timing_qualified'] is False


def test_sup_empty_false_arm_and_caller_completion_observations(client):
    response=post(client,'saved_sup_event_53772',minimal_sup_payload());assert response.status_code==200
    r=response.get_json()['result'];assert r['selected_case_frame']=='54004'and r['leaf_observations']==r['local_assignments']==[]
    p=sup_payload();p['completed_sinks']=['55317','54637']
    response=post(client,'saved_sup_event_53772',p);assert response.status_code==200
    r=response.get_json()['result'];assert r['completed_sinks']==p['completed_sinks']
    assert r['completion_observations_are_feasible_trace'] is False


def test_sup_carrier_literal_reference_error_and_native_boundary_refusals(client):
    mutants=[]
    for uid in ('54644','55216'):
        for value in ([False]*39,[False]*41,[0]*40):
            p=sup_payload();p['local_reads'][uid]=value;mutants.append(p)
    for uid in ('54623','55116','76784'):
        p=sup_payload();p['literal_inputs'][uid]=0;mutants.append(p)
        p=sup_payload();del p['literal_inputs'][uid];mutants.append(p)
    p=sup_payload();p['reference_bindings']['54587']['stored_URI_bytes']['bytes_hex']+='00';mutants.append(p)
    p=sup_payload();p['native_boundaries']['54669']['outputs']['54682']['status']=0;mutants.append(p)
    p=sup_payload();p['native_boundaries']['55252']['outputs']['55281']['code']=2**31;mutants.append(p)
    p=sup_payload();del p['unwired_inputs']['55271'];mutants.append(p)
    p=sup_payload();p['unwired_inputs']['54821']=65536;mutants.append(p)
    for report in (['55317','55317'],['55543']):
        p=sup_payload();p['completed_sinks']=report;mutants.append(p)
    for flag in sup_payload()['unqualified_boundaries']:
        p=sup_payload();p['unqualified_boundaries'][flag]=True;mutants.append(p)
    for p in mutants:assert post(client,'saved_sup_event_53772',p).status_code==400
    p=sup_payload();p['unwired_inputs']['54806']={'bytes_hex':'00FF'}
    response=post(client,'saved_sup_event_53772',p);assert response.status_code==200
    assert response.get_json()['result']['leaf_observations'][1]['inputs']['54806']=={'bytes_hex':'00FF'}
    p['unwired_inputs']['54806']={'bytes_hex':'ff'}
    assert post(client,'saved_sup_event_53772',p).status_code==400


@pytest.mark.parametrize('operation,factory',[('saved_acq_event_17899',acq_payload),('saved_sup_event_53772',sup_payload)])
def test_exact_identity_and_no_execution_extension(client,operation,factory):
    for key in ('source_id','source_version','event_uid','frame_uid'):
        p=factory();p[key]='wrong';assert post(client,operation,p).status_code==400
    p=factory();p['execute_native']=True;assert post(client,operation,p).status_code==400


def test_actual_request_cap_and_distinct_web_response_policy(client):
    p=oversized_sup_payload()
    raw=json.dumps(dict(operation='saved_sup_event_53772',inputs=p),ensure_ascii=False,separators=(',',':')).encode('utf8')
    assert len(raw)<=65536
    response=client.post('/api/elyse/supervision/replay',data=raw,content_type='application/json')
    assert response.status_code==200 and len(response.data)>65536
    assert response.get_json()['execution_allowed'] is False
    response=client.post('/api/elyse/supervision/replay',data=b'X'*65537,content_type='application/json')
    assert response.status_code==413 and response.get_json()['error']=='Replay body exceeds 65536 bytes'
    for raw in (b'{"operation":"saved_sup_event_53772","operation":"saved_sup_event_53772","inputs":{}}',
                b'{"operation":"saved_sup_event_53772","inputs":{"event_outputs":NaN}}'):
        response=client.post('/api/elyse/supervision/replay',data=raw,content_type='application/json')
        assert response.status_code==400 and response.get_json()['execution_allowed'] is False
