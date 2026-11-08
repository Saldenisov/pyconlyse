"""V0 packet/order contracts using an indexed fake camera; no Tango or SDK."""

import hashlib
import json
from importlib import import_module
from threading import RLock
from types import SimpleNamespace
import zlib

import numpy as np
import pytest

from DeviceServers.cameras.andor.v0_orders import (
    V0Orders, config_fingerprint, sdk_configuration_mutation,
)


def configuration(**changes):
    return {
        "trigger_mode": "ext", "read_mode": "multi_track", "acquisition_mode": "cont",
        "track_count": 2, "width": 3, "wavelengths": [500.000000001, 500.000000002, 500.000000001],
        "exposure_seconds": 0.001, "multi_track": [2, 1, 0], "amplifier": [0, 0, 0, 0],
        "axis_source": "configured_calibration", "indexed_buffer_size": 1000, **changes,
    }


class Camera:
    def __init__(self):
        self.frames = []
        self.read_index = 0
        self.overwritten_before = 0
        self.calls = []
        self.return_shift = 0
        self.config = configuration()
        self.active = True
        self.buffer_size = 1000

    def append(self, value):
        frame = np.asarray(value)
        self.frames.append(frame.copy())

    def get_frames_status(self):
        return SimpleNamespace(acquired=len(self.frames), buffer_size=self.buffer_size)

    def get_new_images_range(self):
        first = max(self.read_index, self.overwritten_before)
        return (first, len(self.frames)) if first < len(self.frames) else None

    def read_multiple_images(self, *, rng, return_rng, missing_frame):
        assert return_rng and missing_frame == "skip"
        self.calls.append(rng)
        first, end = rng
        first += self.return_shift
        self.read_index = end
        return [f.copy() for f in self.frames[first:end]], (first, end)

    def get_data_dimensions(self):
        return self.config["track_count"], self.config["width"]

    def get_trigger_mode(self):
        return self.config["trigger_mode"]

    def get_read_mode(self):
        return self.config["read_mode"]

    def get_acquisition_mode(self):
        return self.config["acquisition_mode"]

    def get_exposure(self):
        return self.config["exposure_seconds"]

    def get_multi_track_mode_parameters(self):
        return self.config["multi_track"]

    def get_amp_mode(self):
        return self.config["amplifier"]

    def acquisition_in_progress(self):
        return self.active


def frame(value):
    return np.full((2, 3), value, dtype=np.float32)


def admitted(**book_kwargs):
    book = V0Orders(**book_kwargs)
    epoch = book.new_epoch()
    config = configuration()
    capabilities = book.observe(config, True)
    assert capabilities["lossless"]
    return book, Camera(), {
        "request_id": "request-1", "run_id": "run-A", "point_index": 2, "frame_count": 3,
        "acquisition_epoch": epoch, "expected_config_fingerprint": config_fingerprint(config),
    }


def read(book, order_id):
    header, packet = book.read(order_id)
    metadata = json.loads(header)
    raw = zlib.decompress(packet)
    assert hashlib.sha256(raw).hexdigest() == metadata["payload_sha256"]
    return metadata, raw


def test_release_is_idempotent_after_lost_reply_and_does_not_remove_other_orders():
    book, camera, request = admitted()
    first = book.begin(request)["order_id"]
    book.cancel(first)
    book.release(first)
    second = book.begin({**request, "request_id": "request-2"})["order_id"]
    assert book.release(first)["already_absent"] is True
    assert book.status(second)["state"] == "queued"


def test_queued_registration_is_not_armed_and_worker_excludes_all_old_frames():
    book, camera, request = admitted()
    for i in range(4):
        camera.append(frame(i))
    queued = book.begin(request)
    assert queued["state"] == "queued" and not queued["armed"]
    assert queued["boundary_frame_id"] is None and camera.calls == []
    book.pump(camera)
    armed = book.status(queued["order_id"])
    assert armed["state"] == "capturing" and armed["armed"]
    assert armed["boundary_frame_id"] == 4 and camera.calls == [(0, 4)]
    for i in range(4, 7):
        camera.append(frame(i))
    book.pump(camera)
    header, raw = read(book, queued["order_id"])
    assert header["state"] == "complete" and header["frame_ids"] == [4, 5, 6]
    data = np.frombuffer(raw, dtype="<f4").reshape(header["shape"])
    np.testing.assert_array_equal(data[:, 0, 0], [4, 5, 6])


def test_packet_preserves_float32_bits_track_order_and_float64_repeated_axis():
    book, camera, request = admitted()
    request["frame_count"] = 1
    oid = book.begin(request)["order_id"]
    book.pump(camera)
    bits = np.array([0x80000000, 0x3f800001, 0x7fc00042, 0xff800000, 0, 0x7f800000], dtype="<u4")
    original = bits.view("<f4").reshape(2, 3)
    camera.append(original)
    book.pump(camera)
    camera.frames[0][:] = 999
    header, raw = read(book, oid)
    assert raw == original.tobytes(order="C")
    assert header["dtype"] == "<f4" and header["shape"] == [1, 2, 3]
    assert header["track_order"] == ["detector_I", "detector_II"]
    assert header["wavelengths"] == configuration()["wavelengths"]
    assert header["wavelengths"][0] != header["wavelengths"][1]
    assert header["phase_labels"] is None and header["sdk_timestamps"] is None
    assert "not exposure or trigger time" in header["timestamp_semantics"]


def test_partial_cancel_is_readable_rejected_packet_and_release_removes_identity():
    book, camera, request = admitted()
    oid = book.begin(request)["order_id"]
    book.pump(camera)
    camera.append(frame(9))
    book.pump(camera)
    status = book.cancel(oid)
    assert status["state"] == "cancelled" and status["frames_captured"] == 1
    header, raw = read(book, oid)
    assert header["error"]["code"] == "CANCELLED"
    assert header["shape"] == [1, 2, 3] and len(raw) == 24
    assert book.release(oid)["released"]
    with pytest.raises(KeyError):
        book.read(oid)


def test_possible_ring_overwrite_during_read_is_rejected_even_with_full_returned_array():
    book, camera, request = admitted()
    oid = book.begin(request)["order_id"]
    book.pump(camera)
    for i in range(3):
        camera.append(frame(i))
    camera.buffer_size = 2
    book.pump(camera)
    header, raw = read(book, oid)
    assert header["state"] == "failed"
    assert "FRAME_OVERWRITTEN_DURING_READ" in {entry["code"] for entry in header["violations"]}
    assert header["frame_ids"] == [None, None] and not header["frame_ids_verified"]
    assert raw == frame(0).tobytes() + frame(1).tobytes()


@pytest.mark.parametrize("mode,code", [("overwritten", "FRAME_GAP"), ("truncated", "FRAME_GAP"), ("extra", "EXTRA_FRAMES"), ("reset", "FRAME_COUNTER_RESET")])
def test_gaps_extra_and_counter_reset_fail_without_inventing_frames(mode, code):
    book, camera, request = admitted()
    if mode == "reset":
        camera.append(frame(-1))
    oid = book.begin(request)["order_id"]
    book.pump(camera)
    if mode == "reset":
        camera.frames.clear()
    else:
        for i in range(4 if mode == "extra" else 2):
            camera.append(frame(i))
        if mode == "overwritten":
            camera.overwritten_before = 1
        elif mode == "truncated":
            camera.return_shift = 1
    book.pump(camera)
    status = book.status(oid)
    assert status["state"] == "failed" and status["error"]["code"] == code
    header, raw = read(book, oid)
    ids = {"overwritten": [1], "truncated": [1], "extra": [0, 1, 2, 3], "reset": []}[mode]
    assert header["frame_ids"] == ids and header["shape"] == [len(ids), 2, 3]
    assert raw == b"".join(frame(i).tobytes() for i in ids)


@pytest.mark.parametrize("dtype", ["<u2", "<i4", "<f4", ">i4"])
def test_sdk_sample_dtype_is_preserved_without_sgl_rounding(dtype):
    book, camera, request = admitted()
    request["frame_count"] = 1
    oid = book.begin(request)["order_id"]
    book.pump(camera)
    values = [0, 1, 65535, 3, 4, 5] if dtype.endswith("u2") else [2**24 + 1, -(2**24 + 1), 7, 9, 11, 13]
    original = np.array(values, dtype=dtype).reshape(2, 3)
    camera.append(original)
    book.pump(camera)
    header, raw = read(book, oid)
    expected_dtype = np.dtype(dtype).newbyteorder("<")
    expected = original.astype(expected_dtype)
    assert header["state"] == "complete" and header["dtype"] == expected_dtype.str
    assert header["sample_encoding"] == "contiguous" and raw == expected.tobytes()
    assert header["source_sample_dtypes"] == [np.dtype(dtype).str]
    if expected_dtype.str == "<i4":
        decoded = np.frombuffer(raw, dtype="<i4")
        assert decoded[0] == 2**24 + 1 and decoded[0] != np.float32(decoded[0])


def test_mixed_and_unsupported_numeric_buffers_are_retained_as_failed_typed_segments():
    book, camera, request = admitted()
    oid = book.begin(request)["order_id"]
    book.pump(camera)
    originals = [np.full((2, 3), 2**24 + 1, dtype="<i4"), frame(1), np.full((2, 3), 0.123456789012345, dtype="<f8")]
    for original in originals:
        camera.append(original)
    book.pump(camera)
    header, raw = read(book, oid)
    assert header["state"] == "failed" and header["sample_encoding"] == "typed_segments-v1"
    assert header["dtype"] is None and header["shape"] is None
    assert {entry["code"] for entry in header["violations"]} >= {"MIXED_SAMPLE_DTYPES", "UNSUPPORTED_SAMPLE_DTYPE"}
    assert raw == b"".join(original.tobytes() for original in originals)
    assert [segment["dtype"] for segment in header["segments"]] == ["<i4", "<f4", "<f8"]
    assert [segment["offset"] for segment in header["segments"]] == [0, 24, 48]
    assert header["frame_ids"] == [0, 1, 2]


def test_bad_geometry_retains_returned_original_samples_without_rectangular_padding():
    book, camera, request = admitted()
    oid = book.begin(request)["order_id"]
    book.pump(camera)
    original = np.arange(4, dtype="<u2").reshape(2, 2)
    camera.append(original)
    book.pump(camera)
    header, raw = read(book, oid)
    assert header["error"]["code"] == "FRAME_SHAPE_CHANGED"
    assert header["sample_encoding"] == "typed_segments-v1" and raw == original.tobytes()
    assert header["segments"][0]["shape"] == [2, 2]


def test_unqualified_returned_range_retains_samples_but_does_not_fabricate_frame_ids():
    book, camera, request = admitted()
    oid = book.begin(request)["order_id"]
    book.pump(camera)
    camera.append(frame(8))
    original_read = camera.read_multiple_images
    def read_without_range(**kwargs):
        frames, _ = original_read(**kwargs)
        return frames, ("malformed",)
    camera.read_multiple_images = read_without_range
    book.pump(camera)
    header, raw = read(book, oid)
    assert header["error"]["code"] == "FRAME_GAP"
    assert header["frame_ids"] == [None] and not header["frame_ids_verified"]
    assert raw == frame(8).tobytes()


def test_post_read_status_failure_keeps_the_returned_sample_buffer():
    book, camera, request = admitted()
    oid = book.begin(request)["order_id"]
    book.pump(camera)
    camera.append(frame(8))
    original_read = camera.read_multiple_images
    def read_then_lose_status(**kwargs):
        result = original_read(**kwargs)
        camera.get_frames_status = lambda: (_ for _ in ()).throw(RuntimeError("status unavailable"))
        return result
    camera.read_multiple_images = read_then_lose_status
    book.pump(camera)
    header, raw = read(book, oid)
    assert header["error"]["code"] == "SDK_READ_ERROR" and raw == frame(8).tobytes()
    assert header["frame_ids"] == [None]


def test_excess_capture_is_bounded_and_omitted_sdk_range_is_explicit():
    book, camera, request = admitted(max_history_bytes=72)
    oid = book.begin(request)["order_id"]
    book.pump(camera)
    for i in range(6):
        camera.append(frame(i))
    book.pump(camera)
    header, raw = read(book, oid)
    assert header["state"] == "failed" and header["error"]["code"] == "EXTRA_FRAMES"
    assert header["capture_truncated"] and header["capture_byte_limit"] == 72
    assert header["observed_ranges"][0]["readable"] == [0, 6]
    assert header["observed_ranges"][0]["requested"] == [0, 3]
    assert len(raw) == 72 and header["frame_ids"] == [0, 1, 2]


def test_retained_byte_history_requires_explicit_release():
    book, camera, request = admitted(max_history_bytes=72)
    oid = book.begin(request)["order_id"]
    book.pump(camera)
    camera.append(frame(4))
    book.pump(camera)
    book.cancel(oid)
    with pytest.raises(ValueError, match="retained-byte limit"):
        book.begin(request | {"request_id": "other"})
    book.release(oid)
    assert book.begin(request | {"request_id": "other"})["state"] == "queued"


def test_six_hundred_fresh_sdk_frames_fit_and_later_triggers_are_not_reassigned():
    book, camera, request = admitted()
    request["frame_count"] = 600
    oid = book.begin(request)["order_id"]
    book.pump(camera)
    for i in range(600):
        camera.append(np.full((2, 3), i, dtype="<u2"))
    book.pump(camera)
    header, raw = read(book, oid)
    assert header["state"] == "complete" and header["shape"] == [600, 2, 3]
    assert header["frame_ids"] == list(range(600)) and len(raw) == 600 * 2 * 3 * 2
    camera.append(np.full((2, 3), 600, dtype="<u2"))
    assert book.pump(camera) == []
    assert read(book, oid)[1] == raw


def test_pointer_objects_are_not_exposed_as_scientific_payload_bytes():
    book, camera, request = admitted()
    oid = book.begin(request)["order_id"]
    book.pump(camera)
    camera.append(np.full((2, 3), "not numeric", dtype=object))
    book.pump(camera)
    header, raw = read(book, oid)
    assert header["state"] == "failed" and header["error"]["code"] == "UNSUPPORTED_SAMPLE_DTYPE"
    assert raw == b"" and header["unretained_samples"][0]["frame_id"] == 0


def test_idempotency_overlap_release_and_retained_history_are_bounded():
    book, camera, request = admitted(max_orders=1)
    original = book.begin(request)
    assert book.begin(dict(request)) == original
    with pytest.raises(ValueError, match="reused"):
        book.begin(request | {"point_index": 3})
    with pytest.raises(ValueError, match="active"):
        book.begin(request | {"request_id": "other"})
    with pytest.raises(ValueError, match="Cancel or finish"):
        book.release(original["order_id"])
    book.cancel(original["order_id"])
    with pytest.raises(ValueError, match="retained-order limit"):
        book.begin(request | {"request_id": "other"})
    book.release(original["order_id"])
    assert book.begin(request | {"request_id": "other"})["state"] == "queued"


def test_timeout_without_incoming_images_retains_partial_packet():
    now = [0.0]
    book, camera, request = admitted(clock=lambda: now[0], timeout=1)
    oid = book.begin(request)["order_id"]
    book.pump(camera)
    now[0] = 2
    assert book.status(oid)["error"]["code"] == "ORDER_TIMEOUT"
    assert read(book, oid)[0]["state"] == "failed"


@pytest.mark.parametrize("change", [{"trigger_mode": "int"}, {"read_mode": "image"}, {"track_count": 4}, {"acquisition_mode": "accum"}, {"wavelengths": [1, 2]}, {"axis_source": "pixel_index"}, {"axis_source": "unavailable"}])
def test_non_qualifying_camera_configuration_never_advertises_lossless(change):
    book = V0Orders()
    book.new_epoch()
    assert not book.observe(configuration(**change), True)["lossless"]


def test_epoch_config_and_stale_request_reject_mix_across_camera_changes():
    book, camera, request = admitted()
    with pytest.raises(ValueError, match="Stale"):
        book.begin(request | {"acquisition_epoch": "old"})
    oid = book.begin(request)["order_id"]
    book.observe(configuration(exposure_seconds=0.5), True)
    assert book.status(oid)["error"]["code"] == "CONFIG_CHANGED"
    header, _ = read(book, oid)
    assert header["configuration"]["exposure_seconds"] == 0.001
    book.new_epoch()
    assert book.epoch != request["acquisition_epoch"]
    assert not book.capabilities()["lossless"]


def test_configuration_guard_invalidates_before_sdk_write_and_holds_same_lock():
    book, camera, request = admitted()
    oid = book.begin(request)["order_id"]
    lock = RLock()
    class Device:
        _v0_orders = book
        _get_lifecycle_lock = lambda self: lock

        @sdk_configuration_mutation
        def change(self):
            assert lock._is_owned()
            assert book.status(oid)["state"] == "failed"
    Device().change()


andor_device = import_module("DeviceServers.cameras.andor.DS_ANDOR_CCD")


def device_methods(*names):
    methods = {}
    for name in names:
        method = getattr(andor_device.DS_ANDOR_CCD, name)
        methods[name] = getattr(method, "__wrapped__", method)
    return methods



def test_actual_device_hook_uses_indexed_nonblocking_reads_under_sdk_guard():
    book, camera, request = admitted()
    methods = device_methods("_v0_configuration", "_v0_worker_tick", "V0Capabilities", "V0BeginOrder", "V0ReadOrder")
    lock = RLock()
    device = SimpleNamespace(camera=camera, abort=False, _v0_orders=book,
                             _v0_wavelengths=np.array(configuration()["wavelengths"]),
                             _v0_axis_source="configured_calibration", _get_lifecycle_lock=lambda: lock,
                             _v0_refresh_calibration=lambda width: None,
                             _consume_frame_for_orders=lambda f: None)
    device._v0_configuration = lambda: methods["_v0_configuration"](device)
    capabilities = json.loads(methods["V0Capabilities"](device))
    assert capabilities["lossless"] and capabilities["external_trigger"]
    request["expected_config_fingerprint"] = capabilities["config_fingerprint"]
    oid = json.loads(methods["V0BeginOrder"](device, json.dumps(request)))["order_id"]
    camera.append(frame(-4))
    original_read = camera.read_multiple_images
    def guarded_read(**kwargs):
        assert lock._is_owned()
        return original_read(**kwargs)
    camera.read_multiple_images = guarded_read
    methods["_v0_worker_tick"](device)
    for i in range(3):
        camera.append(frame(i))
    methods["_v0_worker_tick"](device)
    header, packet = methods["V0ReadOrder"](device, oid)
    assert json.loads(header)["frame_ids"] == [1, 2, 3]
    np.testing.assert_array_equal(device.last_image, frame(2))
    assert len(zlib.decompress(packet)) == 3 * 2 * 3 * 4


def test_actual_device_capabilities_fail_closed_when_camera_is_unavailable():
    book = V0Orders()
    methods = device_methods("_v0_configuration", "V0Capabilities")
    device = SimpleNamespace(camera=None, _v0_orders=book, _get_lifecycle_lock=RLock)
    device._v0_configuration = lambda: methods["_v0_configuration"](device)
    capabilities = json.loads(methods["V0Capabilities"](device))
    assert not capabilities["lossless"] and not capabilities["acquisition_active"]
    assert capabilities["admission_error"] == "Camera is not opened"
    assert capabilities["configuration_fresh"] is False


def test_actual_worker_does_not_block_stop_join_when_lifecycle_lock_is_busy():
    methods = device_methods("_v0_worker_tick")
    class BusyLock:
        def acquire(self, *, timeout):
            assert timeout == 0.05
            return False
    device = SimpleNamespace(_get_lifecycle_lock=BusyLock)
    methods["_v0_worker_tick"](device)


def test_stopped_camera_reports_fresh_trigger_geometry_but_does_not_admit_order():
    book, camera, request = admitted()
    camera.active = False
    camera.buffer_size = 0
    methods = device_methods("_v0_configuration", "V0Capabilities")
    device = SimpleNamespace(camera=camera, abort=False, _v0_orders=book,
                             _v0_wavelengths=np.array(configuration()["wavelengths"]),
                             _v0_refresh_calibration=lambda width: None,
                             _v0_axis_source="configured_calibration", _get_lifecycle_lock=RLock)
    device._v0_configuration = lambda: methods["_v0_configuration"](device)
    caps = json.loads(methods["V0Capabilities"](device))
    assert caps["external_trigger"] and caps["track_count"] == 2 and caps["configuration_fresh"]
    assert not caps["lossless"] and not caps["acquisition_active"]
    with pytest.raises(ValueError, match="not active"):
        book.begin(request)


def test_sampling_fingerprint_excludes_only_transient_buffer_allocation():
    config = configuration()
    assert config_fingerprint(config) == config_fingerprint(config | {"indexed_buffer_size": 0})
    assert config_fingerprint(config) != config_fingerprint(config | {"multi_track": [2, 2, 0]})
    assert config_fingerprint(config) != config_fingerprint(config | {"amplifier": [0, 0, 0, 1]})


def calibrated_device(book, camera, methods, path=""):
    device = SimpleNamespace(camera=camera, abort=False, _v0_orders=book,
                             _v0_wavelengths=np.array(configuration()["wavelengths"]),
                             _v0_axis_source="configured_calibration", _get_lifecycle_lock=RLock,
                             wavelengths=repr(configuration()["wavelengths"]), wavelengths_file=str(path),
                             linked_spectrograph_ds="", _coerce_str=lambda value, default: str(value or default),
                             _consume_frame_for_orders=lambda f: None)
    device._parse_array_property = lambda value, **kwargs: methods["_parse_array_property"](device, value, **kwargs)
    device._v0_refresh_calibration = lambda width: methods["_v0_refresh_calibration"](device, width)
    device._v0_configuration = lambda: methods["_v0_configuration"](device)
    return device


def test_queued_arm_reads_calibration_again_and_rejects_changed_axis(tmp_path):
    book, camera, request = admitted()
    methods = device_methods("_parse_array_property", "_v0_refresh_calibration", "_v0_configuration", "V0Capabilities", "_v0_worker_tick")
    path = tmp_path / "wavelengths.txt"
    path.write_text("\n".join(format(value, ".17g") for value in configuration()["wavelengths"]), encoding="utf-8")
    device = calibrated_device(book, camera, methods, path)
    caps = json.loads(methods["V0Capabilities"](device))
    assert caps["wavelengths"] == configuration()["wavelengths"]
    request["expected_config_fingerprint"] = caps["config_fingerprint"]
    oid = book.begin(request)["order_id"]
    assert book.needs_arm()
    path.write_text("510\n511\n512\n", encoding="utf-8")
    methods["_v0_worker_tick"](device)
    assert book.status(oid)["error"]["code"] == "CONFIG_CHANGED" and camera.calls == []
    assert not book.status(oid)["armed"] and not book.needs_arm()
    assert read(book, oid)[0]["wavelengths"] == configuration()["wavelengths"]


@pytest.mark.parametrize("contents", [None, "1\n2\n", "1\nnan\n3\n"])
def test_v0_calibration_does_not_fall_back_from_bad_file_to_valid_property(tmp_path, contents):
    book, camera, request = admitted()
    methods = device_methods("_parse_array_property", "_v0_refresh_calibration", "_v0_configuration", "V0Capabilities")
    path = tmp_path / "wavelengths.txt"
    if contents is not None:
        path.write_text(contents, encoding="utf-8")
    device = calibrated_device(book, camera, methods, path)
    caps = json.loads(methods["V0Capabilities"](device))
    assert not caps["lossless"] and not caps["configuration_fresh"]
    assert caps["admission_error"]


def test_optional_sampling_geometry_and_gain_are_in_fresh_configuration_fingerprint():
    methods = device_methods("_v0_configuration")
    camera = Camera()
    camera.get_roi = lambda: (0, 3, 0, 20, 1, 2)
    camera.get_EMCCD_gain = lambda: (30, False)
    camera.get_vsspeed = lambda: 2
    camera.get_hsspeed = lambda: 1
    camera.get_image_indexing = lambda: "rcb"
    device = SimpleNamespace(camera=camera, abort=False, _v0_wavelengths=np.array(configuration()["wavelengths"]),
                             _v0_axis_source="configured_calibration")
    before, _ = methods["_v0_configuration"](device)
    camera.get_EMCCD_gain = lambda: (31, False)
    after, _ = methods["_v0_configuration"](device)
    assert before["image_mode_roi"]["value"] == (0, 3, 0, 20, 1, 2)
    assert before["emccd_gain"] == {"method_present": True, "value": (30, False)}
    assert config_fingerprint(before) != config_fingerprint(after)


def test_camera_axis_parser_preserves_dbl_values_without_changing_legacy_sgl_default():
    methods = device_methods("_parse_array_property")
    device = SimpleNamespace()
    raw = "[500.000000001, 500.000000002, 500.000000001]"
    old = methods["_parse_array_property"](device, raw)
    precise = methods["_parse_array_property"](device, raw, dtype=np.float64)
    assert old.dtype == np.float32 and old[0] == old[1]
    assert precise.dtype == np.float64 and precise[0] != precise[1]
    assert precise[0] == precise[2]


def test_camera_factory_binds_the_loaded_sdk_unsupported_exception_without_opening_another_camera(monkeypatch):
    methods = device_methods("_create_camera")
    class UnsupportedOption(Exception):
        pass
    calls = []
    camera = object()
    def create(**kwargs):
        calls.append(kwargs)
        return camera
    monkeypatch.setattr(
        andor_device, "get_andor_module",
        lambda **kwargs: SimpleNamespace(
            AndorNotSupportedError=UnsupportedOption, AndorSDK2Camera=create,
        ),
    )
    device = SimpleNamespace(dll_path="configured-sdk", ini_path="configured-ini", camera_index=0,
                             default_temperature=-50, fan_mode="full",
                             _coerce_str=lambda v, fallback: str(v or fallback),
                             _coerce_int=lambda v, fallback: int(v))
    assert methods["_create_camera"](device) is camera
    assert device._andor_not_supported_errors == (UnsupportedOption,)
    assert len(calls) == 1 and calls[0]["idx"] == 0


def test_non_EM_camera_reports_fresh_idle_configuration_with_explicit_unsupported_gain():
    methods = device_methods("_v0_configuration", "V0Capabilities")
    class UnsupportedOption(Exception):
        pass
    camera = Camera()
    camera.active = False
    camera.buffer_size = 0
    message = "option get.AC_GETFUNCTION_EMCCDGAIN is not supported by DU920_BV"
    def gain():
        raise UnsupportedOption(message)
    camera.get_EMCCD_gain = gain
    device = SimpleNamespace(camera=camera, abort=False, _v0_orders=V0Orders(),
                             _v0_wavelengths=np.array(configuration()["wavelengths"]),
                             _v0_refresh_calibration=lambda width: None,
                             _v0_axis_source="configured_calibration", _get_lifecycle_lock=RLock,
                             _andor_not_supported_errors=(UnsupportedOption,))
    device._v0_configuration = lambda: methods["_v0_configuration"](device)
    caps = json.loads(methods["V0Capabilities"](device))
    assert caps["configuration_fresh"] and not caps["acquisition_active"]
    assert not caps["lossless"] and "not active" in caps["admission_error"]
    gain = caps["configuration"]["emccd_gain"]
    assert gain == {"method_present": True, "value": None, "unsupported": True, "reason": message}
    assert caps["config_fingerprint"] == config_fingerprint(caps["configuration"])
    zero_gain = caps["configuration"] | {"emccd_gain": {"method_present": True, "value": 0}}
    assert caps["config_fingerprint"] != config_fingerprint(zero_gain)
    assert camera.calls == []


@pytest.mark.parametrize("message", ["SDK communication failed", "option EMCCDGAIN is not supported by DU920_BV"])
def test_optional_gain_runtime_errors_still_invalidate_configuration_freshness(message):
    methods = device_methods("_v0_configuration", "V0Capabilities")
    class UnsupportedOption(Exception):
        pass
    camera = Camera()
    def gain():
        raise RuntimeError(message)
    camera.get_EMCCD_gain = gain
    device = SimpleNamespace(camera=camera, abort=False, _v0_orders=V0Orders(),
                             _v0_wavelengths=np.array(configuration()["wavelengths"]),
                             _v0_refresh_calibration=lambda width: None,
                             _v0_axis_source="configured_calibration", _get_lifecycle_lock=RLock,
                             _andor_not_supported_errors=(UnsupportedOption,))
    device._v0_configuration = lambda: methods["_v0_configuration"](device)
    caps = json.loads(methods["V0Capabilities"](device))
    assert not caps["configuration_fresh"] and not caps["lossless"]
    assert caps["admission_error"] == message
    assert camera.calls == []
