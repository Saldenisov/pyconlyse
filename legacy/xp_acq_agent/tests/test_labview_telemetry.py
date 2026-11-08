import copy
from importlib.machinery import SourceFileLoader
import os
import shutil
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch

from elyse_agent.errors import CommandError
from elyse_agent.labview_telemetry import LabviewTelemetryStore
from elyse_agent.protocol import recv_message, send_message
from main import build_agent
from main import main as agent_main


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def packet(sequence=0):
    return dict(session_id="test-session", publication="C1NI6071E", sequence=sequence,
                source_seconds_1904=3870000000.25, producer_kind="fixture",
                data=[1.5, None, -0.2], error=dict(status=False, code=0, source=""))


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.now = [10.0]
        self.store = LabviewTelemetryStore("test-session", clock=lambda: self.now[0])

    def test_empty_is_missing_not_synthetic(self):
        result = self.store.snapshot()
        self.assertEqual(result["publications"], {})
        self.assertEqual(len(result["missing_publications"]), 8)
        self.assertFalse(result["physical_measurements_verified"])

    def test_duplicate_does_not_refresh_age(self):
        params = packet()
        self.store.ingest(params, "127.0.0.1:1")
        self.now[0] += 3.0
        self.assertTrue(self.store.ingest(params, "127.0.0.1:2")["duplicate"])
        result = self.store.snapshot()["publications"]["C1NI6071E"]
        self.assertEqual(result["age_seconds"], 3.0)
        self.assertTrue(result["stale"])
        self.assertEqual(result["source_seconds_1904"], params["source_seconds_1904"])

    def test_session_sequence_and_remote_publication_rejected(self):
        self.store.ingest(packet(2), "127.0.0.1:1")
        for invalid in (packet(1), dict(packet(2), data=[5]),
                        dict(packet(3), session_id="other"),
                        dict(packet(3), publication="C6_AO_WRITE")):
            with self.assertRaises(CommandError):
                self.store.ingest(invalid, "127.0.0.1:1")
        for peer in (None, "10.20.30.2:1234", "127.0.0.10:1234", "127.0.0.1.evil:1"):
            with self.assertRaises(CommandError):
                self.store.ingest(packet(3), peer)

    def test_payload_schema_and_limits(self):
        invalid_packets = [dict(packet(), sequence=True), dict(packet(), source_seconds_1904=True),
                           dict(packet(), source_seconds_1904=10 ** 1000),
                           dict(packet(), data=[float("nan")]),
                           dict(packet(), data=[float("inf")]),
                           dict(packet(), data=list(range(9000))),
                           dict(packet(), error=dict(status="false", code=0, source="")),
                           dict(packet(), extra="write")]
        deep = 1
        for unused in range(14):
            deep = [deep]
        invalid_packets.append(dict(packet(), data=deep))
        for params in invalid_packets:
            with self.assertRaises(CommandError):
                self.store.ingest(params, "127.0.0.1:1")
        self.assertEqual(self.store.snapshot()["publications"], {})

    def test_error_and_mutable_values_preserved_without_certifying_measurement(self):
        params = packet()
        params["error"] = dict(status=True, code=-200279, source="DAQ read fixture")
        original = copy.deepcopy(params)
        self.store.ingest(params, "127.0.0.1:1")
        params["data"][0] = 99
        result = self.store.snapshot()["publications"]["C1NI6071E"]
        self.assertEqual(result["data"], original["data"])
        self.assertTrue(result["producer_reports_error"])
        result["data"][0] = 98
        self.assertEqual(self.store.snapshot()["publications"]["C1NI6071E"]["data"], original["data"])


class TelemetryServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = dict(agent_name="telemetry-test", mode="discover_only", bind_host="127.0.0.1",
                           command_port=0, max_frame_bytes=1048576, socket_timeout_seconds=2.0,
                           data_path=os.path.join(ROOT, "data"), audit_path=os.path.join(self.temp_dir, "audit.jsonl"),
                           allow_input_task_creation=True, allow_hardware_writes=False)
        self.server, unused = build_agent(self.config, telemetry_options=dict(session_id="test-session"))

    def tearDown(self):
        self.server.server_close()
        shutil.rmtree(self.temp_dir)

    def request(self, command, params=None, request_id="repeated-reader"):
        return dict(id=request_id, command=command, params=params or {})

    def test_mode_conflicts_and_bind_constraints(self):
        with self.assertRaises(ValueError):
            build_agent(self.config, supervision_options={"enabled": True},
                        telemetry_options=dict(session_id="test-session"))
        with self.assertRaises(ValueError):
            build_agent(dict(self.config, bind_host="10.20.30.10"),
                        telemetry_options=dict(session_id="test-session"))
        # Validate wildcard configuration without opening a non-loopback
        # socket or triggering Windows Firewall during a software-only test.
        with patch("main.AgentServer") as server_class:
            build_agent(dict(self.config, bind_host="0.0.0.0"),
                        telemetry_options=dict(session_id="test-session"))
            self.assertEqual(server_class.call_args[0][0][0], "0.0.0.0")
            self.assertIsNone(server_class.call_args[0][1].backend)

    def test_cli_conflicts_fail_before_startup(self):
        config_path = os.path.join(ROOT, "config.labview-telemetry.json")
        for incompatible in ("--discover-once", "--initialize-simulation", "--supervision"):
            with self.assertRaises(ValueError):
                agent_main(["--config", config_path, "--labview-telemetry", incompatible])
        with self.assertRaises(ValueError):
            agent_main(["--config", config_path, "--bind", "0.0.0.0"])

    def test_legacy_configured_wildcard_is_not_changed_by_new_cli_guard(self):
        with patch("main.AgentServer") as server_class:
            build_agent(dict(self.config, mode="simulation", bind_host="0.0.0.0"))
            self.assertEqual(server_class.call_args[0][0][0], "0.0.0.0")
            self.assertIsNotNone(server_class.call_args[0][1].backend)

    def test_gui_launcher_import_does_not_start_and_forces_safe_mode(self):
        loader = SourceFileLoader("telemetry_receiver_test", os.path.join(ROOT, "telemetry_receiver.pyw"))
        with patch("main.build_agent") as builder:
            launcher = loader.load_module()
            self.assertFalse(builder.called)
        with patch.object(launcher, "load_config", return_value=dict(self.config, bind_host="0.0.0.0",
                          command_port=8765, allow_hardware_writes=True)), \
                patch.object(launcher, "build_agent", return_value=(None, None)) as builder:
            launcher.create_receiver()
            supplied = builder.call_args[0][0]
            self.assertEqual((supplied["bind_host"], supplied["command_port"]), ("127.0.0.1", 8766))
            self.assertFalse(supplied["allow_input_task_creation"])
            self.assertFalse(supplied["allow_hardware_writes"])
            self.assertEqual(builder.call_args[1]["telemetry_options"]["session_id"], "acq-copy-20261012")

    def test_no_backend_and_all_operational_commands_blocked(self):
        router = self.server.router
        self.assertIsNone(router.backend)
        for command in router.COMMANDS:
            if command in ("ping", "get_status", "get_capabilities"):
                continue
            result = router.dispatch(self.request(command), peer="127.0.0.1:1")
            self.assertFalse(result["ok"], command)
        caps = router.dispatch(self.request("get_capabilities", request_id="caps"))
        self.assertFalse(caps["result"]["hardware_writes"])
        self.assertNotIn("initialize", caps["result"]["commands"])
        status = router.dispatch(self.request("get_status", request_id="status"))["result"]
        self.assertEqual(status["mode"], "labview_telemetry")
        self.assertFalse(status["input_task_creation_allowed"])

    def test_fresh_reads_and_peer_check_bypass_request_cache(self):
        router = self.server.router
        req = self.request("ingest_labview_telemetry", packet(), "same-ingest-id")
        self.assertTrue(router.dispatch(req, peer="127.0.0.1:1")["ok"])
        self.assertFalse(router.dispatch(req, peer="10.20.30.2:1")["ok"])
        first = router.dispatch(self.request("get_labview_telemetry"))
        router.dispatch(self.request("ingest_labview_telemetry", packet(1)), peer="127.0.0.1:1")
        second = router.dispatch(self.request("get_labview_telemetry"))
        self.assertEqual(first["result"]["publications"]["C1NI6071E"]["sequence"], 0)
        self.assertEqual(second["result"]["publications"]["C1NI6071E"]["sequence"], 1)

    def test_existing_tcp_json_protocol_fixture_round_trip(self):
        thread = threading.Thread(target=self.server.serve_forever)
        thread.daemon = True
        thread.start()
        try:
            sock = socket.create_connection(self.server.server_address, timeout=2.0)
            try:
                send_message(sock, self.request("ingest_labview_telemetry", packet(), "fixture-0"))
                accepted = recv_message(sock, 1048576)
                send_message(sock, self.request("get_labview_telemetry"))
                snapshot = recv_message(sock, 1048576)
            finally:
                sock.close()
            self.assertTrue(accepted["ok"])
            result = snapshot["result"]
            self.assertEqual(result["publications"]["C1NI6071E"]["data"], packet()["data"])
            self.assertEqual(result["publications"]["C1NI6071E"]["producer_kind"], "fixture")
            self.assertFalse(result["hardware_writes"])
        finally:
            self.server.shutdown()
            thread.join(2.0)


if __name__ == "__main__":
    unittest.main()
