"""V0 Tango transport and source-derived, shot-level detector formation.

No Tango import or device construction occurs at import time. The caller
supplies an authorized proxy factory and a frozen run plan. Source detector II
selects the background using SUM(SGL frame) < BG_level; detector I follows its
index. Three-frame ambiguity is retained in the packet journal, never silently
paired with a different accelerator cycle.
"""

import ast
import hashlib
import json
import math
import time
import uuid
import zlib
from dataclasses import dataclass

import numpy as np


PACKET_SCHEMA = "andor-v0-raw-order-v1"
CLASSIFIER_VERSION = "trancon-clean-both-channels-sgl-v1"
TRACK_ORDER = ["detector_I", "detector_II"]


class AcquisitionCancelled(RuntimeError):
    pass


class TangoPacketError(ValueError):
    def __init__(self, message, packet=b"", metadata=None):
        super().__init__(message)
        self.packet = bytes(packet)
        self.metadata = metadata or {}


class RejectedCycle(TangoPacketError):
    """Measured packet rejected by explicit complete-cycle admission rules."""


def _json_object(value):
    if isinstance(value, dict):
        return value
    try:
        def invalid_constant(_value):
            raise ValueError("Tango JSON metadata must be finite")
        result = json.loads(value, parse_constant=invalid_constant)
    except (TypeError, ValueError):
        raise ValueError("Tango response must be a JSON object") from None
    if not isinstance(result, dict):
        raise ValueError("Tango response must be a JSON object")
    return result


def _integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _axis(values):
    if not isinstance(values, list) or not values:
        raise ValueError("Camera wavelength axis must be a nonempty array")
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in values):
        raise ValueError("Camera wavelength coordinates must be finite numbers")
    array = np.asarray(values, dtype=np.float64)
    if not np.isfinite(array).all():
        raise ValueError("Camera wavelength coordinates must be finite numbers")
    return array


def _mapping(background):
    return {"BG": background, "Ie": (background + 2) % 3, "I0": (background + 1) % 3}


def classify_trancon_cycle(frames, background_level, all_cycles=False):
    """Map one measured triplet to [BGI,BGII,IeI,IeII,I0I,I0II].

    The legacy SGL reduction/comparison is modeled explicitly. Near-threshold
    native SIMD/coercion rounding is not asserted equivalent. Exact-integer
    fixtures qualify the index/phase logic. All=True reproduces the documented
    source fallback quirk: II uses g=1 while its exported index for I is 0.
    All=False rejects the complete physical triplet, an explicit Web admission
    rule preventing unequal detector sequences from being paired later.
    """
    data = np.asarray(frames)
    if data.ndim != 3 or data.shape[:2] != (3, 2) or data.shape[2] == 0:
        raise ValueError("A detector cycle requires three frames x two tracks x wavelengths")
    if data.dtype != np.dtype("float32") or not np.isfinite(data).all():
        raise ValueError("Detector frames must contain finite original float32 samples")
    if not _integer(background_level) or not -(2**31) <= background_level < 2**31:
        raise ValueError("BG_level must be an I32 integer")
    if not isinstance(all_cycles, bool):
        raise ValueError("all_cycles must be boolean")
    # Source Add Array Elements has SGL input and output; keep the reduction
    # policy visible instead of silently replacing the threshold with argmin.
    with np.errstate(over="ignore", invalid="ignore"):
        sums = np.zeros(3, dtype=np.float32)
        for pixel in range(data.shape[2]):
            sums = np.add(sums, data[:, 1, pixel], dtype=np.float32)
    if not np.isfinite(sums).all():
        raise ValueError("Detector-II SGL sums overflowed")
    candidates = np.flatnonzero(sums < np.float32(background_level)).tolist()
    ambiguous = len(candidates) != 1
    details = {
        "version": CLASSIFIER_VERSION, "anchor_track": "detector_II",
        "background_level": background_level, "detector_II_sums": sums.tolist(),
        "background_candidates": candidates, "all_cycles": all_cycles,
        "ambiguous": ambiguous, "reduction": "sequential_float32_compare_float32_threshold",
        "native_rounding_equivalence": "not asserted near threshold",
        "invalid_triplet_policy": "reject_whole_physical_cycle",
    }
    if ambiguous and not all_cycles:
        raise RejectedCycle("Triplet does not contain exactly one background below BG_level", metadata={"classification": details})
    g = candidates[0] if not ambiguous else 0
    first = _mapping(g)
    second = _mapping(g) if not ambiguous else {"BG": 1, "Ie": 0, "I0": 2}
    phases = {"detector_I": first, "detector_II": second}
    details["source_fallback_quirk"] = ambiguous
    details["phase_mapping"] = phases
    groups = np.stack([data[first["BG"], 0], data[second["BG"], 1],
                       data[first["Ie"], 0], data[second["Ie"], 1],
                       data[first["I0"], 0], data[second["I0"], 1]])
    return groups, details


@dataclass(frozen=True)
class TangoCycle:
    frames: np.ndarray
    packet: bytes
    metadata: dict


@dataclass(frozen=True)
class TangoBatch:
    cycles: tuple
    rejected: tuple
    packet: bytes
    envelope: dict


def decode_tango_batch(encoded, *, order_id, run_id, point_index, acquisition_epoch,
                       config_fingerprint, wavelengths, background_level, all_cycles=False,
                       cycle_count=1):
    """Validate DevEncoded and retain the original compressed transport bytes."""
    if not isinstance(encoded, (tuple, list)) or len(encoded) != 2:
        raise TangoPacketError("V0ReadOrder must return DevEncoded(header, payload)")
    header, payload = encoded
    if not isinstance(header, str) or not isinstance(payload, (bytes, bytearray, memoryview)):
        raise TangoPacketError("Invalid DevEncoded header or payload type")
    packet = bytes(payload)
    preserved = {"raw_header": header}
    try:
        envelope = _json_object(header)
        preserved["source_envelope"] = envelope
        if envelope.get("schema") != PACKET_SCHEMA:
            raise ValueError("Unsupported Andor RAW packet schema")
        expected = {"order_id": order_id, "run_id": run_id, "point_index": point_index,
                    "acquisition_epoch": acquisition_epoch, "config_fingerprint": config_fingerprint}
        if any(envelope.get(key) != value for key, value in expected.items()):
            raise ValueError("RAW packet belongs to a different acquisition context")
        if not _integer(envelope.get("point_index")):
            raise ValueError("RAW point index must be an integer")
        if envelope.get("state") != "complete" or envelope.get("armed") is not True:
            raise ValueError("RAW order is incomplete or was not armed")
        sample_dtype = envelope.get("dtype")
        if sample_dtype not in {"<u2", "<i4", "<f4"} or envelope.get("array_order") != "C" or envelope.get("compression") != "zlib":
            raise ValueError("Unsupported RAW sample encoding")
        if envelope.get("phase_labels") is not None or envelope.get("track_order") != TRACK_ORDER:
            raise ValueError("RAW packet has incompatible detector semantics")
        axis = _axis(envelope.get("wavelengths"))
        expected_axis = np.asarray(wavelengths, dtype=np.float64)
        if axis.shape != expected_axis.shape or not np.array_equal(axis.view(np.uint64), expected_axis.view(np.uint64)):
            raise ValueError("RAW wavelength axis changed during acquisition")
        if not _integer(cycle_count) or not 1 <= cycle_count <= 200:
            raise ValueError("A RAW batch requires 1..200 detector cycles")
        frame_count = cycle_count * 3
        if envelope.get("frame_count") != frame_count or envelope.get("frames_captured") != frame_count:
            raise ValueError("RAW order frame counts disagree with the requested batch")
        shape = envelope.get("shape")
        if (not isinstance(shape, list) or not all(_integer(v) for v in shape)
                or shape != [frame_count, 2, len(axis)] or len(axis) > 16384):
            raise ValueError("RAW packet must contain exactly three two-track frames per requested cycle")
        frame_ids = envelope.get("frame_ids")
        if (not isinstance(frame_ids, list) or len(frame_ids) != frame_count
                or any(not _integer(v) or v < 0 for v in frame_ids)
                or frame_ids != list(range(frame_ids[0], frame_ids[0] + frame_count))):
            raise ValueError("RAW SDK frame sequence is incomplete")
        boundary = envelope.get("boundary_frame_id")
        if not _integer(boundary) or frame_ids[0] != boundary:
            raise ValueError("RAW frame sequence does not start at its armed SDK watermark")
        expected_length = frame_count * 2 * len(axis) * np.dtype(sample_dtype).itemsize
        decoder = zlib.decompressobj()
        samples = decoder.decompress(packet, expected_length + 1)
        if (len(samples) != expected_length or not decoder.eof
                or decoder.unused_data or decoder.unconsumed_tail):
            raise ValueError("RAW packet has invalid compressed length or trailing data")
        if hashlib.sha256(samples).hexdigest() != envelope.get("payload_sha256"):
            raise ValueError("RAW payload checksum mismatch")
        data = np.frombuffer(samples, dtype=sample_dtype).reshape(shape)
        if not np.isfinite(data).all():
            raise ValueError("RAW detector samples must be finite")
        # Original SDK values remain byte-exact in packet; canonical source
        # arithmetic uses SGL just as the inspected TRANCON detector does.
        canonical_data = np.asarray(data, dtype=np.float32)
        base = {
            **preserved, "source_order_id": order_id,
            "acquisition_epoch": acquisition_epoch, "config_fingerprint": config_fingerprint,
            "track_order": list(TRACK_ORDER), "packet_sha256": hashlib.sha256(packet).hexdigest(),
            "source_sample_dtype": sample_dtype, "canonical_sample_dtype": "<f4",
            "canonicalization": "TRANCON_SGL; original SDK bytes retained in transport packet",
            "samples_rounded_to_sgl": bool(np.any(data.astype(np.float64) != canonical_data.astype(np.float64))),
        }
        cycles, rejected = [], []
        for index in range(cycle_count):
            metadata = {**base, "packet_cycle_index": index, "frame_indices": frame_ids[3*index:3*index+3]}
            try:
                groups, classification = classify_trancon_cycle(canonical_data[3*index:3*index+3], background_level, all_cycles)
            except RejectedCycle as exc:
                rejected.append(RejectedCycle(str(exc), packet, {**metadata, **exc.metadata}))
            else:
                metadata.update(phase_mapping=classification["phase_mapping"], classification=classification)
                cycles.append(TangoCycle(groups, packet, metadata))
        return TangoBatch(tuple(cycles), tuple(rejected), packet, envelope)
    except RejectedCycle as exc:
        raise RejectedCycle(str(exc), packet, {**preserved, **exc.metadata}) from exc
    except (TypeError, ValueError, OverflowError, zlib.error) as exc:
        raise TangoPacketError(str(exc), packet, preserved) from exc


def decode_tango_cycle(encoded, **context):
    batch = decode_tango_batch(encoded, **context)
    if batch.rejected:
        raise batch.rejected[0]
    return batch.cycles[0]


def _dict_attribute(value):
    if isinstance(value, dict):
        return value
    try:
        parsed = ast.literal_eval(str(value))
    except (ValueError, SyntaxError):
        raise ValueError("OWIS attribute is not a dictionary") from None
    if not isinstance(parsed, dict):
        raise ValueError("OWIS attribute is not a dictionary")
    return parsed


class TangoRawAdapter:
    """Bounded device I/O, executed only by the authorized scan worker."""

    def __init__(self, plan, proxy_factory, stop_event, *, monotonic=time.monotonic,
                 on_motion=None, on_order=None):
        self.plan, self.proxy_factory, self.stop_event = plan, proxy_factory, stop_event
        self.profile, self.hardware = plan.profile, plan.hardware_config
        self.monotonic = monotonic
        self.on_motion = on_motion or (lambda *_args: None)
        self.on_order = on_order or (lambda *_args: None)
        self.camera = self.stage = self.dg645 = None
        self.capabilities = None
        self.pending_order = None
        self.pending_request = None
        self.pending_journaled = False
        self.owns_camera_start = False
        self.owns_stage_motion = False
        self.cleanup_errors = []

    def _check_cancel(self):
        if self.stop_event.is_set():
            raise AcquisitionCancelled("Acquisition cancelled")

    def _command(self, proxy, name, argument=None):
        self._check_cancel()
        return proxy.command_inout(name) if argument is None else proxy.command_inout(name, argument)

    def _wait(self):
        if self.stop_event.wait(self.profile["poll_interval_s"]):
            raise AcquisitionCancelled("Acquisition cancelled")

    def open(self):
        self._check_cancel()
        self.camera = self.proxy_factory(self.hardware["andor_device"], timeout_ms=2500)
        self.stage = self.proxy_factory(self.hardware["owis_aggregator_device"], timeout_ms=2500)
        self.dg645 = self.proxy_factory(self.hardware["dg645_device"], timeout_ms=2500)
        state = str(self.camera.state()).upper().split(".")[-1]
        if state not in {"ON", "RUNNING", "STANDBY"}:
            raise RuntimeError("Andor is not ready: " + state)
        before = _json_object(self._command(self.camera, "V0Capabilities"))
        self._validate_capabilities(before, active_required=False)
        self._verify_timing()
        if not before.get("acquisition_active"):
            # A timed-out command may already have started the camera.
            self.owns_camera_start = True
            self._command(self.camera, "start_grabbing")
        self.capabilities = _json_object(self._command(self.camera, "V0Capabilities"))
        self._validate_capabilities(self.capabilities, active_required=True)
        if self.capabilities["config_fingerprint"] != self.profile.get("expected_config_fingerprint"):
            raise ValueError("Andor readout configuration does not match the commissioned detector profile")
        return _axis(self.capabilities["wavelengths"])

    def _validate_capabilities(self, caps, active_required):
        if (caps.get("schema") != PACKET_SCHEMA or caps.get("track_count") != 2
                or caps.get("external_trigger") is not True
                or caps.get("configuration_fresh") is not True
                or (active_required and caps.get("lossless") is not True)
                or (active_required and caps.get("acquisition_active") is not True)
                or not isinstance(caps.get("config_fingerprint"), str)
                or not caps.get("config_fingerprint")
                or (active_required and not caps.get("acquisition_epoch"))):
            raise ValueError("Andor lacks a ready lossless externally triggered two-track RAW contract")
        axis = _axis(caps.get("wavelengths"))
        if caps.get("width") != len(axis) or len(axis) > 16384:
            raise ValueError("Andor RAW geometry is invalid")
        if active_required and caps.get("admission_error"):
            raise ValueError(str(caps["admission_error"]))

    def _verify_timing(self):
        recall = self.plan.dg645_recall
        policy = self.hardware.get("dg645_preflight_policy", "apply_recall_then_verify")
        if policy in {"apply_recall_then_verify", "recall_then_verify", "apply"}:
            self._command(self.dg645, "scpi_write", "*RCL " + str(recall["recall_slot"]))
            if self.stop_event.wait(1.0):
                raise AcquisitionCancelled("Acquisition cancelled during DG645 recall")
        elif policy not in {"verify", "verify_only"}:
            raise ValueError("Tango RAW runs require DG645 timing verification")
        expected = recall.get("snapshot", {}).get("raw_queries", {})
        if not expected:
            raise ValueError("DG645 profile lacks a verification snapshot")
        # The reply must numerically match each frozen source timing setting.
        for query, wanted in expected.items():
            if query == "*IDN?":
                continue
            actual = str(self._command(self.dg645, "scpi_query", query)).strip()
            if not _scpi_equal(actual, str(wanted)):
                raise ValueError("DG645 timing mismatch: " + query)

    def move_to(self, point_index):
        target = self.plan.scan_plan.positions[point_index]
        axis = self.hardware["delay_line_axis"]
        self._check_cancel()
        self.owns_stage_motion = True
        self._command(self.stage, "move_axis", [float(axis), float(target)])
        deadline = self.monotonic() + self.profile["move_timeout_s"]
        stable = 0
        while True:
            self._check_cancel()
            if self.monotonic() >= deadline:
                raise TimeoutError("Delay stage did not settle before the scan deadline")
            positions = _dict_attribute(self.stage.read_attribute("positions").value)
            states = _dict_attribute(self.stage.read_attribute("states").value)
            position = positions.get(axis, positions.get(str(axis)))
            status = states.get(axis, states.get(str(axis)))
            if isinstance(position, bool) or not isinstance(position, (int, float)) or not math.isfinite(position):
                raise ValueError("OWIS delay readback is missing or invalid")
            status = str(status).upper().split(".")[-1]
            if status not in {"ON", "STANDBY", "MOVING", "RUNNING"}:
                raise ValueError("OWIS delay axis is not ready: " + status)
            settled = abs(position - target) <= self.profile["move_tolerance_mm"] and status in {"ON", "STANDBY"}
            self.on_motion(float(position), float(target), not settled)
            stable = stable + 1 if settled else 0
            if stable >= self.profile["settled_samples"]:
                return float(position)
            self._wait()

    def acquire_batch(self, run_id, point_index, cycle_count=1):
        if self.pending_order is not None:
            raise RuntimeError("Journal and acknowledge the previous RAW order before requesting another")
        if not _integer(cycle_count) or not 1 <= cycle_count <= 200:
            raise ValueError("A RAW batch requires 1..200 detector cycles")
        caps = self.capabilities
        request = {"request_id": uuid.uuid4().hex, "run_id": run_id, "point_index": point_index,
                   "frame_count": 3 * cycle_count, "acquisition_epoch": caps["acquisition_epoch"],
                   "expected_config_fingerprint": caps["config_fingerprint"]}
        # Retain exact idempotency content across an uncertain Begin reply.
        self.pending_request = json.dumps(request, sort_keys=True)
        descriptor = _json_object(self._command(self.camera, "V0BeginOrder", self.pending_request))
        order = descriptor.get("order_id")
        if not isinstance(order, str) or not order:
            raise ValueError("Andor did not return a RAW order identity")
        self.pending_order = order
        self.pending_journaled = False
        self.on_order(order)
        deadline = self.monotonic() + self.profile["order_timeout_s"]
        while True:
            self._check_cancel()
            if self.monotonic() >= deadline:
                raise TimeoutError("Andor RAW order timed out")
            status = _json_object(self._command(self.camera, "V0OrderStatus", order))
            if status.get("order_id") != order:
                raise ValueError("Andor returned status for a different RAW order")
            state = status.get("state")
            if state in {"complete", "failed", "cancelled"}:
                encoded = self._command(self.camera, "V0ReadOrder", order)
                self._check_cancel()
                if self.monotonic() >= deadline:
                    raise TimeoutError("Andor RAW reply arrived after the order deadline")
                batch = decode_tango_batch(
                        encoded, order_id=order, run_id=run_id, point_index=point_index,
                        acquisition_epoch=caps["acquisition_epoch"], config_fingerprint=caps["config_fingerprint"],
                        wavelengths=caps["wavelengths"], background_level=self.profile["background_level"],
                        all_cycles=self.profile["all_cycles"],
                        cycle_count=cycle_count,
                    )
                self._check_cancel()
                if self.monotonic() >= deadline:
                    raise TimeoutError("Andor RAW validation exceeded the order deadline")
                expected_dtype = self.profile.get("expected_sample_dtype")
                if expected_dtype is not None and batch.envelope["dtype"] != expected_dtype:
                    raise TangoPacketError("Andor SDK sample dtype differs from the commissioned detector profile", batch.packet,
                                           {"source_order_id": order, "source_envelope": batch.envelope, "raw_header": encoded[0]})
                return batch
            if state not in {"queued", "capturing"}:
                raise ValueError("Unknown Andor RAW order state")
            self._wait()

    def acquire_cycle(self, run_id, point_index):
        batch = self.acquire_batch(run_id, point_index)
        if batch.rejected:
            raise batch.rejected[0]
        return batch.cycles[0]

    def acknowledge_cycle(self):
        """Release only after the caller's durable RAW/rejection journal commit."""
        if self.pending_order is not None:
            self.pending_journaled = True
            self.camera.command_inout("V0ReleaseOrder", self.pending_order)
            self.pending_order = None
            self.pending_request = None
            self.on_order(None)

    def close(self):
        """Best-effort cleanup within the original approved run's target set.

        This intentionally bypasses cancellation checks for owned cleanup only.
        A partial packet remains readable after cancellation and is returned for
        the rejected-transport journal before its camera order is released.
        """
        partial = None
        if self.camera is not None and self.pending_order is None and self.pending_request is not None:
            try:
                descriptor = _json_object(self.camera.command_inout("V0BeginOrder", self.pending_request))
                order = descriptor.get("order_id")
                if not isinstance(order, str) or not order:
                    raise ValueError("Missing idempotent RAW order identity")
                self.pending_order = order
                self.on_order(order)
            except Exception as exc:
                self.cleanup_errors.append("Andor uncertain Begin reply: " + str(exc))
        if self.camera is not None and self.pending_order is not None:
            order = self.pending_order
            if self.pending_journaled:
                try:
                    self.acknowledge_cycle()
                except Exception as exc:
                    self.cleanup_errors.append("Andor order release: " + str(exc))
            else:
                try:
                    self.camera.command_inout("V0CancelOrder", order)
                    header, payload = self.camera.command_inout("V0ReadOrder", order)
                    if isinstance(payload, (bytes, bytearray, memoryview)):
                        partial = (bytes(payload), {"raw_header": str(header), "source_order_id": order})
                except Exception as exc:
                    self.cleanup_errors.append("Andor partial order: " + str(exc))
        if self.camera is not None and self.owns_camera_start:
            try:
                self.camera.command_inout("stop_grabbing")
            except Exception as exc:
                self.cleanup_errors.append("Andor stop: " + str(exc))
        if self.stage is not None and self.owns_stage_motion:
            try:
                self.stage.command_inout("stop_axis", int(self.hardware["delay_line_axis"]))
            except Exception as exc:
                self.cleanup_errors.append("OWIS stop: " + str(exc))
        return partial


def _scpi_equal(actual, expected):
    left, right = actual.split(","), expected.split(",")
    if len(left) != len(right):
        return False
    for a, b in zip(left, right):
        try:
            x, y = float(a), float(b)
        except ValueError:
            if a.strip() != b.strip():
                return False
        else:
            if not math.isfinite(x) or not math.isfinite(y) or not math.isclose(x, y, rel_tol=1e-8, abs_tol=1e-12):
                return False
    return True
