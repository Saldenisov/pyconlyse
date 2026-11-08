import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "web" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from vd2_measurement_protocol import Vd2MeasurementProtocol, Vd2ProtocolError


class FakeProxy:
    def __init__(self):
        self.calls = []

    def set_timeout_millis(self, value):
        self.calls.append(("timeout", value))

    def read_attribute(self, name):
        class Attribute:
            value = True
        self.calls.append(("read", name))
        return Attribute()

    def write_attribute(self, name, value):
        self.calls.append(("write", name, value))

    def command_inout(self, name, value=None):
        self.calls.append(("command", name, value))


def test_repeat_with_corrected_frame_count_runs_full_his_h5_manifest_pipeline_without_touching_old_data(tmp_path):
    import h5py
    import numpy as np
    from vd2_phase_destination import PhaseDestinations
    from vd2_project_manifest import MANIFEST_NAME, Vd2ProjectManifest, load_manifest
    from vd2_sequence_processing import check_new_sequence, process_saved_sequence, retire_source_his
    class FileProxy(FakeProxy):
        frames = 0
        def write_attribute(self, name, value):
            super().write_attribute(name,value)
            assert name == 'sequence_loops'
            self.frames = int(value)
        def command_inout(self, name, value=None):
            super().command_inout(name,value)
            if name != 'SaveCurrentSequence':
                return
            text=('ScalingXScalingFile= Other,ScalingXScale=1,ScalingXUnit="nm",'
                  'ScalingYScale=1,ScalingYUnit="ns",').encode()
            header=bytearray(64)
            for start,number in ((2,len(text)),(4,2),(6,3),(12,2),(14,self.frames)):
                header[start:start+2]=number.to_bytes(2,'little')
            with Path(value).open('wb') as handle:
                handle.write(header);handle.write(text)
                for index in range(self.frames):
                    level={'BRUIT.his':10,'BASE.his':110,'ABS.his':90}[Path(value).name]
                    handle.write(np.full(6,level+index,dtype=np.int16).tobytes());handle.write(bytes(64))
    proxy=FileProxy()
    protocol=Vd2MeasurementProtocol(lambda:proxy,artifact_preflight=check_new_sequence,
        artifact_journal=Vd2ProjectManifest(),sequence_processor=process_saved_sequence,artifact_finalizer=retire_source_his,
        snapshot_reader=lambda device:{'synthetic_camera':True})
    protocol.start(phase='ABSORPTION',frames_per_his=3,output_root=str(tmp_path),run_name='sample')
    protocol.wait(5)
    assert protocol.status()['status'] == 'completed'
    old_file=tmp_path/'sample/ABS.h5';old_bytes=old_file.read_bytes()
    previous=load_manifest(tmp_path/MANIFEST_NAME)['samples']['sample']['phases']['ABSORPTION']
    request=protocol._build_request('ABSORPTION',5,str(tmp_path),'sample')
    planner=PhaseDestinations()
    target=planner.consume(planner.review(request)['choices']['replace']['token'],request)
    protocol.start_request(target);protocol.wait(5)
    status=protocol.status()
    assert status['status'] == 'completed',status['error']
    assert status['frame_count'] == 5 and status['source_his_retained'] is False
    assert old_file.read_bytes() == old_bytes
    with h5py.File(status['h5_path'],'r') as handle:
        assert handle['raw_data'].shape[0] == 5
        assert handle['metadata'].attrs['frames_requested'] == 5
    manifest=load_manifest(tmp_path/MANIFEST_NAME)
    current=manifest['samples']['sample']['phases']['ABSORPTION']
    assert current != previous
    assert manifest['artifacts'][current]['replaces'] == previous
    assert not Path(target.his_path).exists()
    # A real converter queued behind a held first job must not prevent saving
    # Base/Absorption with different frame counts or mix their native settings.
    entered=threading.Event();release=threading.Event()
    def convert_later(request):
        if request.phase=='BRUIT':entered.set();assert release.wait(5)
        return process_saved_sequence(request)
    parallel=Vd2MeasurementProtocol(FileProxy,artifact_preflight=check_new_sequence,
        artifact_journal=Vd2ProjectManifest(),sequence_processor=convert_later,artifact_finalizer=retire_source_his,
        snapshot_reader=lambda device:{'synthetic_camera':True,'frames':device.frames})
    parallel.start(phase='BRUIT',frames_per_his=3,output_root=str(tmp_path),run_name='parallel')
    try:
        assert entered.wait(2)
        for phase,count in [('BASE',5),('ABSORPTION',2)]:
            parallel.start(phase=phase,frames_per_his=count,output_root=str(tmp_path),run_name='parallel')
            deadline=time.monotonic()+2
            while parallel.status()['acquisition_active'] and time.monotonic()<deadline:time.sleep(.001)
            assert not parallel.status()['acquisition_active']
        assert [job['status'] for job in parallel.status()['processing_jobs']]==['processing','queued','queued']
        assert all((tmp_path/'parallel'/name).exists() for name in ['BRUIT.his','BASE.his','ABS.his'])
    finally:
        release.set();parallel.wait(10)
    assert all(job['status']=='completed' for job in parallel.status()['processing_jobs'])
    for stem,count in [('BRUIT',3),('BASE',5),('ABS',2)]:
        with h5py.File(tmp_path/'parallel'/f'{stem}.h5','r') as handle:
            assert handle['raw_data'].shape[0]==count
        assert not (tmp_path/'parallel'/f'{stem}.his').exists()
    manifest=load_manifest(tmp_path/MANIFEST_NAME)
    sample=manifest['samples']['parallel']
    assert sample['bruit_reference']==sample['phases']['BRUIT']
    assert manifest['artifacts'][sample['phases']['BASE']]['machine_after']['frames']==5
    assert manifest['artifacts'][sample['phases']['ABSORPTION']]['machine_after']['frames']==2


def test_phase_protocol_writes_bruit_his_after_sequence():
    proxy = FakeProxy()
    protocol = Vd2MeasurementProtocol(lambda: proxy)

    state = protocol.start(
        phase="bruit",
        frames_per_his=25,
        output_root=r"E:\DATA_VD2",
        run_name="LiCl_001",
    )
    protocol.wait(1)

    assert state["phase"] == "BRUIT"
    assert state["his_path"] == r"E:\DATA_VD2\LiCl_001\BRUIT.his"
    assert protocol.status()["status"] == "completed"
    assert ("write", "sequence_loops", "25") in proxy.calls
    assert ("command", "StartSequence", None) in proxy.calls
    assert ("command", "WaitForIdle", None) in proxy.calls
    assert ("command", "SaveCurrentSequence", r"E:\DATA_VD2\LiCl_001\BRUIT.his") in proxy.calls


def test_phase_protocol_accepts_legacy_brew_name_as_bruit():
    protocol = Vd2MeasurementProtocol(FakeProxy)

    state = protocol.start(phase="brew", frames_per_his=1, run_name="legacy")

    assert state["phase"] == "BRUIT"
    assert state["his_path"].endswith(r"legacy\BRUIT.his")


def test_phase_protocol_rejects_invalid_run_name():
    protocol = Vd2MeasurementProtocol(FakeProxy)

    try:
        protocol.start(phase="BASE", frames_per_his=1, run_name="../unsafe")
    except Vd2ProtocolError as exc:
        assert "Run name" in str(exc)
    else:
        raise AssertionError("Expected invalid run name to fail")


def test_conversion_uses_another_thread_and_releases_camera_for_the_next_phase():
    entered=threading.Event();release=threading.Event();second_saved=threading.Event()
    proxy=FakeProxy();order=[];snapshot_threads=[]
    original_command=proxy.command_inout
    def command(name,value=None):
        assert threading.current_thread().name != 'vd2-h5-conversion'
        original_command(name,value)
        if name=='SaveCurrentSequence' and 'two' in value:second_saved.set()
    proxy.command_inout=command
    def convert(request):
        assert threading.current_thread().name=='vd2-h5-conversion'
        order.append(request.run_name)
        if request.run_name=='one':
            entered.set();assert release.wait(5)
        return {'h5_path':request.his_path.replace('.his','.h5'),'frame_count':3}
    def snapshot(device):
        snapshot_threads.append(threading.current_thread().name)
        return {'acquisition_thread':threading.current_thread().name}
    protocol=Vd2MeasurementProtocol(lambda:proxy,sequence_processor=convert,snapshot_reader=snapshot)
    protocol.start(phase='BASE',frames_per_his=3,run_name='one')
    try:
        assert entered.wait(2)
        assert protocol.status()['acquisition_active'] is False
        assert protocol.status()['status']=='processing'
        protocol.start(phase='ABSORPTION',frames_per_his=3,run_name='two')
        assert second_saved.wait(2)
        # Status calls remain responsive while the conversion callback waits.
        deadline=time.monotonic()+1
        while protocol.status()['acquisition_active'] and time.monotonic()<deadline:
            time.sleep(.001)
        state=protocol.status()
        assert state['acquisition_active'] is False
        assert [job['status'] for job in state['processing_jobs']]==['processing','queued']
        assert order==['one']
    finally:
        release.set();protocol.wait(5)
    assert order==['one','two']
    assert all(name.endswith('-his') for name in snapshot_threads)
    assert protocol.status()['h5_path'].endswith(r'two\ABS.h5')
    assert all(job['status']=='completed' for job in protocol.status()['processing_jobs'])


def test_queue_capacity_stops_before_hardware_and_conversion_failure_does_not_stop_next_file():
    entered=threading.Event();release=threading.Event();saved=threading.Event();proxy=FakeProxy()
    native_calls=[]
    def factory():
        native_calls.append('proxy');return proxy
    original=proxy.command_inout
    def command(name,value=None):
        original(name,value)
        if name=='SaveCurrentSequence' and 'two' in value:saved.set()
    proxy.command_inout=command
    def convert(request):
        if request.run_name=='one':
            entered.set();assert release.wait(5);raise RuntimeError('Synthetic conversion failure')
        return {'frame_count':2}
    protocol=Vd2MeasurementProtocol(factory,sequence_processor=convert,max_pending_processing=2)
    protocol.start(phase='BRUIT',frames_per_his=2,run_name='one')
    try:
        assert entered.wait(2)
        protocol.start(phase='BASE',frames_per_his=2,run_name='two')
        assert saved.wait(2)
        deadline=time.monotonic()+1
        while protocol.status()['acquisition_active'] and time.monotonic()<deadline:time.sleep(.001)
        before=len(native_calls)
        with pytest.raises(Vd2ProtocolError,match='queue is full'):
            protocol.start(phase='ABSORPTION',frames_per_his=2,run_name='three')
        assert len(native_calls)==before
    finally:
        release.set();protocol.wait(5)
    state=protocol.status()
    assert [job['status'] for job in state['processing_jobs']]==['failed','completed']
    assert state['status']=='completed'
    assert 'Synthetic conversion failure' in state['processing_jobs'][0]['error']


def test_old_conversion_failure_cannot_release_or_overwrite_a_new_camera_save():
    entered=threading.Event();release_conversion=threading.Event();saving=threading.Event();release_save=threading.Event()
    proxy=FakeProxy();original=proxy.command_inout
    def command(name,value=None):
        original(name,value)
        if name=='SaveCurrentSequence' and 'two' in value:
            saving.set();assert release_save.wait(5)
    proxy.command_inout=command
    def convert(request):
        if request.run_name=='one':
            entered.set();assert release_conversion.wait(5);raise RuntimeError('old conversion failed')
        return {}
    protocol=Vd2MeasurementProtocol(lambda:proxy,sequence_processor=convert)
    protocol.start(phase='BRUIT',frames_per_his=2,run_name='one')
    try:
        assert entered.wait(2)
        protocol.start(phase='BASE',frames_per_his=2,run_name='two');assert saving.wait(2)
        release_conversion.set()
        deadline=time.monotonic()+1
        while protocol.status()['processing_jobs'][0]['status']!='failed' and time.monotonic()<deadline:time.sleep(.001)
        state=protocol.status()
        assert state['sample_name']=='two' and state['status']=='saving'
        assert state['acquisition_active'] is True
        assert state['processing_jobs'][0]['status']=='failed'
    finally:
        release_save.set();release_conversion.set();protocol.wait(5)


def test_slow_manifest_preparation_does_not_hold_the_status_lock():
    entered=threading.Event();release=threading.Event();status_read=threading.Event()
    class Journal:
        def prepare(self,request):
            entered.set();assert release.wait(5);return {'artifact_id':'synthetic'}
        def record(self,*args,**kwargs):pass
    protocol=Vd2MeasurementProtocol(FakeProxy,artifact_journal=Journal())
    starter=threading.Thread(target=lambda:protocol.start(phase='BASE',frames_per_his=2,run_name='sample'))
    starter.start()
    try:
        assert entered.wait(2)
        reader=threading.Thread(target=lambda:(protocol.status(),status_read.set()));reader.start()
        assert status_read.wait(1),'status blocked behind manifest I/O'
        assert protocol.status()['acquisition_phase']=='preparing'
    finally:
        release.set();starter.join(3);protocol.wait(3)


def test_conversion_failure_is_not_reported_as_completed():
    def process(_request):
        raise ValueError("H5 verification failed; HIS retained")

    protocol = Vd2MeasurementProtocol(FakeProxy, sequence_processor=process)
    protocol.start(phase="ABSORPTION", frames_per_his=1, run_name="failure")
    protocol.wait(1)
    assert protocol.status()["status"] == "failed"
    assert protocol.status()["h5_path"] is None
    assert protocol.status()["error"] == "H5 verification failed; HIS retained"


def test_artifact_conflict_rejects_before_any_hardware_access():
    def reject(_request):
        raise Vd2ProtocolError("Existing phase")

    protocol = Vd2MeasurementProtocol(
        lambda: pytest.fail("Hardware must not be accessed"), artifact_preflight=reject
    )
    with pytest.raises(Vd2ProtocolError, match="Existing phase"):
        protocol.start(phase="BRUIT", frames_per_his=1, run_name="existing")
    assert protocol.status()["status"] == "idle"


def test_manifest_is_prepared_before_hardware_and_snapshots_surround_acquisition():
    events = []
    proxy = FakeProxy()
    class Journal:
        def prepare(self, request):
            assert proxy.calls == []
            assert request.sample_description == 'Water, 10 mm'
            return {'artifact_id': 'phase', 'manifest_path': 'project.json'}
        def record(self, request, identity, status, **details):
            assert identity == 'phase'
            events.append((status, details))
    protocol = Vd2MeasurementProtocol(lambda: proxy, artifact_journal=Journal(),
        snapshot_reader=lambda _: {'exposure': '10 ms'})
    protocol.start(phase='BASE', frames_per_his=3, run_name='sample 1', sample_description='Water, 10 mm')
    protocol.wait(2)
    assert protocol.status()['status'] == 'completed'
    assert [status for status, _ in events] == ['acquiring', 'saved', 'completed']
    assert events[0][1]['machine_before'] == {'exposure': '10 ms'}
    assert events[-1][1]['machine_after'] == {'exposure': '10 ms'}


def test_manifest_failure_does_not_replay_acquisition():
    proxy = FakeProxy()
    class Journal:
        def prepare(self, request): return {'artifact_id': 'phase'}
        def record(self, request, identity, status, **details):
            if status == 'completed': raise OSError('Manifest disk full')
    protocol = Vd2MeasurementProtocol(lambda: proxy, artifact_journal=Journal())
    protocol.start(phase='BASE', frames_per_his=3, run_name='sample')
    protocol.wait(2)
    assert protocol.status()['status'] == 'failed'
    assert protocol.status()['error'] == 'Manifest disk full'
    assert proxy.calls.count(('command', 'StartSequence', None)) == 1


def test_source_retirement_runs_only_after_durable_completed_manifest():
    events = []
    class Journal:
        def prepare(self, request): return {'artifact_id': 'phase'}
        def record(self, request, identity, status, **details): events.append(status)
        def record_retention(self, request, identity, cleanup):
            assert cleanup['source_his_retained'] is False
            events.append('retention recorded')
    def finalize(request, conversion):
        assert events[-1] == 'completed'
        events.append('his removed')
        return {'source_his_retained': False, 'source_his_cleanup_status': 'removed'}
    protocol = Vd2MeasurementProtocol(FakeProxy, artifact_journal=Journal(),
        sequence_processor=lambda _: {'lossless_verified': True}, artifact_finalizer=finalize)
    protocol.start(phase='BASE', frames_per_his=3, run_name='sample')
    protocol.wait(2)
    assert protocol.status()['status'] == 'completed'
    assert protocol.status()['source_his_retained'] is False
    assert events[-3:] == ['completed', 'his removed', 'retention recorded']


def test_manifest_failure_preserves_source_before_retirement():
    class Journal:
        def prepare(self, request): return {'artifact_id': 'phase'}
        def record(self, request, identity, status, **details):
            if status == 'completed': raise OSError('Manifest unavailable')
    protocol = Vd2MeasurementProtocol(FakeProxy, artifact_journal=Journal(),
        artifact_finalizer=lambda *_: pytest.fail('HIS removal must not run'))
    protocol.start(phase='BASE', frames_per_his=3, run_name='sample')
    protocol.wait(2)
    assert protocol.status()['status'] == 'failed'
    assert protocol.status()['error'] == 'Manifest unavailable'
