"""Driver-free cold/package and signed loopback check; Python 3.4 compatible."""
import hashlib
import hmac
import json
import os
import socketserver
import sys
import threading


def main():
    import ctypes
    def refuse_native(*args, **kwargs):
        raise AssertionError("Native library loading forbidden by cold acceptance check")
    ctypes.CDLL = ctypes.WinDLL = refuse_native
    root = os.path.abspath(sys.argv[1])
    sys.path.insert(0, root)
    from elyse_agent.acquisition_control_runtime import AcquisitionControlRuntime, control_identity
    from elyse_agent.native_telemetry import INPUTS, standard_packet, validate_standard_packet, StandardTelemetryPublisher
    from elyse_agent.telemetry_relay import sign, DeadlineSocket, MAX_RELAY_FRAME
    from elyse_agent.protocol import recv_message, send_message
    from elyse_agent.dual_mode_telemetry import DualModeTelemetryPublisher
    from elyse_agent.shared_state import BANKS, validate_snapshot_packet
    from elyse_agent.command_dispatch import CommandDispatcher
    from elyse_agent.command_protocol import OPERATIONS
    from elyse_agent.acquisition_beamline import BEAMLINE_OPERATIONS, SOURCE_PATHS
    from elyse_agent.control_policy import require_ht_value
    import time
    factory_calls = []
    cold = AcquisitionControlRuntime(lambda: factory_calls.append(True))
    assert cold.snapshot()["state"] == "IDLE" and cold.snapshot()["resource_count"] == 0
    assert len(OPERATIONS) == 23 and set(BEAMLINE_OPERATIONS).issubset(OPERATIONS)
    assert [SOURCE_PATHS[name]["field"] for name in BEAMLINE_OPERATIONS] == [23, 25, 22, 26]
    assert [SOURCE_PATHS[name]["nominal_wait_seconds"] for name in BEAMLINE_OPERATIONS] == [.5, .5, 1., 1.]
    assert not cold.snapshot()["stage_execution"]["beamline_commissioned"]
    sequence = dict(owner_current=True, command_known=True, current_command_kv=0.,
                    supply_sequence_completed=False, pulses_sequence_completed=False)
    try:
        require_ht_value(sequence, 1.)
    except RuntimeError as error:
        assert "HT_INCREASE_REQUIRES" in str(error)
    else:
        raise AssertionError("Unstarted supply/pulses must block HT increase")
    sequence.update(supply_sequence_completed=True, pulses_sequence_completed=True)
    require_ht_value(sequence, 1.)  # RAM-only policy, never driver execution.
    assert not factory_calls and "nidaqmx" not in sys.modules
    key = b"test-only-cold-loopback-key-000000000000000"
    received = []
    class Sink(socketserver.BaseRequestHandler):
        def handle(self):
            connection = DeadlineSocket(self.request, time.monotonic() + 2)
            request = recv_message(connection, MAX_RELAY_FRAME)
            signed = dict(body=request["body"], nonce=request["nonce"])
            assert hmac.compare_digest(request["signature"], sign(key, "ACQ-TELEMETRY-REQUEST-1", signed))
            packet = request["body"]["packet"]
            if packet["producer_kind"] == "python_acquisition":
                validate_standard_packet(packet)
            else:
                assert packet["source_site"] == "xp_unified_labview_bridge_27_banks"
                validate_snapshot_packet(packet)
            received.append(request["body"])
            response = dict(body=dict(accepted=True, duplicate=False, relay_id=request["body"]["relay_id"],
                                     message_id=request["body"]["message_id"], storage_mode="ram_latest", durable=False),
                            nonce=request["nonce"])
            response["signature"] = sign(key, "ACQ-TELEMETRY-ACK-1", response)
            send_message(connection, response, MAX_RELAY_FRAME)
    class FakeRuntime(object):
        status_only = False
        def snapshot(self):
            banks = {}
            for name, (source, kind, device, count, field, scalar) in INPUTS.items():
                record = dict(kind=kind, device=device, values=[False if scalar == "Boolean" else 1.] * count)
                if scalar == "DBL": record[field] = [123.] * count
                banks[source] = record
            result = dict(session_id="a" * 32, sequence=1, state_revision=2, state="RUNNING", stale=False,
                age_seconds=.2, error="", latest=dict(source="python_daqmx_acquisition", simulated=False, banks=banks))
            if self.status_only:
                eps, dps = [False] * 77, [False] * 29
                eps[8], dps[2] = True, True
                result.update(state="EXECUTING", stale=True, age_seconds=3., measurement_current=False,
                    software_state_current=True, software_state_sequence=1, software_state_age_seconds=.1,
                    software_state=dict(source="python_acquisition_software_memory", simulated=False,
                        session_id=result["session_id"], sequence=1, source_revision=1,
                        local_banks=dict(EPS=eps, DPS=dps), hardware_acknowledged=False,
                        psp_delivery_acknowledged=False))
            return result
    server = socketserver.TCPServer(("127.0.0.1", 0), Sink)
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=.02))
    thread.daemon = True; thread.start()
    publisher = StandardTelemetryPublisher(FakeRuntime(), server.server_address, key)
    dual = dispatcher = None
    try:
        assert publisher.publish_once() and publisher.relay.send_once()
        packet = received[0]["packet"]
        assert len(packet["data"]["banks"]) == 27
        assert publisher.status()["everest_acknowledged"] == 1
        assert not publisher.publish_once()
        publisher.runtime.status_only = True
        assert publisher.publish_once() and publisher.relay.send_once()
        software_banks = {row["publication"]: row for row in received[-1]["packet"]["data"]["banks"]}
        assert software_banks["EPS"]["data"][8] is True and len(software_banks["EPS"]["data"]) == 77
        assert software_banks["DPS"]["data"][2] is True and len(software_banks["DPS"]["data"]) == 29
        assert software_banks["C1NI6071E"]["data"] is None
        assert not factory_calls and "nidaqmx" not in sys.modules
        bridge_clock = [time.monotonic()]
        dual = DualModeTelemetryPublisher(cold, server.server_address, key,
            ingress_address=("127.0.0.1", 0), clock=lambda: bridge_clock[0])
        cold.telemetry_publisher = dual
        rows = []
        for name in BANKS:
            rows.append('<Cluster><Name></Name><NumElts>3</NumElts>'
                '<String><Name>bank</Name><Val>{0}</Val></String>'
                '<LvVariant><Name>value</Name><DBL><Name>fixture</Name><Val>1.25</Val></DBL></LvVariant>'
                '<Cluster><Name>error</Name><NumElts>3</NumElts>'
                '<Boolean><Name>status</Name><Val>0</Val></Boolean>'
                '<I32><Name>code</Name><Val>0</Val></I32>'
                '<String><Name>source</Name><Val></Val></String></Cluster></Cluster>'.format(name))
        xml = ('<LvVariant><Name></Name><Array><Name></Name><Dimsize>27</Dimsize>'
               + ''.join(rows) + '</Array></LvVariant>').encode('ascii')
        dual.ingest(xml, "127.0.0.1")
        assert dual.relay.send_once()
        assert received[-1]["packet"]["producer_kind"] == "copied_acquisition"
        assert len(received[-1]["packet"]["data"]["banks"]) == 27
        try:
            cold.initialize(startup_confirmed=True)
        except RuntimeError as error:
            assert "LabVIEW telemetry is still arriving" in str(error)
        else:
            raise AssertionError("Recent VI traffic must block Initialize")
        assert not factory_calls and cold.snapshot()["resource_count"] == 0
        # Telemetry must not enter full metadata, command ledger or journal.
        def refuse_metadata():
            raise AssertionError("Telemetry entered full metadata snapshot")
        cold.snapshot = refuse_metadata
        entered, release = threading.Event(), threading.Event()
        def hold_owner():
            with cold._lock:
                entered.set()
                assert release.wait(3)
        holder = threading.Thread(target=hold_owner)
        holder.start()
        try:
            assert entered.wait(3)
            started = time.monotonic()
            vi_sequence, vi_receipt = dual.sequence, dual.last_vi_receipt
            assert not dual.publish_once() and time.monotonic() - started < .5
            assert dual.sequence == vi_sequence and dual.last_vi_receipt == vi_receipt
            assert dual.outbox.status()["pending"] == 0  # No replay/freshness extension.
            assert not dual.status()["owner_state_current"]
            bridge_clock[0] += 2  # Existing Initialize quiet boundary, not a new permit.
            started = time.monotonic()
            assert dual.publish_once() and time.monotonic() - started < .5
            assert dual.relay.send_once()
            assert not dual.status()["owner_state_current"]
            assert all(row["data"] is None for row in received[-1]["packet"]["data"]["banks"])
        finally:
            release.set(); holder.join(3)
        class AdmissionFixture(object):
            def submit(self, request, lease):
                assert threading.current_thread().name == "ACQ-command-admission"
                return dict(outcome="REJECTED", hardware_acknowledged=False)
        dispatcher = CommandDispatcher(AdmissionFixture())
        dispatcher.start()
        receipt = dispatcher.submit(dict(command_id="b" * 32, session_id="a" * 32,
            expected_revision=0, operation="chauffage.stop", operator_confirmed=True, value=None), None)
        assert receipt["outcome"] == "REJECTED" and not factory_calls
        hashes_ok = all(hashlib.sha256(open(os.path.join(root, item["path"]), "rb").read()).hexdigest()
            == item["sha256"] for item in json.load(open(os.path.join(root, "manifest.json")))["files"])
        assert hashes_ok
        print(json.dumps(dict(result="PASS", python=sys.version.split()[0],
            bank_count=27, signed_loopback_ack=True, dual_mode_bridge_and_initialize_fence=True,
            independent_command_admission=True, non_waiting_telemetry_projection=True,
            eps_dps_during_commands_without_measurement_refresh=True,
            recent_vi_contention_does_not_erase_or_replay=True,
            named_operation_count=len(OPERATIONS), beamline_default_disabled=True,
            source_beamline_pulse_metadata=True, ht_software_order_gate=True,
            build_id=control_identity(root)["build_id"],
            manifest_hashes_verified=hashes_ok,
            cards_initialized=False, hardware_commands_sent=False, live_everest_contacted=False)))
    finally:
        if dispatcher is not None: dispatcher.close()
        if dual is not None: dual.close()
        publisher.close(); server.shutdown(); server.server_close(); thread.join(3)


if __name__ == "__main__":
    main()
