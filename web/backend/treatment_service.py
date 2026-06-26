import logging
import json
import re
import sys
import tempfile
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    import h5py
except ImportError:  # pragma: no cover - optional runtime dependency
    h5py = None
else:
    if not hasattr(h5py, "File"):  # pragma: no cover - broken namespace install
        h5py = None

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gui.controllers.openers import (
    ASCIIOpener,
    H5Opener,
    HamamatsuFileOpener,
    OPENER_ACCRODANCE,
    OpenersTypes,
)
from treatment_network_path import copy_local_file_to_smb, is_smb_path, smb_join, smb_parent

module_logger = logging.getLogger(__name__)


class TreatmentDataService:
    def __init__(self):
        self.logger = module_logger
        self._lock = Lock()
        self._openers = {
            OpenersTypes.Hamamatsu: HamamatsuFileOpener(logger=self.logger),
            OpenersTypes.ASCII: ASCIIOpener(logger=self.logger),
        }
        if H5Opener is not None:
            self._openers[OpenersTypes.H5Opener] = H5Opener(logger=self.logger)

        self._runtimes: Dict[str, Dict[str, object]] = {}

    @property
    def supported_suffixes(self):
        return tuple(sorted(OPENER_ACCRODANCE.keys()))

    @staticmethod
    def _empty_runtime() -> Dict[str, object]:
        return {
            "noise_average": None,
            "result": None,
            "result_info": None,
            "result_source_path": None,
            "cleaning_file_path": None,
            "cleaning_info": None,
            "cleaning_measurements": None,
            "cleaning_indices": None,
            "cleaning_removed_measurements": None,
            "cleaning_removed_records": None,
            "cleaning_original_count": None,
            "cleaning_summary": None,
        }

    @staticmethod
    def _clear_cleaning_runtime(runtime: Dict[str, object]) -> None:
        runtime["cleaning_file_path"] = None
        runtime["cleaning_info"] = None
        runtime["cleaning_measurements"] = None
        runtime["cleaning_indices"] = None
        runtime["cleaning_removed_measurements"] = None
        runtime["cleaning_removed_records"] = None
        runtime["cleaning_original_count"] = None
        runtime["cleaning_summary"] = None

    def reset_runtime(self, session_id: Optional[str] = None):
        with self._lock:
            if session_id is None:
                self._runtimes.clear()
                return
            self._runtimes[session_id] = self._empty_runtime()

    def runtime_status(self, session_id: str):
        with self._lock:
            runtime = self._runtimes.get(session_id) or self._empty_runtime()
            result = runtime["result"]
            result_source_path = runtime["result_source_path"]
            result_shape = tuple(result.shape) if result is not None else None
            result_source = (
                str(result_source_path) if result_source_path is not None else ""
            )
            cleaning_file_path = runtime["cleaning_file_path"]
            cleaning_measurements = runtime["cleaning_measurements"]
            return {
                "noise_ready": runtime["noise_average"] is not None,
                "result_ready": result is not None,
                "result_shape": result_shape,
                "result_source_path": result_source,
                "cleaning_ready": cleaning_measurements is not None,
                "cleaning_file_path": (
                    str(cleaning_file_path) if cleaning_file_path is not None else ""
                ),
                "cleaning_current_measurements": (
                    int(len(cleaning_measurements))
                    if cleaning_measurements is not None
                    else 0
                ),
                "cleaning_original_measurements": int(
                    runtime["cleaning_original_count"] or 0
                ),
            }

    def get_file_info(self, file_path: Path) -> Dict[str, object]:
        opener, info = self._get_opener_and_info(file_path)
        preview, _ = opener.read_map(file_path, 0)
        if preview is False:
            raise ValueError("Could not read first map from file")
        return self._format_file_info(file_path, info, preview.data.shape)

    def get_preview(self, file_path: Path, map_index: int = 0) -> Dict[str, object]:
        opener, info = self._get_opener_and_info(file_path)
        measurement, comments = opener.read_map(file_path, map_index)
        if measurement is False:
            raise ValueError(comments or "Could not preview file")

        data = np.asarray(measurement.data)
        sample = self._downsample_2d(data)
        return {
            "file_info": self._format_file_info(file_path, info, data.shape),
            "map_index": int(map_index),
            "data_shape": list(data.shape),
            "sample_shape": list(sample.shape),
            "sample": sample.tolist(),
            "wavelengths": self._downsample_1d(np.asarray(measurement.wavelengths)).tolist(),
            "timedelays": self._downsample_1d(np.asarray(measurement.timedelays)).tolist(),
            "time_scale": measurement.time_scale,
            "min": float(np.min(data)),
            "max": float(np.max(data)),
            "mean": float(np.mean(data)),
        }

    def get_selection_view(
        self,
        session_state: Dict[str, object],
        session_id: Optional[str] = None,
    ) -> Dict[str, object]:
        active_data_type = str(session_state.get("active_data_type") or "").strip()
        result_payload = None
        if active_data_type == "OD" and session_id:
            with self._lock:
                runtime = self._runtimes.get(session_id)
                if runtime and runtime["result"] is not None and runtime["result_info"] is not None:
                    result_payload = (
                        np.asarray(runtime["result"], dtype=float),
                        runtime["result_info"],
                        Path(str(runtime["result_source_path"] or "calculated_od.dat")),
                    )

        if result_payload is not None:
            data, info, file_path = result_payload
            map_index = 0
            wavelengths = np.asarray(info.wavelengths, dtype=float)
            timedelays = np.asarray(info.timedelays, dtype=float)
            time_scale = getattr(info, "scaling_yunit", "") or ""
            file_info = self._format_file_info(file_path, info, data.shape)
            file_info["number_maps"] = 1
            resolved_active_data_type = "OD"
        else:
            resolved_active_data_type, file_path = self._resolve_active_path(session_state)
            opener, info = self._get_opener_and_info(file_path)

            map_index = int(session_state.get("map_index") or 0)
            if map_index < 0 or map_index >= int(info.number_maps):
                raise ValueError("Selected map index is outside the available range")

            measurement, comments = opener.read_map(file_path, map_index)
            if measurement is False:
                raise ValueError(comments or "Could not read selected map")

            data = np.asarray(measurement.data, dtype=float)
            wavelengths = np.asarray(measurement.wavelengths, dtype=float)
            timedelays = np.asarray(measurement.timedelays, dtype=float)
            time_scale = measurement.time_scale
            file_info = self._format_file_info(file_path, info, data.shape)
        cursor_state = self._normalize_selection(session_state.get("selection"), data.shape)

        x1 = cursor_state["x1"]
        x2 = cursor_state["x2"]
        y1 = cursor_state["y1"]
        y2 = cursor_state["y2"]

        kinetics = np.mean(data[x1:x2], axis=0)
        spectrum = np.mean(data[:, y1:y2], axis=1)
        heatmap_sample, heatmap_wavelengths, heatmap_timedelays = self._downsample_heatmap(
            data,
            wavelengths,
            timedelays,
        )

        assigned_data_types = [
            data_type
            for data_type, assigned_path in (session_state.get("paths") or {}).items()
            if assigned_path
        ]
        if result_payload is not None:
            assigned_data_types = ["OD", *assigned_data_types]

        return {
            "selection_ready": True,
            "active_data_type": resolved_active_data_type,
            "assigned_data_types": assigned_data_types,
            "map_index": map_index,
            "file_info": file_info,
            "heatmap": {
                "z": heatmap_sample.tolist(),
                "wavelengths": heatmap_wavelengths.tolist(),
                "timedelays": heatmap_timedelays.tolist(),
            },
            "cursors": {
                "x1": x1,
                "x2": x2,
                "y1": y1,
                "y2": y2,
                "x1_value": float(wavelengths[x1]),
                "x2_value": float(wavelengths[min(x2, len(wavelengths) - 1)]),
                "y1_value": float(timedelays[y1]),
                "y2_value": float(timedelays[min(y2, len(timedelays) - 1)]),
            },
            "kinetics": {
                "x": timedelays.tolist(),
                "y": kinetics.tolist(),
                "time_scale": time_scale,
            },
            "spectrum": {
                "x": wavelengths.tolist(),
                "y": spectrum.tolist(),
            },
        }

    def export_selection_average(
        self,
        session_state: Dict[str, object],
        user_type: str,
        ranges_text: str,
    ) -> Dict[str, object]:
        active_data_type, file_path = self._resolve_active_path(session_state)
        opener, info = self._get_opener_and_info(file_path)

        map_index = int(session_state.get("map_index") or 0)
        if map_index < 0 or map_index >= int(info.number_maps):
            raise ValueError("Selected map index is outside the available range")

        measurement, comments = opener.read_map(file_path, map_index)
        if measurement is False:
            raise ValueError(comments or "Could not read selected map")

        parsed_ranges = self._parse_average_ranges(ranges_text)
        if not parsed_ranges:
            raise ValueError(
                'Provide at least one range using "value+-range" or "value range", '
                'for example: "500+-10; 600+-5".'
            )

        if user_type == "kinetics":
            variables = np.asarray(info.wavelengths, dtype=float)
            x_values = np.asarray(info.timedelays, dtype=float)
            axis = 0
            output_path = file_path.parent / f"{file_path.stem}_kinetics.txt"
        elif user_type == "spectra":
            variables = np.asarray(info.timedelays, dtype=float)
            x_values = np.asarray(info.wavelengths, dtype=float)
            axis = 1
            output_path = file_path.parent / f"{file_path.stem}_spectra.txt"
        else:
            raise ValueError(f"Unsupported user_type '{user_type}'")

        data = np.asarray(measurement.data, dtype=float)
        normalized_ranges: List[Dict[str, float]] = []
        averaged_blocks = []

        for center, width in parsed_ranges:
            bounds = self._resolve_average_range_bounds(variables, center, width)
            if bounds is None:
                continue

            lower_idx, upper_idx, normalized_width = bounds
            if user_type == "kinetics":
                data_cut = data[lower_idx:upper_idx, :]
            else:
                data_cut = data[:, lower_idx:upper_idx]

            averaged = np.mean(data_cut, axis=axis)
            averaged_blocks.append(np.insert(x_values, 0, normalized_width))
            averaged_blocks.append(np.insert(averaged, 0, center))
            normalized_ranges.append(
                {
                    "center": float(center),
                    "width": float(normalized_width),
                    "lower_index": int(lower_idx),
                    "upper_index": int(upper_idx),
                }
            )

        if not normalized_ranges:
            raise ValueError("None of the requested ranges fit inside the selected file axes")

        payload = np.asarray(averaged_blocks, dtype=float).transpose()
        np.savetxt(str(output_path), payload, delimiter="\t", fmt="%1.3f")

        return {
            "user_type": user_type,
            "active_data_type": active_data_type,
            "map_index": map_index,
            "file_path": str(file_path),
            "output_path": str(output_path),
            "rows": int(payload.shape[0]),
            "cols": int(payload.shape[1]),
            "ranges": normalized_ranges,
        }

    def analyze_sam_cleaning(
        self,
        session_id: str,
        session_state: Dict[str, object],
        angle_threshold: float,
        surface_threshold: float,
    ) -> Dict[str, object]:
        _active_data_type, active_file_path = self._resolve_active_path(session_state)

        with self._lock:
            runtime = self._runtimes.setdefault(session_id, self._empty_runtime())
            has_cleaning_state = (
                runtime["cleaning_file_path"] == active_file_path
                and runtime["cleaning_measurements"] is not None
                and runtime["cleaning_info"] is not None
            )
            existing_measurements = (
                list(runtime["cleaning_measurements"])
                if has_cleaning_state
                else None
            )
            original_measurement_count = (
                int(runtime["cleaning_original_count"] or 0)
                if has_cleaning_state
                else None
            )
            existing_indices = (
                list(runtime["cleaning_indices"])
                if has_cleaning_state and runtime.get("cleaning_indices") is not None
                else None
            )
            existing_removed_records = (
                list(runtime["cleaning_removed_records"] or [])
                if has_cleaning_state
                else None
            )
            existing_removed_measurements = (
                list(runtime["cleaning_removed_measurements"] or [])
                if has_cleaning_state
                else None
            )

        file_path, info, _source_measurements, kept_measurements, removed_measurements, summary = self._compute_sam_cleaning(
            session_state,
            angle_threshold,
            surface_threshold,
            measurements=existing_measurements,
            original_measurement_count=original_measurement_count,
            source_indices=existing_indices,
            previous_removed_records=existing_removed_records,
        )
        removed_measurements = list(existing_removed_measurements or []) + list(removed_measurements)
        summary["file_path"] = str(file_path)
        with self._lock:
            runtime = self._runtimes.setdefault(session_id, self._empty_runtime())
            if kept_measurements:
                runtime["cleaning_file_path"] = file_path
                runtime["cleaning_info"] = info
                runtime["cleaning_measurements"] = list(kept_measurements)
                runtime["cleaning_indices"] = list(summary["kept_indices"])
                runtime["cleaning_removed_measurements"] = list(removed_measurements)
                runtime["cleaning_removed_records"] = list(summary["removed_records"])
                runtime["cleaning_original_count"] = int(summary["original_measurements"])
                runtime["cleaning_summary"] = dict(summary)
                summary["state_updated"] = True
            else:
                summary["state_updated"] = False
                if has_cleaning_state:
                    summary["warning"] = (
                        "No measurements passed the thresholds; the previous cleaned state was kept."
                    )
                else:
                    summary["warning"] = (
                        "No measurements passed the thresholds; no cleaned state was stored."
                    )
        return summary

    def reset_sam_cleaning(
        self,
        session_id: str,
        session_state: Dict[str, object],
    ) -> Dict[str, object]:
        _active_data_type, file_path = self._resolve_active_path(session_state)
        with self._lock:
            runtime = self._runtimes.setdefault(session_id, self._empty_runtime())
            has_matching_state = runtime["cleaning_file_path"] == file_path
            discarded_measurements = (
                int(len(runtime["cleaning_measurements"]))
                if has_matching_state and runtime["cleaning_measurements"] is not None
                else 0
            )
            original_measurements = (
                int(runtime["cleaning_original_count"] or 0)
                if has_matching_state
                else 0
            )
            if has_matching_state:
                self._clear_cleaning_runtime(runtime)

        return {
            "reset": True,
            "file_path": str(file_path),
            "discarded_measurements": discarded_measurements,
            "original_measurements": original_measurements,
        }

    def get_cleaning_view(
        self,
        session_id: str,
        session_state: Dict[str, object],
        trace_limit: int = 80,
    ) -> Dict[str, object]:
        _active_data_type, active_file_path = self._resolve_active_path(session_state)

        with self._lock:
            runtime = self._runtimes.setdefault(session_id, self._empty_runtime())
            has_cleaning_state = (
                runtime["cleaning_file_path"] == active_file_path
                and runtime["cleaning_measurements"] is not None
            )
            runtime_measurements = (
                list(runtime["cleaning_measurements"])
                if has_cleaning_state
                else None
            )
            runtime_original_count = int(runtime["cleaning_original_count"] or 0)

        opener, info = self._get_opener_and_info(active_file_path)
        if not hasattr(opener, "give_all_maps"):
            raise ValueError("Selected file type does not support cleaning preview")

        measurements = runtime_measurements or list(opener.give_all_maps(active_file_path))
        if not measurements:
            raise ValueError("No measurements were found in the selected file")

        maps = np.asarray([measurement.data for measurement in measurements], dtype=float)
        if maps.ndim != 3:
            raise ValueError("Cleaning preview requires map-based treatment data")

        kinetics = np.mean(maps, axis=1)
        average = np.mean(kinetics, axis=0)
        indices = self._sample_indices(kinetics.shape[0], max(1, int(trace_limit)))
        positive_values = kinetics[np.isfinite(kinetics)]
        can_use_log = positive_values.size > 0 and np.all(positive_values > 0)

        return {
            "file_path": str(active_file_path),
            "source_file_path": self._active_source_path(session_state, active_file_path),
            "cleaned_state": bool(has_cleaning_state),
            "original_measurements": (
                runtime_original_count if has_cleaning_state else int(len(measurements))
            ),
            "current_measurements": int(len(measurements)),
            "shown_measurements": int(len(indices)),
            "time_scale": getattr(info, "scaling_yunit", "") or "",
            "x": np.asarray(info.timedelays, dtype=float).tolist(),
            "traces": [
                {
                    "index": int(index),
                    "y": kinetics[int(index)].tolist(),
                }
                for index in indices
            ],
            "average": average.tolist(),
            "y_axis_type": "log" if can_use_log else "linear",
        }

    def save_sam_cleaned_h5(
        self,
        session_id: str,
        session_state: Dict[str, object],
        angle_threshold: float,
        surface_threshold: float,
        output_file_name: str = "",
    ) -> Dict[str, object]:
        if h5py is None:
            raise ValueError("h5py is not available in this Python environment")
        _active_data_type, active_file_path = self._resolve_active_path(session_state)

        with self._lock:
            runtime = self._runtimes.setdefault(session_id, self._empty_runtime())
            has_cleaning_state = (
                runtime["cleaning_file_path"] == active_file_path
                and runtime["cleaning_measurements"] is not None
                and runtime["cleaning_info"] is not None
            )
            if has_cleaning_state:
                file_path = active_file_path
                info = runtime["cleaning_info"]
                kept_measurements = list(runtime["cleaning_measurements"])
                removed_measurements = list(runtime.get("cleaning_removed_measurements") or [])
                summary = dict(runtime["cleaning_summary"] or {})
            else:
                file_path, info, _measurements, kept_measurements, removed_measurements, summary = self._compute_sam_cleaning(
                    session_state,
                    angle_threshold,
                    surface_threshold,
                )
                summary["file_path"] = str(file_path)
                if kept_measurements:
                    runtime["cleaning_file_path"] = file_path
                    runtime["cleaning_info"] = info
                    runtime["cleaning_measurements"] = list(kept_measurements)
                    runtime["cleaning_indices"] = list(summary["kept_indices"])
                    runtime["cleaning_removed_measurements"] = list(removed_measurements)
                    runtime["cleaning_removed_records"] = list(summary["removed_records"])
                    runtime["cleaning_original_count"] = int(summary["original_measurements"])
                    runtime["cleaning_summary"] = dict(summary)

        if not kept_measurements:
            raise ValueError(
                "No cleaned measurements are available. Run Analyze SAM with thresholds that keep at least one map."
            )

        source_path = self._active_source_path(session_state, file_path)

        file_name = Path(output_file_name).name.strip()
        if not file_name:
            file_name = f"{self._path_stem(source_path)}.h5"
        if not file_name.lower().endswith(".h5"):
            file_name = f"{Path(file_name).stem}.h5"

        output_target = self._cleaning_output_target(session_state, source_path, file_name)
        saved_angle_threshold = float(summary.get("angle_threshold", angle_threshold))
        saved_surface_threshold = float(summary.get("surface_threshold", surface_threshold))
        if is_smb_path(output_target):
            with tempfile.TemporaryDirectory(prefix="pyconlyse_cleaned_h5_") as tmp_dir:
                local_output_path = Path(tmp_dir) / file_name
                self._write_cleaned_h5(
                    output_path=local_output_path,
                    info=info,
                    kept_measurements=kept_measurements,
                    removed_measurements=removed_measurements,
                    original_file_path=file_path,
                    original_measurements=int(summary.get("original_measurements", len(kept_measurements))),
                    angle_threshold=saved_angle_threshold,
                    surface_threshold=saved_surface_threshold,
                    kept_indices=summary.get("kept_indices"),
                    removed_indices=summary.get("removed_indices"),
                    removed_records=summary.get("removed_records"),
                )
                copy_local_file_to_smb(local_output_path, output_target)
        else:
            output_path = Path(output_target).expanduser()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            self._write_cleaned_h5(
                output_path=output_path,
                info=info,
                kept_measurements=kept_measurements,
                removed_measurements=removed_measurements,
                original_file_path=file_path,
                original_measurements=int(summary.get("original_measurements", len(kept_measurements))),
                angle_threshold=saved_angle_threshold,
                surface_threshold=saved_surface_threshold,
                kept_indices=summary.get("kept_indices"),
                removed_indices=summary.get("removed_indices"),
                removed_records=summary.get("removed_records"),
            )

        summary["file_path"] = str(file_path)
        summary["source_file_path"] = source_path
        summary["output_path"] = str(output_target)
        return summary

    def save_file_sam_cleaned_h5(
        self,
        file_path: Path,
        angle_threshold: float,
        surface_threshold: float,
        output_file_name: str = "",
    ) -> Dict[str, object]:
        if h5py is None:
            raise ValueError("h5py is not available in this Python environment")

        path = Path(str(file_path)).expanduser()
        if not path.is_file():
            raise ValueError("Selected file does not exist")

        file_path, info, _measurements, kept_measurements, removed_measurements, summary = self._compute_sam_cleaning(
            {
                "active_data_type": "ABS",
                "paths": {"ABS": str(path)},
            },
            angle_threshold,
            surface_threshold,
        )
        if not kept_measurements:
            raise ValueError("No measurements passed the SAM cleaning thresholds")

        file_name = Path(output_file_name).name.strip()
        if not file_name:
            file_name = f"{file_path.stem}_cleaned.h5"
        if not file_name.lower().endswith(".h5"):
            file_name = f"{Path(file_name).stem}.h5"

        output_path = file_path.parent / file_name
        self._write_cleaned_h5(
            output_path=output_path,
            info=info,
            kept_measurements=kept_measurements,
            removed_measurements=removed_measurements,
            original_file_path=file_path,
            original_measurements=int(summary["original_measurements"]),
            angle_threshold=float(angle_threshold),
            surface_threshold=float(surface_threshold),
            kept_indices=summary.get("kept_indices"),
            removed_indices=summary.get("removed_indices"),
            removed_records=summary.get("removed_records"),
        )

        summary["file_path"] = str(file_path)
        summary["output_path"] = str(output_path)
        return summary

    def convert_file_to_h5(self, source_path: Path, output_path: Path) -> Dict[str, object]:
        if h5py is None:
            raise ValueError("h5py is not available in this Python environment")

        source = Path(source_path).expanduser()
        if not source.is_file():
            raise ValueError("Selected file does not exist")

        opener, info = self._get_opener_and_info(source)
        if not hasattr(opener, "give_all_maps"):
            raise ValueError("Selected file type does not support H5 conversion")

        measurements = list(opener.give_all_maps(source))
        if not measurements:
            raise ValueError("No measurements were found in the selected file")

        raw_data = np.asarray([measurement.data for measurement in measurements], dtype=float)
        target = Path(output_path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)

        with h5py.File(target, "w") as h5_file:
            metadata_group = h5_file.create_group("metadata")
            h5_file.create_dataset("timedelays", data=np.asarray(info.timedelays, dtype=float))
            h5_file.create_dataset("wavelengths", data=np.asarray(info.wavelengths, dtype=float))
            h5_file.create_dataset(
                "raw_data",
                data=raw_data,
                compression="gzip",
                compression_opts=4,
            )
            description = getattr(info, "header", "") or ""
            metadata_group.attrs["description"] = str(description).replace("\0", "").encode("utf-8")
            metadata_group.attrs["source_file"] = str(source)
            metadata_group.attrs["original_measurements"] = int(len(measurements))
            metadata_group.attrs["converted_without_cleaning"] = True

        return {
            "source_path": str(source),
            "output_path": str(target),
            "original_measurements": int(len(measurements)),
        }

    def average_noise(self, session_id: str, session_state: Dict[str, object]) -> Dict[str, object]:
        noise_path = self._require_path(session_state, "NOISE")
        opener, info = self._get_opener_and_info(noise_path)
        noise_average = np.asarray(opener.average_map(noise_path))

        with self._lock:
            runtime = self._runtimes.setdefault(session_id, self._empty_runtime())
            runtime["noise_average"] = noise_average

        return {
            "noise_ready": True,
            "shape": list(noise_average.shape),
            "sample": self._downsample_2d(noise_average).tolist(),
            "file_info": self._format_file_info(noise_path, info, noise_average.shape),
        }

    def calc_abs(self, session_id: str, session_state: Dict[str, object]) -> Dict[str, object]:
        exp_type = session_state.get("exp_type")
        if exp_type == "ABS+BASE+NOISE":
            data, info, source_path = self._calc_abs_base_noise(session_state)
        elif exp_type == "HIS+NOISE":
            data, info, source_path = self._calc_his_noise(session_id, session_state)
        elif exp_type == "HIS":
            data, info, source_path = self._calc_his(session_state)
        else:
            raise ValueError(f"Unsupported experiment type '{exp_type}'")

        with self._lock:
            runtime = self._runtimes.setdefault(session_id, self._empty_runtime())
            runtime["result"] = data
            runtime["result_info"] = info
            runtime["result_source_path"] = source_path

        return {
            "result_ready": True,
            "shape": list(data.shape),
            "sample": self._downsample_2d(data).tolist(),
            "file_info": self._format_file_info(source_path, info, data.shape),
            "min": float(np.min(data)),
            "max": float(np.max(data)),
            "mean": float(np.mean(data)),
        }

    def save_result(self, session_id: str, session_state: Dict[str, object]) -> Dict[str, object]:
        with self._lock:
            runtime = self._runtimes.get(session_id)
            if runtime is None or runtime["result"] is None or runtime["result_info"] is None:
                raise ValueError("No calculated result is available to save")
            data = np.array(runtime["result"], copy=True)
            info = runtime["result_info"]

        raw_save_folder = str(session_state.get("save_folder") or "").strip()
        save_file_name = Path(str(session_state.get("save_file_name") or "")).name
        if not raw_save_folder:
            raise ValueError("save_folder is not configured")
        if not save_file_name:
            raise ValueError("save_file_name is not configured")
        if not save_file_name.lower().endswith(".dat"):
            save_file_name = f"{Path(save_file_name).stem}.dat"

        payload = self._build_ascii_export(data, info)
        if is_smb_path(raw_save_folder):
            save_path = smb_join(raw_save_folder, save_file_name)
            with tempfile.NamedTemporaryFile(suffix=".dat", delete=True) as temp_file:
                np.savetxt(temp_file.name, payload, delimiter="\t", fmt="%.4f")
                bytes_written = copy_local_file_to_smb(temp_file.name, save_path)
            return {
                "save_path": save_path,
                "rows": int(payload.shape[0]),
                "cols": int(payload.shape[1]),
                "bytes": int(bytes_written),
            }

        save_folder = Path(raw_save_folder).expanduser()
        save_path = save_folder / save_file_name
        np.savetxt(str(save_path), payload, delimiter="\t", fmt="%.4f")
        return {
            "save_path": str(save_path),
            "rows": int(payload.shape[0]),
            "cols": int(payload.shape[1]),
        }

    def _calc_abs_base_noise(
        self, session_state: Dict[str, object]
    ) -> Tuple[np.ndarray, object, Path]:
        abs_path = self._require_path(session_state, "ABS")
        base_path = self._require_path(session_state, "BASE")
        noise_path = self._require_path(session_state, "NOISE")

        abs_opener, abs_info = self._get_opener_and_info(abs_path)
        base_opener, _ = self._get_opener_and_info(base_path)
        noise_opener, _ = self._get_opener_and_info(noise_path)

        abs_data = np.asarray(abs_opener.average_map(abs_path), dtype=float)
        base_data = np.asarray(base_opener.average_map(base_path), dtype=float)
        noise_data = np.asarray(noise_opener.average_map(noise_path), dtype=float)

        if abs_data.shape != base_data.shape or abs_data.shape != noise_data.shape:
            raise ValueError("ABS, BASE and NOISE shapes do not match")

        result = self._safe_log10_ratio(base_data - noise_data, abs_data - noise_data)
        return result, abs_info, abs_path

    def _calc_his(
        self, session_state: Dict[str, object]
    ) -> Tuple[np.ndarray, object, Path]:
        data_path = self._require_path(session_state, "ABS+BASE+NOISE")
        opener, info = self._get_opener_and_info(data_path)
        result = self._compute_his_pair_result(
            opener,
            data_path,
            calc_mode=str(session_state.get("calc_mode", "individual")),
            first_map_with_electrons=bool(
                session_state.get("first_map_with_electrons", True)
            ),
        )
        return result, info, data_path

    def _calc_his_noise(
        self, session_id: str, session_state: Dict[str, object]
    ) -> Tuple[np.ndarray, object, Path]:
        data_path = self._require_path(session_state, "ABS+BASE")
        opener, info = self._get_opener_and_info(data_path)
        if not hasattr(opener, "give_pair_maps"):
            raise ValueError("Selected file type does not support paired HIS maps")

        with self._lock:
            runtime = self._runtimes.get(session_id)
            noise_average = None
            if runtime is not None and runtime["noise_average"] is not None:
                noise_average = np.array(runtime["noise_average"], copy=True)

        if noise_average is None:
            self.average_noise(session_id, session_state)
            with self._lock:
                runtime = self._runtimes.get(session_id) or self._empty_runtime()
                noise_average = np.array(runtime["noise_average"], copy=True)

        result = self._compute_his_pair_result(
            opener,
            data_path,
            calc_mode=str(session_state.get("calc_mode", "individual")),
            first_map_with_electrons=bool(
                session_state.get("first_map_with_electrons", True)
            ),
            noise_average=noise_average,
        )
        return result, info, data_path

    def _compute_his_pair_result(
        self,
        opener,
        data_path: Path,
        calc_mode: str,
        first_map_with_electrons: bool,
        noise_average: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        if not hasattr(opener, "give_pair_maps"):
            raise ValueError("Selected file type does not support paired HIS maps")

        pair_data = []
        for measurements in opener.give_pair_maps(data_path):
            if first_map_with_electrons:
                abs_data = np.asarray(measurements[0].data, dtype=float)
                base_data = np.asarray(measurements[1].data, dtype=float)
            else:
                abs_data = np.asarray(measurements[1].data, dtype=float)
                base_data = np.asarray(measurements[0].data, dtype=float)
            pair_data.append((abs_data, base_data))

        if not pair_data:
            raise ValueError("No paired maps were found in selected HIS data")

        noise_data = None
        if noise_average is not None:
            noise_data = np.asarray(noise_average, dtype=float)
            if noise_data.shape != pair_data[0][0].shape:
                raise ValueError("Averaged NOISE shape does not match HIS map shape")

        if calc_mode == "individual":
            result = np.zeros_like(pair_data[0][0], dtype=float)
            treated_maps = 0
            for abs_data, base_data in pair_data:
                numerator = base_data if noise_data is None else base_data - noise_data
                denominator = abs_data if noise_data is None else abs_data - noise_data
                result += self._safe_log10_ratio(numerator, denominator)
                treated_maps += 1
            return result / treated_maps

        if calc_mode == "averaged":
            abs_data = np.mean(np.stack([pair[0] for pair in pair_data]), axis=0)
            base_data = np.mean(np.stack([pair[1] for pair in pair_data]), axis=0)
            numerator = base_data if noise_data is None else base_data - noise_data
            denominator = abs_data if noise_data is None else abs_data - noise_data
            return self._safe_log10_ratio(numerator, denominator)

        raise ValueError(f"Unsupported calculation mode '{calc_mode}'")

    def _get_opener_and_info(self, file_path: Path):
        opener = self._get_opener(file_path)
        success, comments = opener.fill_critical_info(file_path)
        if not success:
            raise ValueError(comments or f"Could not read file '{file_path}'")
        return opener, opener.paths[file_path]

    @staticmethod
    def _resolve_active_path(session_state: Dict[str, object]) -> Tuple[str, Path]:
        paths = session_state.get("paths") or {}
        active_data_type = str(session_state.get("active_data_type") or "").strip()
        if active_data_type and paths.get(active_data_type):
            return active_data_type, Path(str(paths[active_data_type])).expanduser()

        for data_type, file_path in paths.items():
            if file_path:
                return str(data_type), Path(str(file_path)).expanduser()

        raise ValueError("Assign at least one input file before using selection tools")

    def _active_source_path(self, session_state: Dict[str, object], fallback_path: Path) -> str:
        paths = session_state.get("paths") or {}
        path_sources = session_state.get("path_sources") or {}
        active_data_type = str(session_state.get("active_data_type") or "").strip()
        if active_data_type and path_sources.get(active_data_type):
            return str(path_sources[active_data_type])

        for data_type, file_path in paths.items():
            if file_path and Path(str(file_path)).expanduser() == fallback_path:
                return str(path_sources.get(data_type) or fallback_path)
        return str(fallback_path)

    @staticmethod
    def _path_stem(path: str) -> str:
        if is_smb_path(path):
            return Path(str(path).rstrip("/").split("/")[-1]).stem
        return Path(path).stem

    @staticmethod
    def _join_parent(path: str, file_name: str) -> str:
        if is_smb_path(path):
            return smb_join(smb_parent(path), file_name)
        return str(Path(path).expanduser().parent / file_name)

    @staticmethod
    def _cleaning_output_target(session_state: Dict[str, object], source_path: str, file_name: str) -> str:
        if is_smb_path(source_path):
            return smb_join(smb_parent(source_path), file_name)

        for folder_key in ("save_folder", "folder_path"):
            folder = str(session_state.get(folder_key) or "").strip()
            if is_smb_path(folder):
                return smb_join(folder, file_name)

        return str(Path(source_path).expanduser().parent / file_name)

    def _compute_sam_cleaning(
        self,
        session_state: Dict[str, object],
        angle_threshold: float,
        surface_threshold: float,
        measurements: Optional[List[object]] = None,
        original_measurement_count: Optional[int] = None,
        source_indices: Optional[List[int]] = None,
        previous_removed_records: Optional[List[Dict[str, object]]] = None,
    ):
        if angle_threshold <= 0:
            raise ValueError("angle_threshold must be positive")
        if surface_threshold <= 0:
            raise ValueError("surface_threshold must be positive")

        _active_data_type, file_path = self._resolve_active_path(session_state)
        opener, info = self._get_opener_and_info(file_path)
        if not hasattr(opener, "give_all_maps"):
            raise ValueError("Selected file type does not support SAM cleaning")

        if measurements is None:
            measurements = list(opener.give_all_maps(file_path))
        else:
            measurements = list(measurements)
        if not measurements:
            raise ValueError("No measurements were found in the selected file")
        if original_measurement_count is None:
            original_measurement_count = int(
                getattr(measurements[0], "original_measurements", len(measurements))
            )
        if source_indices is None:
            source_indices = [
                int(getattr(measurement, "original_index", index))
                for index, measurement in enumerate(measurements)
            ]
        else:
            source_indices = [int(index) for index in source_indices]
        if len(source_indices) != len(measurements):
            source_indices = list(range(len(measurements)))
        if not previous_removed_records and file_path.suffix.lower() == ".h5":
            previous_removed_records = self._existing_deleted_records(file_path)
        previous_removed_records = list(previous_removed_records or [])

        maps = np.asarray([measurement.data for measurement in measurements], dtype=float)
        if maps.ndim != 3:
            raise ValueError("SAM cleaning requires map-based treatment data")

        measurements_formed = np.mean(maps, axis=1)
        ref_array = np.mean(measurements_formed, axis=0)
        reference_norm = np.linalg.norm(ref_array)
        if reference_norm == 0:
            raise ValueError("Cannot compute SAM on zero-intensity reference data")
        ref_vector = ref_array / reference_norm

        spectral_angles = []
        for trace in measurements_formed:
            trace_norm = np.linalg.norm(trace)
            if trace_norm == 0:
                spectral_angles.append(float("inf"))
                continue
            dot_product = float(np.dot(trace / trace_norm, ref_vector))
            spectral_angles.append(float(np.degrees(np.arccos(np.clip(dot_product, -1.0, 1.0)))))

        average_surface = float(np.sum(np.mean(measurements_formed, axis=0)))
        if average_surface == 0:
            raise ValueError("Cannot apply surface filtering on zero-intensity data")

        kept_measurements = []
        kept_indices = []
        removed_records = []
        removed_measurements = []
        removed_by_angle = 0
        removed_by_surface = 0

        for index, (angle, measurement) in enumerate(zip(spectral_angles, measurements)):
            original_index = int(source_indices[index])
            if angle > angle_threshold:
                removed_by_angle += 1
                removed_measurements.append(measurement)
                removed_records.append({
                    "index": original_index,
                    "pass_index": int(index),
                    "reason": "angle",
                    "sam_angle": float(angle),
                    "surface_diff_percent": None,
                })
                continue

            surface = float(np.sum(np.mean(np.asarray(measurement.data, dtype=float), axis=0)))
            diff = abs((average_surface - surface) / average_surface * 100.0)
            if diff >= surface_threshold:
                removed_by_surface += 1
                removed_measurements.append(measurement)
                removed_records.append({
                    "index": original_index,
                    "pass_index": int(index),
                    "reason": "surface",
                    "sam_angle": float(angle),
                    "surface_diff_percent": float(diff),
                })
                continue

            kept_measurements.append(measurement)
            kept_indices.append(original_index)

        removed_records = previous_removed_records + removed_records
        kept_index_set = set(int(index) for index in kept_indices)
        removed_indices = [
            int(index)
            for index in range(int(original_measurement_count))
            if index not in kept_index_set
        ]

        summary = {
            "angle_threshold": float(angle_threshold),
            "surface_threshold": float(surface_threshold),
            "original_measurements": int(original_measurement_count),
            "source_measurements": int(len(measurements)),
            "cleaned_measurements": int(len(kept_measurements)),
            "removed_measurements": int(original_measurement_count - len(kept_measurements)),
            "removed_in_pass": int(len(measurements) - len(kept_measurements)),
            "removed_by_angle": int(removed_by_angle),
            "removed_by_surface": int(removed_by_surface),
            "retention_rate": float(
                len(kept_measurements) / max(1, int(original_measurement_count)) * 100.0
            ),
            "pass_retention_rate": float(len(kept_measurements) / len(measurements) * 100.0),
            "average_surface": average_surface,
            "sam_angles_sample": [float(value) for value in spectral_angles[:64]],
            "sam_angle_min": float(np.min(spectral_angles)),
            "sam_angle_max": float(np.max(spectral_angles)),
            "sam_angle_mean": float(np.mean(spectral_angles)),
            "kept_indices": kept_indices,
            "removed_indices": removed_indices,
            "removed_records": removed_records,
            "removed_current_records": removed_records[len(previous_removed_records):],
            "removed_records_sample": removed_records[:128],
        }
        return file_path, info, measurements, kept_measurements, removed_measurements, summary

    @staticmethod
    def _existing_deleted_records(file_path: Path) -> List[Dict[str, object]]:
        path = Path(file_path).expanduser()
        if path.suffix.lower() == ".h5" and h5py is not None:
            try:
                with h5py.File(path, "r") as h5_file:
                    if "deleted" in h5_file and "records_json" in h5_file["deleted"].attrs:
                        return json.loads(str(h5_file["deleted"].attrs["records_json"]))
                    if "metadata" in h5_file and "removed_records_json" in h5_file["metadata"].attrs:
                        return json.loads(str(h5_file["metadata"].attrs["removed_records_json"]))
            except Exception:
                return []
        return []

    @staticmethod
    def _existing_deleted_payload(file_path: Path) -> Tuple[np.ndarray, List[int], List[Dict[str, object]]]:
        path = Path(file_path).expanduser()
        if path.suffix.lower() != ".h5" or h5py is None:
            return np.asarray([], dtype=float), [], []
        try:
            with h5py.File(path, "r") as h5_file:
                if "deleted" not in h5_file:
                    return np.asarray([], dtype=float), [], []
                deleted_group = h5_file["deleted"]
                data = (
                    np.asarray(deleted_group["data"], dtype=float)
                    if "data" in deleted_group
                    else np.asarray([], dtype=float)
                )
                indices = (
                    [int(value) for value in np.asarray(deleted_group.attrs["indices"], dtype=int).tolist()]
                    if "indices" in deleted_group.attrs
                    else []
                )
                records = (
                    json.loads(str(deleted_group.attrs["records_json"]))
                    if "records_json" in deleted_group.attrs
                    else []
                )
                return data, indices, records
        except Exception:
            return np.asarray([], dtype=float), [], []

    @staticmethod
    def _write_cleaned_h5(
        output_path: Path,
        info,
        kept_measurements: List[object],
        removed_measurements: Optional[List[object]],
        original_file_path: Path,
        original_measurements: int,
        angle_threshold: float,
        surface_threshold: float,
        kept_indices: Optional[List[int]] = None,
        removed_indices: Optional[List[int]] = None,
        removed_records: Optional[List[Dict[str, object]]] = None,
    ) -> None:
        raw_data = np.asarray([measurement.data for measurement in kept_measurements], dtype=float)
        kept_indices_array = np.asarray(kept_indices or [], dtype=np.int64)
        removed_indices_array = np.asarray(removed_indices or [], dtype=np.int64)
        existing_deleted_data, existing_deleted_indices, existing_deleted_records = (
            TreatmentDataService._existing_deleted_payload(original_file_path)
        )
        current_removed_records = list(removed_records or [])[len(existing_deleted_records):]
        current_removed_data = np.asarray(
            [measurement.data for measurement in (removed_measurements or [])],
            dtype=float,
        )
        current_removed_indices = [
            int(record.get("index"))
            for record in current_removed_records
            if record.get("index") is not None
        ]
        if existing_deleted_data.size and current_removed_data.size:
            deleted_data = np.concatenate([existing_deleted_data, current_removed_data], axis=0)
        elif existing_deleted_data.size:
            deleted_data = existing_deleted_data
        elif current_removed_data.size:
            deleted_data = current_removed_data
        else:
            deleted_data = np.empty((0,) + tuple(raw_data.shape[1:]), dtype=float)
        deleted_indices = existing_deleted_indices + current_removed_indices

        with h5py.File(output_path, "w") as h5_file:
            metadata_group = h5_file.create_group("metadata")
            deleted_group = h5_file.create_group("deleted")
            h5_file.create_dataset("timedelays", data=np.asarray(info.timedelays, dtype=float))
            h5_file.create_dataset("wavelengths", data=np.asarray(info.wavelengths, dtype=float))
            h5_file.create_dataset(
                "raw_data",
                data=raw_data,
                compression="gzip",
                compression_opts=4,
            )
            deleted_group.create_dataset("data", data=deleted_data, compression="gzip", compression_opts=4)

            description = getattr(info, "header", "") or ""
            metadata_group.attrs["description"] = str(description).replace("\0", "").encode("utf-8")
            metadata_group.attrs["sam_angle_threshold"] = float(angle_threshold)
            metadata_group.attrs["sam_surface_threshold"] = float(surface_threshold)
            metadata_group.attrs["original_file"] = str(original_file_path)
            metadata_group.attrs["original_measurements"] = int(original_measurements)
            metadata_group.attrs["cleaned_measurements"] = int(len(kept_measurements))
            metadata_group.attrs["kept_indices"] = kept_indices_array
            metadata_group.attrs["removed_indices"] = removed_indices_array
            metadata_group.attrs["removed_records_json"] = json.dumps(
                removed_records or [],
                separators=(",", ":"),
            )
            deleted_group.attrs["indices"] = np.asarray(deleted_indices, dtype=np.int64)
            deleted_group.attrs["records_json"] = json.dumps(
                removed_records or [],
                separators=(",", ":"),
            )

    @staticmethod
    def _parse_average_ranges(ranges_text: str) -> List[Tuple[float, float]]:
        parsed: List[Tuple[float, float]] = []
        for chunk in str(ranges_text or "").split(";"):
            item = chunk.strip()
            if not item:
                continue

            plus_minus_match = re.match(
                r"^\s*([-+]?\d*\.?\d+)\s*\+\-\s*([-+]?\d*\.?\d+)\s*$",
                item,
            )
            if plus_minus_match:
                center = float(plus_minus_match.group(1))
                width = abs(float(plus_minus_match.group(2)))
                parsed.append((center, width))
                continue

            parts = item.split()
            if len(parts) == 1:
                center = float(parts[0])
                parsed.append((center, 3.0))
                continue
            if len(parts) == 2:
                center = float(parts[0])
                width = abs(float(parts[1]))
                parsed.append((center, width))
                continue

            raise ValueError(
                f'Invalid range "{item}". Use "value+-range" or "value range".'
            )

        return parsed

    @staticmethod
    def _resolve_average_range_bounds(
        variables: np.ndarray,
        center: float,
        width: float,
    ) -> Optional[Tuple[int, int, float]]:
        values = np.asarray(variables, dtype=float)
        if values.size < 2:
            return None

        center_idx = int(np.searchsorted(values, center))
        if center_idx <= 0 or center_idx >= values.size - 1:
            return None

        lower_target = center - width
        upper_target = center + width
        lower_idx = int(np.searchsorted(values, lower_target, side="left"))
        upper_idx = int(np.searchsorted(values, upper_target, side="right"))

        lower_idx = max(0, min(lower_idx, values.size - 2))
        upper_idx = max(lower_idx + 1, min(upper_idx, values.size))

        if upper_idx - lower_idx <= 0:
            return None

        lower_value = values[lower_idx]
        upper_value = values[min(upper_idx - 1, values.size - 1)]
        normalized_width = round(abs(upper_value - lower_value) / 2.0, 1)
        return lower_idx, upper_idx, normalized_width

    @classmethod
    def _normalize_selection(
        cls,
        selection_state: Optional[Dict[str, object]],
        data_shape: Tuple[int, int],
    ) -> Dict[str, int]:
        if len(data_shape) != 2:
            raise ValueError("Selection tools require 2D treatment data")

        selection_state = selection_state or {}
        x1, x2 = cls._normalize_bounds(
            selection_state.get("x1"),
            selection_state.get("x2"),
            int(data_shape[0]),
        )
        y1, y2 = cls._normalize_bounds(
            selection_state.get("y1"),
            selection_state.get("y2"),
            int(data_shape[1]),
        )
        return {"x1": x1, "x2": x2, "y1": y1, "y2": y2}

    @staticmethod
    def _normalize_bounds(start, end, length: int) -> Tuple[int, int]:
        if length <= 0:
            raise ValueError("Selection cannot be created for empty data")

        if length == 1:
            return 0, 1

        default_start = max(0, int(length * 0.2))
        default_end = min(length - 1, max(default_start + 1, int(length * 0.8)))

        start_idx = default_start if start is None else int(start)
        end_idx = default_end if end is None else int(end)

        start_idx = max(0, min(start_idx, length - 2))
        end_idx = max(1, min(end_idx, length - 1))
        if start_idx > end_idx:
            start_idx, end_idx = end_idx, start_idx
        if start_idx == end_idx:
            if end_idx < length - 1:
                end_idx += 1
            else:
                start_idx -= 1
        return start_idx, end_idx

    def _get_opener(self, file_path: Path):
        suffix = file_path.suffix.lower()
        opener_type = OPENER_ACCRODANCE.get(suffix)
        if opener_type is None:
            raise ValueError(f"Unsupported file type '{suffix}'")
        opener = self._openers.get(opener_type)
        if opener is None:
            raise ValueError(
                f"Support for '{suffix}' files is not available in this Python environment"
            )
        return opener

    @staticmethod
    def _require_path(session_state: Dict[str, object], data_type: str) -> Path:
        paths = session_state.get("paths", {})
        file_path = paths.get(data_type)
        if not file_path:
            raise ValueError(f"File for '{data_type}' is not assigned")
        path = Path(str(file_path)).expanduser()
        if not path.is_file():
            raise ValueError(f"Assigned file for '{data_type}' does not exist")
        return path

    @staticmethod
    def _safe_log10_ratio(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
        numerator = np.asarray(numerator, dtype=float)
        denominator = np.asarray(denominator, dtype=float)
        if numerator.shape != denominator.shape:
            raise ValueError("Numerator and denominator shapes do not match")

        if np.any(numerator <= 0) or np.any(denominator <= 0):
            raise ValueError("Treatment calculation produced non-positive transmission values")

        transmission = numerator / denominator
        if np.any(transmission <= 0):
            raise ValueError("Treatment calculation produced invalid transmission values")
        return np.log10(transmission)

    @staticmethod
    def _downsample_1d(values: np.ndarray, limit: int = 64) -> np.ndarray:
        arr = np.asarray(values)
        if arr.shape[0] <= limit:
            return arr
        idx = np.linspace(0, arr.shape[0] - 1, num=limit, dtype=int)
        return arr[idx]

    @staticmethod
    def _downsample_2d(values: np.ndarray, limit: int = 64) -> np.ndarray:
        arr = np.asarray(values)
        if arr.ndim != 2:
            return arr
        rows = (
            np.linspace(0, arr.shape[0] - 1, num=min(limit, arr.shape[0]), dtype=int)
            if arr.shape[0] > limit
            else np.arange(arr.shape[0], dtype=int)
        )
        cols = (
            np.linspace(0, arr.shape[1] - 1, num=min(limit, arr.shape[1]), dtype=int)
            if arr.shape[1] > limit
            else np.arange(arr.shape[1], dtype=int)
        )
        return arr[np.ix_(rows, cols)]

    @classmethod
    def _downsample_heatmap(
        cls,
        values: np.ndarray,
        wavelengths: np.ndarray,
        timedelays: np.ndarray,
        limit: int = 96,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        arr = np.asarray(values)
        waves = np.asarray(wavelengths)
        times = np.asarray(timedelays)
        wave_idx = cls._sample_indices(arr.shape[0], limit)
        time_idx = cls._sample_indices(arr.shape[1], limit)
        sampled = arr[np.ix_(wave_idx, time_idx)].transpose()
        return sampled, waves[wave_idx], times[time_idx]

    @staticmethod
    def _sample_indices(length: int, limit: int) -> np.ndarray:
        if length <= limit:
            return np.arange(length, dtype=int)
        return np.linspace(0, length - 1, num=limit, dtype=int)

    @staticmethod
    def _format_file_info(file_path: Path, info, data_shape) -> Dict[str, object]:
        wavelengths = np.asarray(info.wavelengths, dtype=float)
        return {
            "file_path": str(file_path),
            "suffix": file_path.suffix.lower(),
            "number_maps": int(info.number_maps),
            "timedelays_length": int(info.timedelays_length),
            "wavelengths_length": int(info.wavelengths_length),
            "wavelength_min": float(np.min(wavelengths)) if wavelengths.size else None,
            "wavelength_max": float(np.max(wavelengths)) if wavelengths.size else None,
            "time_scale": getattr(info, "scaling_yunit", "") or "",
            "data_shape": list(data_shape),
        }

    @staticmethod
    def _build_ascii_export(data: np.ndarray, info) -> np.ndarray:
        result = np.asarray(data, dtype=float).transpose()
        wavelengths = np.asarray(info.wavelengths, dtype=float)
        final_data = np.vstack((wavelengths, result))
        final_data = final_data.transpose()
        timedelays = np.insert(np.asarray(info.timedelays, dtype=float), 0, 0.0)
        final_data = np.vstack((timedelays, final_data))
        return final_data
