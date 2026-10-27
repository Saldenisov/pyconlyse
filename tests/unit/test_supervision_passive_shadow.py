"""Pinned passive policy: private loopback/RAM only, no NI, live VI or children."""
import copy
import hmac
import json
import os
import socket
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import uuid
from unittest.mock import Mock

from legacy.xp_acq_control.elyse_agent.supervision_runtime import SupervisionRuntime
from legacy.xp_acq_control.elyse_agent.supervision_gui import (
    BUTTON_LABELS, SupervisionWindow, default_supervision_configuration, validate_supervision_configuration)
from legacy.xp_acq_control.elyse_agent.acquisition_http import request_signature, response_signature
from legacy.xp_acq_control.elyse_agent.application_view import ApplicationView
from legacy.xp_acq_control.elyse_agent.command_http import ControlHTTPServer
from legacy.xp_acq_control.elyse_agent.command_protocol import command_signature
from tests.unit.test_orchestrator_release_install import (
    installer, source_fixture, runtime_fixture, site_fixture, refresh_site, json_file)


IDENTITY = dict(runtime_protocol_version=2, session_id="a" * 32, build_id="b" * 64)


class PassiveShadowTests(unittest.TestCase):
    def runtime(self, **options):
        options.setdefault("vi_passive_shadow", True)
        return SupervisionRuntime(identity=IDENTITY, **options)

    def test_true_is_pinned_independent_of_missing_vi_and_silence_duration(self):
        now, constructed = [0.], []
        before = set(name for name in sys.modules if name in ("nidaqmx", "PyDAQmx"))
        runtime = self.runtime(remote_enabled=True, counter_timing_controls_verified=True,
            clock=lambda: now[0], endpoint_factory=lambda **values: constructed.append(values))
        runtime.start()
        try:
            for seconds in (0., 2.1, 3600., 10 ** 6):
                now[0] = seconds
                with self.assertRaisesRegex(RuntimeError, "VI_PASSIVE_SHADOW"):
                    runtime.initialize(startup_confirmed=True)
                with self.assertRaisesRegex(RuntimeError, "VI_PASSIVE_SHADOW"):
                    runtime._initialize_cards()
            self.assertEqual(constructed, [])
            self.assertEqual(runtime._owners, {})
            self.assertIsNone(runtime._pending)
            self.assertEqual(runtime._state, "IDLE")
            self.assertFalse(runtime.broker.enabled)
            self.assertIsNone(runtime.broker.issue_lease_nonblocking())
            self.assertEqual(set(name for name in sys.modules if name in ("nidaqmx", "PyDAQmx")), before)
            self.assertRaises(AttributeError, setattr, runtime, "vi_passive_shadow", False)
        finally:
            runtime.request_shutdown()
            self.assertTrue(runtime.join(3.))

    def test_configured_permissions_cannot_admit_commands_or_native_memory(self):
        runtime = self.runtime(remote_enabled=True, counter_timing_controls_verified=True)
        self.assertFalse(runtime.broker.enabled)
        for operation in ("counter_timing.set", "modulator.general.start", "arbitrary.write"):
            self.assertRaises(RuntimeError, runtime.dispatch_remote, operation, None)
        # The runtime gate remains authoritative if another internal component
        # accidentally changes this mutable transport flag.
        runtime.broker.enabled = True
        value = runtime.snapshot()
        self.assertEqual(value["owner_mode"], "VI_PASSIVE_SHADOW")
        self.assertTrue(value["vi_passive_shadow"])
        self.assertFalse(value["native_initialization_allowed"])
        self.assertFalse(value["control"]["enabled"])
        self.assertFalse(value["remote_setpoints_enabled"])
        self.assertFalse(value["stage_execution"]["remote_commands_enabled"])
        self.assertTrue(all(not row["enabled"] and row["reason"] == "VI_PASSIVE_SHADOW"
                            for row in value["control"]["capabilities"].values()))
        self.assertTrue(value["telemetry_bridge_mode"])
        self.assertEqual(value["resource_count"], 0)
        self.assertIsNone(runtime.video_frame_snapshot())
        self.assertIsNone(runtime.counter_memory_part())
        self.assertFalse(runtime.video_snapshot()["available"])

    def test_original_vi_exports_still_pass_while_native_takeover_remains_pinned_off(self):
        from legacy.xp_acq_control.elyse_agent.supervision_vi_telemetry import SupervisionTelemetryPublisher
        from tests.unit.test_supervision_vi_telemetry import xml
        now = [0.]
        runtime = self.runtime(clock=lambda: now[0])
        publisher = SupervisionTelemetryPublisher(runtime, ("127.0.0.1", 12345), b"r" * 32,
                                                   clock=lambda: now[0])
        runtime.telemetry_publisher = publisher
        try:
            receipt = publisher.ingest(xml(), "127.0.0.1")
            self.assertEqual(receipt["bank_count"], 27)
            value = publisher.outbox.peek()["packet"]
            self.assertEqual(value["owner"], "supervision")
            self.assertEqual(value["source_mode"], "LABVIEW_BRIDGE")
            self.assertEqual(len(value["counter_part"]["values"]), 16)
            publisher.assert_initialize_allowed = Mock(side_effect=AssertionError("Silence is not a permit"))
            now[0] = 3600.
            self.assertRaises(RuntimeError, runtime.initialize, True)
            publisher.assert_initialize_allowed.assert_not_called()
            self.assertEqual(runtime._owners, {})
            self.assertIsNone(runtime._thread)
            self.assertIsNone(publisher.worker)
        finally:
            publisher.close()

    def test_public_signed_http_get_cannot_issue_lease_and_post_cannot_admit_command(self):
        read_key, command_key = b"r" * 32, b"w" * 32
        config = default_supervision_configuration()
        config.update(vi_passive_shadow=True, remote_control_enabled=True,
                      counter_timing_controls_verified=True)
        validate_supervision_configuration(config)
        constructed = []
        runtime = SupervisionRuntime(identity=IDENTITY,
            vi_passive_shadow=config["vi_passive_shadow"], remote_enabled=config["remote_control_enabled"],
            counter_timing_controls_verified=config["counter_timing_controls_verified"],
            endpoint_factory=lambda **values: constructed.append(values))
        view = ApplicationView(runtime)
        view.capture_once()
        server = ControlHTTPServer(("127.0.0.1", 0), view, read_key, command_key)
        worker = threading.Thread(target=lambda: server.serve_forever(poll_interval=.01))
        worker.daemon = True
        worker.start()
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        def exchange(path, body=None):
            nonce = uuid.uuid4().hex
            raw = None if body is None else json.dumps(body, separators=(",", ":")).encode("utf-8")
            key = read_key if body is None else command_key
            signed = request_signature(key, path, nonce) if body is None else command_signature(key, nonce, raw)
            request = urllib.request.Request("http://127.0.0.1:{0}{1}".format(server.server_port, path),
                data=raw, headers={"X-ACQ-Nonce": nonce, "X-ACQ-Signature": signed,
                                  "Content-Type": "application/json"})
            try:
                response = opener.open(request, timeout=2.)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                value = response.read(262145)
                self.assertTrue(hmac.compare_digest(response_signature(key, nonce, value),
                    response.headers.get("X-ACQ-Response-Signature", "")))
                return response.code, json.loads(value.decode("utf-8"))
        try:
            code, status = exchange("/snapshot")
            self.assertEqual(code, 200)
            self.assertEqual(status["owner_mode"], "VI_PASSIVE_SHADOW")
            self.assertFalse(status["native_initialization_allowed"])
            self.assertFalse(status["control"]["enabled"])
            self.assertIsNone(status["control"]["lease"])
            self.assertEqual(status["control"]["lease_seconds"], 0)
            self.assertTrue(all(not item["enabled"] for item in status["control"]["capabilities"].values()))
            request = dict(command_id="d" * 32, session_id=status["session_id"],
                expected_revision=status["state_revision"], operation="counter_timing.set",
                operator_confirmed=True, value=dict(counter=2, delay_us=1., width_us=2.))
            code, refusal = exchange("/commands", dict(request=request, lease="e" * 32))
            self.assertEqual(code, 403)
            self.assertEqual(refusal["error"], "remote_control_disabled")
            self.assertEqual(runtime.broker.records, {})
            self.assertEqual(runtime.broker.leases, {})
            self.assertEqual(constructed, [])
            self.assertEqual(runtime._owners, {})
            self.assertIsNone(runtime._pending)
            self.assertIsNone(runtime._thread)
        finally:
            server.shutdown(); server.server_close(); worker.join(2.)
            self.assertFalse(worker.is_alive())

    def test_production8768_handler_accepts_typed_shadow_export_on_private_ephemeral_port(self):
        from legacy.xp_acq_control.elyse_agent.supervision_vi_telemetry import (
            SupervisionTelemetryPublisher, SupervisionVIServer, MAX_VI_BYTES, VI_ADDRESS)
        from legacy.xp_acq_control.elyse_agent.protocol import recv_message, send_message
        from tests.unit.test_supervision_vi_telemetry import observation, part, image
        self.assertEqual(VI_ADDRESS, ("127.0.0.1", 8768))
        constructed = []
        runtime = self.runtime(remote_enabled=True,
            endpoint_factory=lambda **values: constructed.append(values))
        publisher = SupervisionTelemetryPublisher(runtime, ("127.0.0.1", 12345), b"r" * 32)
        runtime.telemetry_publisher = publisher
        # Exercise the actual8768 handler at an ephemeral private fixture port;
        # never bind the configured live port or start the outbound relay.
        server = SupervisionVIServer(("127.0.0.1", 0), publisher)
        worker = threading.Thread(target=lambda: server.serve_forever(poll_interval=.01))
        worker.daemon = True
        worker.start()
        value = observation(counter=part(), video=image())
        try:
            with socket.create_connection(server.server_address, timeout=2.) as connection:
                send_message(connection, value, MAX_VI_BYTES)
                reply = recv_message(connection, 16384)
            self.assertTrue(reply["ok"])
            packet = publisher.outbox.peek()["packet"]
            self.assertEqual(packet["source_mode"], "LABVIEW_BRIDGE")
            self.assertEqual(packet["counter_part"]["values"], value["counter_part"]["values"])
            self.assertEqual(packet["video_frame"]["data"], value["video_frame"]["data"])
            self.assertEqual(packet["video_frame"]["capture_session_id"], value["video_frame"]["capture_session_id"])
            self.assertEqual(runtime.snapshot()["owner_mode"], "VI_PASSIVE_SHADOW")
            self.assertFalse(runtime.broker.enabled)
            self.assertEqual(constructed, [])
            self.assertEqual(runtime._owners, {})
            self.assertIsNone(publisher.worker)
        finally:
            server.shutdown(); server.server_close(); worker.join(2.)
            self.assertFalse(worker.is_alive())
            publisher.close()

    def test_shadow_close_does_not_release_a_prior_native_ownership_marker(self):
        marker = Mock()
        marker.snapshot.return_value = dict(required=True, reason="old owner", protection_active=True)
        runtime = self.runtime(recovery_guard=marker)
        runtime.start()
        try:
            self.assertEqual(runtime.snapshot()["state"], "RECOVERY_REQUIRED")
            self.assertRaises(RuntimeError, runtime.initialize, True)
            runtime.request_shutdown()
            self.assertTrue(runtime.join(3.))
            marker.acquire.assert_not_called()
            marker.release_after_cleanup.assert_not_called()
        finally:
            if not runtime.join(0):
                runtime.request_shutdown(); self.assertTrue(runtime.join(3.))

    def test_default_and_false_retain_native_capability_without_automatic_initialization(self):
        class ExistingThread(object):
            def is_alive(self): return True
        for value in ({}, {"vi_passive_shadow": False}):
            runtime = SupervisionRuntime(identity=IDENTITY, remote_enabled=True, **value)
            self.assertFalse(runtime.vi_passive_shadow)
            self.assertTrue(runtime.broker.enabled)
            self.assertEqual(runtime.snapshot()["owner_mode"], "NATIVE_CAPABLE")
            self.assertEqual(runtime._owners, {})
            runtime._thread = ExistingThread()  # Does not execute the queued action.
            runtime.initialize(startup_confirmed=True)
            self.assertEqual(runtime._pending, ("initialize", None))
            self.assertEqual(runtime._owners, {})

    def test_gui_keeps_three_buttons_and_cannot_confirm_or_queue_initialize(self):
        runtime = self.runtime()
        value = runtime.snapshot()
        value.update(application_view_current=True)
        window = SupervisionWindow.__new__(SupervisionWindow)
        window.runtime, window.view = runtime, Mock()
        window.view.snapshot.return_value = value
        window.messagebox = Mock()
        window.initialize()
        window.messagebox.askyesno.assert_not_called()
        window.view.initialize.assert_not_called()
        window.status, window.link, window.display, window.root = Mock(), Mock(), Mock(), Mock()
        window.buttons, window.closing = [Mock(), Mock(), Mock()], False
        window.refresh()
        window.buttons[0].configure.assert_called_with(state="disabled")
        self.assertEqual(BUTTON_LABELS, ("Initialize", "Deinitialize", "Stop server"))

    def test_exact_boolean_configuration_and_constructor_only(self):
        config = default_supervision_configuration()
        self.assertFalse(config["vi_passive_shadow"])
        self.assertIs(validate_supervision_configuration(config), config)
        omitted = copy.deepcopy(config); omitted.pop("vi_passive_shadow")
        self.assertIs(validate_supervision_configuration(omitted), omitted)
        for wrong in (None, 0, 1, "true", [], {}):
            changed = dict(config, vi_passive_shadow=wrong)
            self.assertRaises(ValueError, validate_supervision_configuration, changed)
            self.assertRaises(ValueError, self.runtime, vi_passive_shadow=wrong)

    def test_cold_installer_preserves_optional_true_false_and_rejects_non_boolean(self):
        with tempfile.TemporaryDirectory(prefix="elyse-shadow-installer-test-") as folder:
            package, site, portable = [os.path.join(folder, name) for name in ("package", "site", "portable")]
            source_pin = source_fixture(package)
            runtime_fixture(portable)
            site_fixture(site, "supervision")
            config_path = os.path.join(site, "config.supervision.control.json")
            config = installer._read_json(config_path)
            for index, mode in enumerate((True, False)):
                config["vi_passive_shadow"] = mode
                json_file(config_path, config)
                pin = refresh_site(site, "supervision")
                target = os.path.join(folder, "owned-new-" + str(index))
                result = installer.install(package, site, "supervision", source_pin, pin,
                                           target=target, runtime=portable)
                self.assertFalse(result["processes_started"])
                installed = installer._read_json(os.path.join(target, "config.supervision.control.json"))
                self.assertIs(installed["vi_passive_shadow"], mode)
            for wrong in (None, 0, 1, "true", [], {}):
                config["vi_passive_shadow"] = wrong
                json_file(config_path, config)
                pin = refresh_site(site, "supervision")
                self.assertRaises(ValueError, installer._site, site, pin, "supervision")


if __name__ == "__main__":
    unittest.main()
