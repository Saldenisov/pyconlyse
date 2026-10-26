"""Python3.4: authenticated read-only video over private loopback and RAM only.

No XP, camera, driver, card process, command, file journal or external network.
The modern --deny-network lane permits these explicitly private127.0.0.1 tests.
"""
import base64
import copy
import hmac
import importlib
import json
import os
import sys
import threading
import types
import unittest
import urllib.error
import urllib.request
import uuid

from legacy.xp_acq_control.elyse_agent.acquisition_http import (
    RuntimeHTTPServer, request_signature, response_signature,
    SUPERVISION_VIDEO_PATH, MAX_VIDEO_RUNTIME_BYTES)
from legacy.xp_acq_control.elyse_agent.application_view import ApplicationView
from legacy.xp_acq_control.elyse_agent.command_http import ControlHTTPServer
from legacy.xp_acq_control.elyse_agent.supervision_runtime import SupervisionRuntime
# The production Everest client files themselves are stdlib/Python3.4-safe.
# Load them under a private local package to avoid DeviceServers' unrelated
# modern/Tango package bootstrap in the actual3.4 offline lane.
_client_package = types.ModuleType("_elyse_video_client_test")
_client_package.__path__ = [os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                                      "DeviceServers", "control", "elyse_acq")]
sys.modules[_client_package.__name__] = _client_package
ControlClient = importlib.import_module(_client_package.__name__ + ".control_client").ControlClient
MAX_RUNTIME_BYTES = importlib.import_module(_client_package.__name__ + ".control_runtime_client").MAX_RUNTIME_BYTES


KEY = b"r" * 32


def frame(count=4):
    return dict(source="python_supervision_ni1409", simulated=False, sequence=1,
        sequence_interpretation="software grab observation, not hardware frame counter",
        observed_utc="2026-10-26T16:00:00+00:00", sample_elapsed_seconds=.01,
        width=count, height=1, pixel_type="U8", encoding="base64_raw_row_major",
        data=base64.b64encode(b"\x00\x11\x80\xff" * (count // 4)).decode("ascii"),
        channel=2, processing="raw_grab_before_legacy_interlace_bcg_profiles",
        hardware_acknowledged=False)


class RamVideoEndpoint(object):
    def __init__(self, count=4):
        self.frame = frame(count)
        self.current, self.age, self.generation, self.uncertain = True, .1, "c" * 32, False
        self.reads, self.hook = 0, None

    def input_snapshot(self):
        self.reads += 1
        value = dict(sample=dict(video_frame=copy.deepcopy(self.frame)), age_seconds=self.age,
                     current=self.current, card_generation=self.generation)
        if self.hook is not None:
            self.hook()
        return value

    def status(self):
        return dict(state="READY", input_current=self.current and not self.uncertain,
            unresolved_request=False, sample_sequence=1, sample_age_seconds=self.age,
            sample=dict(video_frame=copy.deepcopy(self.frame)), error="", input_error="",
            native=dict(worker_generation=self.generation, ownership_uncertain=self.uncertain,
                        resource_count=2, worker_state="IDLE_OWNED", active_request_id=None))


class VideoHTTPTests(unittest.TestCase):
    def setUp(self):
        self.now = [100.]
        self.endpoint = RamVideoEndpoint()
        self.runtime = SupervisionRuntime(identity=dict(runtime_protocol_version=2,
            session_id="a" * 32, build_id="b" * 64), clock=lambda: self.now[0])
        self.runtime._owners = {"video": self.endpoint}
        self.runtime._state, self.runtime._state_revision = "RUNNING", 7
        self.view = ApplicationView(self.runtime, clock=lambda: self.now[0])
        self.view.capture_once()
        self.servers = []

    def tearDown(self):
        for server, worker in self.servers:
            server.shutdown()
            server.server_close()
            worker.join(2.)
            self.assertFalse(worker.is_alive())

    def serve(self, runtime=None, control=True):
        cls = ControlHTTPServer if control else RuntimeHTTPServer
        server = cls(("127.0.0.1", 0), runtime or self.view, KEY)
        worker = threading.Thread(target=lambda: server.serve_forever(poll_interval=.01))
        worker.daemon = True
        worker.start()
        self.servers.append((server, worker))
        return server

    def exchange(self, server, path=SUPERVISION_VIDEO_PATH, key=KEY):
        nonce = uuid.uuid4().hex
        headers = {"X-ACQ-Nonce": nonce, "X-ACQ-Signature": request_signature(key, SUPERVISION_VIDEO_PATH, nonce)}
        request = urllib.request.Request("http://127.0.0.1:{0}{1}".format(server.server_port, path), headers=headers)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            response = opener.open(request, timeout=2.)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            raw = response.read(MAX_VIDEO_RUNTIME_BYTES + 1)
            return response.code, raw, response.headers, nonce

    def test_authenticated_video_read_is_separate_from_snapshot_and_does_not_issue_command_lease(self):
        server = self.serve()
        self.runtime.broker.issue_lease_nonblocking = lambda **unused: self.fail("Video read issued command lease")
        code, raw, headers, nonce = self.exchange(server)
        self.assertEqual(code, 200)
        self.assertTrue(hmac.compare_digest(headers["X-ACQ-Response-Signature"], response_signature(KEY, nonce, raw)))
        value = json.loads(raw.decode("utf-8"))
        self.assertTrue(value["available"])
        self.assertFalse(value["stale"])
        self.assertFalse(value["hardware_writes"])
        self.assertFalse(value["execution_allowed"])
        self.assertEqual(value["frame"]["data"], self.endpoint.frame["data"])
        self.assertEqual(value["capture_session_id"], self.endpoint.generation)
        snapshot = json.dumps(self.view.snapshot())
        self.assertNotIn('"data":', snapshot)
        self.assertLess(len(snapshot), MAX_RUNTIME_BYTES)

    def test_maximum512kib_image_crosses_existing_small_snapshot_bound_but_remains_bounded(self):
        self.endpoint = RamVideoEndpoint(512 * 1024)
        self.endpoint.frame.update(width=1024, height=512)
        self.runtime._owners["video"] = self.endpoint
        self.view.capture_once()
        server = self.serve()
        client = ControlClient(KEY, enabled=False, owner="supervision", host="127.0.0.1", port=server.server_port)
        value = client.read_video()
        self.assertTrue(value["available"])
        self.assertEqual(len(base64.b64decode(value["frame"]["data"])), 512 * 1024)
        self.assertGreater(len(json.dumps(value)), MAX_RUNTIME_BYTES)
        self.assertLess(len(json.dumps(value)), MAX_VIDEO_RUNTIME_BYTES)
        self.assertEqual(client.read()["server_variant"], "supervision_control_vnext")

    def test_wrong_read_key_unknown_path_and_acquisition_role_never_expose_image(self):
        server = self.serve()
        self.assertEqual(self.exchange(server, key=b"x" * 32)[0], 401)
        self.assertEqual(self.endpoint.reads, 0)
        self.assertEqual(self.exchange(server, path=SUPERVISION_VIDEO_PATH + "?camera=other")[0], 404)
        self.assertEqual(self.endpoint.reads, 0)
        class Acquisition(object):
            server_variant = "acquisition_control_vnext"
            def snapshot(self):
                raise AssertionError("Video path entered Acquisition runtime")
        other = self.serve(Acquisition(), control=False)
        self.assertEqual(self.exchange(other)[0], 404)
        self.assertRaises(ValueError, request_signature, KEY, "/supervision/video/start", "a" * 32)
        client = ControlClient(KEY, enabled=False)
        client._exchange = lambda *args, **kwargs: self.fail("Acquisition requested SuperVision video")
        self.assertRaises(ValueError, client.read_video)

    def test_stale_uncertain_or_lifecycle_input_cannot_return_retained_pixels(self):
        for case in ("stale", "uncertain", "missing", "closing", "geometry", "generation"):
            self.endpoint.current, self.endpoint.age, self.endpoint.uncertain = True, .1, False
            self.endpoint.generation, self.endpoint.frame = "c" * 32, frame()
            self.runtime._state, self.runtime._owners = "FAULT", {"video": self.endpoint}
            if case == "stale": self.endpoint.age = 2.
            elif case == "uncertain": self.endpoint.uncertain = True
            elif case == "missing": self.endpoint.current = False
            elif case == "closing": self.runtime._state = "DEINITIALIZING"
            elif case == "geometry": self.endpoint.frame["width"] = 512 * 1024 + 1
            else: self.endpoint.generation = "unqualified"
            value = self.runtime.video_snapshot()
            self.assertFalse(value["available"], case)
            self.assertTrue(value["stale"], case)
            self.assertIsNone(value["frame"], case)

    def test_snapshot_fence_blocks_stale_metadata_local_actions_and_changed_owner(self):
        self.now[0] += 2.
        self.assertFalse(self.view.video_snapshot()["available"])
        self.assertEqual(self.endpoint.reads, 0)
        self.view.capture_once()
        self.assertTrue(self.view.video_snapshot()["available"])
        original = self.runtime.video_snapshot
        def local_action():
            value = original()
            with self.view._condition:
                self.view._pending.append(("deinitialize", {}))
            return value
        self.runtime.video_snapshot = local_action
        self.assertFalse(self.view.video_snapshot()["available"])
        self.runtime.video_snapshot = original
        self.view._pending.clear()
        old = self.endpoint
        self.endpoint.hook = lambda: self.runtime._owners.update(video=RamVideoEndpoint())
        self.assertIsNone(self.runtime.video_frame_snapshot())
        self.assertIsNot(self.runtime._owners["video"], old)

    def test_runtime_lock_is_nonblocking_and_unrelated_sync_command_keeps_video_readable(self):
        entered, release = threading.Event(), threading.Event()
        def hold():
            with self.runtime._lock:
                entered.set()
                release.wait(2.)
        worker = threading.Thread(target=hold)
        worker.start()
        try:
            self.assertTrue(entered.wait(1.))
            self.assertIsNone(self.runtime.video_frame_snapshot())
        finally:
            release.set(); worker.join(2.)
        self.runtime._state, self.runtime._operation = "EXECUTING", "counter_timing.set"
        self.assertTrue(self.runtime.video_snapshot()["available"])
        self.runtime._state = "FAULT"
        self.assertTrue(self.runtime.video_snapshot()["available"])

    def test_client_transport_time_expires_pixels_without_retry_or_command(self):
        value = self.runtime.video_snapshot()
        now, requests = [100.], []
        class Response(object):
            code = 200
            def __enter__(self): return self
            def __exit__(self, *unused): pass
            def read(self, maximum):
                self.maximum = maximum
                now[0] += 1.95
                return self.raw[:maximum]
        class Opener(object):
            def open(self, request, timeout):
                requests.append(request)
                reply = Response()
                reply.raw = json.dumps(value, separators=(",", ":")).encode("utf-8")
                nonce = request.get_header("X-acq-nonce")
                reply.headers = {"X-ACQ-Response-Signature": response_signature(KEY, nonce, reply.raw)}
                return reply
        client = ControlClient(KEY, owner="supervision", host="127.0.0.1", enabled=False,
                               opener=Opener(), clock=lambda: now[0], timeout=2.)
        result = client.read_video()
        self.assertFalse(result["available"])
        self.assertTrue(result["stale"])
        self.assertIsNone(result["frame"])
        self.assertEqual(len(requests), 1)
        self.assertTrue(requests[0].full_url.endswith(SUPERVISION_VIDEO_PATH))
        self.assertEqual(requests[0].get_method(), "GET")


if __name__ == "__main__":
    unittest.main()
