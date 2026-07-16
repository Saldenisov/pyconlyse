"""Streaming storage for emulator V0 pump-probe runs."""

import json
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np


RAW_GROUPS = ("BG1", "Ir1", "Is1", "BG2", "Ir2", "Is2")


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def _od_from_means(means):
    bg1, ir1, is1, bg2, ir2, is2 = means
    with np.errstate(divide="ignore", invalid="ignore"):
        s_off = is1 - bg1
        r_off = ir1 - bg1
        s_on = is2 - bg2
        r_on = ir2 - bg2
        ratio = (s_off / r_off) / (s_on / r_on)
        od = np.log10(ratio)
    return np.where(np.isfinite(od), od, np.nan).astype(np.float32)


class V0EmulatorRunWriter:
    """Owns one emulator scan and persists every unaveraged detector frame."""

    def __init__(self, wavelengths, delays, positions, shots_per_point, config, run_id=None):
        self.run_id = run_id or f"v0_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}"
        self.wavelengths = np.asarray(wavelengths, dtype=np.float32)
        self.delays = np.asarray(delays, dtype=np.float32)
        self.positions = np.asarray(positions, dtype=np.float32)
        self.shots_per_point = int(shots_per_point)
        self._events = []
        self._closed = False
        self._staging_dir = Path(tempfile.mkdtemp(prefix=f"pyconlyse-{self.run_id}-"))
        self.h5_path = self._staging_dir / f"{self.run_id}.h5"
        self.dat_path = self._staging_dir / f"{self.run_id}.dat"
        self.manifest_path = self._staging_dir / f"{self.run_id}.jsonl"
        self._sums = np.zeros((len(self.delays), len(RAW_GROUPS), len(self.wavelengths)), dtype=np.float64)
        self._counts = np.zeros(len(self.delays), dtype=np.int32)

        self._h5 = h5py.File(self.h5_path, "w")
        self._h5.create_dataset(
            "raw_data",
            shape=(len(self.delays), len(RAW_GROUPS), self.shots_per_point, len(self.wavelengths)),
            dtype=np.float32,
            fillvalue=np.nan,
            compression="gzip",
            compression_opts=1,
            chunks=(1, 1, min(self.shots_per_point, 8), len(self.wavelengths)),
        )
        self._h5.create_dataset("od", shape=(len(self.wavelengths), len(self.delays)), dtype=np.float32, fillvalue=np.nan)
        self._h5.create_dataset("mean_spectra", shape=(len(self.delays), len(RAW_GROUPS), len(self.wavelengths)), dtype=np.float32, fillvalue=np.nan)
        self._h5.create_dataset("frame_counts", data=self._counts)
        self._h5.create_dataset("wavelength_nm", data=self.wavelengths)
        self._h5.create_dataset("delay_ps", data=self.delays)
        self._h5.create_dataset("position_mm", data=self.positions)
        self._h5.create_dataset("raw_group_names", data=np.asarray(RAW_GROUPS, dtype=h5py.string_dtype("utf-8")))
        self._h5.create_dataset("metadata/config_json", data=json.dumps(config, sort_keys=True), dtype=h5py.string_dtype("utf-8"))
        self._h5.create_dataset("metadata/run_started_iso", data=_utc_now(), dtype=h5py.string_dtype("utf-8"))
        self._manifest_dataset = self._h5.create_dataset(
            "manifest/events_jsonl",
            shape=(0,),
            maxshape=(None,),
            dtype=h5py.string_dtype("utf-8"),
        )
        self._event("run_started", run_id=self.run_id)
        self._h5.flush()

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
        if len(frames) != len(RAW_GROUPS):
            raise ValueError(f"Expected {len(RAW_GROUPS)} raw groups, got {len(frames)}")
        if not 0 <= int(delay_index) < len(self.delays):
            raise IndexError(f"Invalid delay index {delay_index}")

        delay_index = int(delay_index)
        shot_index = int(self._counts[delay_index])
        if shot_index >= self.shots_per_point:
            raise RuntimeError(f"Delay point {delay_index} is already complete")

        raw_data = self._h5["raw_data"]
        for group_index, values in enumerate(frames):
            frame = np.asarray(values, dtype=np.float32)
            if frame.shape != self.wavelengths.shape:
                raise ValueError(f"Invalid frame shape {frame.shape}; expected {self.wavelengths.shape}")
            raw_data[delay_index, group_index, shot_index, :] = frame
            self._sums[delay_index, group_index] += frame
            self._event(
                "frame_acquired",
                delay_index=delay_index,
                delay_ps=float(self.delays[delay_index]),
                target_position_mm=float(target_mm),
                readback_position_mm=float(readback_mm),
                group=RAW_GROUPS[group_index],
                shot_index=shot_index,
            )

        self._counts[delay_index] += 1
        self._h5["frame_counts"][...] = self._counts
        od = self.od_for_delay(delay_index)
        self._h5["od"][:, delay_index] = od
        self._h5.flush()
        return od.tolist()

    def od_for_delay(self, delay_index):
        count = int(self._counts[int(delay_index)])
        if count <= 0:
            return np.full(len(self.wavelengths), np.nan, dtype=np.float32)
        return _od_from_means(self._sums[int(delay_index)] / count)

    def finalize(self, status="completed", error=""):
        if self._closed:
            return self.artifacts()

        means = np.full(self._sums.shape, np.nan, dtype=np.float32)
        od = np.full((len(self.wavelengths), len(self.delays)), np.nan, dtype=np.float32)
        for delay_index, count in enumerate(self._counts):
            if count <= 0:
                continue
            point_means = self._sums[delay_index] / int(count)
            means[delay_index] = point_means
            od[:, delay_index] = _od_from_means(point_means)

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
        np.savetxt(self.dat_path, matrix, delimiter="\t", fmt="%.8g")

    def artifacts(self):
        return {
            "run_id": self.run_id,
            "h5_path": str(self.h5_path),
            "dat_path": str(self.dat_path),
            "manifest_path": str(self.manifest_path),
            "frame_counts": self._counts.tolist(),
        }
