"""VD2 three-phase acquisition built on the HPD-TA streak controller."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

import h5py
import numpy as np

from gui.controllers.openers import HamamatsuFileOpener


class Vd2Phase(str, Enum):
    NOISE = "NOISE"
    BASE = "BASE"
    ABS = "ABS"


VD2_PHASE_ORDER = (Vd2Phase.NOISE, Vd2Phase.BASE, Vd2Phase.ABS)


class Vd2PhaseController(Protocol):
    """Sets and verifies the physical state associated with one VD2 phase."""

    def prepare_phase(self, phase: Vd2Phase) -> None:
        """Put accelerator/shutters/Faraday hardware into the requested phase."""

    def verify_phase(self, phase: Vd2Phase) -> None:
        """Raise when hardware readback does not match the requested phase."""


class Vd2StreakController(Protocol):
    """Subset of :class:`HamamatsuStreakController` required by VD2."""

    def set_sequence_loops(self, value: object) -> str: ...
    def start_sequence(self, wait: bool = False) -> None: ...
    def wait_for_async_idle(self) -> Any: ...
    def save_current_sequence_his(self, path: str, overwrite: bool = True) -> str: ...
    def refresh_cached_state(self) -> Any: ...
    def set_time_range(self, value: str) -> str: ...
    def set_wavelength_nm(self, value_nm: float) -> str: ...
    def set_grating(self, value: object) -> str: ...
    def set_slit_width_um(self, value_um: float) -> str: ...
    def set_delay_channel(self, channel_name: str, value: object) -> str: ...


@dataclass(frozen=True)
class Vd2AcquisitionConfig:
    run_directory: Path
    run_name: str
    frames_per_phase: int = 100
    time_range: str | None = None
    wavelength_nm: float | None = None
    grating: str | None = None
    slit_width_um: float | None = None
    dg645_delays: Mapping[str, str] = field(default_factory=dict)
    extra_metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Vd2RunResult:
    manifest_path: Path
    phase_files: Mapping[Vd2Phase, Mapping[str, Path]]


class Vd2AcquisitionError(RuntimeError):
    """A VD2 run did not complete with the expected artifacts."""


class Vd2Acquisition:
    """Acquire ``NOISE``, ``BASE``, and ``ABS`` as independent HIS/H5 files."""

    def __init__(
        self,
        streak: Vd2StreakController,
        phase_controller: Vd2PhaseController,
        his_to_h5: Callable[[Path, Path, Vd2Phase, Mapping[str, Any]], int] | None = None,
    ):
        self.streak = streak
        self.phase_controller = phase_controller
        self.his_to_h5 = his_to_h5 or convert_his_to_h5

    def run(self, config: Vd2AcquisitionConfig) -> Vd2RunResult:
        self._validate_config(config)
        run_directory = Path(config.run_directory).expanduser().resolve()
        run_directory.mkdir(parents=True, exist_ok=True)
        manifest_path = run_directory / "run.json"
        phase_files: dict[Vd2Phase, dict[str, Path]] = {}
        manifest = self._new_manifest(config)

        try:
            readback = self._configure_streak(config)
            manifest["hardware_readback"] = readback
            self._write_manifest(manifest_path, manifest)

            for phase in VD2_PHASE_ORDER:
                self.phase_controller.prepare_phase(phase)
                self.phase_controller.verify_phase(phase)

                his_path = run_directory / f"{phase.value}.his"
                h5_path = run_directory / f"{phase.value}.h5"
                self.streak.set_sequence_loops(config.frames_per_phase)
                self.streak.start_sequence(wait=False)
                self.streak.wait_for_async_idle()
                self.streak.save_current_sequence_his(str(his_path), overwrite=False)

                phase_readback = _snapshot_as_dict(self.streak.refresh_cached_state())
                frame_count = self.his_to_h5(
                    his_path,
                    h5_path,
                    phase,
                    {
                        "run_name": config.run_name,
                        "frames_requested": config.frames_per_phase,
                        "phase_readback": phase_readback,
                    },
                )
                if frame_count != config.frames_per_phase:
                    raise Vd2AcquisitionError(
                        f"{phase.value} contains {frame_count} frames; "
                        f"expected {config.frames_per_phase}"
                    )

                phase_files[phase] = {"his": his_path, "h5": h5_path}
                manifest["phases"][phase.value] = {
                    "status": "completed",
                    "frame_count": frame_count,
                    "his": _artifact_metadata(his_path),
                    "h5": _artifact_metadata(h5_path),
                    "hardware_readback": phase_readback,
                    "completed_at": _utc_now(),
                }
                self._write_manifest(manifest_path, manifest)

            manifest["status"] = "completed"
            manifest["completed_at"] = _utc_now()
            self._write_manifest(manifest_path, manifest)
            return Vd2RunResult(manifest_path=manifest_path, phase_files=phase_files)
        except Exception as exc:
            manifest["status"] = "failed"
            manifest["error"] = str(exc)
            manifest["failed_at"] = _utc_now()
            self._write_manifest(manifest_path, manifest)
            raise

    def _configure_streak(self, config: Vd2AcquisitionConfig) -> dict[str, Any]:
        if config.time_range:
            self.streak.set_time_range(config.time_range)
        if config.wavelength_nm is not None:
            self.streak.set_wavelength_nm(config.wavelength_nm)
        if config.grating:
            self.streak.set_grating(config.grating)
        if config.slit_width_um is not None:
            self.streak.set_slit_width_um(config.slit_width_um)
        for channel, value in config.dg645_delays.items():
            self.streak.set_delay_channel(channel, value)
        return _snapshot_as_dict(self.streak.refresh_cached_state())

    @staticmethod
    def _validate_config(config: Vd2AcquisitionConfig) -> None:
        if not str(config.run_name).strip() or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", config.run_name):
            raise Vd2AcquisitionError("run_name must contain only letters, digits, '.', '_' or '-'")
        if int(config.frames_per_phase) <= 0:
            raise Vd2AcquisitionError("frames_per_phase must be positive")
        invalid_channels = set(config.dg645_delays) - {
            "Delay A", "Delay B", "Delay C", "Delay D", "Delay E", "Delay F", "Delay G", "Delay H",
        }
        if invalid_channels:
            raise Vd2AcquisitionError(f"Unsupported DG645 channels: {sorted(invalid_channels)}")

    @staticmethod
    def _new_manifest(config: Vd2AcquisitionConfig) -> dict[str, Any]:
        config_data = asdict(config)
        config_data["run_directory"] = str(config.run_directory)
        return {
            "schema_version": 1,
            "experiment": "VD2 streak camera",
            "run_name": config.run_name,
            "status": "running",
            "started_at": _utc_now(),
            "configuration": config_data,
            "phases": {},
        }

    @staticmethod
    def _write_manifest(path: Path, payload: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, default=str)
            handle.write("\n")
            temp_path = Path(handle.name)
        os.replace(temp_path, path)


def convert_his_to_h5(
    his_path: Path,
    h5_path: Path,
    phase: Vd2Phase,
    metadata: Mapping[str, Any] | None = None,
) -> int:
    """Convert one HPD-TA HIS sequence to the H5 contract used by VD2 Treatment."""
    source = Path(his_path)
    target = Path(h5_path)
    opener = HamamatsuFileOpener()
    info = opener.read_critical_info(source)
    frame_count = int(info.number_maps)
    if frame_count <= 0:
        raise Vd2AcquisitionError(f"{source} has no image maps")

    target.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(target, "w") as h5_file:
        h5_file.create_dataset("timedelays", data=np.asarray(info.timedelays, dtype=float))
        h5_file.create_dataset("wavelengths", data=np.asarray(info.wavelengths, dtype=float))
        raw_data = h5_file.create_dataset(
            "raw_data",
            shape=(frame_count, int(info.wavelengths_length), int(info.timedelays_length)),
            dtype=np.float32,
            compression="gzip",
            compression_opts=4,
        )
        for index, measurement in enumerate(opener.give_all_maps(source)):
            if measurement is False:
                raise Vd2AcquisitionError(f"Could not read HIS map {index + 1}/{frame_count}")
            raw_data[index] = np.asarray(measurement.data, dtype=np.float32)

        metadata_group = h5_file.create_group("metadata")
        metadata_group.attrs["phase"] = phase.value
        metadata_group.attrs["source_file"] = str(source)
        metadata_group.attrs["frame_count"] = frame_count
        metadata_group.attrs["time_scale"] = str(info.scaling_yunit)
        metadata_group.attrs["description"] = str(info.header).replace("\0", "")
        for key, value in (metadata or {}).items():
            metadata_group.attrs[key] = json.dumps(value, default=str) if isinstance(value, (dict, list)) else str(value)
    return frame_count


def _artifact_metadata(path: Path) -> dict[str, Any]:
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": _sha256(path)}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _snapshot_as_dict(snapshot: Any) -> dict[str, Any]:
    if is_dataclass(snapshot):
        return asdict(snapshot)
    if isinstance(snapshot, Mapping):
        return dict(snapshot)
    return {"value": str(snapshot)}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
