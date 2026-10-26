"""Private RAM card children only. No NI, XP, external network or live process."""
import json
import os
import tempfile
import time
import unittest

from legacy.xp_acq_control.elyse_agent.supervision_cards import SupervisionCounterCard
from legacy.xp_acq_control.elyse_agent.supervision_imaq import SupervisionVideoCard
from legacy.xp_acq_control.elyse_agent.supervision_runtime import SupervisionRuntime
from legacy.xp_acq_control.elyse_agent.supervision_service import SupervisionVideoService
from legacy.xp_acq_control.elyse_agent.card_process_owner import CardProcessEndpoint
from legacy.xp_acq_control.elyse_agent.supervision_gui import (
    BUTTON_LABELS, default_supervision_configuration, validate_supervision_configuration,
    load_supervision_configuration,
)
from legacy.xp_acq_control.elyse_agent.acquisition_recovery import OwnershipMarker, RecoveryRequired
from legacy.xp_acq_control.elyse_agent.command_protocol import OPERATIONS
from tests.unit.test_supervision_card_adapters import FakeDriver, FakeVideo


class SlowSyncAdapter(SupervisionCounterCard):
    def configure_timing(self, *args, **kwargs):
        time.sleep(.25)
        return SupervisionCounterCard.configure_timing(self, *args, **kwargs)


def ram_sync_adapter():
    return SlowSyncAdapter(driver_factory=FakeDriver)


def ram_video_adapter():
    return SupervisionVideoCard(driver=FakeVideo())


class FailingVideoAdapter(SupervisionVideoCard):
    def read_frame(self):
        if self.sequence >= 2:
            raise IOError("injected independent video input failure")
        return SupervisionVideoCard.read_frame(self)


def ram_failing_video_adapter():
    return FailingVideoAdapter(driver=FakeVideo())


class SupervisionRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.runtime = None

    def tearDown(self):
        runtime = self.runtime
        if runtime is not None and not runtime.join(0):
            try:
                self.wait(lambda: runtime.snapshot()["current_operation"] is None)
                runtime.request_shutdown(electrical_off_confirmed=True)
                self.assertTrue(runtime.join(15))
            finally:
                # Only private RAM-fixture descendants created by this test;
                # never discover or terminate any external/live NI process.
                for endpoint in list(runtime._owners.values()):
                    process = getattr(getattr(endpoint, "client", None), "_process", None)
                    if process is not None and process.poll() is None:
                        process.terminate()
                        process.wait(5)
        self.folder.cleanup()

    def wait(self, predicate, timeout=10):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(.02)
        self.fail("Private fixture deadline exceeded")

    def make_runtime(self, commissioned=True):
        identity = dict(runtime_protocol_version=2, session_id="a" * 32, build_id="b" * 64)
        marker = OwnershipMarker(os.path.join(self.folder.name, "sup.ownership"),
                                 identity["session_id"], identity["build_id"])
        runtime = SupervisionRuntime(identity=identity, recovery_guard=marker,
            remote_enabled=True, counter_timing_controls_verified=commissioned, period=.03,
            trusted_service_options=dict(
                sync={"trusted_factory": __name__ + ":ram_sync_adapter"},
                video={"trusted_factory": __name__ + ":ram_video_adapter"}))
        self.runtime = runtime
        return runtime

    def initialize(self, runtime):
        runtime.start()
        runtime.initialize(startup_confirmed=True)
        self.wait(lambda: runtime.snapshot()["state"] in ("RUNNING", "FAULT"))
        self.assertEqual(runtime.snapshot()["state"], "RUNNING", runtime.snapshot()["error"])
        self.wait(lambda: runtime.snapshot()["card_health"]["all_required_ready"]
                  and runtime.video_frame_snapshot() is not None and runtime.counter_memory_part() is not None)

    def test_cold_runtime_starts_no_card_or_import_and_three_buttons_remain(self):
        import sys
        runtime = self.make_runtime()
        self.assertEqual(runtime.snapshot()["state"], "IDLE")
        self.assertEqual(runtime._owners, {})
        self.assertFalse(os.path.exists(runtime._recovery_guard.path))
        runtime.start()
        time.sleep(.05)
        self.assertEqual(runtime._owners, {})
        self.assertNotIn("nidaqmx", sys.modules)
        self.assertEqual(BUTTON_LABELS, ("Initialize", "Deinitialize", "Stop server"))
        self.assertFalse(runtime.snapshot()["remote_initialization_enabled"])
        self.assertRaises(ValueError, runtime.initialize)
        self.assertFalse(os.path.exists(runtime._recovery_guard.path))

    def test_two_private_owners_ready_and_images_stay_outside_control_snapshot(self):
        runtime = self.make_runtime()
        self.initialize(runtime)
        value = runtime.snapshot()
        self.assertEqual(value["resource_count"], 10)
        self.assertEqual(value["server_variant"], "supervision_control_vnext")
        cards = value["card_processes"]["cards"]
        self.assertNotEqual(cards["sync"]["native"]["worker_pid"], cards["video"]["native"]["worker_pid"])
        self.assertNotIn("data", cards["video"]["sample"]["video_frame"])
        self.assertNotIn("data", value["video_frame"])
        self.assertLess(len(json.dumps(value).encode("utf-8")), 262144)
        frame = runtime.video_frame_snapshot()
        self.assertIn("data", frame)
        self.assertEqual(frame["capture_session_id"], cards["video"]["native"]["worker_generation"])
        self.assertEqual(frame["owner_session_id"], value["session_id"])
        self.assertLess(frame["source_age_seconds"], 2)
        memory = runtime.counter_memory_part()
        self.assertEqual(len(memory["values"]), 16)
        self.assertEqual(memory["values"][4:6], [2008.3, 10.])
        self.assertEqual(memory["selector"], -1)

    def test_only_commissioned_counter_timing_is_admitted_and_video_continues(self):
        runtime = self.make_runtime()
        self.initialize(runtime)
        view = runtime.snapshot()
        capabilities = view["control"]["capabilities"]
        self.assertEqual(set(capabilities), set(OPERATIONS))
        self.assertTrue(capabilities["counter_timing.set"]["enabled"])
        self.assertTrue(all(not cap["enabled"] for name, cap in capabilities.items() if name != "counter_timing.set"))
        before = runtime.video_frame_snapshot()["sequence"]
        request = dict(command_id="c" * 32, session_id=view["session_id"],
            expected_revision=view["state_revision"], operation="counter_timing.set",
            operator_confirmed=True, value=dict(counter=2, delay_us=1., width_us=2.))
        lease = runtime.broker.snapshot(issue_lease=True)["lease"]
        receipt = runtime.broker.submit(request, lease)
        self.assertEqual(receipt["outcome"], "QUEUED")
        self.wait(lambda: runtime.snapshot()["state"] == "EXECUTING")
        self.assertIsNone(runtime.counter_memory_part())
        self.wait(lambda: runtime.video_frame_snapshot()["sequence"] >= before + 2)
        self.wait(lambda: any(r["outcome"] == "COMPLETED" for r in runtime.broker.snapshot()["results"]))
        self.wait(lambda: runtime.counter_memory_part() is not None
                  and runtime.counter_memory_part()["values"][4:6] == [1., 2.])
        self.assertTrue(runtime.broker.submit(request, None)["duplicate"])
        self.assertRaises(RuntimeError, runtime.dispatch_remote, "modulator.general.start", None)

    def test_uncommissioned_timing_and_old_revision_cannot_mutate(self):
        runtime = self.make_runtime(commissioned=False)
        self.initialize(runtime)
        value = runtime.snapshot()
        self.assertFalse(value["control"]["capabilities"]["counter_timing.set"]["enabled"])
        self.assertRaises(RuntimeError, runtime.dispatch_remote, "counter_timing.set",
                          dict(counter=2, delay_us=1., width_us=2.))
        self.assertRaises(RuntimeError, runtime.fenced_local_request, value["session_id"],
                          value["state_revision"] - 1, lambda: self.fail("Stale callback executed"))

    def test_video_input_failure_does_not_restart_or_hide_synchronization(self):
        runtime = self.make_runtime()
        runtime._service_options["video"] = {"trusted_factory": __name__ + ":ram_failing_video_adapter"}
        runtime.start()
        runtime.initialize(startup_confirmed=True)
        self.wait(lambda: runtime.snapshot()["card_processes"]["cards"].get("video", {}).get("input_error"))
        self.wait(lambda: runtime.counter_memory_part() is not None)
        value = runtime.snapshot()
        before = value["card_processes"]["cards"]["sync"]
        self.assertFalse(value["card_health"]["all_required_ready"])
        self.assertTrue(value["card_health"]["independently_current"]["sync"])
        self.assertFalse(value["card_health"]["independently_current"]["video"])
        self.assertIsNone(runtime.video_frame_snapshot())
        self.wait(lambda: runtime.snapshot()["card_processes"]["cards"]["sync"]["sample_sequence"]
                  > before["sample_sequence"] + 1)
        after = runtime.snapshot()["card_processes"]["cards"]["sync"]
        self.assertEqual(after["native"]["worker_pid"], before["native"]["worker_pid"])
        self.assertEqual(after["native"]["worker_generation"], before["native"]["worker_generation"])
        self.assertEqual(after["sample"]["counter_memory"]["running_counters"], list(range(8)))

    def test_local_dispatch_start_failure_still_starts_the_other_board(self):
        runtime = self.make_runtime()
        def endpoint_factory(**options):
            endpoint = CardProcessEndpoint(**options)
            if options["device"] == "sync":
                def fail_start():
                    raise IOError("injected local synchronization dispatcher start failure")
                endpoint.start = fail_start
            return endpoint
        runtime._endpoint_factory = endpoint_factory
        runtime.start()
        runtime.initialize(startup_confirmed=True)
        self.wait(lambda: runtime.snapshot()["state"] == "FAULT")
        self.wait(lambda: runtime.video_frame_snapshot() is not None)
        value = runtime.snapshot()
        self.assertIn("synchronization dispatcher start failure", value["error"])
        self.assertEqual(set(value["card_processes"]["cards"]), {"sync", "video"})
        self.assertFalse(value["card_health"]["all_required_ready"])
        self.assertTrue(value["card_health"]["independently_current"]["video"])
        self.assertIsNone(runtime.counter_memory_part())

    def test_prior_ownership_marker_is_preserved_without_creating_workers(self):
        runtime = self.make_runtime()
        old = OwnershipMarker(runtime._recovery_guard.path, "d" * 32, "e" * 64, process_id=123456)
        old.acquire()
        with open(old.path, "rb") as stream:
            before = stream.read()
        runtime.start()
        self.assertEqual(runtime.snapshot()["state"], "RECOVERY_REQUIRED")
        self.assertRaises((RecoveryRequired, RuntimeError), runtime.initialize, True)
        self.assertEqual(runtime._owners, {})
        runtime.request_shutdown()
        self.assertTrue(runtime.join(5))
        with open(old.path, "rb") as stream:
            self.assertEqual(stream.read(), before)

    def test_deinitialize_requires_explicit_off_and_closes_both_owners(self):
        runtime = self.make_runtime()
        self.initialize(runtime)
        self.assertRaises(ValueError, runtime.deinitialize)
        runtime.deinitialize(electrical_off_confirmed=True)
        self.wait(lambda: runtime.snapshot()["state"] == "IDLE")
        self.assertEqual(runtime.snapshot()["resource_count"], 0)
        self.assertFalse(os.path.exists(runtime._recovery_guard.path))
        self.assertEqual(runtime._owners, {})
        self.assertIsNone(runtime.counter_memory_part())
        self.assertIsNone(runtime.video_frame_snapshot())

    def test_strict_configuration_and_authentication_key_separation(self):
        config = default_supervision_configuration()
        self.assertFalse(config["telemetry"]["enabled"])
        self.assertEqual(validate_supervision_configuration(config)["video"]["channel"], 2)
        for invalid in (dict(config, bind_host="10.20.30.10"), dict(config, arbitrary_factory="evil"),
                        dict(config, read_key_file="../secret"), dict(config, remote_control_enabled=1)):
            self.assertRaises(ValueError, validate_supervision_configuration, invalid)
        config["telemetry"].update(enabled=True, wire="legacy_27")
        self.assertRaises(ValueError, validate_supervision_configuration, config)
        config = default_supervision_configuration()
        path = os.path.join(self.folder.name, "config.supervision.control.json")
        with open(path, "w") as stream:
            json.dump(config, stream)
        for name, key in ((config["read_key_file"], b"r" * 32), (config["command_key_file"], b"w" * 32)):
            with open(os.path.join(self.folder.name, name), "wb") as stream:
                stream.write(key)
        loaded, read_key, command_key = load_supervision_configuration(path)
        self.assertNotEqual(read_key, command_key)
        with open(os.path.join(self.folder.name, config["command_key_file"]), "wb") as stream:
            stream.write(read_key)
        self.assertRaises(ValueError, load_supervision_configuration, path)


if __name__ == "__main__":
    unittest.main()
