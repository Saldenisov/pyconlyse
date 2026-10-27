"""Read-only counter observations; RAM stores, no sockets, NI, or devices."""
import copy
import importlib
import json
import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace

# Everest's top-level package initializer uses modern syntax. Load the actual
# shared store module under package paths on XP without importing that unrelated
# initializer or substituting any store/wire/safety implementation.
if sys.version_info < (3, 8):
    root = Path(__file__).resolve().parents[2]
    for package in ("DeviceServers", "DeviceServers.control", "DeviceServers.control.elyse_acq"):
        namespace = ModuleType(package)
        namespace.__path__ = [str(root.joinpath(*package.split(".")))]
        sys.modules[package] = namespace

from DeviceServers.control.elyse_acq.federated_telemetry import FederatedTelemetryStore
from legacy.xp_acq_control.elyse_agent.federation_wire import owner_frame
from legacy.xp_acq_agent.elyse_agent.telemetry_relay import sign


KEYS = dict(acquisition=b"acquisition-counter-test-key-00000000000000",
            supervision=b"supervision-counter-test-key-00000000000000")


def counter(value=1., age=0., selector=-1., pending=False, bridge=True):
    return dict(values=[value + n for n in range(16)], source_age_seconds=age,
                selector=selector, pending_selector=pending,
                source="observed_labview_control_memory" if bridge else "last_successful_counter_command_memory")


def source(value=None, session="b" * 32, sequence=1, mode="LABVIEW_BRIDGE"):
    identity = None if mode != "LABVIEW_BRIDGE" else dict(
        source="labview_supervision_typed_local", session_id="9" * 32, sequence=sequence)
    return owner_frame("supervision", session, sequence, source_mode=mode,
                       counter_part=value, source_identity=identity)


def request(frame, message=1, relay="d" * 32, age=0.):
    body = dict(schema_version=1, relay_id=relay, message_id=message,
        received_utc_on_xp="2026-10-27T19:00:00+00:00", age_seconds_on_xp=age,
        packet=frame, hardware_writes=False)
    signed = dict(body=body, nonce="e" * 32)
    return dict(signed, signature=sign(KEYS[frame.get("owner", "acquisition")],
                                      "ACQ-TELEMETRY-REQUEST-1", signed))


class SupervisionCounterProjectionTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.
        self.store = FederatedTelemetryStore(KEYS, clock=lambda: self.now)

    def tearDown(self):
        self.store.close()

    def test_waiting_is_explicitly_unavailable_not_zero_filled(self):
        value = self.store.counter_snapshot()
        self.assertFalse(value["available"])
        self.assertIsNone(value["values"])
        self.assertIsNone(value["age_seconds"])
        self.assertTrue(value["read_only"])
        self.assertFalse(value["hardware_acknowledged"])

    def test_vi_counter_exports_all_16_values_and_distinct_source_identity(self):
        frame = source(counter(100.))
        self.store.accept(request(frame))
        view = self.store.snapshot()
        value = view["supervision_counter"]
        self.assertEqual(value["values"], [100. + n for n in range(16)])
        self.assertEqual(value["source"], "observed_labview_control_memory")
        self.assertEqual(value["selector"], -1.)
        self.assertFalse(value["pending_selector"])
        self.assertEqual(value["session_id"], "b" * 32)
        self.assertEqual(value["sequence"], 1)
        self.assertEqual(value["source_identity"], frame["source_identity"])
        self.assertFalse(value["hardware_acknowledged"])
        self.assertFalse(value["physical_measurements_verified"])
        self.assertIsNone(view["publications"]["C1011NI6602"]["data"])
        self.assertTrue(self.store.owner_current("supervision", native=False))
        self.assertFalse(self.store.owner_current("supervision", native=True))

    def test_counter_age_combines_sample_delivery_and_elapsed_without_peer_refresh(self):
        self.store.accept(request(source(counter(age=1.1)), age=.2))
        self.now = .69
        self.assertAlmostEqual(self.store.counter_snapshot()["age_seconds"], 1.99)
        self.assertTrue(self.store.counter_snapshot()["available"])
        acq = owner_frame("acquisition", "a" * 32, 1, source_mode="PYTHON_NATIVE",
                          counter_part=counter(20., bridge=False))
        self.store.accept(request(acq, relay="c" * 32))
        self.now = .7
        value = self.store.counter_snapshot()
        self.assertAlmostEqual(value["age_seconds"], 2.)
        self.assertFalse(value["available"])
        self.assertIsNone(value["values"])
        self.assertTrue(value["stale"])

    def test_pending_selector_is_observation_not_aggregate_or_hardware_ack(self):
        acq = owner_frame("acquisition", "a" * 32, 1, source_mode="PYTHON_NATIVE",
                          counter_part=counter(20., bridge=False))
        self.store.accept(request(acq, relay="c" * 32))
        self.store.accept(request(source(counter(5., selector=17., pending=True))))
        value = self.store.snapshot()
        self.assertTrue(value["supervision_counter"]["available"])
        self.assertEqual(value["supervision_counter"]["selector"], 17.)
        self.assertTrue(value["supervision_counter"]["pending_selector"])
        self.assertFalse(value["supervision_counter"]["hardware_acknowledged"])
        self.assertIsNone(value["publications"]["C1011NI6602"]["data"])

    def test_duplicate_relay_does_not_reset_counter_age(self):
        value = request(source(counter()))
        self.store.accept(value)
        self.now = 1.8
        self.assertTrue(self.store.accept(value)["body"]["duplicate"])
        self.now = 2.
        self.assertFalse(self.store.counter_snapshot()["available"])

    def test_empty_restart_cannot_replace_then_current_restart_retires_old_counter(self):
        old = request(source(counter()))
        self.store.accept(old)
        self.store.accept(request(source(None, session="f" * 32), relay="1" * 32))
        self.assertEqual(self.store.counter_snapshot()["session_id"], "b" * 32)
        self.store.accept(request(source(counter(9.), session="f" * 32, sequence=2),
                                  message=2, relay="1" * 32))
        value = self.store.counter_snapshot()
        self.assertEqual(value["session_id"], "f" * 32)
        self.assertEqual(value["values"][0], 9.)
        self.assertRaises(ValueError, self.store.accept, old)

    def test_returned_values_and_identity_cannot_mutate_authenticated_store(self):
        self.store.accept(request(source(counter())))
        value = self.store.counter_snapshot()
        value["values"][0] = 999.
        value["source_identity"]["session_id"] = "0" * 32
        actual = self.store.counter_snapshot()
        self.assertEqual(actual["values"][0], 1.)
        self.assertEqual(actual["source_identity"]["session_id"], "9" * 32)

    def test_mode_transition_with_no_counter_hides_prior_values(self):
        self.store.accept(request(source(counter())))
        self.store.accept(request(source(None, sequence=2, mode="PYTHON_NATIVE"), message=2))
        value = self.store.counter_snapshot()
        self.assertFalse(value["available"])
        self.assertIsNone(value["values"])
        self.assertIsNone(value["source_identity"])
        self.assertEqual(value["source_mode"], "PYTHON_NATIVE")


@unittest.skipIf(sys.version_info < (3, 8), "Everest-only modules require modern Python; shared store tested above")
class HybridCounterProjectionTests(unittest.TestCase):
    def setUp(self):
        from DeviceServers.control.elyse_acq.hybrid_telemetry import HybridTelemetryStore
        from tests.unit.test_acq_hybrid_telemetry import packet
        self.now = 0.
        self.store = HybridTelemetryStore(KEYS["acquisition"], KEYS["supervision"],
            clock=lambda: self.now, permitted_producer_kind="unified_acquisition")
        self.store.accept(request(packet(), relay="c" * 32))

    def tearDown(self):
        self.store.close()

    def test_sidecar_sync_never_overwrites_or_freshens_legacy_C1011(self):
        before = copy.deepcopy(self.store.snapshot()["publications"])
        self.store.accept(request(source(counter(500.))))
        value = self.store.snapshot()
        self.assertEqual(value["publications"], before)
        self.assertEqual(value["supervision_counter"]["values"][0], 500.)
        self.now = 2.
        self.store.accept(request(source(counter(700.), sequence=2), message=2))
        value = self.store.snapshot()
        self.assertEqual(value["publications"]["C1011NI6602"]["data"], list(range(33)))
        self.assertTrue(value["publications"]["C1011NI6602"]["stale"])
        self.assertTrue(value["supervision_counter"]["available"])
        self.assertEqual(value["supervision_counter"]["values"][0], 700.)

    def test_tango_projection_and_bridge_current_keep_every_command_disabled(self):
        import tango.server
        original = getattr(tango.server, "run", None)
        tango.server.run = lambda *args, **kwargs: None
        try:
            module = importlib.import_module("DeviceServers.control.elyse_acq.DS_AcqTelemetry")
        finally:
            if original is None:
                del tango.server.run
            else:
                tango.server.run = original
        self.store.accept(request(source(counter(500.))))
        device = module.DS_AcqTelemetry()
        device._store, device._migration, device._federated = self.store, True, False
        device._closing, device.commands_enabled = False, True
        runtime = dict(session_id="b" * 32, telemetry_delivery=dict(source_mode="LABVIEW_BRIDGE"),
            control=dict(capabilities={"counter_timing.set": dict(enabled=True, reason="")}))
        view = dict(runtime=runtime, commands_enabled=True)
        device._bridges = {"supervision": SimpleNamespace(snapshot=lambda: copy.deepcopy(view))}
        self.assertTrue(device._control_view("supervision")["telemetry_source_current"])
        self.assertFalse(device._control_view("supervision")["commands_enabled"])
        projected = json.loads(device.supervision_counter_json())
        self.assertEqual(projected["values"][0], 500.)
        self.assertFalse(projected["hardware_acknowledged"])
        self.assertFalse(device._control_view("supervision")["runtime"]["control"]["capabilities"]["counter_timing.set"]["enabled"])
        with self.assertRaisesRegex(RuntimeError, "MIGRATION_SUPERVISION_READ_ONLY"):
            device.ExecuteOwnerCommand(json.dumps(dict(owner="supervision", request={})))
        runtime["session_id"] = None
        self.assertFalse(device._control_view("supervision")["telemetry_source_current"])
        runtime["session_id"] = "b" * 32
        self.now = 2.
        self.assertFalse(device._control_view("supervision")["telemetry_source_current"])


if __name__ == "__main__":
    unittest.main()
