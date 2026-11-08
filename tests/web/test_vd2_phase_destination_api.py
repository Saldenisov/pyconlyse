import sys
from pathlib import Path

from flask import Flask, jsonify
import pytest
from tests._tango_stub import install_tango_stub


class Patch:
    def setitem(self, mapping, key, value):
        mapping[key] = value


install_tango_stub(Patch())
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'web/backend'))
import pump_probe_vd2_api as vd2
import treatment_api
from vd2_measurement_protocol import Vd2MeasurementProtocol
from vd2_phase_destination import PhaseDestinations


@pytest.fixture
def setup(monkeypatch, tmp_path):
    class Protocol:
        _build_request = staticmethod(Vd2MeasurementProtocol._build_request)
        calls = []
        def status(self):
            return {'status': 'idle'}
        def start_request(self, request):
            self.calls.append(request)
            return {'status': 'acquiring', 'his_path': request.his_path, 'sample_name': request.run_name}
    protocol = Protocol()
    monkeypatch.setattr(vd2, '_measurement_protocol', protocol)
    monkeypatch.setattr(vd2, '_phase_destinations', PhaseDestinations())
    monkeypatch.setattr(vd2, '_proxy', lambda: pytest.fail('Unexpected hardware access'))
    monkeypatch.setattr(treatment_api, '_ensure_within_allowed_root', lambda path: path if Path(path) == tmp_path else pytest.fail('Unexpected project root'))
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.register_blueprint(vd2.pump_probe_vd2_api)
    body = dict(phase='ABSORPTION',frames_per_his=20,output_root=str(tmp_path),run_name='sample')
    old = tmp_path / 'sample/ABS.h5';old.parent.mkdir();old.write_bytes(b'old measurement')
    return app.test_client(), body, old, protocol


def test_review_is_passive_and_returns_both_repeat_choices_without_creating_folders(setup):
    client, body, old, protocol = setup
    response = client.post('/api/pump-probe-vd2/protocol/plan',json=body)
    assert response.status_code == 200
    assert response.json['conflict'] is True
    assert response.json['choices']['new_folder']['run_name'] == 'sample_2'
    assert not (old.parent / '.versions').exists()
    assert old.read_bytes() == b'old measurement'
    assert protocol.calls == []


def test_hardware_denial_precedes_destination_consumption_or_worker_and_binds_exact_new_path(setup, monkeypatch):
    client, body, old, protocol = setup
    choice = client.post('/api/pump-probe-vd2/protocol/plan',json=body).json['choices']['replace']
    calls = []
    def deny(**plan):
        calls.append(plan)
        return jsonify(success=False),428
    monkeypatch.setattr(vd2,'require_http_hardware',deny)
    response=client.post('/api/pump-probe-vd2/protocol/start',json={**body,'destination_token':choice['token']})
    assert response.status_code == 428
    assert calls[0]['args']['his_path'] == choice['his_path']
    assert calls[0]['args']['destination_token'] == choice['token']
    assert not Path(choice['his_path']).parent.exists()
    assert vd2._phase_destinations.resolve(choice['token'],protocol._build_request('ABSORPTION',20,body['output_root'],'sample')).his_path == choice['his_path']
    assert protocol.calls == []


def test_changed_destination_or_settings_fail_before_any_proxy_or_sequence(setup,monkeypatch):
    client,body,old,protocol=setup
    monkeypatch.setattr(vd2,'_approval_or_response',lambda *args:None)
    choice=client.post('/api/pump-probe-vd2/protocol/plan',json=body).json['choices']['replace']
    changed=client.post('/api/pump-probe-vd2/protocol/start',json={**body,'frames_per_his':21,'destination_token':choice['token']})
    assert changed.status_code == 409
    old.write_bytes(b'modified after review')
    response=client.post('/api/pump-probe-vd2/protocol/start',json={**body,'destination_token':choice['token']})
    assert response.status_code == 409
    assert 'changed after review' in response.json['error']
    assert protocol.calls == []


def test_selected_numbered_folder_is_exactly_the_authorized_worker_target_and_token_cannot_replay(setup,monkeypatch):
    client,body,old,protocol=setup
    monkeypatch.setattr(vd2,'_approval_or_response',lambda *args:None)
    monkeypatch.setattr(vd2,'_proxy',lambda:object())
    monkeypatch.setattr(vd2,'_verify_vd2_timing_ready',lambda proxy:None)
    choice=client.post('/api/pump-probe-vd2/protocol/plan',json=body).json['choices']['new_folder']
    request={**body,'destination_token':choice['token']}
    result=client.post('/api/pump-probe-vd2/protocol/start',json=request)
    assert result.status_code == 200
    assert result.json['sample_name'] == 'sample_2'
    assert protocol.calls[0].his_path == choice['his_path']
    assert protocol.calls[0].frames_per_his == 20
    assert len(protocol.calls) == 1
    assert client.post('/api/pump-probe-vd2/protocol/start',json=request).status_code == 409
    assert len(protocol.calls) == 1
    assert old.read_bytes() == b'old measurement'


def test_plan_requires_mutation_authentication_before_reading_the_project(setup,monkeypatch):
    import mutation_auth
    from flask_jwt_extended.exceptions import JWTExtendedException
    client,body,_,_=setup
    monkeypatch.setattr(mutation_auth,'mutation_auth_required',lambda:True)
    def deny():
        raise JWTExtendedException('not authenticated')
    monkeypatch.setattr(mutation_auth,'verify_jwt_in_request',deny)
    monkeypatch.setattr(vd2._phase_destinations,'review',lambda request:pytest.fail('Unauthenticated project access'))
    assert client.post('/api/pump-probe-vd2/protocol/plan',json=body).status_code == 401
