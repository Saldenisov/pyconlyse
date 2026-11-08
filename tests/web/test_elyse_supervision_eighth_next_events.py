"""G69 modern web calls exact shared pure source bodies; no provider access."""
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
from eighth_next_event_fixtures import acq_payload,sup_payload,minimum_sup_payload,sparse_sup_payload
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
    app.config.update(TESTING=True,JWT_SECRET_KEY='G69-software-only-pure-web-key')
    JWTManager(app);app.register_blueprint(api.elyse_supervision_api)
    return app.test_client()


def post(client,operation,payload):
    return client.post('/api/elyse/supervision/replay',json=dict(operation=operation,inputs=payload))


def test_exact_shared_core_function_identity():
    from DeviceServers.control.elyse_acq.vi_simulation import acquisition_event_48846 as acq,supervision_event_33463 as sup
    from legacy.xp_acq_agent.elyse_agent import saved_acq_event_48846,saved_sup_event_33463
    assert acq.replay_event is saved_acq_event_48846.replay_event
    assert acq.replay_saved_acq_event_48846 is saved_acq_event_48846.replay_saved_acq_event_48846
    assert sup.project_event_33463 is saved_sup_event_33463.project_event_33463
    assert sup.replay_saved_sup_event_33463 is saved_sup_event_33463.replay_saved_sup_event_33463


@pytest.mark.parametrize('operation,factory',[
    ('saved_acq_event_48846',acq_payload),('saved_sup_event_33463',sup_payload),
    ('saved_sup_event_33463',minimum_sup_payload),('saved_sup_event_33463',sparse_sup_payload)])
def test_exact_new_envelope_and_same_pure_function(client,operation,factory):
    from legacy.xp_acq_agent.elyse_agent.saved_acq_event_48846 import replay_saved_acq_event_48846
    from legacy.xp_acq_agent.elyse_agent.saved_sup_event_33463 import replay_saved_sup_event_33463
    p=factory();before=copy.deepcopy(p);response=post(client,operation,p)
    assert response.status_code==200
    body=response.get_json();assert body['execution_allowed'] is False
    assert body['physical_status']=='NOT_EXECUTED'and body['input_origin']=='OPERATOR_SUPPLIED_REPLAY'
    adapter=replay_saved_acq_event_48846 if operation=='saved_acq_event_48846'else replay_saved_sup_event_33463
    assert body['result']==adapter(p)
    assert body['result']['whole_event_equivalence'] is False
    assert tuple(body['result'][k]for k in('source_id','source_version','event_uid','frame_uid'))==tuple(p[k]for k in('source_id','source_version','event_uid','frame_uid'))
    assert p==before


def test_acq_actual_C4_EPS_DPS_fields_and_fresh_publications(client):
    p=acq_payload();p['snapshots']['54039'][3]=True;p['snapshots']['54110'][3]=False
    p['snapshots']['35726'][15]=True;p['snapshots']['47280'][49]=True;p['snapshots']['47323'][18]=True
    response=post(client,'saved_acq_event_48846',p);assert response.status_code==200
    r=response.get_json()['result'];w={x['node_uid']:x['value']for x in r['writes']}
    assert(w['54021'][18],w['54094'][18])==(True,False)
    assert(w['54021'][3],w['54094'][3])==(True,False)
    assert w['54045'] is True
    assert w['54162'][49] is False and w['54162'][45] is True
    assert w['54192'][15] is False
    calls={x['node_uid']:x['input_ports']for x in r['leaf_calls']}
    assert calls['47263']['47277']==p['snapshots']['35726']
    assert calls['47306']['47320']==p['snapshots']['47280']
    assert calls['47349']['47363']==p['snapshots']['47323']
    for uid,face,producer,out in(('47306','47314','47263','47274'),('47349','47357','47306','47317'),('47366','47396','47349','47360')):
        assert calls[uid][face]==p['leaf_returns'][producer][out]
    assert calls['54053']=={'54058':150}and calls['50582']=={'50592':100}
    assert r['completed_stages']==['53995','54078','54126','54238','50555']
    assert len([x for x in r['log']if x['kind']=='border_transfer'])==5
    assert r['wait_units_or_pulse_duration_qualified'] is False
    assert r['snapshot_equality_qualified'] is False


def test_acq_false_and_pending_wait_require_no_invented_completion(client):
    p=acq_payload(False)
    for key in('schedule','snapshots','leaf_returns','unwired_inputs','reference_bindings'):p[key]=None
    response=post(client,'saved_acq_event_48846',p);assert response.status_code==200
    r=response.get_json()['result'];assert r['selected_case_frame']=='53972'and r['leaf_calls']==r['writes']==[]
    p=acq_payload();p['schedule']=p['schedule'][:p['schedule'].index(dict(kind='leaf_call',uid='54053'))+1]
    response=post(client,'saved_acq_event_48846',p);assert response.status_code==200
    r=response.get_json()['result'];assert r['pending_leaf_uids']==['54053']and r['completed_stages']==[]
    p['schedule'].append(dict(kind='stage_complete',uid='53995'))
    assert post(client,'saved_acq_event_48846',p).status_code==400


def test_sup_exact_source_mask_arithmetic_copy_paths_and_phase3_reads(client):
    p=sup_payload();response=post(client,'saved_sup_event_33463',p);assert response.status_code==200
    r=response.get_json()['result'];assert(r['loop_iteration_count'],r['max_mask'],r['selected_index'])==(9,128,0)
    assert r['masks']==[128]+[0]*8
    assert r['updated_cluster'][5]==0.5-0.1 and r['updated_cluster'][7:]==[False]*4
    a={x['node_uid']:x['data']for x in r['local_assignments']}
    c6=list(p['local_reads']['46632']);c7=list(p['local_reads']['46671']);voie=p['local_reads']['46585']
    for dst,src in((6,4),(7,5),(9,8),(8,7)):c6[dst]=voie[src][5]
    for dst,src in((9,6),(6,0),(7,1),(3,2),(4,3)):c7[dst]=voie[src][5]
    assert a['46665']==c6 and a['46698']==c7
    leaves={x['node_uid']:x for x in r['leaf_observations']}
    for read,writer,face,handler,errorface,out in(
        ('46864','47022','47036','46870','46900','47033'),('46903','47039','47053','46909','46939','47050'),
        ('46942','47056','47070','46948','46978','47067'),('46981','47073','47087','46989','47019','47084')):
        assert leaves[writer]['inputs'][face]==p['local_reads'][read]
        assert leaves[handler]['inputs'][errorface]==p['native_returns'][writer][out]
    assert leaves['47022']['inputs']['47036']!=c6
    assert leaves['33935']['inputs']['33949']==r['updated_cluster']
    for flag in('native_variant_conversion_qualified','source_schedule_qualified','native_defaults_qualified','same_name_callee_body_equivalence'):
        assert r[flag] is False


def test_sup_sparse_reports_descriptor_absence_and_inactive_carriers(client):
    response=post(client,'saved_sup_event_33463',sparse_sup_payload());assert response.status_code==200
    r=response.get_json()['result'];assert r['max_mask']==1 and r['local_assignments']==[]
    assert [x['node_uid']for x in r['local_reads']]==['46864','46903','46942','46981']
    fields={x['terminal_uid']:x for x in r['field_projections']}
    for uid in('34033','34061'):
        assert fields[uid]['raw_flattened_field_index'] is None
        assert fields[uid]['descriptor_projection_ordinal']==0 and fields[uid]['typed_position_path']==[0]
    assert r['null_model_ports_preserved']==['28333','33657','33724']
    assert r['null_ports_are_caller_inputs'] is False and r['ctlRefConst33897_is_gRef_bank_read'] is False


@pytest.mark.parametrize('operation,factory',[
    ('saved_acq_event_48846',acq_payload),('saved_sup_event_33463',sup_payload)])
@pytest.mark.parametrize('mutation',['source','version','missing_version','frame','event','native','defaults','hardware'])
def test_source_exactness_and_native_flag_refusal(client,operation,factory,mutation):
    p=factory()
    if mutation=='missing_version':p.pop('source_version')
    else:
        key,value={'source':('source_id','APP-02'),'version':('source_version','0'*64),
            'frame':('frame_uid','31552'),'event':('event_uid','44'),'native':('native_execution',True),
            'defaults':('native_defaults_qualified',True),'hardware':('hardware_execution',True)}[mutation]
        p[key]=value
    assert post(client,operation,p).status_code==400


@pytest.mark.parametrize('mutation',['tie','composite','shape','reference','completion','literal_type'])
def test_sup_invalid_source_boundary_domains(client,mutation):
    p=sup_payload()
    if mutation=='tie':p['event_returns']['33480']['33497'][1][7]=True
    elif mutation=='composite':p['event_returns']['33480']['33497'][0][0]=True
    elif mutation=='shape':p['native_returns']['65169']['65191'].pop()
    elif mutation=='reference':p['native_returns']['33859']['33889']=[]
    elif mutation=='completion':p['completed_sinks']=['foreign']
    else:p['literal_inputs']['46410']=0
    assert post(client,'saved_sup_event_33463',p).status_code==400


def test_outer_envelope_duplicates_nonfinite_and_request_cap(client):
    path='/api/elyse/supervision/replay'
    response=client.post(path,json=dict(operation='saved_acq_event_48846',inputs=acq_payload(),execute_native=True))
    assert response.status_code==400
    raw='{"operation":"saved_acq_event_48846","operation":"saved_sup_event_33463","inputs":'+json.dumps(acq_payload())+'}'
    assert client.post(path,data=raw,content_type='application/json').status_code==400
    p=sup_payload();p['native_returns']['65169']['65191'][5]=float('nan')
    raw=json.dumps(dict(operation='saved_sup_event_33463',inputs=p))
    assert client.post(path,data=raw,content_type='application/json').status_code==400
    response=client.post(path,data=b' '*65537,content_type='application/json')
    assert response.status_code==413 and response.get_json()['error']=='Replay body exceeds 65536 bytes'
