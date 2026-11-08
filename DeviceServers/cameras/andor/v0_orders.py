"""Bounded, indexed V0 orders. No Tango, SDK loading, or phase inference.

The device worker calls ``pump`` under its short SDK/lifecycle guard. Commands
only enqueue/cancel requests; registration is not an acquisition barrier until
the worker publishes ``armed=True`` and an SDK counter watermark.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import OrderedDict
from functools import wraps
from threading import RLock
from time import monotonic, time_ns
from uuid import uuid4
import zlib

import numpy as np


SCHEMA = "andor-v0-raw-order-v1"
TRACK_ORDER = ["detector_I", "detector_II"]
TERMINAL = {"complete", "cancelled", "failed"}
MAX_PACKET_BYTES = 128 * 1024 * 1024
MAX_HISTORY_BYTES = 4 * MAX_PACKET_BYTES
MAX_CAPTURE_FRAMES = 4096
SUPPORTED_SAMPLE_DTYPES = ("<u2", "<i4", "<f4")


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def config_fingerprint(configuration):
    # Buffer allocation changes between stopped/active acquisition. It remains
    # an admission/read-safety check, not a sampling configuration parameter.
    sampling = {key: value for key, value in configuration.items() if key != "indexed_buffer_size"}
    return hashlib.sha256(canonical_json(sampling).encode("utf-8")).hexdigest()


def sdk_configuration_mutation(method):
    """Serialize configuration writes and reject any in-flight V0 packet first."""
    @wraps(method)
    def guarded(self, *args, **kwargs):
        with self._get_lifecycle_lock():
            book = getattr(self, "_v0_orders", None)
            if book is not None:
                book.invalidate("CONFIG_CHANGED", method.__name__)
            return method(self, *args, **kwargs)
    return guarded


class V0Orders:
    def __init__(self, *, max_orders=16, max_history_bytes=MAX_HISTORY_BYTES, timeout=100.0, clock=monotonic):
        self.lock = RLock()
        self.orders = OrderedDict()
        self.max_orders = max_orders
        self.max_history_bytes = int(max_history_bytes)
        self.timeout = timeout
        self.clock = clock
        self.epoch = None
        self.configuration = None
        self.fingerprint = None
        self.acquisition_active = False
        self.configuration_fresh = False
        self.admission_error = "No fresh camera configuration"

    def new_epoch(self):
        with self.lock:
            self.invalidate("ACQUISITION_CHANGED", "Camera acquisition restarted")
            self.epoch = uuid4().hex
            self.acquisition_active = False
            self.configuration = None
            self.fingerprint = None
            self.configuration_fresh = False
            self.admission_error = "No fresh camera configuration for this acquisition epoch"
            return self.epoch

    def _expire(self):
        now = self.clock()
        for order in self.orders.values():
            if order["state"] not in TERMINAL and now >= order["deadline"]:
                self._fail(order, "ORDER_TIMEOUT", "Order deadline elapsed")

    def invalidate(self, code, message):
        with self.lock:
            for order in self.orders.values():
                if order["state"] not in TERMINAL:
                    self._fail(order, code, message)

    def observe(self, configuration, active):
        with self.lock:
            self._expire()
            fingerprint = config_fingerprint(configuration)
            self.configuration = json.loads(canonical_json(configuration))
            self.configuration_fresh = True
            self.fingerprint = fingerprint
            self.acquisition_active = bool(active)
            errors = []
            if not active or not self.epoch:
                errors.append("Camera acquisition is not active")
            if configuration.get("trigger_mode") != "ext":
                errors.append("V0 requires external trigger mode ext")
            if configuration.get("read_mode") != "multi_track":
                errors.append("V0 requires multi_track read mode")
            if configuration.get("acquisition_mode") != "cont":
                errors.append("V0 requires continuous, non-accumulating acquisition")
            if configuration.get("track_count") != 2:
                errors.append("V0 requires exactly two detector tracks")
            if configuration.get("axis_source") not in {"linked_spectrograph", "configured_calibration"}:
                errors.append("V0 requires a calibrated wavelength axis")
            if configuration.get("indexed_buffer_size", 0) <= 0:
                errors.append("SDK indexed acquisition buffer is not allocated")
            width = configuration.get("width", 0)
            axis = configuration.get("wavelengths", [])
            if not isinstance(width, int) or width < 1 or len(axis) != width or not all(math.isfinite(v) for v in axis):
                errors.append("Wavelength axis does not match camera width")
            self.admission_error = "; ".join(errors) or None
            for order in self.orders.values():
                if order["state"] in TERMINAL:
                    continue
                if self.admission_error:
                    self._fail(order, "CAMERA_NOT_ADMITTED", self.admission_error)
                elif order["config_fingerprint"] != fingerprint or order["acquisition_epoch"] != self.epoch:
                    self._fail(order, "CONFIG_CHANGED", "Camera configuration or epoch changed")
            return self.capabilities()

    def unavailable(self, message):
        with self.lock:
            self.acquisition_active = False
            self.configuration_fresh = False
            self.admission_error = str(message)
            self.invalidate("CAMERA_UNAVAILABLE", str(message))
            return self.capabilities()

    def capabilities(self):
        with self.lock:
            self._expire()
            config = self.configuration or {}
            return {
                "schema": SCHEMA, "lossless": self.admission_error is None,
                "acquisition_epoch": self.epoch, "config_fingerprint": self.fingerprint,
                "acquisition_active": self.acquisition_active,
                "configuration_fresh": self.configuration_fresh,
                "external_trigger": config.get("trigger_mode") == "ext",
                "trigger_mode": config.get("trigger_mode"), "read_mode": config.get("read_mode"),
                "track_count": config.get("track_count"), "width": config.get("width"),
                "wavelengths": config.get("wavelengths", []), "track_order": list(TRACK_ORDER),
                "dtype": None, "supported_sample_dtypes": list(SUPPORTED_SAMPLE_DTYPES),
                "phase_labels": None, "configuration": config,
                "admission_error": self.admission_error,
                "max_packet_bytes": MAX_PACKET_BYTES, "max_retained_orders": self.max_orders,
                "max_history_bytes": self.max_history_bytes, "max_capture_frames": MAX_CAPTURE_FRAMES,
                "order_timeout_seconds": self.timeout,
            }

    def begin(self, request):
        keys = {"request_id", "run_id", "point_index", "frame_count", "acquisition_epoch", "expected_config_fingerprint"}
        if not isinstance(request, dict) or set(request) != keys:
            raise ValueError("V0BeginOrder requires exactly " + ", ".join(sorted(keys)))
        for key in ("request_id", "run_id", "acquisition_epoch", "expected_config_fingerprint"):
            if not isinstance(request[key], str) or not request[key] or len(request[key]) > 256:
                raise ValueError(f"Invalid {key}")
        for key in ("point_index", "frame_count"):
            if type(request[key]) is not int:
                raise ValueError(f"{key} must be an integer")
        if request["point_index"] < 0 or not 1 <= request["frame_count"] <= MAX_CAPTURE_FRAMES:
            raise ValueError("Invalid point_index or frame_count")
        with self.lock:
            self._expire()
            for order in self.orders.values():
                if order["request_id"] == request["request_id"]:
                    if order["request"] != request:
                        raise ValueError("request_id was reused with different parameters")
                    return self._status(order)
            if self.admission_error:
                raise ValueError(self.admission_error)
            if request["acquisition_epoch"] != self.epoch or request["expected_config_fingerprint"] != self.fingerprint:
                raise ValueError("Stale acquisition_epoch or expected_config_fingerprint")
            if any(order["state"] not in TERMINAL for order in self.orders.values()):
                raise ValueError("Another V0 order is active")
            width = self.configuration["width"]
            required = request["frame_count"] * 2 * width * 4
            if required > MAX_PACKET_BYTES:
                raise ValueError("Requested packet exceeds V0 byte limit")
            if len(self.orders) >= self.max_orders:
                raise ValueError("V0 retained-order limit reached; release terminal orders")
            available_bytes = self.max_history_bytes - sum(o["raw_bytes"] for o in self.orders.values())
            if required > available_bytes:
                raise ValueError("V0 retained-byte limit reached; release terminal orders")
            order = {
                **request, "request": dict(request), "order_id": uuid4().hex,
                "config_fingerprint": self.fingerprint, "configuration": self.configuration,
                "state": "queued", "armed": False, "boundary_frame_id": None,
                "frame_ids": [], "frames": [], "host_received_ns": [], "error": None,
                "source_sample_dtypes": [],
                "raw_bytes": 0, "capture_byte_limit": min(MAX_PACKET_BYTES, available_bytes),
                "capture_truncated": False, "observed_ranges": [], "unretained_samples": [],
                "violations": [],
                "deadline": self.clock() + self.timeout, "created_host_ns": time_ns(),
            }
            self.orders[order["order_id"]] = order
            return self._status(order)

    @staticmethod
    def _fail(order, code, message):
        order["state"] = "failed"
        order["error"] = {"code": code, "message": str(message)}

    @staticmethod
    def _status(order):
        return {key: order[key] for key in (
            "order_id", "request_id", "run_id", "point_index", "state", "armed", "frame_count",
            "acquisition_epoch", "config_fingerprint", "boundary_frame_id", "error",
        )} | {"schema": SCHEMA, "frames_captured": len(order["frames"]), "frame_ids": list(order["frame_ids"])}

    def status(self, order_id):
        with self.lock:
            self._expire()
            return self._status(self.orders[order_id])

    def cancel(self, order_id):
        with self.lock:
            self._expire()
            order = self.orders[order_id]
            if order["state"] not in TERMINAL:
                order["state"] = "cancelled"
                order["error"] = {"code": "CANCELLED", "message": "Cancelled by client; partial samples retained"}
            return self._status(order)

    def release(self, order_id):
        with self.lock:
            self._expire()
            if order_id not in self.orders:
                return {"schema": SCHEMA, "order_id": order_id, "released": True, "already_absent": True}
            order = self.orders[order_id]
            if order["state"] not in TERMINAL:
                raise ValueError("Cancel or finish the V0 order before release")
            del self.orders[order_id]
            return {"schema": SCHEMA, "order_id": order_id, "released": True}

    def has_active(self):
        with self.lock:
            self._expire()
            return any(order["state"] not in TERMINAL for order in self.orders.values())

    def needs_arm(self):
        with self.lock:
            self._expire()
            return any(order["state"] == "queued" for order in self.orders.values())

    @staticmethod
    def _retain_returned(order, frames, frame_ids):
        """Keep bounded returned numeric buffers without changing their values.

        A rejected packet may contain gaps, excess frames, mixed dtypes or wrong
        geometry. Typed diagnostic segments preserve these buffers; they cannot
        be mistaken for a complete homogeneous acquisition.
        """
        issues = []
        retained = []
        received = time_ns()
        for position, frame in enumerate(frames):
            try:
                source = np.asarray(frame)
            except Exception as exc:
                order["unretained_samples"].append({"frame_id": frame_ids[position], "reason": str(exc)})
                issues.append(("UNSUPPORTED_SAMPLE_DTYPE", "Returned object has no serializable numeric buffer"))
                continue
            descriptor = {"frame_id": frame_ids[position], "dtype": source.dtype.str,
                          "shape": list(source.shape), "nbytes": int(source.nbytes)}
            if source.dtype.fields is not None or source.dtype.kind not in "biufc" or source.dtype.itemsize > 16:
                order["unretained_samples"].append(descriptor | {"reason": "unsafe or unknown sample encoding"})
                issues.append(("UNSUPPORTED_SAMPLE_DTYPE", f"Cannot serialize {source.dtype} as numeric samples"))
                continue
            if len(order["frames"]) >= MAX_CAPTURE_FRAMES or order["raw_bytes"] + source.nbytes > order["capture_byte_limit"]:
                order["capture_truncated"] = True
                order["unretained_samples"].append(descriptor | {"reason": "capture byte/frame limit"})
                issues.append(("CAPTURE_LIMIT", "Returned samples exceed bounded retained-packet capacity"))
                continue
            array = np.array(source, order="C", copy=True)
            if array.dtype.byteorder == ">" or (array.dtype.byteorder == "=" and not np.little_endian):
                array = array.byteswap().view(array.dtype.newbyteorder("<"))
            array.setflags(write=False)
            order["frames"].append(array)
            order["source_sample_dtypes"].append(source.dtype.str)
            order["frame_ids"].append(frame_ids[position])
            order["host_received_ns"].append(received)
            order["raw_bytes"] += array.nbytes
            if array.dtype.str not in SUPPORTED_SAMPLE_DTYPES:
                issues.append(("UNSUPPORTED_SAMPLE_DTYPE", f"Unsupported complete-packet dtype {array.dtype.str}"))
            if array.shape != (2, order["configuration"]["width"]):
                issues.append(("FRAME_SHAPE_CHANGED", f"Unexpected frame shape {array.shape}"))
            if array.shape == (2, order["configuration"]["width"]) and array.dtype.str in SUPPORTED_SAMPLE_DTYPES:
                retained.append(array)
        if len({array.dtype.str for array in order["frames"]}) > 1:
            issues.append(("MIXED_SAMPLE_DTYPES", "SDK returned multiple sample dtypes in one order"))
        return retained, issues

    def pump(self, camera):
        """Nonblocking SDK calls only; caller owns SDK/lifecycle guard.

        SDK2/pylablib ranges are zero-based half-open SDK frame-counter IDs.
        They are not hardware trigger IDs or exposure timestamps.
        """
        with self.lock:
            self._expire()
            order = next((o for o in self.orders.values() if o["state"] not in TERMINAL), None)
            if order is None:
                return []
            try:
                if order["state"] == "queued":
                    boundary = int(camera.get_frames_status().acquired)
                    if boundary < 0:
                        raise ValueError("Invalid SDK acquired-frame counter")
                    old = camera.get_new_images_range()
                    if old is not None and old[0] < min(old[1], boundary):
                        # The boundary is the acquired-count snapshot, not the
                        # last image returned by a latest-only read.
                        camera.read_multiple_images(rng=(old[0], min(old[1], boundary)), return_rng=True, missing_frame="skip")
                    order["boundary_frame_id"] = boundary
                    order["armed"] = True
                    order["state"] = "capturing"
                    return []
                expected = order["boundary_frame_id"] + len(order["frames"])
                issues = []
                before = camera.get_frames_status()
                acquired = int(before.acquired)
                if acquired < expected:
                    issues.append(("FRAME_COUNTER_RESET", "SDK frame counter moved backwards"))
                requested = camera.get_new_images_range()
                if requested is None:
                    if acquired > expected:
                        issues.append(("FRAME_GAP", "SDK reports acquired frames without a readable range"))
                    if issues:
                        order["violations"].extend({"code": code, "message": message} for code, message in issues)
                        self._fail(order, *issues[0])
                    return []
                readable_first, end = map(int, requested)
                if end <= expected and not issues:
                    return []
                if readable_first > expected:
                    issues.append(("FRAME_GAP", f"Expected SDK frame {expected}, readable range starts at {readable_first}"))
                first = readable_first if acquired < expected else max(readable_first, expected)
                remaining = order["frame_count"] - len(order["frames"])
                if end - first > remaining:
                    issues.append(("EXTRA_FRAMES", f"SDK range contains {end-first} frames, expected at most {remaining}"))
                byte_budget = order["capture_byte_limit"] - order["raw_bytes"]
                read_slots = min(MAX_CAPTURE_FRAMES - len(order["frames"]),
                                 max(0, int(before.buffer_size)),
                                 max(0, byte_budget // (2 * order["configuration"]["width"] * 4)))
                read_end = min(end, first + read_slots)
                if read_end < end:
                    order["capture_truncated"] = True
                    issues.append(("CAPTURE_LIMIT", f"SDK range [{read_end},{end}) exceeds retained-packet capacity"))
                record = {"readable": [readable_first, end], "requested": [first, read_end],
                          "returned": None, "frame_ids_qualified": False}
                order["observed_ranges"].append(record)
                if read_end <= first:
                    order["violations"].extend({"code": code, "message": message} for code, message in issues)
                    self._fail(order, *(issues[0] if issues else ("CAPTURE_LIMIT", "No remaining capture capacity")))
                    return []
                frames, actual = camera.read_multiple_images(rng=(first, read_end), return_rng=True, missing_frame="skip")
                try:
                    actual = tuple(map(int, actual)) if actual is not None else None
                except (ValueError, TypeError, OverflowError):
                    actual = None
                frames = list(frames) if frames is not None else []
                record["returned"] = list(actual) if actual is not None else None
                qualified = (actual is not None and len(actual) == 2 and
                             first <= actual[0] <= actual[1] <= read_end and len(frames) == actual[1] - actual[0])
                if actual != (first, read_end) or len(frames) != read_end - first:
                    issues.append(("FRAME_GAP", "SDK returned a truncated or shifted frame range"))
                try:
                    after = camera.get_frames_status()
                    record["acquired_after"] = int(after.acquired)
                    record["buffer_size_after"] = int(after.buffer_size)
                    if int(after.acquired) < read_end:
                        issues.append(("FRAME_COUNTER_RESET", "SDK frame counter reset during read"))
                        qualified = False
                    # SDK2's adapter discards GetImages validfirst/last. Keep
                    # received buffers, but do not certify IDs after possible
                    # circular-buffer overwrite during the read.
                    if int(after.buffer_size) <= 0 or int(after.acquired) - int(after.buffer_size) > first:
                        issues.append(("FRAME_OVERWRITTEN_DURING_READ", "Requested SDK span no longer fits the camera ring buffer"))
                        qualified = False
                except Exception as exc:
                    issues.append(("SDK_READ_ERROR", f"Post-read status unavailable: {exc}"))
                    qualified = False
                record["frame_ids_qualified"] = qualified
                ids = list(range(actual[0], actual[1])) if qualified else [None] * len(frames)
                retained, sample_issues = self._retain_returned(order, frames, ids)
                issues.extend(sample_issues)
                if issues:
                    order["violations"].extend({"code": code, "message": message} for code, message in issues)
                    self._fail(order, *issues[0])
                elif len(order["frames"]) == order["frame_count"]:
                    order["state"] = "complete"
                return retained
            except Exception as exc:
                self._fail(order, "SDK_READ_ERROR", str(exc))
                return []

    def read(self, order_id):
        with self.lock:
            self._expire()
            order = self.orders[order_id]
            if order["state"] not in TERMINAL:
                raise ValueError("V0 order is not terminal")
            width = order["configuration"]["width"]
            shape = (len(order["frames"]), 2, width)
            dtypes = {array.dtype.str for array in order["frames"]}
            homogeneous = (len(dtypes) <= 1 and all(array.shape == (2, width) for array in order["frames"]) and
                           all(dtype in SUPPORTED_SAMPLE_DTYPES for dtype in dtypes))
            raw = b"".join(array.tobytes(order="C") for array in order["frames"])
            segments = []
            offset = 0
            if not homogeneous:
                for frame_id, array in zip(order["frame_ids"], order["frames"]):
                    segments.append({"frame_id": frame_id, "dtype": array.dtype.str,
                                     "shape": list(array.shape), "offset": offset, "nbytes": array.nbytes})
                    offset += array.nbytes
            metadata = self._status(order) | {
                "dtype": next(iter(dtypes)) if homogeneous and dtypes else None,
                "shape": list(shape) if homogeneous else None,
                "sample_encoding": "contiguous" if homogeneous else "typed_segments-v1", "segments": segments,
                "array_order": "C", "compression": "zlib", "sample_conversion": "none; byte-order normalization only",
                "source_sample_dtypes": list(order["source_sample_dtypes"]),
                "capture_byte_limit": order["capture_byte_limit"], "capture_truncated": order["capture_truncated"],
                "observed_ranges": order["observed_ranges"], "unretained_samples": order["unretained_samples"],
                "violations": order["violations"], "frame_ids_verified": all(i is not None for i in order["frame_ids"]),
                "wavelengths": order["configuration"]["wavelengths"], "track_order": list(TRACK_ORDER),
                "host_received_ns": list(order["host_received_ns"]), "created_host_ns": order["created_host_ns"],
                "timestamp_semantics": "host batch receipt; not exposure or trigger time",
                "frame_id_semantics": "zero-based SDK acquisition counter; not trigger ID",
                "phase_labels": None, "sdk_timestamps": None, "configuration": order["configuration"],
                "payload_sha256": hashlib.sha256(raw).hexdigest(), "uncompressed_bytes": len(raw),
            }
            return canonical_json(metadata), zlib.compress(raw)
