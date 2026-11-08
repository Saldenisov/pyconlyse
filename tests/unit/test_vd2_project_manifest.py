"""Synthetic camera files only: identity, noise reuse and source preservation."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "web/backend"))
from vd2_measurement_protocol import PhaseRequest
from vd2_project_manifest import MANIFEST_NAME, Vd2ProjectManifest, fingerprint, inspect_project, load_manifest
from vd2_sequence_processing import process_saved_sequence, retire_source_his


def measure(root, sample, phase, level, reuse="latest", target=None):
    stems = {"BRUIT": "BRUIT", "BASE": "BASE", "ABSORPTION": "ABS"}
    source = Path(target.his_path) if target else root / sample / f"{stems[phase]}.his"
    request = target or PhaseRequest(phase, 4, str(root), sample, str(source), f"Details for {sample}", reuse)
    journal = Vd2ProjectManifest()
    entry = journal.prepare(request)
    journal.record(request, entry["artifact_id"], "acquiring", machine_before={"test_fixture": True, "exposure_ms": 10})
    header = ('ScalingXScalingFile= Other,ScalingXScale=1,ScalingXUnit="nm",'
              'ScalingYScale=1,ScalingYUnit="ns",').encode()
    binary = bytearray(64)
    for start, value in ((2, len(header)), (4, 2), (6, 3), (12, 2), (14, 4)):
        binary[start:start + 2] = value.to_bytes(2, "little")
    with source.open("wb") as handle:
        handle.write(binary); handle.write(header)
        for _ in range(4):
            handle.write(np.full(6, level, dtype=np.int16).tobytes()); handle.write(bytes(64))
    result = process_saved_sequence(request)
    journal.record(request, entry["artifact_id"], "completed", machine_after={"test_fixture": True})
    cleanup = retire_source_his(request, result)
    journal.record_retention(request, entry['artifact_id'], cleanup)
    result.update(cleanup)
    return entry, result


def test_replacement_failure_keeps_current_data_and_success_selects_new_verified_h5(tmp_path):
    from vd2_phase_destination import PhaseDestinations
    from vd2_measurement_protocol import Vd2MeasurementProtocol
    two_samples(tmp_path)
    path = tmp_path / MANIFEST_NAME
    before = load_manifest(path)
    previous = before['samples']['sample 1']['phases']['ABSORPTION']
    old_file = tmp_path / 'sample 1/ABS.h5'
    old_bytes = old_file.read_bytes()
    original = Vd2MeasurementProtocol._build_request('ABSORPTION',4,str(tmp_path),'sample 1')
    planner = PhaseDestinations()
    target = planner.consume(planner.review(original)['choices']['replace']['token'], original)
    journal = Vd2ProjectManifest()
    pending = journal.prepare(target)
    assert load_manifest(path)['samples']['sample 1']['phases']['ABSORPTION'] == previous
    journal.record(target,pending['artifact_id'],'failed',error='Synthetic acquisition failure')
    assert inspect_project(path)['samples'][0]['ready'] is True
    target = planner.consume(planner.review(original)['choices']['replace']['token'], original)
    completed, result = measure(tmp_path,'sample 1','ABSORPTION',65,target=target)
    after = load_manifest(path)
    assert after['samples']['sample 1']['phases']['ABSORPTION'] == completed['artifact_id']
    assert after['artifacts'][completed['artifact_id']]['replaces'] == previous
    assert after['artifacts'][previous] == before['artifacts'][previous]
    assert after['samples']['sample 2']['bruit_reference'] == before['samples']['sample 2']['bruit_reference']
    assert old_file.read_bytes() == old_bytes
    plan = inspect_project(path)
    assert plan['samples'][0]['inputs']['ABS'] == result['h5_path']
    assert all(sample['ready'] for sample in plan['samples'])
    assert not Path(target.his_path).exists()
    row = plan['samples'][0]
    assert row['folder'] == str(tmp_path / 'sample 1')
    absorption_history = [item for item in row['measurements'] if item['phase'] == 'ABSORPTION']
    assert len(absorption_history) == 3
    assert any(item['status'] == 'failed' for item in absorption_history)
    assert sum(item['selected'] for item in absorption_history) == 1


def test_replacing_bruit_preserves_the_exact_noise_source_used_by_another_sample(tmp_path):
    from vd2_phase_destination import PhaseDestinations
    from vd2_measurement_protocol import Vd2MeasurementProtocol
    two_samples(tmp_path)
    before = load_manifest(tmp_path / MANIFEST_NAME)
    previous = before['samples']['sample 2']['bruit_reference']
    original = Vd2MeasurementProtocol._build_request('BRUIT',4,str(tmp_path),'sample 1')
    planner = PhaseDestinations()
    target = planner.consume(planner.review(original)['choices']['replace']['token'],original)
    new, _ = measure(tmp_path,'sample 1','BRUIT',12,target=target)
    after = load_manifest(tmp_path / MANIFEST_NAME)
    assert after['samples']['sample 1']['bruit_reference'] == new['artifact_id']
    assert after['samples']['sample 2']['bruit_reference'] == previous
    assert after['artifacts'][previous] == before['artifacts'][previous]
    assert all(sample['ready'] for sample in inspect_project(tmp_path / MANIFEST_NAME)['samples'])


def test_late_replacement_failure_restores_prior_phase_and_noise_reference(tmp_path):
    from vd2_phase_destination import PhaseDestinations
    from vd2_measurement_protocol import Vd2MeasurementProtocol
    two_samples(tmp_path)
    path = tmp_path / MANIFEST_NAME
    before = load_manifest(path)
    previous = before['samples']['sample 1']['bruit_reference']
    original = Vd2MeasurementProtocol._build_request('BRUIT',4,str(tmp_path),'sample 1')
    planner = PhaseDestinations()
    target = planner.consume(planner.review(original)['choices']['replace']['token'],original)
    new, _ = measure(tmp_path,'sample 1','BRUIT',12,target=target)
    Vd2ProjectManifest().record(target,new['artifact_id'],'failed',error='Late verification failure')
    after = load_manifest(path)
    assert after['samples']['sample 1']['bruit_reference'] == previous
    assert after['samples']['sample 1']['phases']['BRUIT'] == previous
    assert after['artifacts'][new['artifact_id']]['status'] == 'failed'
    assert all(sample['ready'] for sample in inspect_project(path)['samples'])


def test_base_pins_its_saved_bruit_while_conversion_is_pending_and_does_not_substitute_on_failure(tmp_path):
    measure(tmp_path,'older noise','BRUIT',10)
    journal=Vd2ProjectManifest()
    bruit=PhaseRequest('BRUIT',4,str(tmp_path),'sample',str(tmp_path/'sample/BRUIT.his'))
    entry=journal.prepare(bruit)
    Path(bruit.his_path).write_bytes(b'saved source fixture')
    journal.record(bruit,entry['artifact_id'],'saved')
    journal.record(bruit,entry['artifact_id'],'processing')
    base=PhaseRequest('BASE',4,str(tmp_path),'sample',str(tmp_path/'sample/BASE.his'))
    journal.prepare(base)
    data=load_manifest(tmp_path/MANIFEST_NAME)
    assert data['samples']['sample']['bruit_reference']==entry['artifact_id']
    assert any(item['id']==entry['artifact_id'] and item['status']=='processing' for item in inspect_project(tmp_path/MANIFEST_NAME)['bruit_options'])
    journal.record(bruit,entry['artifact_id'],'failed',error='conversion failed')
    assert load_manifest(tmp_path/MANIFEST_NAME)['samples']['sample']['bruit_reference']==entry['artifact_id']


def test_completed_file_hashing_does_not_hold_the_manifest_lock(tmp_path,monkeypatch):
    import threading
    import vd2_project_manifest as module
    journal=Vd2ProjectManifest()
    request=PhaseRequest('BRUIT',4,str(tmp_path),'sample',str(tmp_path/'sample/BRUIT.his'))
    entry=journal.prepare(request)
    Path(request.his_path).write_bytes(b'fixture his')
    Path(request.his_path).with_suffix('.h5').write_bytes(b'fixture h5')
    journal.record(request,entry['artifact_id'],'saved')
    entered=threading.Event();release=threading.Event();prepared=threading.Event()
    actual=module.fingerprint
    def slow(path):
        if Path(path).suffix=='.h5':entered.set();assert release.wait(5)
        return actual(path)
    monkeypatch.setattr(module,'fingerprint',slow)
    converter=threading.Thread(target=lambda:journal.record(request,entry['artifact_id'],'completed'));converter.start()
    second=PhaseRequest('BASE',4,str(tmp_path),'other',str(tmp_path/'other/BASE.his'))
    starter=threading.Thread(target=lambda:(journal.prepare(second),prepared.set()))
    try:
        assert entered.wait(2);starter.start()
        assert prepared.wait(1),'new acquisition blocked by conversion hash'
    finally:
        release.set();converter.join(3);starter.join(3)
    assert 'other' in load_manifest(tmp_path/MANIFEST_NAME)['samples']


def two_samples(root):
    noise, _ = measure(root, "sample 1", "BRUIT", 10)
    for sample in ("sample 1", "sample 2"):
        measure(root, sample, "BASE", 110)
        measure(root, sample, "ABSORPTION", 90)
    return noise


def test_project_records_machine_state_and_exact_reused_bruit(tmp_path):
    noise = two_samples(tmp_path)
    path = tmp_path / MANIFEST_NAME
    data = load_manifest(path)
    assert data["samples"]["sample 2"]["bruit_reference"] == noise["artifact_id"]
    assert not (tmp_path / "sample 2/BRUIT.his").exists()
    artifact = data["artifacts"][noise["artifact_id"]]
    assert artifact["machine_before"]["exposure_ms"] == 10
    assert artifact["h5"]["sha256"] == fingerprint(tmp_path / "sample 1/BRUIT.h5")["sha256"]
    plan = inspect_project(path)
    assert all(sample["ready"] for sample in plan["samples"])
    assert plan["samples"][1]["bruit_reused"] is True
    assert plan["samples"][1]["bruit_sample"] == "sample 1"
    assert len(list(tmp_path.rglob("*.his"))) == 0
    assert all(artifact['his']['retained'] is False for artifact in data['artifacts'].values())
    assert all('sha256' in artifact['his'] for artifact in data['artifacts'].values())


def test_existing_reference_does_not_drift_when_new_bruit_is_acquired(tmp_path):
    old, _ = measure(tmp_path, "first", "BRUIT", 10)
    measure(tmp_path, "second", "BASE", 110)
    new, _ = measure(tmp_path, "third", "BRUIT", 11)
    measure(tmp_path, "second", "ABSORPTION", 90)
    data = load_manifest(tmp_path / MANIFEST_NAME)
    assert old["artifact_id"] != new["artifact_id"]
    assert data["samples"]["second"]["bruit_reference"] == old["artifact_id"]


def test_changed_noise_is_reported_instead_of_substituted(tmp_path):
    two_samples(tmp_path)
    (tmp_path / "sample 1/BRUIT.h5").write_bytes(b"changed")
    plan = inspect_project(tmp_path / MANIFEST_NAME)
    assert all(not sample["ready"] and "changed" in sample["error"] for sample in plan["samples"])


def test_partial_acquisition_and_failed_phase_remain_explicit(tmp_path):
    request = PhaseRequest("BASE", 4, str(tmp_path), "partial", str(tmp_path / "partial/BASE.his"))
    journal = Vd2ProjectManifest(); entry = journal.prepare(request)
    journal.record(request, entry["artifact_id"], "failed", error="Native sequence outcome uncertain")
    data = load_manifest(tmp_path / MANIFEST_NAME)
    assert data["artifacts"][entry["artifact_id"]]["error"] == "Native sequence outcome uncertain"
    assert inspect_project(tmp_path / MANIFEST_NAME)["samples"][0]["ready"] is False


def test_corrupt_existing_manifest_is_never_replaced(tmp_path):
    path = tmp_path / MANIFEST_NAME; path.write_text("broken")
    before = path.read_bytes()
    request = PhaseRequest("BRUIT", 4, str(tmp_path), "sample", str(tmp_path / "sample/BRUIT.his"))
    with pytest.raises(ValueError): Vd2ProjectManifest().prepare(request)
    assert path.read_bytes() == before


@pytest.mark.parametrize("relative", ["../outside.h5", "C:\\outside.h5", "/outside.h5", "..\\outside.h5"])
def test_manifest_cannot_reference_files_outside_project(tmp_path, relative):
    two_samples(tmp_path)
    path = tmp_path / MANIFEST_NAME; data = load_manifest(path)
    identity = data["samples"]["sample 1"]["bruit_reference"]
    data["artifacts"][identity]["h5"]["path"] = relative
    path.write_text(json.dumps(data))
    assert all(not sample["ready"] and "project folder" in sample["error"] for sample in inspect_project(path)["samples"])


@pytest.mark.parametrize("as_method", [False, True])
@pytest.mark.parametrize("failed", [False, True])
def test_machine_snapshot_accepts_tango_failure_property_and_method(monkeypatch, as_method, failed):
    from types import SimpleNamespace
    import pump_probe_vd2_api as api
    class Attribute:
        value = np.int64(3)
        has_failed = (lambda self: failed) if as_method else failed
        def get_err_stack(self): return ['native read failed']
    class ArrayAttribute(Attribute):
        value = np.asarray([1.5, -2.5])
    class Proxy:
        def __init__(self, name): self.name = name
        def set_timeout_millis(self, value): pass
        def attribute_list_query_ex(self):
            return [SimpleNamespace(name='gain', data_format=SimpleNamespace(name='SCALAR')),
                    SimpleNamespace(name='currents_meas', data_format=SimpleNamespace(name='SPECTRUM')),
                    SimpleNamespace(name='image', data_format=SimpleNamespace(name='IMAGE'))]
        def read_attributes(self, names):
            assert names == (['gain', 'currents_meas'] if self.name == 'ELYSE/pdu/iTest' else ['gain'])
            return [Attribute() if name == 'gain' else ArrayAttribute() for name in names]
    class ControlProxy:
        def read_attributes(self, names): return [Attribute() for _ in names]
        def state(self): return 'ON'
    control = api._snapshot(ControlProxy())
    assert bool(control['attribute_errors']) is failed
    if not failed:
        assert control['values']['sequence_loops'] == 3
    monkeypatch.setattr(api, 'DeviceProxy', lambda name: Proxy(name))
    monkeypatch.setattr(api, '_snapshot', lambda _: {'values': {'exposure': '10 ms'}})
    monkeypatch.setattr(api, '_owis_sample_stage_state', lambda: {'position_mm': 65.0})
    monkeypatch.setattr(api, '_zaber_stage_state', lambda: {'position_mm': 0.0})
    result = api._machine_snapshot(None)
    assert len(result['devices']) == 6
    for name, device in result['devices'].items():
        if failed:
            assert device['values'] == {}
            assert 'native read failed' in device['errors']['gain']
        else:
            assert device['values'] == ({'gain': 3, 'currents_meas': [1.5, -2.5]}
                                        if name == 'ELYSE/pdu/iTest' else {'gain': 3})
            assert device['errors'] == {}
