import sys
import threading
from pathlib import Path
from types import SimpleNamespace

from flask import Flask
import pytest
from tests._tango_stub import install_tango_stub


class Patch:
    def setitem(self,mapping,key,value):mapping[key]=value


install_tango_stub(Patch())
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'web/backend'))
import pump_probe_vd2_api as vd2
from vd2_measurement_protocol import Vd2MeasurementProtocol


class Proxy:
    def set_timeout_millis(self,value):pass
    def read_attribute(self,name):return SimpleNamespace(value=True)
    def write_attribute(self,*args):pass
    def command_inout(self,*args):pass


@pytest.fixture
def app(monkeypatch):
    app=Flask(__name__);app.config['TESTING']=True
    app.register_blueprint(vd2.pump_probe_vd2_api)
    return app


def test_state_and_cached_preview_respond_while_conversion_is_held(app,monkeypatch):
    entered=threading.Event();release=threading.Event();responded=threading.Event();responses=[]
    def convert(request):
        entered.set();assert release.wait(5);return {}
    protocol=Vd2MeasurementProtocol(Proxy,sequence_processor=convert)
    monkeypatch.setattr(vd2,'_measurement_protocol',protocol)
    monkeypatch.setattr(vd2,'_preview_cache',({'success':True,'frame_available':True,'pixels_b64':'fixture'},200))
    monkeypatch.setattr(vd2,'_preview_cache_until',float('inf'))
    monkeypatch.setattr(vd2,'_proxy',lambda:pytest.fail('cached preview must not touch hardware'))
    protocol.start(phase='BRUIT',frames_per_his=2,run_name='synthetic')
    def requests():
        with app.test_client() as client:
            responses.extend([client.get('/api/pump-probe-vd2/protocol/state').json,client.get('/api/pump-probe-vd2/preview').json])
        responded.set()
    reader=threading.Thread(target=requests)
    try:
        assert entered.wait(2);reader.start()
        assert responded.wait(1),'HTTP request blocked behind conversion'
        assert responses[0]['status']=='processing' and responses[0]['acquisition_active'] is False
        assert responses[1]['frame_available'] is True
    finally:
        release.set();reader.join(3);protocol.wait(3)


@pytest.mark.parametrize('value,expected',[
    ({'status':'processing'},'processing'),
    ({'status':'processing','acquisition_active':False,'acquisition_phase':'idle'},'idle'),
    ({'status':'saving','acquisition_active':True,'acquisition_phase':'saving'},'saving'),
])
def test_only_explicit_camera_release_can_bypass_the_legacy_processing_guard(monkeypatch,value,expected):
    monkeypatch.setattr(vd2,'_measurement_protocol',SimpleNamespace(status=lambda:value))
    assert vd2._protocol_hardware_phase()==expected


def test_plan_is_allowed_during_file_conversion_but_full_queue_rejects_before_project_reads(app,monkeypatch,tmp_path):
    import treatment_api
    from vd2_phase_destination import PhaseDestinations
    state={'status':'processing','acquisition_active':False,'acquisition_phase':'idle','queue_full':False}
    protocol=SimpleNamespace(status=lambda:state,_build_request=Vd2MeasurementProtocol._build_request)
    monkeypatch.setattr(vd2,'_measurement_protocol',protocol)
    monkeypatch.setattr(vd2,'_phase_destinations',PhaseDestinations())
    monkeypatch.setattr(treatment_api,'_ensure_within_allowed_root',lambda path:path)
    monkeypatch.setattr(vd2,'_proxy',lambda:pytest.fail('plan must not reach equipment'))
    body={'phase':'BASE','frames_per_his':3,'output_root':str(tmp_path),'run_name':'next'}
    with app.test_client() as client:
        response=client.post('/api/pump-probe-vd2/protocol/plan',json=body)
        assert response.status_code==200 and response.json['conflict'] is False
        state['queue_full']=True
        monkeypatch.setattr(vd2._phase_destinations,'review',lambda request:pytest.fail('full queue reached filesystem'))
        response=client.post('/api/pump-probe-vd2/protocol/plan',json=body)
        assert response.status_code==409
        assert 'queue is full' in response.json['error']


def test_another_phase_conversion_can_publish_during_destination_review(tmp_path):
    from vd2_phase_destination import PhaseDestinations
    from vd2_project_manifest import Vd2ProjectManifest
    journal=Vd2ProjectManifest()
    bruit=Vd2MeasurementProtocol._build_request('BRUIT',3,str(tmp_path),'sample')
    saved=journal.prepare(bruit)
    Path(bruit.his_path).write_bytes(b'fixture saved HIS')
    journal.record(bruit,saved['artifact_id'],'saved')
    base=Vd2MeasurementProtocol._build_request('BASE',3,str(tmp_path),'sample')
    planner=PhaseDestinations();token=planner.review(base)['choices']['record']['token']
    journal.record(bruit,saved['artifact_id'],'processing')
    Path(bruit.his_path).with_suffix('.h5').write_bytes(b'fixture H5 changes folder timestamp')
    assert planner.consume(token,base).his_path==base.his_path


def test_changing_the_selected_phase_still_invalidates_a_review(tmp_path):
    from vd2_phase_destination import PhaseDestinations
    from vd2_project_manifest import Vd2ProjectManifest
    from vd2_measurement_protocol import Vd2ProtocolError
    journal=Vd2ProjectManifest()
    # Establish project identity before taking a quote for its empty Base slot.
    bruit=Vd2MeasurementProtocol._build_request('BRUIT',3,str(tmp_path),'sample');journal.prepare(bruit)
    base=Vd2MeasurementProtocol._build_request('BASE',3,str(tmp_path),'sample')
    planner=PhaseDestinations();token=planner.review(base)['choices']['record']['token']
    journal.prepare(base)
    with pytest.raises(Vd2ProtocolError,match='Project changed'):
        planner.consume(token,base)


def test_review_of_a_tracked_repeat_survives_its_conversion_and_his_retirement(tmp_path):
    from vd2_phase_destination import PhaseDestinations
    from vd2_project_manifest import Vd2ProjectManifest
    journal=Vd2ProjectManifest()
    request=Vd2MeasurementProtocol._build_request('ABSORPTION',3,str(tmp_path),'sample')
    entry=journal.prepare(request)
    source=Path(request.his_path);source.write_bytes(b'fixture HIS')
    journal.record(request,entry['artifact_id'],'saved')
    planner=PhaseDestinations();token=planner.review(request)['choices']['replace']['token']
    journal.record(request,entry['artifact_id'],'processing')
    source.with_suffix('.h5').write_bytes(b'fixture verified H5')
    journal.record(request,entry['artifact_id'],'completed')
    source.unlink()
    journal.record_retention(request,entry['artifact_id'],{'source_his_retained':False,'source_his_cleanup_status':'removed'})
    replacement=planner.consume(token,request)
    assert replacement.replaces_artifact==entry['artifact_id']
    assert Path(replacement.his_path)!=source
