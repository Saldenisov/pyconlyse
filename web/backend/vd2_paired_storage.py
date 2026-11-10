"""On-disk paired VD2 stream and immutable dark-reference selection."""
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import h5py
import numpy as np

from vd2_project_manifest import MANIFEST_NAME, artifact_file, load_manifest


@dataclass(frozen=True)
class DarkReference:
    identity: str
    artifact: dict
    image: np.ndarray
    roi_blocks: tuple[np.ndarray, ...]
    wavelengths: np.ndarray
    timedelays: np.ndarray
    time_scale: str
    description: str


def load_dark_reference(root, sample, reuse, roi, precision, stop):
    try:
        data = load_manifest(root / MANIFEST_NAME)
    except FileNotFoundError as exc:
        raise ValueError("Record Bruit in this project before paired acquisition") from exc
    candidates = [
        artifact for artifact in data["artifacts"].values()
        if artifact["phase"] == "BRUIT" and artifact.get("status") == "completed"
        and (reuse == "latest" or artifact["sample"] == sample)
    ]
    if not candidates:
        raise ValueError("Record a completed Bruit for the selected Noise Source")
    artifact = max(candidates, key=lambda entry: entry["completed_at"])
    path = artifact_file(root, artifact)
    blocks = []
    with h5py.File(path, "r") as file:
        raw = file["raw_data"]
        if raw.ndim != 3 or not all(0 < size <= 8192 for size in raw.shape[1:]):
            raise ValueError("Invalid Bruit frame geometry")
        count, width, height = raw.shape
        if not count or (precision and count < 8):
            raise ValueError("Precision mode requires at least eight Bruit frames" if precision else "Bruit is empty")
        if roi and (roi.width, roi.height) != (width, height):
            raise ValueError("Selected ROI and Bruit have different detector geometry")
        wavelengths = np.asarray(file["wavelengths"][:], dtype=float)
        timedelays = np.asarray(file["timedelays"][:], dtype=float)
        if (wavelengths.shape != (width,) or timedelays.shape != (height,)
                or not np.isfinite(wavelengths).all() or not np.isfinite(timedelays).all()):
            raise ValueError("Bruit axes do not match detector geometry")
        image_sum = np.zeros((width, height), dtype=np.float64)
        block_count = min(16, count // 2) if precision else 1
        block_width = count // block_count
        for block in range(block_count):
            start = block * block_width
            end = (block + 1) * block_width if block + 1 < block_count else count
            block_sum = np.zeros_like(image_sum)
            for offset in range(start, end, 4):
                if stop.is_set():
                    return None
                block_sum += np.sum(raw[offset:min(end, offset + 4)], axis=0, dtype=np.float64)
            image_sum += block_sum
            if precision:
                blocks.append(block_sum[roi.slices] / (end - start))
        image = image_sum / count
        if not np.isfinite(image).all():
            raise ValueError("Bruit contains invalid detector counts")
        attrs = file["metadata"].attrs
        return DarkReference(artifact["id"], artifact, image, tuple(blocks), wavelengths,
                             timedelays, str(attrs.get("time_scale", "")), str(attrs.get("description", "")))


class PairedRecording:
    def __init__(self, path: Path, dark: DarkReference, config: dict, machine: dict):
        self.file = h5py.File(path, "x")
        try:
            self.file.create_dataset("wavelengths", data=dark.wavelengths)
            self.file.create_dataset("timedelays", data=dark.timedelays)
            self.file.create_dataset("background", data=dark.image)
            self.metadata = self.file.create_group("metadata")
            self.metadata.attrs.update({
                "phase": "PAIRED", "status": "recording", "frame_count": 0, "pair_count": 0,
                "time_scale": dark.time_scale, "description": dark.description,
                "bruit_artifact_id": dark.identity,
                "bruit_artifact": json.dumps(dark.artifact["h5"], allow_nan=False),
                "configuration": json.dumps(config, allow_nan=False),
                "machine_before": json.dumps(machine, allow_nan=False),
                "analysis": "mean_pair_od",
                "beam_state_source": "operator_first_frame",
            })
            self.sequence = self.file.create_dataset("camera_sequence", (0,), maxshape=(None,), dtype="i8")
            self.times = self.file.create_dataset("camera_timestamp_ms", (0,), maxshape=(None,), dtype="f8")
            self.roles = self.file.create_dataset("beam_on", (0,), maxshape=(None,), dtype="i1")
            self.roles.attrs["unknown"] = -1
            self.raw = None
            self.frame_count = 0
            self.file.flush()
        except BaseException:
            self.file.close()
            raise

    def append(self, image, sequence, timestamp, role):
        if self.raw is None:
            self.raw = self.file.create_dataset(
                "raw_data", shape=(0, *image.shape), maxshape=(None, *image.shape),
                dtype=image.dtype, chunks=(1, *image.shape),
            )
        if image.shape != self.raw.shape[1:] or image.dtype != self.raw.dtype:
            raise ValueError("Camera frame format changed during paired recording")
        index = self.frame_count
        for dataset, value in ((self.raw, image), (self.sequence, sequence),
                               (self.times, timestamp), (self.roles, role)):
            dataset.resize(index + 1, axis=0)
            dataset[index] = value
        self.frame_count += 1
        self.metadata.attrs["frame_count"] = self.frame_count
        self.file.flush()

    def finish(self, analysis, status: dict[str, Any]):
        try:
            self.file.create_dataset("paired_od", data=analysis.map())
            self.file.create_dataset("valid_pair_count", data=analysis.valid_count)
            self.file.create_dataset("roi_block_means_mod", data=analysis.block_mean)
            self.metadata.attrs["summary"] = json.dumps(status, allow_nan=False)
            self.metadata.attrs["pair_count"] = status["pairs_recorded"]
            self.metadata.attrs["status"] = status["status"]
        finally:
            self.file.close()
