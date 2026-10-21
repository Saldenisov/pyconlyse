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
    import time
    factory_calls = []
    cold = AcquisitionControlRuntime(lambda: factory_calls.append(True))
    assert cold.snapshot()["state"] == "IDLE" and cold.snapshot()["resource_count"] == 0
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
        def snapshot(self):
            banks = {}
            for name, (source, kind, device, count, field, scalar) in INPUTS.items():
                record = dict(kind=kind, device=device, values=[False if scalar == "Boolean" else 1.] * count)
                if scalar == "DBL": record[field] = [123.] * count
                banks[source] = record
            return dict(session_id="a" * 32, sequence=1, state_revision=2, state="RUNNING", stale=False,
                age_seconds=.2, error="", latest=dict(source="python_daqmx_acquisition", simulated=False, banks=banks))
    server = socketserver.TCPServer(("127.0.0.1", 0), Sink)
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=.02))
    thread.daemon = True; thread.start()
    publisher = StandardTelemetryPublisher(FakeRuntime(), server.server_address, key)
    dual = None
    try:
        assert publisher.publish_once() and publisher.relay.send_once()
        packet = received[0]["packet"]
        assert len(packet["data"]["banks"]) == 27
        assert publisher.status()["everest_acknowledged"] == 1
        assert not publisher.publish_once()
        assert not factory_calls and "nidaqmx" not in sys.modules
        dual = DualModeTelemetryPublisher(cold, server.server_address, key, ingress_address=("127.0.0.1", 0))
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
        hashes_ok = all(hashlib.sha256(open(os.path.join(root, item["path"]), "rb").read()).hexdigest()
            == item["sha256"] for item in json.load(open(os.path.join(root, "manifest.json")))["files"])
        assert hashes_ok
        print(json.dumps(dict(result="PASS", python=sys.version.split()[0],
            bank_count=27, signed_loopback_ack=True, dual_mode_bridge_and_initialize_fence=True,
            build_id=control_identity(root)["build_id"],
            manifest_hashes_verified=hashes_ok,
            cards_initialized=False, hardware_commands_sent=False, live_everest_contacted=False)))
    finally:
        if dual is not None: dual.close()
        publisher.close(); server.shutdown(); server.server_close(); thread.join(3)


if __name__ == "__main__":
    main()
