"""Source arbitration with synthetic VI XML and fake NI ownership only."""
import copy
import socket
import struct
import threading

import pytest

from legacy.xp_acq_control.elyse_agent.acquisition_control_runtime import AcquisitionControlRuntime
from legacy.xp_acq_control.elyse_agent.dual_mode_telemetry import DualModeTelemetryPublisher, BRIDGE_SITE, NATIVE_SITE
from legacy.xp_acq_control.elyse_agent.protocol import recv_message
from DeviceServers.control.elyse_acq.telemetry_sink import TelemetrySinkStore, TelemetrySinkServer
from tests.unit.test_acq_standard_telemetry import KEY, signed, state


def xml():
    from legacy.xp_acq_control.elyse_agent.shared_state import BANKS
    rows = []
    for index, bank in enumerate(BANKS):
        rows.append('<Cluster><Name></Name><NumElts>3</NumElts>'
            '<String><Name>bank</Name><Val>{0}</Val></String>'
            '<LvVariant><Name>value</Name><DBL><Name>fixture</Name><Val>{1}</Val></DBL></LvVariant>'
            '<Cluster><Name>error</Name><NumElts>3</NumElts>'
            '<Boolean><Name>status</Name><Val>0</Val></Boolean>'
            '<I32><Name>code</Name><Val>0</Val></I32>'
            '<String><Name>source</Name><Val></Val></String></Cluster></Cluster>'.format(bank, index + .25))
    return ('<LvVariant><Name></Name><Array><Name></Name><Dimsize>27</Dimsize>'
            + ''.join(rows) + '</Array></LvVariant>').encode('ascii')


@pytest.fixture
def pair():
    factory_calls, clock = [], [100.]
    runtime = AcquisitionControlRuntime(lambda: factory_calls.append(True))
    publisher = DualModeTelemetryPublisher(runtime, ('127.0.0.1', 1), KEY, clock=lambda: clock[0])
    runtime.telemetry_publisher = publisher
    yield runtime, publisher, clock, factory_calls
    publisher.close()
    assert not factory_calls


def packet(publisher):
    return copy.deepcopy(publisher.outbox.peek()['packet'])


def ack(publisher):
    body = publisher.outbox.peek()
    publisher.outbox.acknowledge(body['relay_id'], body['message_id'])


def test_idle_receives_all_vi_banks_without_creating_backend_or_retimestamping(pair):
    runtime, publisher, clock, calls = pair
    assert publisher.publish_once()
    assert all(row['data'] is None for row in packet(publisher)['data']['banks'])
    ack(publisher)
    assert publisher.ingest(xml(), '127.0.0.1')['accepted']
    observed = packet(publisher)
    assert observed['producer_kind'] == 'copied_acquisition'
    assert observed['source_site'] == BRIDGE_SITE
    assert [row['data'] for row in observed['data']['banks']] == [index + .25 for index in range(27)]
    assert not publisher.publish_once()
    assert runtime.snapshot()['resource_count'] == 0 and not calls


def test_recent_vi_blocks_initialize_before_backend_factory_is_called(pair):
    runtime, publisher, clock, calls = pair
    publisher.ingest(xml(), '127.0.0.1')
    with pytest.raises(RuntimeError, match='LabVIEW telemetry is still arriving'):
        runtime.initialize(startup_confirmed=True)
    assert runtime.snapshot()['state'] == 'IDLE' and not calls
    clock[0] += 2.1
    # No owner thread is started: tests the actual acceptance fence only.
    runtime.initialize(startup_confirmed=True)
    assert runtime.snapshot()['state'] == 'INITIALIZING' and not calls
    with pytest.raises(ValueError, match='INGRESS_DISABLED'):
        publisher.ingest(xml(), '127.0.0.1')


@pytest.mark.parametrize('status', ['INITIALIZING', 'RUNNING', 'EXECUTING', 'DEINITIALIZING', 'FAULT', 'RECOVERY_REQUIRED', 'STOPPED'])
def test_vi_admission_is_closed_in_every_non_idle_state(pair, status):
    runtime, publisher, clock, calls = pair
    runtime._state = status
    with pytest.raises(ValueError, match='INGRESS_DISABLED'):
        publisher.ingest(xml(), '127.0.0.1')
    assert publisher.vi_accepted == 0 and publisher.outbox.status()['pending'] == 0


def test_deinitialization_waits_for_new_vi_image_never_revives_cached_data(pair):
    runtime, publisher, clock, calls = pair
    publisher.ingest(xml(), '127.0.0.1'); ack(publisher)
    runtime._state, runtime._state_revision = 'RUNNING', 1
    runtime._latest = state()['latest']
    runtime._received_at = runtime._clock()
    assert publisher.publish_once()
    assert packet(publisher)['source_site'] == NATIVE_SITE
    assert packet(publisher)['data']['banks'][0]['data'] == [123.] * 64
    ack(publisher)
    runtime._state, runtime._state_revision = 'IDLE', 2
    assert publisher.publish_once()
    waiting = packet(publisher)
    assert waiting['producer_kind'] == 'copied_acquisition'
    assert all(row['data'] is None for row in waiting['data']['banks'])
    assert publisher.last_vi_receipt is None
    ack(publisher)
    assert not publisher.publish_once()
    publisher.ingest(xml(), '127.0.0.1')
    assert packet(publisher)['data']['banks'][0]['data'] == .25


def test_receiver_changes_source_atomically_inside_one_boot_and_relay(pair):
    runtime, publisher, clock, calls = pair
    store = TelemetrySinkStore(KEY, permitted_producer_kind='unified_acquisition')
    publisher.ingest(xml(), '127.0.0.1')
    first = publisher.outbox.peek()
    store.accept(signed(first['packet'], relay=first['relay_id'], message=first['message_id']))
    assert store.snapshot()['source'] == 'copied_labview_telemetry'
    ack(publisher)
    runtime._state, runtime._state_revision = 'RUNNING', 1
    runtime._latest, runtime._received_at = state()['latest'], runtime._clock()
    publisher.publish_once()
    second = publisher.outbox.peek()
    store.accept(signed(second['packet'], relay=second['relay_id'], message=second['message_id']))
    native = store.snapshot()
    assert native['source'] == 'python_daqmx_acquisition'
    assert all(row['producer_kind'] == 'python_acquisition' for row in native['publications'].values())
    # Earlier VI receipt cannot re-enter after the new source.
    with pytest.raises(ValueError):
        store.accept(signed(first['packet'], relay=first['relay_id'], message=first['message_id']))
    with pytest.raises(ValueError, match='competing relay'):
        store.accept(signed(second['packet']))
    old_bridge = copy.deepcopy(first['packet']); old_bridge['source_site'] = 'old_standalone_bridge'
    with pytest.raises(ValueError, match='mode-arbitrated'):
        store.accept(signed(old_bridge))


def test_pending_inflight_vi_is_not_overtaken_or_relabelled_at_mode_change(pair):
    runtime, publisher, clock, calls = pair
    publisher.ingest(xml(), '127.0.0.1')
    first = publisher.outbox.peek()
    runtime._state, runtime._state_revision = 'INITIALIZING', 1
    publisher.publish_once()
    assert publisher.outbox.peek()['packet'] == first['packet']  # immutable in-flight receipt
    assert publisher.outbox.peek()['packet']['producer_kind'] == 'copied_acquisition'
    ack(publisher)
    assert packet(publisher)['producer_kind'] == 'python_acquisition'
    assert all(row['data'] is None for row in packet(publisher)['data']['banks'])


def test_loopback_xml_and_signed_everest_ack_with_one_publisher(pair):
    runtime, publisher, clock, calls = pair
    store = TelemetrySinkStore(KEY, permitted_producer_kind='unified_acquisition')
    sink = TelemetrySinkServer(('127.0.0.1', 0), store, permitted_peers=('127.0.0.1',))
    worker = threading.Thread(target=lambda: sink.serve_forever(poll_interval=.02), daemon=True)
    worker.start()
    publisher.relay.address = sink.server_address
    publisher.ingress_address = ('127.0.0.1', 0)
    try:
        publisher.start()
        with socket.create_connection(publisher.server.server_address, timeout=2) as connection:
            connection.sendall(struct.pack('!I', len(xml())) + xml())
            assert recv_message(connection, 1048576)['result']['bank_count'] == 27
        import time
        until = time.monotonic() + 4
        while time.monotonic() < until and not store.snapshot()['publications'].get('C1NI6071E', {}).get('data'):
            time.sleep(.02)
        assert store.snapshot()['publications']['C1NI6071E']['data'] == .25
        assert publisher.status()['everest_acknowledged'] >= 1
    finally:
        publisher.close(); sink.shutdown(); sink.server_close(); worker.join(3); store.close()


def test_busy_loopback_port_fails_closed_without_starting_a_second_bridge(pair):
    runtime, publisher, clock, calls = pair
    with socket.socket() as occupied:
        occupied.bind(('127.0.0.1', 0)); occupied.listen(1)
        publisher.ingress_address = occupied.getsockname()
        with pytest.raises(OSError): publisher.start()
    assert publisher.worker is None and runtime.snapshot()['resource_count'] == 0


def test_native_fault_with_retained_ownership_does_not_fall_back_to_vi_or_disable_stop(pair):
    runtime, publisher, clock, calls = pair
    from types import SimpleNamespace
    runtime._state = 'FAULT'
    runtime._error = 'fake native read failure'
    runtime._backend = SimpleNamespace(resource_count=1, control_profile='extended_ht_stop')
    publisher.publish_once()
    assert publisher.status()['source_mode'] == 'PYTHON_NATIVE'
    assert packet(publisher)['producer_kind'] == 'python_acquisition'
    assert all(row['data'] is None for row in packet(publisher)['data']['banks'])
    with pytest.raises(ValueError): publisher.ingest(xml(), '127.0.0.1')
    runtime._backend = None


def test_xml_decoded_concurrently_with_initialize_cannot_enter_after_owner_fence(pair, monkeypatch):
    runtime, publisher, clock, calls = pair
    from legacy.xp_acq_control.elyse_agent import dual_mode_telemetry as module
    original, entered, proceed, failures = module.decode_snapshot_xml, threading.Event(), threading.Event(), []
    def delayed(raw, encoding):
        result = original(raw, encoding)
        entered.set()
        assert proceed.wait(3)
        return result
    def ingest():
        try: publisher.ingest(xml(), '127.0.0.1')
        except ValueError as error: failures.append(str(error))
    monkeypatch.setattr(module, 'decode_snapshot_xml', delayed)
    worker = threading.Thread(target=ingest)
    worker.start()
    try:
        assert entered.wait(3)
        runtime.initialize(startup_confirmed=True)  # Admission only; no owner thread or real backend.
    finally:
        proceed.set(); worker.join(3)
    assert failures == ['VI_INGRESS_DISABLED_WHILE_PYTHON_OWNS_OR_TRANSITIONS']
    assert publisher.vi_accepted == 0 and not calls


def test_recorder_journals_both_source_switches_without_pooling_values(pair):
    runtime, publisher, clock, calls = pair
    from tests.unit.test_acq_telemetry_hdf5_recorder import recorder
    observer = recorder.Observations()
    store = TelemetrySinkStore(KEY, permitted_producer_kind='unified_acquisition')
    def deliver():
        body = publisher.outbox.peek()
        store.accept(signed(body['packet'], relay=body['relay_id'], message=body['message_id']))
        result = observer.accept(store.snapshot())
        ack(publisher)
        return result
    publisher.ingest(xml(), '127.0.0.1'); deliver()
    runtime._state, runtime._state_revision = 'RUNNING', 1
    runtime._latest, runtime._received_at = state()['latest'], runtime._clock()
    publisher.publish_once()
    unused, events = deliver()
    assert events[0]['event'] == 'telemetry_producer_changed'
    assert observer.summary()['numeric_statistics']['C1NI6071E/0']['mean'] == 123.
    runtime._state, runtime._state_revision = 'IDLE', 2
    publisher.publish_once(); deliver()
    assert observer.producer_changes == 2
    assert not observer.numeric  # Null VI-waiting boundary is not a zero measurement.
