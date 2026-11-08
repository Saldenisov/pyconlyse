"""Offline full-plan -> indexed camera packet -> immutable RAW/OD contracts."""

import copy
import hashlib
import json
import sys
import threading
import zlib
from pathlib import Path
from types import SimpleNamespace

import h5py
import numpy as np
import pytest
from flask import Flask, jsonify

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "web/backend"))
import pump_probe_v0_api as api
from pump_probe_v0_processing import TRANCON_GROUPS


def triplet(ratio=1.):
    # Source g=1: Ie, BG, I0. Detector II alone anchors the phase index.
    return np.array([[[11., 11.], [21., 21.]], [[1., 1.], [1., 1.]],
                     [[1. + 10. * ratio] * 2, [21., 21.]]], dtype=np.float32)


class Camera:
    def __init__(self, rig):
        self.rig = rig
        self.active = True
        self.orders = {}
        self.next_frame = 7
        self.requests = []
        self.entered = threading.Event()
        self.block = False
        self.bad_checksum = False
        self.start_timeout = False
        self.begin_timeout = False
        self.release_timeout = False
        self.on_release = lambda: None
        self.config_fingerprint = "c" * 64
        self.make_cycles = lambda count, point: [triplet(1. if i % 2 == 0 else 9.) for i in range(count)]

    def state(self):
        self.rig.calls.append("camera.state")
        return "ON"

    def command_inout(self, command, argument=None):
        self.rig.calls.append(command)
        if command == "V0Capabilities":
            return json.dumps({"schema": "andor-v0-raw-order-v1", "configuration_fresh": True,
                "track_count": 2, "external_trigger": True, "lossless": self.active,
                "acquisition_active": self.active, "acquisition_epoch": "epoch1",
                "config_fingerprint": self.config_fingerprint, "width": 2,
                "wavelengths": [500., 600.], "admission_error": None if self.active else "inactive"})
        if command == "start_grabbing":
            self.active = True
            if self.start_timeout:
                raise TimeoutError("start reply lost after execution")
            return None
        if command == "stop_grabbing":
            self.active = False
            return None
        if command == "V0BeginOrder":
            request = json.loads(argument)
            prior = next((order for order in self.orders.values() if order["request_id"] == request["request_id"]), None)
            if prior is not None:
                assert prior["request"] == request
                return json.dumps({"order_id": prior["order_id"]})
            assert not any(not item["released"] for item in self.orders.values()), "previous RAW packet not acknowledged"
            order_id = "order-" + str(len(self.orders))
            self.requests.append(request)
            count = request["frame_count"] // 3
            cycles = self.make_cycles(count, request["point_index"])
            data = np.concatenate(cycles, axis=0).astype("<f4")
            ids = list(range(self.next_frame, self.next_frame + len(data)))
            self.next_frame += len(data)
            samples = data.tobytes()
            header = {"schema": "andor-v0-raw-order-v1", "order_id": order_id,
                **{key: value for key, value in request.items() if key != "expected_config_fingerprint"},
                "config_fingerprint": request["expected_config_fingerprint"],
                "state": "complete", "armed": True, "dtype": "<f4", "array_order": "C",
                "compression": "zlib", "phase_labels": None,
                "track_order": ["detector_I", "detector_II"], "wavelengths": [500., 600.],
                "shape": list(data.shape), "frame_ids": ids, "boundary_frame_id": ids[0],
                "frames_captured": len(data), "payload_sha256": hashlib.sha256(samples).hexdigest()}
            if self.bad_checksum:
                header["payload_sha256"] = "0" * 64
            order = {**header, "header": header, "packet": zlib.compress(samples),
                     "released": False, "request": request}
            self.orders[order_id] = order
            self.entered.set()
            if self.begin_timeout:
                raise TimeoutError("Begin reply lost after execution")
            return json.dumps({"order_id": order_id})
        order = self.orders[argument]
        if command == "V0OrderStatus":
            return json.dumps({"order_id": argument, "state": "capturing" if self.block else "complete"})
        if command == "V0ReadOrder":
            return json.dumps(order["header"]), order["packet"]
        if command == "V0CancelOrder":
            if self.block:
                order["header"]["state"] = "cancelled"
            return "{}"
        if command == "V0ReleaseOrder":
            writer = self.rig.controller._run_writer
            assert writer is not None and not writer._closed
            # Read flushed storage independently, before allowing the camera to
            # discard its original packet. Both accepted and rejected count.
            with h5py.File(writer.h5_path, "r") as saved:
                assert len(saved["transport/accepted"]) + len(saved["transport/rejected"]) > 0
            order["released"] = True
            self.on_release()
            if self.release_timeout:
                self.release_timeout = False
                raise TimeoutError("Release reply lost after execution")
            return "{}"
        raise AssertionError(command)


class Stage:
    def __init__(self, rig):
        self.rig, self.position = rig, 0.

    def command_inout(self, name, argument):
        self.rig.calls.append(name)
        if name == "move_axis":
            self.position = argument[1]
            self.rig.moves.append(tuple(argument))
        else:
            assert name == "stop_axis"

    def read_attribute(self, name):
        self.rig.calls.append("read:" + name)
        axis = self.rig.controller._hardware_config["delay_line_axis"]
        return SimpleNamespace(value={str(axis): self.position if name == "positions" else "ON"})


@pytest.fixture
def rig(monkeypatch, tmp_path):
    monkeypatch.setenv("PYCONLYSE_PUMP_PROBE_DATA_ROOT", str(tmp_path))
    controller = api.PumpProbeV0Controller()
    controller._hardware_config.update(control_mode="tango", dg645_preflight_policy="verify_only")
    controller._settings.update(delay_points_ps=[0., 2., 0.], pulses_per_point=2, real_zero_ps=0.)
    profile = json.loads((Path(__file__).resolve().parents[2] / "web/pump_probe/config/v0_tango_raw_profile.json").read_text())
    profile.update(commissioned=True, expected_config_fingerprint="c" * 64, background_level=10,
                   poll_interval_s=.002, max_rejected_cycles=2)
    monkeypatch.setattr(controller, "_load_tango_profile_locked", lambda: copy.deepcopy(profile))
    # Legacy idle/manual diagnostics are outside this RAW worker test fixture.
    monkeypatch.setattr(controller, "_read_tango_motion_state_locked", lambda state: state)
    dg = {"device": controller._hardware_config["dg645_device"], "recall_slot": 8,
          "snapshot": {"raw_queries": {"TRAT?": "5", "DLAY? 2": "0,0.001"}}}
    monkeypatch.setattr(api, "_load_dg645_recall_config", lambda _path: copy.deepcopy(dg))
    value = SimpleNamespace(controller=controller, profile=profile, calls=[], moves=[], proxies=[], tmp=tmp_path)
    value.camera, value.stage = Camera(value), Stage(value)

    class Timing:
        def command_inout(self, name, query):
            value.calls.append(name)
            assert name == "scpi_query"
            return dg["snapshot"]["raw_queries"][query]

    def proxy(name, **kwargs):
        value.proxies.append(name)
        return {controller._hardware_config["andor_device"]: value.camera,
                controller._hardware_config["owis_aggregator_device"]: value.stage,
                controller._hardware_config["dg645_device"]: Timing()}[name]

    monkeypatch.setattr(api, "_tango_proxy", proxy)
    monkeypatch.setattr(api, "_emulator", controller)
    monkeypatch.setattr(api, "authorization_required", lambda: False)
    monkeypatch.setattr(api, "require_http_hardware", lambda *args, **kwargs: None)
    app = Flask(__name__)
    app.register_blueprint(api.pump_probe_v0_api)
    value.client = app.test_client()
    value.timing = dg
    value.payload = {"running": True, "run_action": "new", "save_path": str(tmp_path), "sample_name": "offline"}
    yield value
    if controller._tango_stop_event is not None:
        controller.set_running(False)
        assert controller._tango_done_event.wait(5.)


def start(rig, action="new"):
    payload = {**rig.payload, "run_action": action}
    preview = rig.client.post("/api/pump-probe-v0/run/plan", json=payload)
    assert preview.status_code == 200, preview.get_json()
    payload["plan_fingerprint"] = preview.get_json()["fingerprint"]
    response = rig.client.post("/api/pump-probe-v0/run", json=payload)
    assert response.status_code == 200, response.get_json()
    return response


def finished(rig):
    assert rig.controller._tango_done_event.wait(5.), "offline worker did not finish"
    return rig.controller.state()


def test_full_point_batches_preserve_RAW_packets_order_repeated_delays_and_mean_logs(rig):
    start(rig)
    state = finished(rig)
    assert state["run"]["status"] == "completed", state["run"]
    assert [item["frame_count"] for item in rig.camera.requests] == [6, 6, 6]
    assert [item["point_index"] for item in rig.camera.requests] == [0, 1, 2]
    np.testing.assert_allclose([move[1] for move in rig.moves], rig.controller._scan_plan.positions)
    assert state["run"]["artifacts"]["frame_counts"] == [2, 2, 2]
    assert "stop_grabbing" not in rig.calls  # preexisting acquisition belongs to its caller
    saved = rig.controller._run_artifacts["h5"]
    with h5py.File(saved, "r") as handle:
        assert tuple(handle["raw_group_names"].asstr()[...]) == TRANCON_GROUPS
        np.testing.assert_allclose(handle["od"][...], np.log10(9.) / 2., atol=1e-14)
        assert len(handle["transport/accepted"]) == 6
        for order in rig.camera.orders.values():
            assert order["released"]
        # Canonical BG, Ie, I0 has independent detector values, not a UI spectrum fallback.
        np.testing.assert_array_equal(handle["raw_data"][0, :, 0], [[1, 1], [1, 1], [11, 11], [21, 21], [11, 11], [21, 21]])


def test_batch_similarity_rejects_before_RAW_commit_then_requests_only_remaining(rig):
    rig.controller._settings.update(delay_points_ps=[0., 1.])
    rig.profile["filters"]["similarity"] = {"enabled": True, "version": "trancon-python-batch-distance-v1",
        "threshold_ref_channel": 1., "mode": "python", "metric": "euclidean", "diff": 3.,
        "min_distance": -1., "from_pixel": 0, "to_pixel": 2}
    start(rig)
    state = finished(rig)
    assert state["run"]["status"] == "completed", state["run"]
    assert [r["frame_count"] for r in rig.camera.requests] == [6, 3, 6, 3]
    assert state["run"]["rejected_cycles"] == 2
    with h5py.File(rig.controller._run_artifacts["h5"], "r") as handle:
        assert len(handle["transport/accepted"]) == 4 and len(handle["transport/rejected"]) == 2
        np.testing.assert_array_equal(handle["frame_counts"], [2, 2])
        np.testing.assert_array_equal(handle["od"], 0.)


def test_ambiguous_background_is_retained_and_bounded_by_rejection_budget(rig):
    rig.camera.make_cycles = lambda count, point: [np.full((3, 2, 2), 20., np.float32) for _ in range(count)]
    start(rig)
    state = finished(rig)
    assert state["run"]["status"] == "fault"
    assert "rejection budget" in state["run"]["error"]
    assert len(rig.camera.requests) == 2
    assert state["run"]["artifacts"]["frame_counts"] == [0, 0, 0]
    with h5py.File(rig.controller._run_artifacts["h5"], "r") as handle:
        assert len(handle["transport/rejected"]) == 4
        assert not len(handle["transport/accepted"])


def test_checksum_failure_journals_original_packet_and_releases_only_after_flush(rig):
    rig.camera.bad_checksum = True
    start(rig)
    state = finished(rig)
    assert state["run"]["status"] == "fault"
    assert "checksum" in state["run"]["error"]
    order = next(iter(rig.camera.orders.values()))
    with h5py.File(rig.controller._run_artifacts["h5"], "r") as handle:
        rejected = next(iter(handle["transport/rejected"].values()))
        assert rejected["packet"][...].tobytes() == order["packet"]
        assert not handle["frame_counts"][...].any()
    assert order["released"]


def test_stop_cancels_pending_packet_continue_uses_child_and_keeps_parent_immutable(rig):
    rig.camera.block = True
    start(rig)
    assert rig.camera.entered.wait(2.)
    before = len(rig.camera.requests)
    for _ in range(3):
        assert rig.client.get("/api/pump-probe-v0/state").status_code == 200
    assert len(rig.camera.requests) == before
    stopped = rig.client.post("/api/pump-probe-v0/run", json={"running": False})
    assert stopped.status_code == 200
    state = finished(rig)
    assert state["run"]["status"] == "stopped" and state["run"]["resume_available"]
    parent = Path(rig.controller._resume_source["h5_path"])
    parent_id = rig.controller._resume_source["run_id"]
    parent_hash = hashlib.sha256(parent.read_bytes()).hexdigest()
    rig.camera.block = False
    start(rig, "continue")
    result = finished(rig)
    assert result["run"]["status"] == "completed", result["run"]
    assert result["run"]["artifacts"]["parent_run_id"] == parent_id
    assert hashlib.sha256(parent.read_bytes()).hexdigest() == parent_hash
    assert result["run"]["artifacts"]["frame_counts"] == [2, 2, 2]


@pytest.mark.parametrize("failure", ["profile", "approval", "stale", "output"])
def test_no_proxy_or_order_before_commissioning_exact_approval_and_plan_validation(rig, monkeypatch, failure):
    if failure == "profile":
        rig.profile["commissioned"] = False
    elif failure == "approval":
        monkeypatch.setattr(api, "require_http_hardware", lambda *a, **k: (jsonify({"success": False}), 428))
    elif failure == "stale":
        rig.payload["plan_fingerprint"] = "0" * 64
    else:
        rig.payload["save_path"] = str(rig.tmp.parent / "outside")
    response = rig.client.post("/api/pump-probe-v0/run", json=rig.payload)
    assert response.status_code in {400, 409, 428}
    assert rig.proxies == [] and rig.calls == []


def test_preview_is_pure_and_approval_receives_full_frozen_plan_before_worker(rig, monkeypatch):
    plan = rig.client.post("/api/pump-probe-v0/run/plan", json=rig.payload).get_json()
    assert rig.proxies == [] and rig.calls == []
    approved = []

    def guard(action, targets, args, **kwargs):
        assert rig.proxies == []
        assert action == "v0.run"
        assert targets == plan["authorization"]["targets"]
        assert args == plan["authorization"]["args"]
        assert args["output_context"]["output_dir"] == str(rig.tmp)
        approved.append(args["fingerprint"])

    monkeypatch.setattr(api, "require_http_hardware", guard)
    start(rig)
    assert finished(rig)["run"]["status"] == "completed"
    assert approved == [plan["fingerprint"]]


def test_config_change_with_same_axis_rejects_before_RAW_orders(rig):
    rig.camera.config_fingerprint = "d" * 64
    start(rig)
    state = finished(rig)
    assert state["run"]["status"] == "fault"
    assert "commissioned" in state["run"]["error"]
    assert rig.camera.requests == [] and rig.moves == []


def test_commissioned_SDK_dtype_mismatch_preserves_packet_without_RAW_commit(rig):
    rig.profile["expected_sample_dtype"] = "<u2"
    start(rig)
    state = finished(rig)
    assert state["run"]["status"] == "fault" and "SDK sample dtype" in state["run"]["error"]
    assert state["run"]["artifacts"]["frame_counts"] == [0, 0, 0]
    assert next(iter(rig.camera.orders.values()))["released"]
    with h5py.File(rig.controller._run_artifacts["h5"], "r") as handle:
        assert len(handle["transport/rejected"]) == 1
        assert next(iter(handle["transport/rejected"].values()))["packet"][...].tobytes() == next(iter(rig.camera.orders.values()))["packet"]


@pytest.mark.parametrize("fault", ["start", "begin"])
def test_uncertain_rpc_reply_retains_owned_cleanup_and_original_packet(rig, fault):
    if fault == "start":
        rig.camera.active = False
        rig.camera.start_timeout = True
    else:
        rig.camera.begin_timeout = True
    start(rig)
    state = finished(rig)
    assert state["run"]["status"] == "fault"
    if fault == "start":
        assert "stop_grabbing" in rig.calls and not rig.camera.active
    else:
        assert rig.calls.count("V0BeginOrder") == 2
        assert len(rig.camera.requests) == 1
        assert next(iter(rig.camera.orders.values()))["released"]
        with h5py.File(rig.controller._run_artifacts["h5"], "r") as handle:
            assert len(handle["transport/rejected"]) == 1


def test_cleanup_storage_failure_always_signals_done_and_retains_camera_packet(rig, monkeypatch):
    rig.camera.block = True
    start(rig)
    assert rig.camera.entered.wait(2.)
    monkeypatch.setattr(api.V0TangoRunWriter, "record_rejected_transport",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    rig.controller.set_running(False)
    state = finished(rig)
    assert state["run"]["status"] == "fault"
    assert "disk full" in state["run"]["error"]
    assert not next(iter(rig.camera.orders.values()))["released"]
    with pytest.raises(RuntimeError, match="cleanup failed"):
        rig.controller.wait_for_tango_cleanup()
    with pytest.raises(RuntimeError, match="unresolved"):
        rig.controller.prepare_tango_run(rig.payload)


def test_manual_delay_and_sample_motion_blocked_until_cleanup_finishes(rig):
    rig.controller._tango_stop_event = threading.Event()
    rig.controller._tango_done_event.clear()
    rig.controller._running = False
    with pytest.raises(RuntimeError):
        rig.controller.move_stage({"position_mm": 1.})
    with pytest.raises(RuntimeError):
        rig.controller.move_sample_stage({"position_mm": 1.})
    assert rig.proxies == []
    rig.controller._tango_stop_event = None
    rig.controller._tango_done_event.set()


def test_continue_replays_partial_point_without_mutating_parent_or_reordering_shots(rig):
    waiting = threading.Event()

    def measured(count, point):
        if len(rig.camera.requests) == 1:
            return [triplet(), np.full((3, 2, 2), 20., np.float32)]
        rig.camera.block = True
        waiting.set()
        return [triplet(9.) for _ in range(count)]

    rig.camera.make_cycles = measured
    start(rig)
    assert waiting.wait(2.)
    rig.controller.set_running(False)
    stopped = finished(rig)
    assert stopped["run"]["artifacts"]["frame_counts"] == [1, 0, 0]
    source = copy.deepcopy(rig.controller._resume_source)
    parent = Path(source["h5_path"])
    original = parent.read_bytes()
    rig.camera.block = False
    rig.camera.make_cycles = lambda count, point: [triplet(9.) for _ in range(count)]
    start(rig, "continue")
    state = finished(rig)
    assert state["run"]["status"] == "completed", state["run"]
    assert rig.camera.requests[2]["frame_count"] == 3
    assert parent.read_bytes() == original
    with h5py.File(rig.controller._run_artifacts["h5"], "r") as child:
        np.testing.assert_allclose(child["od"][:, 0], np.log10(9.) / 2., atol=1e-14)
        assert child["metadata/parent_run_id"].asstr()[()] == source["run_id"]
        np.testing.assert_array_equal(child["raw_data"][0, 4, 0], [11, 11])
        np.testing.assert_array_equal(child["raw_data"][0, 4, 1], [91, 91])


def test_cancel_between_RAW_commits_retains_whole_original_batch_without_late_counts(rig, monkeypatch):
    original_record = api.V0TangoRunWriter.record_tango_cycle

    def commit_then_stop(writer, *args, **kwargs):
        result = original_record(writer, *args, **kwargs)
        rig.controller._request_tango_stop_locked("aborted")
        return result

    monkeypatch.setattr(api.V0TangoRunWriter, "record_tango_cycle", commit_then_stop)
    start(rig)
    state = finished(rig)
    assert state["run"]["status"] == "aborted"
    assert state["run"]["artifacts"]["frame_counts"] == [1, 0, 0]
    assert not state["run"]["resume_available"]
    with h5py.File(rig.controller._run_artifacts["h5"], "r") as saved:
        assert len(saved["transport/accepted"]) == 1 and len(saved["transport/rejected"]) == 1
        packet = next(iter(saved["transport/rejected"].values()))["packet"][...].tobytes()
        assert packet == next(iter(rig.camera.orders.values()))["packet"]
    assert len(rig.camera.requests) == 1


def test_continue_rejects_changed_DG645_snapshot_without_any_device_probe(rig):
    rig.camera.block = True
    start(rig)
    assert rig.camera.entered.wait(2.)
    rig.controller.set_running(False)
    assert finished(rig)["run"]["resume_available"]
    rig.timing["snapshot"]["raw_queries"]["TRAT?"] = "10"
    rig.proxies.clear()
    rig.calls.clear()
    response = rig.client.post("/api/pump-probe-v0/run", json={**rig.payload, "run_action": "continue"})
    assert response.status_code == 400
    assert rig.proxies == [] and rig.calls == []


def test_fsync_failure_retains_original_camera_packet_and_faults(rig, monkeypatch):
    monkeypatch.setattr(api.V0TangoRunWriter, "flush_transport",
                        lambda *a: (_ for _ in ()).throw(OSError("flush failed")))
    start(rig)
    state = finished(rig)
    assert state["run"]["status"] == "fault"
    assert "flush failed" in state["run"]["error"]
    assert not next(iter(rig.camera.orders.values()))["released"]
    assert rig.controller._tango_done_event.is_set()


@pytest.mark.parametrize("dtype", ["<u2", "<i4", "<f4"])
def test_actual_device_order_book_packet_round_trip_to_backend_and_storage(rig, dtype):
    from DeviceServers.cameras.andor.v0_orders import V0Orders
    from pump_probe_v0_tango import decode_tango_batch

    config = {"trigger_mode": "ext", "read_mode": "multi_track", "acquisition_mode": "cont",
              "track_count": 2, "width": 2, "wavelengths": [500., 600.],
              "indexed_buffer_size": 1000, "axis_source": "configured_calibration"}
    book = V0Orders()
    book.new_epoch()
    caps = book.observe(config, True)
    order = book.begin({"request_id": "bridge", "run_id": "bridge-run", "point_index": 0,
                       "frame_count": 6, "acquisition_epoch": caps["acquisition_epoch"],
                       "expected_config_fingerprint": caps["config_fingerprint"]})

    class IndexedSDK:
        def __init__(self):
            self.frames = [np.zeros((2, 2), dtype=dtype) for _ in range(3)]
            self.cursor = 0

        def get_frames_status(self):
            return SimpleNamespace(acquired=len(self.frames), buffer_size=1000)

        def get_new_images_range(self):
            return (self.cursor, len(self.frames)) if self.cursor < len(self.frames) else None

        def read_multiple_images(self, *, rng, **kwargs):
            self.cursor = rng[1]
            return self.frames[rng[0]:rng[1]], rng

    sdk = IndexedSDK()
    book.pump(sdk)  # Discard old SDK samples, establish next-frame boundary=3.
    values = np.concatenate([triplet(), triplet(9.)]).astype(dtype)
    if dtype == "<i4":
        values[5, 0, 0] = 2**24 + 1
    sdk.frames.extend(values)
    book.pump(sdk)
    encoded = book.read(order["order_id"])
    batch = decode_tango_batch(encoded, order_id=order["order_id"], run_id="bridge-run", point_index=0,
              acquisition_epoch=caps["acquisition_epoch"], config_fingerprint=caps["config_fingerprint"],
              wavelengths=[500., 600.], background_level=10, cycle_count=2)
    assert len(batch.cycles) == 2 and not batch.rejected
    assert zlib.decompress(batch.packet) == values.tobytes()
    assert batch.cycles[0].metadata["source_sample_dtype"] == dtype
    assert batch.cycles[0].metadata["samples_rounded_to_sgl"] is (dtype == "<i4")
    plan = rig.controller._current_scan_plan_locked()
    writer = api.V0TangoRunWriter([500., 600.], plan.delays, plan.positions, 2,
                                  {"tango_profile": rig.profile}, plan=plan)
    try:
        for cycle in batch.cycles:
            writer.record_tango_cycle(0, cycle.frames, plan.positions[0], plan.positions[0], cycle.packet, cycle.metadata)
        writer.flush_transport()
        book.release(order["order_id"])
        saved = writer.finalize("stopped")
    finally:
        if not writer._closed:
            writer.finalize("fault")
    with h5py.File(saved["h5_path"], "r") as handle:
        records = list(handle["transport/accepted"].values())
        assert records[0]["packet"].id == records[1]["packet"].id
        assert records[0]["packet"][...].tobytes() == batch.packet
        assert handle["raw_data"].dtype == np.float32


def test_lost_release_reply_retries_only_release_after_durable_commit(rig):
    rig.camera.release_timeout = True
    start(rig)
    state = finished(rig)
    assert state["run"]["status"] == "fault"
    assert state["run"]["cleanup_errors"] == []
    assert rig.calls.count("V0ReleaseOrder") == 2
    assert rig.calls.count("V0ReadOrder") == 1
    assert "V0CancelOrder" not in rig.calls
    assert state["run"]["artifacts"]["frame_counts"] == [2, 0, 0]
    assert next(iter(rig.camera.orders.values()))["released"]


def test_manual_motion_readback_resumes_after_RAW_worker_cleanup(rig, monkeypatch):
    start(rig)
    assert finished(rig)["run"]["status"] == "completed"
    monkeypatch.setattr(rig.controller, "_read_tango_motion_state_locked",
                        api.PumpProbeV0Controller._read_tango_motion_state_locked.__get__(rig.controller))
    old_orders = len(rig.camera.requests)
    state = rig.controller.move_stage({"position_mm": 1.})
    assert state["position_mm"] == 1. and state["set_position_mm"] == 1.
    assert not state["stage_moving"]
    assert len(rig.camera.requests) == old_orders
