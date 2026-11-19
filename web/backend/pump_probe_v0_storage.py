"""Streaming storage for emulator V0 pump-probe runs."""

import hashlib
import json
import os
import stat
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np

from pump_probe_v0_processing import (
    OD_ALGORITHM, TRANCON_FLOAT_LAYOUT, TRANCON_GROUPS, V0_LAYOUT, V0_RAW_GROUPS,
    float32_detector_counts, trancon_shot_od, v0_shot_od,
)
from pump_probe_v0_scanplan import ScanPlan

RAW_GROUPS = V0_RAW_GROUPS


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


class V0EmulatorRunWriter:
    """Owns one emulator scan and persists every unaveraged detector frame."""

    raw_groups = V0_RAW_GROUPS
    raw_layout = V0_LAYOUT
    _shot_od = staticmethod(v0_shot_od)

    def __init__(self, wavelengths, delays, positions, shots_per_point, config, run_id=None,
                 *, plan=None, parent_run_id=None):
        self.run_id = run_id or f"v0_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex}"
        self.wavelengths = np.array(wavelengths, dtype=np.float64, copy=True)
        self.delays = np.array(delays, dtype=np.float64, copy=True)
        self.positions = np.array(positions, dtype=np.float64, copy=True)
        if (self.wavelengths.ndim != 1 or not self.wavelengths.size
                or self.delays.ndim != 1 or not self.delays.size
                or self.positions.shape != self.delays.shape
                or not all(np.isfinite(v).all() for v in (self.wavelengths, self.delays, self.positions))):
            raise ValueError("Run coordinates must be finite nonempty one-dimensional axes")
        if (isinstance(shots_per_point, (bool, np.bool_))
                or not isinstance(shots_per_point, (int, float, np.integer, np.floating))
                or not np.isfinite(shots_per_point) or not float(shots_per_point).is_integer()
                or not 1 <= shots_per_point <= 200):
            raise ValueError("shots_per_point must be an integer in 1..200")
        self.shots_per_point = int(shots_per_point)
        self.plan = plan
        if plan is not None:
            if (not isinstance(plan, ScanPlan) or self.shots_per_point != plan.shots_per_point
                    or not self._same_axis(self.delays, plan.delays)
                    or not self._same_axis(self.positions, plan.positions)):
                raise ValueError("Writer coordinates disagree with scan plan")
        self.parent_run_id = parent_run_id
        self._events = []
        self._closed = False
        self._staging_dir = Path(tempfile.mkdtemp(prefix=f"pyconlyse-{self.run_id}-"))
        self.h5_path = self._staging_dir / f"{self.run_id}.h5"
        self.dat_path = self._staging_dir / f"{self.run_id}.dat"
        self.manifest_path = self._staging_dir / f"{self.run_id}.jsonl"
        self._sums = np.zeros((len(self.delays), len(self.raw_groups), len(self.wavelengths)), dtype=np.float64)
        self._od_sums = np.zeros((len(self.delays), len(self.wavelengths)), dtype=np.float64)
        self._counts = np.zeros(len(self.delays), dtype=np.int32)

        self._h5 = h5py.File(self.h5_path, "w")
        self._h5.create_dataset(
            "raw_data",
            shape=(len(self.delays), len(self.raw_groups), self.shots_per_point, len(self.wavelengths)),
            dtype=np.float32,
            fillvalue=np.nan,
            compression="gzip",
            compression_opts=1,
            chunks=(1, 1, min(self.shots_per_point, 8), len(self.wavelengths)),
        )
        self._h5.create_dataset("od", shape=(len(self.wavelengths), len(self.delays)), dtype=np.float64, fillvalue=np.nan)
        self._h5.create_dataset("mean_spectra", shape=(len(self.delays), len(self.raw_groups), len(self.wavelengths)), dtype=np.float32, fillvalue=np.nan)
        self._h5.create_dataset("frame_counts", data=self._counts)
        self._h5.create_dataset("wavelength_nm", data=self.wavelengths)
        self._h5.create_dataset("delay_ps", data=self.delays)
        self._h5.create_dataset("position_mm", data=self.positions)
        self._h5.create_dataset("raw_group_names", data=np.asarray(self.raw_groups, dtype=h5py.string_dtype("utf-8")))
        self._h5.create_dataset("metadata/config_json", data=json.dumps(config, sort_keys=True), dtype=h5py.string_dtype("utf-8"))
        self._h5.create_dataset("metadata/raw_layout", data=self.raw_layout)
        self._h5.create_dataset("metadata/od_algorithm", data=OD_ALGORITHM)
        self._h5.create_dataset("metadata/run_id", data=self.run_id)
        if parent_run_id is not None:
            self._h5.create_dataset("metadata/parent_run_id", data=str(parent_run_id))
        if plan is not None:
            self._h5.create_dataset("metadata/scan_plan_json", data=json.dumps(plan.to_dict(), sort_keys=True, allow_nan=False))
            self._h5.create_dataset("metadata/scan_plan_fingerprint", data=plan.fingerprint)
        self._h5.create_dataset("metadata/run_started_iso", data=_utc_now(), dtype=h5py.string_dtype("utf-8"))
        self._manifest_dataset = self._h5.create_dataset(
            "manifest/events_jsonl",
            shape=(0,),
            maxshape=(None,),
            dtype=h5py.string_dtype("utf-8"),
        )
        self._event("run_started", run_id=self.run_id)
        self._h5.flush()

    @staticmethod
    def _same_axis(actual, expected):
        actual = np.asarray(actual, dtype=np.float64)
        expected = np.asarray(expected, dtype=np.float64)
        return actual.shape == expected.shape and np.array_equal(actual.view(np.uint64), expected.view(np.uint64))

    @staticmethod
    def _text(value):
        return value.decode("utf-8") if isinstance(value, bytes) else str(value)

    @classmethod
    def resume_from(cls, source_h5, config, *, expected_plan, expected_wavelengths=None):
        """Seed a unique child run from acquired slots of a finalized stopped run.

        All schema/plan/count checks precede writer creation. RAW is streamed a
        shot at a time; padding is never replayed and the parent stays read-only.
        """
        if not isinstance(expected_plan, ScanPlan):
            raise ValueError("Resume requires an immutable expected scan plan")
        with h5py.File(source_h5, "r") as source:
            required = {"raw_data", "frame_counts", "wavelength_nm", "delay_ps", "position_mm",
                        "raw_group_names", "od", "metadata/run_status", "metadata/run_id",
                        "metadata/raw_layout", "metadata/od_algorithm", "metadata/scan_plan_json",
                        "metadata/scan_plan_fingerprint"}
            if any(name not in source for name in required):
                raise ValueError("Stopped run lacks resumable scan-plan metadata")
            if cls._text(source["metadata/run_status"][()]) != "stopped":
                raise ValueError("Only a finalized stopped run can be continued")
            try:
                saved_plan = json.loads(cls._text(source["metadata/scan_plan_json"][()]))
            except (TypeError, ValueError) as exc:
                raise ValueError("Stored scan plan is invalid") from exc
            if (saved_plan != expected_plan.to_dict()
                    or cls._text(source["metadata/scan_plan_fingerprint"][()]) != expected_plan.fingerprint):
                raise ValueError("Continue requires exactly the same scan plan and calibration")
            groups = tuple(cls._text(v) for v in source["raw_group_names"])
            if (groups != tuple(cls.raw_groups) or cls._text(source["metadata/raw_layout"][()]) != cls.raw_layout
                    or cls._text(source["metadata/od_algorithm"][()]) != OD_ALGORITHM):
                raise ValueError("Stopped run RAW layout or OD algorithm is incompatible")
            waves = np.asarray(source["wavelength_nm"], dtype=np.float64)
            delays = np.asarray(source["delay_ps"], dtype=np.float64)
            positions = np.asarray(source["position_mm"], dtype=np.float64)
            raw = source["raw_data"]
            counts = np.asarray(source["frame_counts"])
            if (waves.ndim != 1 or not waves.size or not np.isfinite(waves).all()
                    or not cls._same_axis(delays, expected_plan.delays)
                    or not cls._same_axis(positions, expected_plan.positions)
                    or raw.shape != (len(delays), len(cls.raw_groups), expected_plan.shots_per_point, len(waves))
                    or raw.dtype != np.dtype("float32")
                    or source["od"].shape != (len(waves), len(delays))
                    or counts.shape != delays.shape or counts.dtype.kind not in "iuf"
                    or not np.isfinite(counts).all() or (counts < 0).any()
                    or (counts > expected_plan.shots_per_point).any() or (counts != np.floor(counts)).any()):
                raise ValueError("Stopped run axes, RAW dimensions or frame counts are invalid")
            if expected_wavelengths is not None and not cls._same_axis(waves, expected_wavelengths):
                raise ValueError("Stopped run wavelength axis differs from the active spectrometer")
            counts = counts.astype(np.int32)
            incomplete = np.flatnonzero(counts < expected_plan.shots_per_point)
            if not incomplete.size:
                raise ValueError("Stopped run has no remaining shots")
            next_point = int(incomplete[0])
            if counts[next_point + 1:].any():
                raise ValueError("Stopped run counts are not a sequential point/shot prefix")
            cls._validate_resume_extra(source, config, counts)
            parent = cls._text(source["metadata/run_id"][()])
            if not parent:
                raise ValueError("Stopped run has no parent run identity")
            writer = cls(waves, delays, positions, expected_plan.shots_per_point, config,
                         plan=expected_plan, parent_run_id=parent)
            try:
                for point, count in enumerate(counts):
                    for shot in range(int(count)):
                        frames = np.asarray(raw[point, :, shot, :], dtype=np.float32)
                        writer._h5["raw_data"][point, :, shot, :] = frames
                        writer._sums[point] += frames
                        with np.errstate(invalid="ignore", over="ignore"):
                            writer._od_sums[point] += writer._shot_od(frames)
                    writer._counts[point] = count
                    writer._h5["od"][:, point] = writer.od_for_delay(point)
                writer._h5["frame_counts"][...] = writer._counts
                writer._seed_resume_extra(source)
                writer._event("run_resumed", parent_run_id=parent,
                              frame_counts=counts.tolist(), next_point_index=next_point,
                              next_shot_index=int(counts[next_point]),
                              scan_plan_fingerprint=expected_plan.fingerprint)
                writer._h5.flush()
            except Exception:
                writer._h5.close()
                writer._closed = True
                raise
            return writer

    @classmethod
    def _validate_resume_extra(cls, source, config, counts):
        pass

    def _seed_resume_extra(self, source):
        pass

    def _event(self, event_type, **payload):
        event = {"timestamp": _utc_now(), "event": event_type, **payload}
        text = json.dumps(event, sort_keys=True)
        self._events.append(text)
        size = len(self._manifest_dataset)
        self._manifest_dataset.resize((size + 1,))
        self._manifest_dataset[size] = text

    def record_cycle(self, delay_index, frames, target_mm, readback_mm):
        if self._closed:
            raise RuntimeError("Run writer is already closed")
        if len(frames) != len(self.raw_groups):
            raise ValueError(f"Expected {len(self.raw_groups)} raw groups, got {len(frames)}")
        if not 0 <= int(delay_index) < len(self.delays):
            raise IndexError(f"Invalid delay index {delay_index}")

        delay_index = int(delay_index)
        shot_index = int(self._counts[delay_index])
        if shot_index >= self.shots_per_point:
            raise RuntimeError(f"Delay point {delay_index} is already complete")

        validated = []
        for values in frames:
            frame = np.asarray(values, dtype=np.float32)
            if frame.shape != self.wavelengths.shape:
                raise ValueError(f"Invalid frame shape {frame.shape}; expected {self.wavelengths.shape}")
            validated.append(frame)
        raw_data = self._h5["raw_data"]
        for group_index, frame in enumerate(validated):
            raw_data[delay_index, group_index, shot_index, :] = frame
            self._sums[delay_index, group_index] += frame
            self._event(
                "frame_acquired",
                delay_index=delay_index,
                delay_ps=float(self.delays[delay_index]),
                target_position_mm=float(target_mm),
                readback_position_mm=float(readback_mm),
                group=self.raw_groups[group_index],
                shot_index=shot_index,
            )

        with np.errstate(invalid="ignore", over="ignore"):
            self._od_sums[delay_index] += self._shot_od(validated)
        self._counts[delay_index] += 1
        self._h5["frame_counts"][...] = self._counts
        od = self.od_for_delay(delay_index)
        self._h5["od"][:, delay_index] = od
        self._h5.flush()
        # JSON/Plotly uses null gaps; HDF5 and DAT retain signed infinities.
        return [float(value) if np.isfinite(value) else None for value in od]

    def od_for_delay(self, delay_index):
        count = int(self._counts[int(delay_index)])
        if count <= 0:
            return np.full(len(self.wavelengths), np.nan, dtype=np.float32)
        return self._od_sums[int(delay_index)] / count

    def finalize(self, status="completed", error=""):
        if self._closed:
            return self.artifacts()

        means = np.full(self._sums.shape, np.nan, dtype=np.float32)
        od = np.full((len(self.wavelengths), len(self.delays)), np.nan, dtype=np.float64)
        for delay_index, count in enumerate(self._counts):
            if count <= 0:
                continue
            point_means = self._sums[delay_index] / int(count)
            means[delay_index] = point_means
            od[:, delay_index] = self.od_for_delay(delay_index)

        self._h5["mean_spectra"][...] = means
        self._h5["od"][...] = od
        self._h5.create_dataset("metadata/run_finished_iso", data=_utc_now(), dtype=h5py.string_dtype("utf-8"))
        self._h5.create_dataset("metadata/run_status", data=str(status), dtype=h5py.string_dtype("utf-8"))
        self._h5.create_dataset("metadata/run_error", data=str(error), dtype=h5py.string_dtype("utf-8"))
        self._event("run_finished", status=status, error=str(error))
        self._h5.flush()
        self._h5.close()
        self._write_dat(od)
        self.manifest_path.write_text("\n".join(self._events) + "\n", encoding="utf-8")
        self._closed = True
        return self.artifacts()

    def _write_dat(self, od):
        matrix = np.empty((len(self.wavelengths) + 1, len(self.delays) + 1), dtype=np.float64)
        matrix[0, 0] = 0.0
        matrix[0, 1:] = self.delays
        matrix[1:, 0] = self.wavelengths
        matrix[1:, 1:] = od
        np.savetxt(self.dat_path, matrix, delimiter="\t", fmt="%.17g")

    def artifacts(self):
        incomplete = np.flatnonzero(self._counts < self.shots_per_point)
        next_point = int(incomplete[0]) if incomplete.size else None
        return {
            "run_id": self.run_id,
            "h5_path": str(self.h5_path),
            "dat_path": str(self.dat_path),
            "manifest_path": str(self.manifest_path),
            "frame_counts": self._counts.tolist(),
            "parent_run_id": self.parent_run_id,
            "next_point_index": next_point,
            "next_shot_index": int(self._counts[next_point]) if next_point is not None else None,
            "scan_plan_fingerprint": self.plan.fingerprint if self.plan is not None else None,
        }


class V0TangoRunWriter(V0EmulatorRunWriter):
    """Detector-paired float32 RAW with original, independently stored packets.

    A cycle is one complete six-spectrum shot. Rejected/aborted transport never
    advances frame_counts. These commits are process-level transactions; HDF5
    itself is not a crash-recovery database.
    """

    raw_groups = TRANCON_GROUPS
    raw_layout = TRANCON_FLOAT_LAYOUT
    _shot_od = staticmethod(trancon_shot_od)

    @staticmethod
    def _json(value):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)

    @classmethod
    def profile_fingerprint(cls, config):
        if not isinstance(config, dict) or not isinstance(config.get("tango_profile"), dict) or not config["tango_profile"]:
            raise ValueError("Tango run requires a nonempty tango_profile mapping")
        try:
            encoded = cls._json(config["tango_profile"])
        except (ValueError, TypeError) as exc:
            raise ValueError("tango_profile must contain finite JSON metadata") from exc
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def __init__(self, wavelengths, delays, positions, shots_per_point, config, run_id=None,
                 *, plan=None, parent_run_id=None):
        fingerprint = self.profile_fingerprint(config)
        if not isinstance(plan, ScanPlan):
            raise ValueError("Tango run requires an immutable scan plan")
        # Serialize before opening a file, detaching mutable caller mappings.
        frozen_config = json.loads(self._json(config))
        super().__init__(wavelengths, delays, positions, shots_per_point, frozen_config,
                         run_id, plan=plan, parent_run_id=parent_run_id)
        self.tango_profile_fingerprint = fingerprint
        self._h5.create_dataset("metadata/tango_profile_fingerprint", data=fingerprint)
        self._h5.create_dataset("metadata/tango_profile_json", data=self._json(frozen_config["tango_profile"]))
        self._h5.create_group("transport/accepted")
        self._h5.create_group("transport/rejected")
        self._h5.create_group("transport/packets")
        self._h5.flush()

    @staticmethod
    def _packet_bytes(packet):
        if not isinstance(packet, (bytes, bytearray, memoryview)):
            raise ValueError("Transport packet must be bytes")
        return bytes(packet)

    def _store_transport(self, category, packet, envelope):
        group = self._h5[f"transport/{category}"]
        record = group.create_group(f"{len(group):08d}")
        try:
            digest = hashlib.sha256(packet).hexdigest()
            packets = self._h5.require_group("transport/packets")
            if digest not in packets:
                pooled = packets.create_group(digest)
                pooled.create_dataset("packet", data=np.frombuffer(packet, dtype=np.uint8),
                                      compression="gzip" if packet else None)
            # Every RAW slot keeps the same reader path, while all triplets in
            # one camera batch link to a single original compressed packet.
            record["packet"] = packets[digest]["packet"]
            record.create_dataset("envelope_json", data=self._json(envelope), dtype=h5py.string_dtype("utf-8"))
        except Exception:
            del group[record.name.rsplit("/", 1)[-1]]
            raise
        return record

    def flush_transport(self):
        """Durably flush the local journal before the camera order is released."""
        if self._closed:
            raise RuntimeError("Run writer is already closed")
        if self._h5.driver not in {"sec2", "windows"}:
            raise RuntimeError("Transport durability requires a supported local HDF5 file driver")
        self._h5.flush()
        handle = self._h5.id.get_vfd_handle()
        if type(handle) is not int or handle < 0:
            raise RuntimeError("HDF5 driver did not expose an OS file descriptor")
        try:
            descriptor = os.fstat(handle)
            local_file = os.stat(self.h5_path)
        except (OSError, ValueError) as exc:
            raise RuntimeError("HDF5 driver handle is not a usable local file descriptor") from exc
        if (not stat.S_ISREG(descriptor.st_mode)
                or (descriptor.st_dev, descriptor.st_ino) != (local_file.st_dev, local_file.st_ino)):
            raise RuntimeError("HDF5 driver handle does not identify the transport journal")
        os.fsync(handle)

    def record_rejected_transport(self, packet, metadata, reason):
        """Preserve incomplete/corrupt/aborted bytes without a RAW slot."""
        if self._closed:
            raise RuntimeError("Run writer is already closed")
        packet = self._packet_bytes(packet)
        try:
            detached = json.loads(self._json(metadata)) if isinstance(metadata, dict) else {"invalid_metadata": True}
        except (TypeError, ValueError):
            detached = {"invalid_metadata": True}
        envelope = {"packet_sha256": hashlib.sha256(packet).hexdigest(),
                    "packet_size": len(packet), "reason": str(reason), "metadata": detached,
                    "recorded_iso": _utc_now(), "raw_slot": None}
        self._store_transport("rejected", packet, envelope)
        self._event("transport_rejected", reason=str(reason), packet_sha256=envelope["packet_sha256"])
        self._h5.flush()
        return envelope

    def record_cycle(self, delay_index, frames, target_mm, readback_mm):
        raise ValueError("Tango cycles require original transport bytes and metadata; use record_tango_cycle")

    @staticmethod
    def _validate_cycle_metadata(metadata):
        for name in ("source_order_id", "acquisition_epoch", "config_fingerprint"):
            if not isinstance(metadata.get(name), str) or not metadata[name].strip():
                raise ValueError(f"Transport metadata requires nonempty {name}")
        indices = metadata.get("frame_indices")
        if (not isinstance(indices, list) or len(indices) != 3
                or any(type(value) is not int or value < 0 for value in indices)
                or indices != list(range(indices[0], indices[0] + 3))):
            raise ValueError("Transport frame_indices must contain three consecutive integer SDK frame IDs")
        if metadata.get("track_order") != ["detector_I", "detector_II"]:
            raise ValueError("Transport track_order must be detector_I, detector_II")
        mapping = metadata.get("phase_mapping")
        if not isinstance(mapping, dict) or set(mapping) != {"detector_I", "detector_II"}:
            raise ValueError("Transport phase_mapping must identify both detectors")
        for detector in ("detector_I", "detector_II"):
            phases = mapping[detector]
            if (not isinstance(phases, dict) or set(phases) != {"BG", "Ie", "I0"}
                    or any(type(value) is not int for value in phases.values())
                    or sorted(phases.values()) != [0, 1, 2]):
                raise ValueError("Each detector phase mapping must be a BG/Ie/I0 permutation of 0..2")
        if not isinstance(metadata.get("source_envelope"), dict) or not metadata["source_envelope"]:
            raise ValueError("Transport metadata requires the complete source_envelope mapping")
        source = metadata["source_envelope"]
        if "packet_cycle_index" in metadata:
            cycle = metadata["packet_cycle_index"]
            source_ids = source.get("frame_ids")
            if (type(cycle) is not int or cycle < 0 or not isinstance(source_ids, list)
                    or len(source_ids) % 3 or source_ids[3*cycle:3*cycle+3] != indices):
                raise ValueError("Transport packet cycle index disagrees with original SDK frame IDs")
        for field in ("acquisition_epoch", "config_fingerprint", "track_order"):
            if field in source and source[field] != metadata[field]:
                raise ValueError(f"Transport {field} disagrees with original source envelope")

    def record_tango_cycle(self, delay_index, six_frames, target_mm, readback_mm, packet, metadata):
        if self._closed:
            raise RuntimeError("Run writer is already closed")
        packet = self._packet_bytes(packet)
        try:
            if not packet:
                raise ValueError("Complete transport packet cannot be empty")
            if not isinstance(metadata, dict):
                raise ValueError("Transport metadata must be a mapping")
            detached = json.loads(self._json(metadata))
            self._validate_cycle_metadata(detached)
            digest = hashlib.sha256(packet).hexdigest()
            if detached.get("packet_sha256", digest) != digest:
                raise ValueError("Transport packet SHA256 mismatch")
            if (isinstance(delay_index, (bool, np.bool_)) or not isinstance(delay_index, (int, np.integer))
                    or not 0 <= delay_index < len(self.delays)):
                raise ValueError("Invalid integer delay index")
            delay_index = int(delay_index)
            shot_index = int(self._counts[delay_index])
            incomplete = np.flatnonzero(self._counts < self.shots_per_point)
            if not incomplete.size or delay_index != int(incomplete[0]):
                raise ValueError("Tango cycles must follow the scan plan point/shot prefix")
            if shot_index >= self.shots_per_point:
                raise ValueError("Delay point is already complete")
            for name, value in (("target", target_mm), ("readback", readback_mm)):
                if (isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, np.integer, np.floating))
                        or not np.isfinite(value)):
                    raise ValueError(f"{name} position must be finite")
            if float(target_mm) != float(self.positions[delay_index]):
                raise ValueError("Target position disagrees with scan plan")
            frames = float32_detector_counts(six_frames)
            if frames.shape != (6, len(self.wavelengths)):
                raise ValueError("Complete Tango cycle must contain six groups x wavelengths")
            # No HDF5/accumulator mutation precedes all value/JSON/hash checks.
            shot_od = self._shot_od(frames)
            envelope = {"packet_sha256": digest, "packet_size": len(packet), "metadata": detached,
                        "raw_slot": {"delay_index": delay_index, "shot_index": shot_index},
                        "delay_ps": float(self.delays[delay_index]), "target_position_mm": float(target_mm),
                        "readback_position_mm": float(readback_mm), "raw_groups": list(self.raw_groups),
                        "tango_profile_fingerprint": self.tango_profile_fingerprint,
                        "scan_plan_fingerprint": self.plan.fingerprint, "recorded_iso": _utc_now()}
            self._json(envelope)
        except (ValueError, TypeError, OverflowError) as exc:
            self.record_rejected_transport(packet, metadata, str(exc))
            raise ValueError(str(exc)) from exc

        record = self._store_transport("accepted", packet, envelope)
        old_sum = self._sums[delay_index].copy()
        old_od_sum = self._od_sums[delay_index].copy()
        old_od = self._h5["od"][:, delay_index]
        try:
            self._h5["raw_data"][delay_index, :, shot_index, :] = frames
            self._sums[delay_index] += frames
            with np.errstate(invalid="ignore", over="ignore"):
                self._od_sums[delay_index] += shot_od
            self._counts[delay_index] += 1
            self._h5["od"][:, delay_index] = self.od_for_delay(delay_index)
            self._h5["frame_counts"][...] = self._counts
            self._h5.flush()
        except Exception:
            self._sums[delay_index] = old_sum
            self._od_sums[delay_index] = old_od_sum
            self._counts[delay_index] = shot_index
            self._h5["raw_data"][delay_index, :, shot_index, :] = np.nan
            self._h5["od"][:, delay_index] = old_od
            self._h5["frame_counts"][...] = self._counts
            del self._h5[record.name]
            self._h5.flush()
            raise
        self._event("tango_cycle_acquired", **envelope["raw_slot"], packet_sha256=digest,
                    target_position_mm=float(target_mm), readback_position_mm=float(readback_mm))
        self._h5.flush()
        return [float(v) if np.isfinite(v) else None for v in self.od_for_delay(delay_index)]

    @classmethod
    def _validate_resume_extra(cls, source, config, counts):
        expected = cls.profile_fingerprint(config)
        if ("metadata/tango_profile_fingerprint" not in source
                or cls._text(source["metadata/tango_profile_fingerprint"][()]) != expected
                or "metadata/tango_profile_json" not in source
                or cls._text(source["metadata/tango_profile_json"][()]) != cls._json(config["tango_profile"])):
            raise ValueError("Continue requires exactly the same Tango profile and track mapping")
        if "transport/accepted" not in source or "transport/rejected" not in source:
            raise ValueError("Stopped Tango run lacks original transport records")
        slots = set()
        checked_packets = {}
        for category in ("accepted", "rejected"):
            for record in source[f"transport/{category}"].values():
                if "packet" not in record or "envelope_json" not in record or record["packet"].dtype != np.dtype("uint8"):
                    raise ValueError("Invalid stored transport record")
                packet_dataset = record["packet"]
                address = h5py.h5o.get_info(packet_dataset.id).addr
                if address not in checked_packets:
                    packet = packet_dataset[...].tobytes()
                    checked_packets[address] = (hashlib.sha256(packet).hexdigest(), len(packet))
                packet_digest, packet_length = checked_packets[address]
                envelope = json.loads(cls._text(record["envelope_json"][()]))
                if (envelope.get("packet_sha256") != packet_digest
                        or envelope.get("packet_size") != packet_length):
                    raise ValueError("Stored transport packet hash/length mismatch")
                if category == "accepted":
                    cls._validate_cycle_metadata(envelope.get("metadata", {}))
                    slot = envelope.get("raw_slot", {})
                    point, shot = slot.get("delay_index"), slot.get("shot_index")
                    if (type(point) is not int or type(shot) is not int or not 0 <= point < len(counts)
                            or not 0 <= shot < counts[point] or (point, shot) in slots
                            or envelope.get("tango_profile_fingerprint") != expected):
                        raise ValueError("Stored transport RAW slot mapping is invalid")
                    slots.add((point, shot))
        if len(slots) != int(counts.sum()):
            raise ValueError("Acquired RAW slots lack original transport packets")
        for point, count in enumerate(counts):
            float32_detector_counts(source["raw_data"][point, :, :int(count), :])

    def _seed_resume_extra(self, source):
        del self._h5["transport"]
        source.copy("transport", self._h5)

    def artifacts(self):
        result = super().artifacts()
        result.update(raw_layout=self.raw_layout, tango_profile_fingerprint=self.tango_profile_fingerprint)
        return result
