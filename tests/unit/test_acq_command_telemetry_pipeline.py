"""Software status and real sample publication; actual Python 3.4 compatible.

RAM-only owners and private authenticated loopback. No NI, XP, Tango database,
live receiver, journal or experiment archive is opened or changed.
"""
import copy
import hmac
import socketserver
import sys
import threading
import time
import unittest

from legacy.xp_acq_control.elyse_agent.application_view import ApplicationView
from legacy.xp_acq_control.elyse_agent.dual_mode_telemetry import (
    DualModeTelemetryPublisher, NATIVE_SITE,
)
from legacy.xp_acq_control.elyse_agent.protocol import recv_message, send_message
from legacy.xp_acq_control.elyse_agent.standard_banks import (
    BANKS, INPUTS, COMMANDS, validate_standard_packet,
)
from legacy.xp_acq_control.elyse_agent.telemetry_publisher import StandardTelemetryPublisher
from legacy.xp_acq_control.elyse_agent.telemetry_relay import (
    DeadlineSocket, MAX_RELAY_FRAME, sign,
)


KEY = b"test-only-command-telemetry-loopback-0000000"


def image(measurement_age=5., software_age=.05):
    banks, commands = {}, {}
    for bank, (name, kind, device, count, field, scalar) in INPUTS.items():
        values = [False] * count if scalar == "Boolean" else [1.25] * count
        banks[name] = dict(kind=kind, device=device, values=copy.deepcopy(values))
        banks[name][field] = values
    for name, (section, source, count, kind) in COMMANDS.items():
        commands.setdefault(section, {})[source] = [False if kind == "Boolean" else 6.5] * count
    latest = dict(source="python_daqmx_acquisition", simulated=False, banks=banks, **commands)
    return dict(session_id="a" * 32, state="EXECUTING", state_revision=3,
        sequence=7, error="", resource_count=21, latest=latest,
        age_seconds=measurement_age, stale=measurement_age >= 2,
        measurement_current=measurement_age < 2, telemetry_view_current=True,
        telemetry_bridge_mode=False, software_state_current=True,
        software_state_sequence=1, software_state_age_seconds=software_age,
        software_state=dict(source="python_acquisition_software_memory", simulated=False,
            session_id="a" * 32, sequence=1, source_revision=1,
            local_banks=dict(EPS=[False] * 77, DPS=[False] * 29),
            hardware_acknowledged=False, psp_delivery_acknowledged=False))


class Runtime(object):
    def __init__(self, value):
        self.value, self.now = value, 100.
        self._lock = threading.RLock()
        self._identity = dict(session_id=value["session_id"])
        self._clock = lambda: self.now

    def snapshot(self):
        return copy.deepcopy(self.value)

    def try_telemetry_snapshot(self):
        if not self._lock.acquire(False):
            return None
        try:
            return copy.deepcopy(self.value)
        finally:
            self._lock.release()

    def update_status(self, eps=None, dps=None):
        self.value["software_state_sequence"] += 1
        state = self.value["software_state"]
        state["sequence"] = self.value["software_state_sequence"]
        state["source_revision"] += 1
        for index, value in (eps or ()):
            state["local_banks"]["EPS"][index] = value
        for index, value in (dps or ()):
            state["local_banks"]["DPS"][index] = value
        self.value["software_state_age_seconds"] = .02


def records(body):
    return {row["publication"]: row for row in body["packet"]["data"]["banks"]}


def acknowledge(publisher):
    body = publisher.outbox.peek()
    publisher.outbox.acknowledge(body["relay_id"], body["message_id"])
    return body


class CommandTelemetryPipelineTests(unittest.TestCase):
    def make(self, dual=False, value=None):
        runtime = Runtime(value if value is not None else image())
        publisher = (DualModeTelemetryPublisher(runtime, ("127.0.0.1", 1), KEY,
                        clock=runtime._clock) if dual else
                     StandardTelemetryPublisher(runtime, ("127.0.0.1", 1), KEY))
        self.addCleanup(publisher.close)
        return runtime, publisher

    def test_status_updates_publish_without_advancing_measurement_sequence(self):
        for dual in (False, True):
            with self.subTest(dual=dual):
                runtime, publisher = self.make(dual)
                runtime.value["software_state"]["local_banks"]["DPS"][2] = True
                self.assertTrue(publisher.publish_once())
                first = acknowledge(publisher)
                self.assertTrue(records(first)["DPS"]["data"][2])
                self.assertAlmostEqual(first["age_seconds_on_xp"], 0., delta=.1)
                self.assertFalse(publisher.publish_once())
                runtime.update_status(eps=((8, True),), dps=((2, False),))
                self.assertTrue(publisher.publish_once())
                second = acknowledge(publisher)
                self.assertEqual(runtime.value["sequence"], 7)
                self.assertEqual(runtime.value["age_seconds"], 5.)
                self.assertTrue(records(second)["EPS"]["data"][8])
                self.assertFalse(records(second)["DPS"]["data"][2])
                for bank in set(INPUTS) | set(COMMANDS):
                    self.assertIsNone(records(second)[bank]["data"])
                self.assertEqual(len(records(second)), 27)
                if dual:
                    self.assertEqual(second["packet"]["source_site"], NATIVE_SITE)

    def test_status_change_does_not_relabel_or_overtake_inflight_snapshot(self):
        runtime, publisher = self.make()
        publisher.publish_once()
        first = publisher.outbox.peek()
        runtime.update_status(dps=((4, True),))
        publisher.publish_once()
        retained = publisher.outbox.peek()
        self.assertEqual(retained["packet"], first["packet"])
        self.assertEqual(retained["message_id"], first["message_id"])
        self.assertGreaterEqual(retained["age_seconds_on_xp"], first["age_seconds_on_xp"])
        self.assertFalse(records(first)["DPS"]["data"][4])
        acknowledge(publisher)
        self.assertTrue(records(publisher.outbox.peek())["DPS"]["data"][4])

    def test_mixed_source_packet_preserves_oldest_populated_source_age(self):
        runtime, publisher = self.make(value=image(.8, .1))
        publisher.publish_once()
        first = acknowledge(publisher)
        self.assertAlmostEqual(first["age_seconds_on_xp"], .8, delta=.1)
        self.assertEqual(sum(row["data"] is not None for row in records(first).values()), 14)
        runtime.value.update(age_seconds=2.1, stale=True, measurement_current=False)
        runtime.update_status(eps=((14, True),))
        publisher.publish_once()
        second = acknowledge(publisher)
        self.assertAlmostEqual(second["age_seconds_on_xp"], 0., delta=.1)
        self.assertIsNone(records(second)["C2NI6071E"]["data"])
        self.assertTrue(records(second)["EPS"]["data"][14])

    def test_persistent_literal_age_does_not_poison_fresh_published_inputs(self):
        for dual in (False, True):
            with self.subTest(dual=dual):
                runtime, publisher = self.make(dual, image(.2, 64.))
                publisher.outbox._clock = runtime._clock
                self.assertTrue(publisher.publish_once())
                first = publisher.outbox.peek()
                self.assertAlmostEqual(first["age_seconds_on_xp"], .2)
                self.assertEqual(sum(row["data"] is not None for row in records(first).values()), 14)
                self.assertEqual(runtime.value["software_state_age_seconds"], 64.)
                runtime.now += 3.
                retained = acknowledge(publisher)
                self.assertAlmostEqual(retained["age_seconds_on_xp"], 3.2)
                self.assertEqual(retained["message_id"], first["message_id"])
                runtime.value.update(age_seconds=3.2, stale=True, measurement_current=False,
                                     sequence=8)
                self.assertTrue(publisher.publish_once())
                second = acknowledge(publisher)
                for name in set(INPUTS) | set(COMMANDS):
                    self.assertIsNone(records(second)[name]["data"])
                self.assertIsNotNone(records(second)["EPS"]["data"])
                self.assertAlmostEqual(second["age_seconds_on_xp"], 0.)

    @unittest.skipIf(sys.version_info < (3, 7), "Everest receiver requires Python 3.7+")
    def test_signed_ram_receiver_ages_actual_inputs_after_current_memory_projection(self):
        from DeviceServers.control.elyse_acq.telemetry_sink import TelemetrySinkStore
        runtime, publisher = self.make(True, image(.2, 64.))
        publisher.outbox._clock = runtime._clock
        now = [0.]
        store = TelemetrySinkStore(KEY, clock=lambda: now[0],
                                   permitted_producer_kind="unified_acquisition")
        self.addCleanup(store.close)
        self.assertTrue(publisher.publish_once())
        signed = dict(body=publisher.outbox.peek(), nonce="b" * 32)
        request = dict(signed, signature=sign(KEY, "ACQ-TELEMETRY-REQUEST-1", signed))
        store.accept(request)
        initial = store.snapshot()["publications"]
        populated = [row for row in initial.values() if row["data"] is not None]
        self.assertEqual(len(populated), 14)
        self.assertTrue(all(not row["stale"] for row in populated))
        self.assertAlmostEqual(initial["C1NI6071E"]["age_seconds"], .2)
        now[0] = 2.
        expired = store.snapshot()["publications"]
        self.assertTrue(all(expired[name]["stale"] for name in set(INPUTS) | set(COMMANDS)))
        self.assertAlmostEqual(expired["C1NI6071E"]["age_seconds"], 2.2)

    def test_busy_owner_invalidates_both_sources_without_waiting(self):
        runtime, publisher = self.make(value=image(.2, .1))
        publisher.publish_once()
        acknowledge(publisher)
        entered, release = threading.Event(), threading.Event()
        def hold():
            with runtime._lock:
                entered.set()
                release.wait(3)
        worker = threading.Thread(target=hold)
        worker.start()
        try:
            self.assertTrue(entered.wait(1))
            runtime.now += .5
            started = time.monotonic()
            value = publisher.view.snapshot()
            self.assertLess(time.monotonic() - started, .2)
            self.assertAlmostEqual(value["age_seconds"], .7)
            self.assertAlmostEqual(value["software_state_age_seconds"], .6)
            self.assertFalse(value["measurement_current"])
            self.assertFalse(value["software_state_current"])
            publisher.publish_once()
            self.assertTrue(all(row["data"] is None for row in records(acknowledge(publisher)).values()))
        finally:
            release.set()
            worker.join(3)
            self.assertFalse(worker.is_alive())

    def test_application_cache_ages_software_observations_separately(self):
        runtime = Runtime(image(.2, .1))
        runtime.value["control"] = dict(enabled=False, capabilities={})
        view = ApplicationView(runtime, clock=runtime._clock)
        view.capture_once()
        runtime.now += .5
        value = view.snapshot()
        self.assertAlmostEqual(value["age_seconds"], .7)
        self.assertAlmostEqual(value["software_state_age_seconds"], .6)
        runtime.now += 2
        value = view.snapshot()
        self.assertFalse(value["application_view_current"])
        self.assertFalse(value["software_state_current"])
        self.assertFalse(value["measurement_current"])

    def test_authenticated_loopback_preserves_status_and_null_hardware(self):
        received = []
        class Sink(socketserver.BaseRequestHandler):
            def handle(self):
                connection = DeadlineSocket(self.request, time.monotonic() + 2)
                request = recv_message(connection, MAX_RELAY_FRAME)
                signed = dict(body=request["body"], nonce=request["nonce"])
                if not hmac.compare_digest(request["signature"], sign(KEY, "ACQ-TELEMETRY-REQUEST-1", signed)):
                    raise AssertionError("Synthetic request signature invalid")
                validate_standard_packet(request["body"]["packet"])
                received.append(request["body"])
                reply = dict(body=dict(accepted=True, duplicate=False,
                    relay_id=request["body"]["relay_id"], message_id=request["body"]["message_id"],
                    storage_mode="ram_latest", durable=False), nonce=request["nonce"])
                reply["signature"] = sign(KEY, "ACQ-TELEMETRY-ACK-1", reply)
                send_message(connection, reply, MAX_RELAY_FRAME)
        server = socketserver.TCPServer(("127.0.0.1", 0), Sink)
        worker = threading.Thread(target=lambda: server.serve_forever(poll_interval=.02))
        worker.daemon = True
        worker.start()
        try:
            runtime, publisher = self.make(dual=True)
            publisher.relay.address = server.server_address
            publisher.publish_once()
            self.assertTrue(publisher.relay.send_once())
            runtime.update_status(dps=((10, True),))
            publisher.publish_once()
            self.assertTrue(publisher.relay.send_once())
            self.assertEqual(len(received), 2)
            self.assertEqual(tuple(row["publication"] for row in received[-1]["packet"]["data"]["banks"]), BANKS)
            self.assertTrue(records(received[-1])["DPS"]["data"][10])
            self.assertIsNone(records(received[-1])["C1NI6071E"]["data"])
            self.assertEqual(publisher.status()["everest_acknowledged"], 2)
        finally:
            server.shutdown()
            server.server_close()
            worker.join(3)


if __name__ == "__main__":
    unittest.main()
