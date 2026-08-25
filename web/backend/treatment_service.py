import logging
import json
import re
import sys
import tempfile
from pathlib import Path
from threading import Lock
from types import SimpleNamespace
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

from utilities.dataio import (
    ASCIIOpener,
    H5Opener,
    HamamatsuFileOpener,
    OPENER_ACCRODANCE,
    OpenersTypes,
)
from treatment_network_path import (
    copy_local_file_to_smb,
    copy_local_file_to_smb_atomic,
    is_smb_path,
    smb_join,
    smb_parent,
)

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
        original_number_maps = int(getattr(preview, "original_measurements", int(info.number_maps)))
        return self._format_file_info(
            file_path,
            info,
            preview.data.shape,
            original_number_maps=original_number_maps,
        )

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

        file_path, info, _source_measurements, kept_measurements, removed_measurements, summary = self._compute_sam_cleaning(
            session_state,
            angle_threshold,
            surface_threshold,
        )
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
                    self._clear_cleaning_runtime(runtime)
                    summary["warning"] = (
                        "No measurements passed the thresholds; the previous cleaned preview was cleared."
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

        measurements = runtime_measurements or self._give_all_maps_for_cleaning(
            opener,
            active_file_path,
        )
        if not has_cleaning_state:
            measurements, includes_deleted = self._reconstruct_h5_measurements_with_deleted(
                active_file_path,
                info,
                measurements,
            )
        else:
            includes_deleted = False
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
            "includes_deleted_measurements": bool(includes_deleted),
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

    def restore_cleaned_h5_file(self, file_path: Path) -> Dict[str, object]:
        if h5py is None:
            raise ValueError("h5py is not available in this Python environment")
        path = Path(file_path).expanduser()
        if path.suffix.lower() != ".h5":
            raise ValueError("Restore denoising requires an H5 file")
        if not path.is_file():
            raise ValueError("Selected file does not exist")

        with h5py.File(path, "r") as h5_file:
            if "raw_data" not in h5_file:
                raise ValueError("H5 file does not contain raw_data")
            raw_data = np.asarray(h5_file["raw_data"], dtype=float)
            if raw_data.ndim != 3:
                raise ValueError("Restore denoising requires map-based H5 data")
            wavelengths = np.asarray(h5_file["wavelengths"], dtype=float)
            timedelays = np.asarray(h5_file["timedelays"], dtype=float)
            metadata_attrs = dict(h5_file["metadata"].attrs) if "metadata" in h5_file else {}
            has_map_selection = (
                "map_selection" in h5_file
                and "included" in h5_file["map_selection"]
            )
            selection_mask = (
                np.asarray(h5_file["map_selection"]["included"], dtype=bool)
                if has_map_selection
                else None
            )
            selection_records = []
            if has_map_selection and "records_json" in h5_file["map_selection"].attrs:
                try:
                    selection_records = json.loads(
                        str(h5_file["map_selection"].attrs["records_json"])
                    )
                except (TypeError, ValueError):
                    selection_records = []
            kept_indices = (
                [int(value) for value in np.asarray(metadata_attrs.get("kept_indices"), dtype=int).tolist()]
                if "kept_indices" in metadata_attrs
                else list(range(raw_data.shape[0]))
            )
            deleted_data, deleted_indices, deleted_records = self._existing_deleted_payload(path)

        if has_map_selection:
            if selection_mask.shape != (raw_data.shape[0],):
                raise ValueError("H5 map_selection/included does not match raw_data")
            restored_count = int(np.count_nonzero(~selection_mask))
            if restored_count == 0:
                return {
                    "file_path": str(path),
                    "restored": False,
                    "restored_measurements": 0,
                    "current_measurements": int(raw_data.shape[0]),
                    "original_measurements": int(raw_data.shape[0]),
                }

            with h5py.File(path, "r+") as h5_file:
                metadata_group = h5_file.require_group("metadata")
                selection_group = h5_file["map_selection"]
                del selection_group["included"]
                selection_group.create_dataset(
                    "included",
                    data=np.ones(raw_data.shape[0], dtype=bool),
                )
                selection_group.attrs["schema_version"] = 1
                selection_group.attrs["method"] = "restore"
                selection_group.attrs["records_json"] = "[]"
                for attr_name in ("sam_angle_threshold", "sam_surface_threshold"):
                    if attr_name in selection_group.attrs:
                        del selection_group.attrs[attr_name]
                metadata_group.attrs["original_measurements"] = int(raw_data.shape[0])
                metadata_group.attrs["cleaned_measurements"] = int(raw_data.shape[0])
                metadata_group.attrs["h5_schema_version"] = 2
                metadata_group.attrs["kept_indices"] = np.arange(
                    raw_data.shape[0], dtype=np.int64
                )
                metadata_group.attrs["removed_indices"] = np.asarray([], dtype=np.int64)
                metadata_group.attrs["removed_records_json"] = "[]"
                metadata_group.attrs["restored_excluded_measurements"] = restored_count
                metadata_group.attrs["restored_from_map_selection"] = True

            return {
                "file_path": str(path),
                "restored": True,
                "restored_measurements": restored_count,
                "current_measurements": int(raw_data.shape[0]),
                "original_measurements": int(raw_data.shape[0]),
                "previous_removed_records": selection_records[:128],
            }

        if deleted_data.size == 0 or not deleted_indices:
            return {
                "file_path": str(path),
                "restored": False,
                "restored_measurements": 0,
                "current_measurements": int(raw_data.shape[0]),
                "original_measurements": int(raw_data.shape[0]),
            }

        indexed_maps: Dict[int, np.ndarray] = {}
        for fallback_index, data in enumerate(raw_data):
            index = kept_indices[fallback_index] if fallback_index < len(kept_indices) else fallback_index
            indexed_maps[int(index)] = np.asarray(data, dtype=float)
        for data, index in zip(deleted_data, deleted_indices):
            indexed_maps[int(index)] = np.asarray(data, dtype=float)

        ordered = sorted(indexed_maps.items(), key=lambda item: item[0])
        restored_data = np.asarray([data for _index, data in ordered], dtype=float)
        restored_indices = np.asarray([index for index, _data in ordered], dtype=np.int64)
        restored_count = int(len(deleted_indices))
        metadata_attrs["original_measurements"] = int(restored_data.shape[0])
        metadata_attrs["cleaned_measurements"] = int(restored_data.shape[0])
        metadata_attrs["kept_indices"] = restored_indices
        metadata_attrs["removed_indices"] = np.asarray([], dtype=np.int64)
        metadata_attrs["removed_records_json"] = "[]"
        metadata_attrs["restored_deleted_measurements"] = restored_count
        metadata_attrs["restored_from_deleted"] = True
        metadata_attrs["h5_schema_version"] = 2

        with h5py.File(path, "w") as h5_file:
            metadata_group = h5_file.create_group("metadata")
            h5_file.create_dataset("timedelays", data=timedelays)
            h5_file.create_dataset("wavelengths", data=wavelengths)
            h5_file.create_dataset(
                "raw_data",
                data=restored_data,
                compression="gzip",
                compression_opts=4,
            )
            self._write_map_selection(
                h5_file,
                np.ones(restored_data.shape[0], dtype=bool),
                method="restore",
            )
            for key, value in metadata_attrs.items():
                metadata_group.attrs[key] = value

        return {
            "file_path": str(path),
            "restored": True,
            "restored_measurements": restored_count,
            "current_measurements": int(restored_data.shape[0]),
            "original_measurements": int(restored_data.shape[0]),
            "previous_deleted_records": deleted_records[:128],
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
            runtime_summary = dict(runtime["cleaning_summary"] or {}) if has_cleaning_state else {}
            thresholds_match = (
                has_cleaning_state
                and abs(float(runtime_summary.get("angle_threshold", -1.0)) - float(angle_threshold)) < 1e-12
                and abs(float(runtime_summary.get("surface_threshold", -1.0)) - float(surface_threshold)) < 1e-12
            )
            if thresholds_match:
                file_path = active_file_path
                info = runtime["cleaning_info"]
                kept_measurements = list(runtime["cleaning_measurements"])
                removed_measurements = list(runtime.get("cleaning_removed_measurements") or [])
                summary = runtime_summary
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
                    preserve_existing_deleted=not bool(summary.get("source_includes_deleted_measurements")),
                )
                copy_local_file_to_smb_atomic(local_output_path, output_target)
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
                preserve_existing_deleted=not bool(summary.get("source_includes_deleted_measurements")),
            )

        summary["file_path"] = str(file_path)
        summary["source_file_path"] = source_path
        summary["output_path"] = str(output_target)
        summary["compression"] = "gzip"
        summary["compression_level"] = 4
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
            preserve_existing_deleted=not bool(summary.get("source_includes_deleted_measurements")),
        )

        summary["file_path"] = str(file_path)
        summary["output_path"] = str(output_path)
        summary["compression"] = "gzip"
        summary["compression_level"] = 4
        return summary

    def convert_file_to_h5(self, source_path: Path, output_path: Path, progress_callback=None) -> Dict[str, object]:
        if h5py is None:
            raise ValueError("h5py is not available in this Python environment")

        source = Path(source_path).expanduser()
        if not source.is_file():
            raise ValueError("Selected file does not exist")
        target = Path(output_path).expanduser()

        opener, info = self._get_opener_and_info(source)
        if not hasattr(opener, "give_all_maps"):
            raise ValueError("Selected file type does not support H5 conversion")

        if isinstance(opener, H5Opener) and source.resolve() == target.resolve():
            with h5py.File(source, "r") as h5_file:
                is_canonical_h5 = (
                    "raw_data" in h5_file
                    and "map_selection" in h5_file
                    and "included" in h5_file["map_selection"]
                )
                raw_map_count = (
                    int(h5_file["raw_data"].shape[0]) if "raw_data" in h5_file else 0
                )
            if is_canonical_h5:
                return {
                    "source_path": str(source),
                    "output_path": str(target),
                    "original_measurements": raw_map_count,
                    "compression": "gzip",
                    "compression_level": 4,
                }

        if all(
            hasattr(info, attr)
            for attr in (
                "bytes_per_point",
                "data_pos",
                "timedelays_length",
                "wavelengths_length",
                "number_maps",
            )
        ):
            return self._convert_hamamatsu_file_to_h5(source, output_path, info, progress_callback)

        selection_mask = None
        selection_records = []
        selection_method = "all"
        selection_angle_threshold = None
        selection_surface_threshold = None
        if isinstance(opener, H5Opener):
            with h5py.File(source, "r") as h5_file:
                raw_map_count = int(h5_file["raw_data"].shape[0])
                candidate_mask = H5Opener._selection_mask(h5_file, raw_map_count)
                if "map_selection" in h5_file and "included" in h5_file["map_selection"]:
                    selection_mask = candidate_mask
                    selection_group = h5_file["map_selection"]
                    selection_method = str(selection_group.attrs.get("method", "all"))
                    if "sam_angle_threshold" in selection_group.attrs:
                        selection_angle_threshold = float(
                            selection_group.attrs["sam_angle_threshold"]
                        )
                    if "sam_surface_threshold" in selection_group.attrs:
                        selection_surface_threshold = float(
                            selection_group.attrs["sam_surface_threshold"]
                        )
                    records_json = selection_group.attrs.get("records_json", "[]")
                    if isinstance(records_json, bytes):
                        records_json = records_json.decode("utf-8", errors="ignore")
                    try:
                        selection_records = json.loads(str(records_json))
                    except (TypeError, ValueError):
                        selection_records = []
            measurements = iter(opener.give_all_maps(source, include_excluded=True))
        else:
            measurements = iter(opener.give_all_maps(source))
        first_measurement = next(measurements, None)
        if first_measurement is None:
            raise ValueError("No measurements were found in the selected file")

        first_map = np.asarray(first_measurement.data, dtype=float)
        expected_measurements = int(getattr(info, "number_maps", 0) or 0) or 1
        target.parent.mkdir(parents=True, exist_ok=True)

        with h5py.File(target, "w") as h5_file:
            metadata_group = h5_file.create_group("metadata")
            h5_file.create_dataset("timedelays", data=np.asarray(info.timedelays, dtype=float))
            h5_file.create_dataset("wavelengths", data=np.asarray(info.wavelengths, dtype=float))
            raw_dataset = h5_file.create_dataset(
                "raw_data",
                shape=(expected_measurements,) + tuple(first_map.shape),
                dtype=float,
                compression="gzip",
                compression_opts=4,
            )
            raw_dataset[0] = first_map
            if progress_callback:
                progress_callback(1, expected_measurements)
            written_measurements = 1
            for index, measurement in enumerate(measurements, start=1):
                raw_dataset[index] = np.asarray(measurement.data, dtype=float)
                written_measurements = index + 1
                if progress_callback:
                    progress_callback(written_measurements, expected_measurements)
            self._write_map_selection(
                h5_file,
                selection_mask
                if selection_mask is not None
                else np.ones(written_measurements, dtype=bool),
                records=selection_records,
                method=selection_method,
                angle_threshold=selection_angle_threshold,
                surface_threshold=selection_surface_threshold,
            )
            description = getattr(info, "header", "") or ""
            time_scale = getattr(info, "scaling_yunit", "") or ""
            metadata_group.attrs["description"] = str(description).replace("\0", "").encode("utf-8")
            metadata_group.attrs["source_file"] = str(source)
            metadata_group.attrs["original_measurements"] = int(written_measurements)
            metadata_group.attrs["converted_without_cleaning"] = selection_mask is None
            metadata_group.attrs["h5_schema_version"] = 2
            metadata_group.attrs["compression"] = "gzip"
            metadata_group.attrs["compression_level"] = 4
            metadata_group.attrs["time_scale"] = str(time_scale)
            metadata_group.attrs["scaling_yunit"] = str(time_scale)

        return {
            "source_path": str(source),
            "output_path": str(target),
            "original_measurements": int(written_measurements),
            "compression": "gzip",
            "compression_level": 4,
        }

    def _convert_hamamatsu_file_to_h5(self, source: Path, output_path: Path, info, progress_callback=None) -> Dict[str, object]:
        number_type_by_size = {
            1: np.int8,
            2: np.int16,
            4: np.int32,
        }
        number_type = number_type_by_size.get(int(info.bytes_per_point))
        if number_type is None:
            raise ValueError(f"Unsupported Hamamatsu bytes_per_point: {info.bytes_per_point}")

        number_maps = int(info.number_maps or 1)
        timedelays_length = int(info.timedelays_length)
        wavelengths_length = int(info.wavelengths_length)
        size_data_bytes = int(info.bytes_per_point) * timedelays_length * wavelengths_length
        target = Path(output_path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)

        with h5py.File(target, "w") as h5_file:
            metadata_group = h5_file.create_group("metadata")
            h5_file.create_dataset("timedelays", data=np.asarray(info.timedelays, dtype=float))
            h5_file.create_dataset("wavelengths", data=np.asarray(info.wavelengths, dtype=float))
            raw_dataset = h5_file.create_dataset(
                "raw_data",
                shape=(number_maps, wavelengths_length, timedelays_length),
                dtype=float,
                compression="gzip",
                compression_opts=4,
            )
            with open(source, "rb") as file_handle:
                for map_index in range(number_maps):
                    offset = int(info.data_pos) + 64 * map_index + map_index * size_data_bytes
                    file_handle.seek(offset, 0)
                    raw = file_handle.read(size_data_bytes)
                    if len(raw) != size_data_bytes:
                        raise ValueError(
                            f"Could not read full HIS map {map_index + 1}/{number_maps} from {source}"
                        )
                    data = np.frombuffer(raw, dtype=number_type).reshape(
                        timedelays_length,
                        wavelengths_length,
                    ).transpose()
                    raw_dataset[map_index] = data
                    if progress_callback:
                        progress_callback(map_index + 1, number_maps)

            self._write_map_selection(
                h5_file,
                np.ones(number_maps, dtype=bool),
            )

            description = getattr(info, "header", "") or ""
            time_scale = getattr(info, "scaling_yunit", "") or ""
            metadata_group.attrs["description"] = str(description).replace("\0", "").encode("utf-8")
            metadata_group.attrs["source_file"] = str(source)
            metadata_group.attrs["original_measurements"] = number_maps
            metadata_group.attrs["converted_without_cleaning"] = True
            metadata_group.attrs["h5_schema_version"] = 2
            metadata_group.attrs["compression"] = "gzip"
            metadata_group.attrs["compression_level"] = 4
            metadata_group.attrs["time_scale"] = str(time_scale)
            metadata_group.attrs["scaling_yunit"] = str(time_scale)

        return {
            "source_path": str(source),
            "output_path": str(target),
            "original_measurements": number_maps,
            "compression": "gzip",
            "compression_level": 4,
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
            temp_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".dat", delete=False) as temp_file:
                    temp_path = Path(temp_file.name)
                np.savetxt(temp_path, payload, delimiter="\t", fmt="%.4f")
                bytes_written = copy_local_file_to_smb(temp_path, save_path)
            finally:
                if temp_path is not None:
                    temp_path.unlink(missing_ok=True)
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

    def stitch_od_dat_files(
        self,
        first_path: Path,
        second_path: Path,
        output_path: Path,
        time_regions: Optional[List[Dict[str, float]]] = None,
        left_scale: float = 1.0,
        left_offset: float = 0.0,
        right_scale: float = 1.0,
        right_offset: float = 0.0,
        right_delay_shift_pixels: int = 0,
    ) -> Dict[str, object]:
        stitch = self.build_od_stitch(
            first_path,
            second_path,
            left_scale=left_scale,
            left_offset=left_offset,
            right_scale=right_scale,
            right_offset=right_offset,
            right_delay_shift_pixels=right_delay_shift_pixels,
            time_regions=time_regions,
        )
        stitched_wavelengths = stitch["stitched"]["wavelengths"]
        stitched_data = stitch["stitched"]["data"]
        first_delays = stitch["timedelays"]
        payload = self._build_od_dat_table(stitched_data, stitched_wavelengths, first_delays)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        np.savetxt(str(output_path), payload, delimiter="\t", fmt="%.6g")

        return {
            "first_path": str(first_path),
            "second_path": str(second_path),
            "output_path": str(output_path),
            "rows": int(payload.shape[0]),
            "cols": int(payload.shape[1]),
            "wavelengths": int(stitched_wavelengths.size),
            "timedelays": int(first_delays.size),
            "wavelength_min": float(np.min(stitched_wavelengths)) if stitched_wavelengths.size else None,
            "wavelength_max": float(np.max(stitched_wavelengths)) if stitched_wavelengths.size else None,
            "timedelay_min": float(np.min(first_delays)) if first_delays.size else None,
            "timedelay_max": float(np.max(first_delays)) if first_delays.size else None,
            "overlap_range": stitch["overlap_range"],
            "axis_overlap_range": stitch["axis_overlap_range"],
            "trusted_ranges": stitch["trusted_ranges"],
            "left_path": stitch["left_path"],
            "right_path": stitch["right_path"],
            "left_scale": float(left_scale),
            "left_offset": float(left_offset),
            "right_scale": float(right_scale),
            "right_offset": float(right_offset),
            "right_delay_shift_pixels": int(right_delay_shift_pixels),
        }

    def build_od_stitch(
        self,
        first_path: Path,
        second_path: Path,
        left_scale: float = 1.0,
        left_offset: float = 0.0,
        right_scale: float = 1.0,
        right_offset: float = 0.0,
        right_delay_shift_pixels: int = 0,
        time_regions: Optional[List[Dict[str, float]]] = None,
    ) -> Dict[str, object]:
        first = self._read_od_dat(first_path)
        second = self._read_od_dat(second_path)
        first_delays = first["timedelays"]
        second_delays = second["timedelays"]
        if first_delays.shape != second_delays.shape or not np.allclose(
            first_delays,
            second_delays,
            rtol=1e-7,
            atol=1e-9,
        ):
            raise ValueError("OD maps must have identical delay axes before stitching")

        first_min = float(np.min(first["wavelengths"]))
        second_min = float(np.min(second["wavelengths"]))
        if first_min <= second_min:
            left, right = first, second
            left_path, right_path = str(first_path), str(second_path)
        else:
            left, right = second, first
            left_path, right_path = str(second_path), str(first_path)

        left_waves = np.asarray(left["wavelengths"], dtype=float)
        right_waves = np.asarray(right["wavelengths"], dtype=float)
        left_data = np.asarray(left["data"], dtype=float) * float(left_scale) + float(left_offset)
        right_data = np.asarray(right["data"], dtype=float) * float(right_scale) + float(right_offset)
        right_data = self._shift_od_delay_axis(right_data, int(right_delay_shift_pixels))

        axis_overlap_min = max(float(np.min(left_waves)), float(np.min(right_waves)))
        axis_overlap_max = min(float(np.max(left_waves)), float(np.max(right_waves)))
        if axis_overlap_min > axis_overlap_max:
            raise ValueError("OD maps do not overlap in wavelength")
        trusted = self._stitch_trusted_wavelength_bounds(
            left_waves,
            right_waves,
            time_regions,
            axis_overlap_min,
            axis_overlap_max,
        )
        overlap_min, overlap_max = trusted["overlap"]

        left_lower_mask = left_waves < overlap_min
        right_upper_mask = right_waves > overlap_max
        overlap_waves = self._stitch_overlap_wavelength_grid(
            overlap_min,
            overlap_max,
            left_waves,
            right_waves,
        )
        if overlap_waves.size == 0:
            raise ValueError("Trusted overlap has no wavelength grid points")

        left_interp = self._interpolate_od_matrix(left_waves, left_data, overlap_waves)
        right_interp = self._interpolate_od_matrix(right_waves, right_data, overlap_waves)
        overlap_data = (left_interp + right_interp) / 2.0

        stitched_waves = np.concatenate([
            left_waves[left_lower_mask],
            overlap_waves,
            right_waves[right_upper_mask],
        ])
        stitched_data = np.vstack([
            left_data[left_lower_mask],
            overlap_data,
            right_data[right_upper_mask],
        ])

        return {
            "left": {"wavelengths": left_waves, "data": left_data},
            "right": {"wavelengths": right_waves, "data": right_data},
            "stitched": {"wavelengths": stitched_waves, "data": stitched_data},
            "timedelays": first_delays,
            "overlap_range": [float(overlap_min), float(overlap_max)],
            "axis_overlap_range": [float(axis_overlap_min), float(axis_overlap_max)],
            "trusted_ranges": {
                "left": [float(trusted["left"][0]), float(trusted["left"][1])],
                "right": [float(trusted["right"][0]), float(trusted["right"][1])],
            },
            "left_path": left_path,
            "right_path": right_path,
            "right_delay_shift_pixels": int(right_delay_shift_pixels),
        }

    def fit_od_stitch_right_scale(
        self,
        first_path: Path,
        second_path: Path,
        time_regions: Optional[List[Dict[str, float]]] = None,
        right_delay_shift_pixels: int = 0,
    ) -> Dict[str, float]:
        stitch = self.build_od_stitch(
            first_path,
            second_path,
            right_delay_shift_pixels=right_delay_shift_pixels,
        )
        left_waves = stitch["left"]["wavelengths"]
        right_waves = stitch["right"]["wavelengths"]
        left_data = stitch["left"]["data"]
        right_data = stitch["right"]["data"]
        timedelays = stitch["timedelays"]
        overlap_min, overlap_max = stitch["overlap_range"]
        regions = time_regions or [{
            "delay_start": float(np.min(timedelays)),
            "delay_end": float(np.max(timedelays)),
            "left_wavelength_start": overlap_min,
            "left_wavelength_end": overlap_max,
            "right_wavelength_start": overlap_min,
            "right_wavelength_end": overlap_max,
        }]
        target_profiles = []
        source_profiles = []
        for region in regions:
            delay_indices = self._delay_region_indices(timedelays, [region])
            left_start, left_end = self._region_wavelength_bounds(region, "left", overlap_min, overlap_max)
            right_start, right_end = self._region_wavelength_bounds(region, "right", overlap_min, overlap_max)
            common_min = max(min(left_start, left_end), min(right_start, right_end), overlap_min)
            common_max = min(max(left_start, left_end), max(right_start, right_end), overlap_max)
            if common_min > common_max:
                raise ValueError("Selected stitch regions do not overlap in trusted wavelength range")
            common_waves = self._stitch_overlap_wavelength_grid(
                common_min,
                common_max,
                left_waves,
                right_waves,
            )
            if common_waves.size == 0:
                raise ValueError("Trusted fit overlap has no wavelength grid points")
            left_profile = np.mean(left_data[:, delay_indices], axis=1)
            right_profile = np.mean(right_data[:, delay_indices], axis=1)
            left_interp = np.interp(common_waves, left_waves, left_profile)
            right_interp = np.interp(common_waves, right_waves, right_profile)
            target_profiles.append(left_interp)
            source_profiles.append(right_interp)
        x = np.concatenate(source_profiles).reshape(-1)
        y = np.concatenate(target_profiles).reshape(-1)
        valid = np.isfinite(x) & np.isfinite(y)
        if int(np.sum(valid)) < 1:
            raise ValueError("Not enough spectral profile points to fit right map")
        denominator = float(np.dot(x[valid], x[valid]))
        if abs(denominator) < 1e-15:
            raise ValueError("Right integrated profile is too close to zero to fit")
        scale = float(np.dot(x[valid], y[valid]) / denominator)
        x_valid = x[valid]
        y_valid = y[valid]
        x_centered = x_valid - float(np.mean(x_valid))
        y_centered = y_valid - float(np.mean(y_valid))
        corr_denom = float(np.linalg.norm(x_centered) * np.linalg.norm(y_centered))
        correlation = float(np.dot(x_centered, y_centered) / corr_denom) if corr_denom > 0 else None
        residual = (x_valid * scale) - y_valid
        target_norm = float(np.linalg.norm(y_valid))
        rmse = float(np.sqrt(np.mean(residual ** 2)))
        relative_rmse = float(np.linalg.norm(residual) / target_norm) if target_norm > 0 else None
        return {
            "right_scale": scale,
            "right_offset": 0.0,
            "fit_method": "spectral_profile",
            "fit_points": int(np.sum(valid)),
            "correlation": correlation,
            "rmse": rmse,
            "relative_rmse": relative_rmse,
            "left_profile_min": float(np.min(y_valid)),
            "left_profile_max": float(np.max(y_valid)),
            "right_profile_min": float(np.min(x_valid)),
            "right_profile_max": float(np.max(x_valid)),
        }

    def preview_od_stitch(
        self,
        first_path: Path,
        second_path: Path,
        time_regions: Optional[List[Dict[str, float]]] = None,
        left_scale: float = 1.0,
        left_offset: float = 0.0,
        right_scale: float = 1.0,
        right_offset: float = 0.0,
        right_delay_shift_pixels: int = 0,
    ) -> Dict[str, object]:
        stitch = self.build_od_stitch(
            first_path,
            second_path,
            left_scale=left_scale,
            left_offset=left_offset,
            right_scale=right_scale,
            right_offset=right_offset,
            right_delay_shift_pixels=right_delay_shift_pixels,
            time_regions=time_regions,
        )
        timedelays = stitch["timedelays"]
        regions = time_regions or [
            {
                "delay_start": float(np.min(timedelays)),
                "delay_end": float(np.max(timedelays)),
                "left_wavelength_start": stitch["overlap_range"][0],
                "left_wavelength_end": stitch["overlap_range"][1],
                "right_wavelength_start": stitch["overlap_range"][0],
                "right_wavelength_end": stitch["overlap_range"][1],
                "label": "All delays",
            }
        ]
        return {
            "left_path": stitch["left_path"],
            "right_path": stitch["right_path"],
            "overlap_range": stitch["overlap_range"],
            "axis_overlap_range": stitch["axis_overlap_range"],
            "trusted_ranges": stitch["trusted_ranges"],
            "timedelay_min": float(np.min(timedelays)) if timedelays.size else None,
            "timedelay_max": float(np.max(timedelays)) if timedelays.size else None,
            "left": self._od_heatmap_payload(stitch["left"]["data"], stitch["left"]["wavelengths"], timedelays),
            "right": self._od_heatmap_payload(stitch["right"]["data"], stitch["right"]["wavelengths"], timedelays),
            "stitched": self._od_heatmap_payload(stitch["stitched"]["data"], stitch["stitched"]["wavelengths"], timedelays),
            "spectra": self._od_region_spectra(stitch, regions),
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
            measurements = self._give_all_maps_for_cleaning(opener, file_path)
            measurements, source_includes_deleted = self._reconstruct_h5_measurements_with_deleted(
                file_path,
                info,
                measurements,
            )
        else:
            measurements = list(measurements)
            source_includes_deleted = False
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
            "source_includes_deleted_measurements": bool(source_includes_deleted),
        }
        return file_path, info, measurements, kept_measurements, removed_measurements, summary

    @staticmethod
    def _give_all_maps_for_cleaning(opener, file_path: Path) -> List[object]:
        """Read all source maps, including maps excluded by a prior H5 selection.

        Non-H5 openers keep their established one-argument contract.  Canonical
        H5 files expose the optional flag so cleaning can be recomputed against
        the complete acquisition rather than a previous selected subset.
        """
        if isinstance(opener, H5Opener):
            return list(opener.give_all_maps(file_path, include_excluded=True))
        return list(opener.give_all_maps(file_path))

    @staticmethod
    def _write_map_selection(
        h5_file,
        included: np.ndarray,
        *,
        records: Optional[List[Dict[str, object]]] = None,
        method: str = "all",
        angle_threshold: Optional[float] = None,
        surface_threshold: Optional[float] = None,
    ) -> None:
        """Write the canonical non-destructive map-selection contract."""
        selected = np.asarray(included, dtype=bool)
        selection_group = h5_file.create_group("map_selection")
        selection_group.create_dataset("included", data=selected)
        selection_group.attrs["schema_version"] = 1
        selection_group.attrs["method"] = str(method)
        selection_group.attrs["records_json"] = json.dumps(
            records or [],
            separators=(",", ":"),
        )
        if angle_threshold is not None:
            selection_group.attrs["sam_angle_threshold"] = float(angle_threshold)
        if surface_threshold is not None:
            selection_group.attrs["sam_surface_threshold"] = float(surface_threshold)

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
    def _reconstruct_h5_measurements_with_deleted(
        file_path: Path,
        info,
        measurements: List[object],
    ) -> Tuple[List[object], bool]:
        path = Path(file_path).expanduser()
        if path.suffix.lower() != ".h5" or h5py is None:
            return measurements, False
        deleted_data, deleted_indices, _deleted_records = TreatmentDataService._existing_deleted_payload(path)
        if deleted_data.size == 0 or not deleted_indices:
            return measurements, False

        indexed: Dict[int, object] = {}
        for fallback_index, measurement in enumerate(measurements):
            original_index = int(getattr(measurement, "original_index", fallback_index))
            indexed[original_index] = measurement

        time_scale = getattr(info, "scaling_yunit", "") or ""
        for data, original_index in zip(deleted_data, deleted_indices):
            measurement = SimpleNamespace(
                type=".h5",
                comments="deleted H5 frame restored for cleaning preview",
                author="",
                timestamp=path.stat().st_mtime,
                data=np.asarray(data, dtype=float),
                wavelengths=np.asarray(info.wavelengths, dtype=float),
                timedelays=np.asarray(info.timedelays, dtype=float),
                time_scale=time_scale,
                original_index=int(original_index),
                original_measurements=max(len(measurements) + len(deleted_indices), int(original_index) + 1),
            )
            indexed[int(original_index)] = measurement

        return [measurement for _index, measurement in sorted(indexed.items())], True

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
        preserve_existing_deleted: bool = True,
    ) -> None:
        """Write a canonical H5 without physically removing rejected maps.

        ``raw_data`` is the complete acquisition in original map order.  The
        authoritative cleaning result is ``map_selection/included``.  The
        compatibility parameter is intentionally retained for callers from the
        legacy save flow, but old ``/deleted`` payloads are migrated instead of
        copied into newly written files.
        """
        del preserve_existing_deleted

        total = int(original_measurements)
        if total <= 0:
            raise ValueError("Cannot write H5 map selection without measurements")

        selected_indices = [int(index) for index in (kept_indices or [])]
        if len(selected_indices) != len(kept_measurements):
            selected_indices = [
                int(getattr(measurement, "original_index", index))
                for index, measurement in enumerate(kept_measurements)
            ]
        rejected_indices = [int(index) for index in (removed_indices or [])]
        rejected_measurements = list(removed_measurements or [])
        if len(rejected_indices) != len(rejected_measurements):
            rejected_indices = [
                int(getattr(measurement, "original_index", index))
                for index, measurement in enumerate(rejected_measurements)
            ]

        indexed_maps: Dict[int, np.ndarray] = {}
        for index, measurement in zip(selected_indices, kept_measurements):
            indexed_maps[int(index)] = np.asarray(measurement.data, dtype=float)
        for index, measurement in zip(rejected_indices, rejected_measurements):
            if int(index) in indexed_maps:
                raise ValueError(f"Map {index} is both selected and excluded")
            indexed_maps[int(index)] = np.asarray(measurement.data, dtype=float)

        expected_indices = set(range(total))
        if set(indexed_maps) != expected_indices:
            raise ValueError(
                "SAM cleaning did not retain a complete map archive; refusing to write a lossy H5"
            )

        raw_data = np.asarray([indexed_maps[index] for index in range(total)], dtype=float)
        included = np.zeros(total, dtype=bool)
        included[np.asarray(selected_indices, dtype=int)] = True
        kept_indices_array = np.flatnonzero(included).astype(np.int64)
        removed_indices_array = np.flatnonzero(~included).astype(np.int64)

        with h5py.File(output_path, "w") as h5_file:
            metadata_group = h5_file.create_group("metadata")
            h5_file.create_dataset("timedelays", data=np.asarray(info.timedelays, dtype=float))
            h5_file.create_dataset("wavelengths", data=np.asarray(info.wavelengths, dtype=float))
            h5_file.create_dataset(
                "raw_data",
                data=raw_data,
                compression="gzip",
                compression_opts=4,
            )
            TreatmentDataService._write_map_selection(
                h5_file,
                included,
                records=removed_records,
                method="sam",
                angle_threshold=angle_threshold,
                surface_threshold=surface_threshold,
            )

            description = getattr(info, "header", "") or ""
            time_scale = getattr(info, "scaling_yunit", "") or ""
            metadata_group.attrs["description"] = str(description).replace("\0", "").encode("utf-8")
            metadata_group.attrs["sam_angle_threshold"] = float(angle_threshold)
            metadata_group.attrs["sam_surface_threshold"] = float(surface_threshold)
            metadata_group.attrs["compression"] = "gzip"
            metadata_group.attrs["compression_level"] = 4
            metadata_group.attrs["time_scale"] = str(time_scale)
            metadata_group.attrs["scaling_yunit"] = str(time_scale)
            metadata_group.attrs["original_file"] = str(original_file_path)
            metadata_group.attrs["original_measurements"] = total
            metadata_group.attrs["cleaned_measurements"] = int(np.count_nonzero(included))
            metadata_group.attrs["h5_schema_version"] = 2
            metadata_group.attrs["kept_indices"] = kept_indices_array
            metadata_group.attrs["removed_indices"] = removed_indices_array
            metadata_group.attrs["removed_records_json"] = json.dumps(
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
    def _format_file_info(
        file_path: Path,
        info,
        data_shape,
        original_number_maps: Optional[int] = None,
    ) -> Dict[str, object]:
        wavelengths = np.asarray(info.wavelengths, dtype=float)
        timedelays = np.asarray(info.timedelays, dtype=float)
        number_maps = int(info.number_maps)
        return {
            "file_path": str(file_path),
            "suffix": file_path.suffix.lower(),
            "number_maps": number_maps,
            "original_number_maps": int(original_number_maps or number_maps),
            "timedelays_length": int(info.timedelays_length),
            "wavelengths_length": int(info.wavelengths_length),
            "wavelength_min": float(np.min(wavelengths)) if wavelengths.size else None,
            "wavelength_max": float(np.max(wavelengths)) if wavelengths.size else None,
            "timedelay_min": float(np.min(timedelays)) if timedelays.size else None,
            "timedelay_max": float(np.max(timedelays)) if timedelays.size else None,
            "time_scale": getattr(info, "scaling_yunit", "") or "",
            "data_shape": list(data_shape),
        }

    @classmethod
    def _od_heatmap_payload(
        cls,
        data: np.ndarray,
        wavelengths: np.ndarray,
        timedelays: np.ndarray,
        limit: int = 120,
    ) -> Dict[str, object]:
        sampled, sampled_wavelengths, sampled_timedelays = cls._downsample_heatmap(
            np.asarray(data, dtype=float),
            np.asarray(wavelengths, dtype=float),
            np.asarray(timedelays, dtype=float),
            limit=limit,
        )
        return {
            "x": sampled_wavelengths.tolist(),
            "y": sampled_timedelays.tolist(),
            "z": sampled.tolist(),
            "wavelength_min": float(np.min(wavelengths)) if len(wavelengths) else None,
            "wavelength_max": float(np.max(wavelengths)) if len(wavelengths) else None,
            "timedelay_min": float(np.min(timedelays)) if len(timedelays) else None,
            "timedelay_max": float(np.max(timedelays)) if len(timedelays) else None,
            "shape": [int(data.shape[0]), int(data.shape[1])],
        }

    @classmethod
    def _od_region_spectra(
        cls,
        stitch: Dict[str, object],
        time_regions: List[Dict[str, float]],
    ) -> List[Dict[str, object]]:
        timedelays = np.asarray(stitch["timedelays"], dtype=float)
        spectra = []
        for index, region in enumerate(time_regions):
            delay_indices = cls._delay_region_indices(timedelays, [region])
            start = float(np.min(timedelays[delay_indices]))
            end = float(np.max(timedelays[delay_indices]))
            label = str(region.get("label") or f"{start:g}-{end:g}")
            left_mask = cls._wavelength_region_mask(stitch["left"]["wavelengths"], [region], side="left")
            right_mask = cls._wavelength_region_mask(stitch["right"]["wavelengths"], [region], side="right")
            stitched_mask = cls._wavelength_region_mask(stitch["stitched"]["wavelengths"], [region])
            left_profile = cls._integrated_wavelength_profile(
                stitch["left"]["wavelengths"],
                stitch["left"]["data"],
                left_mask,
            )
            right_profile = cls._integrated_wavelength_profile(
                stitch["right"]["wavelengths"],
                stitch["right"]["data"],
                right_mask,
            )
            stitched_profile = cls._integrated_wavelength_profile(
                stitch["stitched"]["wavelengths"],
                stitch["stitched"]["data"],
                stitched_mask,
            )
            overlap_min, overlap_max = stitch["overlap_range"]
            overlap_waves = cls._stitch_overlap_wavelength_grid(
                overlap_min,
                overlap_max,
                stitch["left"]["wavelengths"],
                stitch["right"]["wavelengths"],
            )
            left_delay_profile = np.mean(stitch["left"]["data"][:, delay_indices], axis=1)
            right_delay_profile = np.mean(stitch["right"]["data"][:, delay_indices], axis=1)
            spectra.append({
                "label": label,
                "delay_start": start,
                "delay_end": end,
                "left_wavelength_start": region.get("left_wavelength_start", region.get("wavelength_start")),
                "left_wavelength_end": region.get("left_wavelength_end", region.get("wavelength_end")),
                "right_wavelength_start": region.get("right_wavelength_start", region.get("wavelength_start")),
                "right_wavelength_end": region.get("right_wavelength_end", region.get("wavelength_end")),
                "left": {
                    "x": stitch["left"]["wavelengths"].tolist(),
                    "y": np.mean(stitch["left"]["data"][:, delay_indices], axis=1).tolist(),
                },
                "right": {
                    "x": stitch["right"]["wavelengths"].tolist(),
                    "y": np.mean(stitch["right"]["data"][:, delay_indices], axis=1).tolist(),
                },
                "stitched": {
                    "x": stitch["stitched"]["wavelengths"].tolist(),
                    "y": np.mean(stitch["stitched"]["data"][:, delay_indices], axis=1).tolist(),
                },
                "left_selected": {
                    "x": stitch["left"]["wavelengths"][left_mask].tolist(),
                    "y": np.mean(stitch["left"]["data"][left_mask][:, delay_indices], axis=1).tolist(),
                },
                "right_selected": {
                    "x": stitch["right"]["wavelengths"][right_mask].tolist(),
                    "y": np.mean(stitch["right"]["data"][right_mask][:, delay_indices], axis=1).tolist(),
                },
                "stitched_selected": {
                    "x": stitch["stitched"]["wavelengths"][stitched_mask].tolist(),
                    "y": np.mean(stitch["stitched"]["data"][stitched_mask][:, delay_indices], axis=1).tolist(),
                },
                "left_overlap": {
                    "x": overlap_waves.tolist(),
                    "y": np.interp(
                        overlap_waves,
                        stitch["left"]["wavelengths"],
                        left_delay_profile,
                    ).tolist(),
                },
                "right_overlap": {
                    "x": overlap_waves.tolist(),
                    "y": np.interp(
                        overlap_waves,
                        stitch["right"]["wavelengths"],
                        right_delay_profile,
                    ).tolist(),
                },
                "profiles": {
                    "left": {
                        "x": timedelays.tolist(),
                        "y": left_profile.tolist(),
                    },
                    "right": {
                        "x": timedelays.tolist(),
                        "y": right_profile.tolist(),
                    },
                    "stitched": {
                        "x": timedelays.tolist(),
                        "y": stitched_profile.tolist(),
                    },
                    "left_selected": {
                        "x": timedelays[delay_indices].tolist(),
                        "y": left_profile[delay_indices].tolist(),
                    },
                    "right_selected": {
                        "x": timedelays[delay_indices].tolist(),
                        "y": right_profile[delay_indices].tolist(),
                    },
                    "stitched_selected": {
                        "x": timedelays[delay_indices].tolist(),
                        "y": stitched_profile[delay_indices].tolist(),
                    },
                },
                "color": cls._region_color(index),
            })
        return spectra

    @staticmethod
    def _integrated_wavelength_profile(
        wavelengths: np.ndarray,
        data: np.ndarray,
        wavelength_mask: np.ndarray,
    ) -> np.ndarray:
        waves = np.asarray(wavelengths, dtype=float)
        values = np.asarray(data, dtype=float)
        mask = np.asarray(wavelength_mask, dtype=bool)
        if values.ndim != 2:
            raise ValueError("OD map data must be a 2D wavelength-delay matrix")
        if values.shape[0] != waves.size:
            raise ValueError("OD map wavelength axis does not match data rows")
        selected_waves = waves[mask]
        selected_values = values[mask]
        if selected_waves.size == 0:
            raise ValueError("Selected stitch region has no wavelength points")
        if selected_waves.size == 1:
            return selected_values[0]
        return np.trapz(selected_values, selected_waves, axis=0)

    @classmethod
    def _stitch_overlap_wavelength_grid(
        cls,
        start: float,
        end: float,
        *axes: np.ndarray,
    ) -> np.ndarray:
        lower = float(min(start, end))
        upper = float(max(start, end))
        if np.isclose(lower, upper):
            return np.asarray([lower], dtype=float)
        steps = []
        for axis in axes:
            values = np.asarray(axis, dtype=float)
            values = np.unique(values[np.isfinite(values)])
            if values.size < 2:
                continue
            diffs = np.diff(np.sort(values))
            diffs = diffs[diffs > 0]
            if diffs.size:
                steps.append(float(np.median(diffs)))
        step = min(steps) if steps else upper - lower
        if step <= 0:
            return np.asarray([lower, upper], dtype=float)
        grid = np.arange(lower, upper + step * 0.5, step, dtype=float)
        grid = grid[(grid >= lower - step * 1e-6) & (grid <= upper + step * 1e-6)]
        if grid.size == 0 or not np.isclose(grid[0], lower):
            grid = np.insert(grid, 0, lower)
        if not np.isclose(grid[-1], upper):
            grid = np.append(grid, upper)
        return np.unique(np.round(grid, decimals=10))

    @staticmethod
    def _interpolate_od_matrix(
        source_wavelengths: np.ndarray,
        source_data: np.ndarray,
        target_wavelengths: np.ndarray,
    ) -> np.ndarray:
        waves = np.asarray(source_wavelengths, dtype=float)
        values = np.asarray(source_data, dtype=float)
        target = np.asarray(target_wavelengths, dtype=float)
        if values.ndim != 2:
            raise ValueError("OD map data must be a 2D wavelength-delay matrix")
        if values.shape[0] != waves.size:
            raise ValueError("OD map wavelength axis does not match data rows")
        return np.vstack([
            np.interp(target, waves, values[:, delay_index])
            for delay_index in range(values.shape[1])
        ]).transpose()

    @classmethod
    def _stitch_trusted_wavelength_bounds(
        cls,
        left_waves: np.ndarray,
        right_waves: np.ndarray,
        time_regions: Optional[List[Dict[str, float]]],
        axis_overlap_min: float,
        axis_overlap_max: float,
    ) -> Dict[str, Tuple[float, float]]:
        if not time_regions:
            left_bounds = (float(np.min(left_waves)), axis_overlap_max)
            right_bounds = (axis_overlap_min, float(np.max(right_waves)))
        else:
            left_starts = []
            left_ends = []
            right_starts = []
            right_ends = []
            for region in time_regions:
                try:
                    left_start, left_end = cls._region_wavelength_bounds(
                        region,
                        "left",
                        axis_overlap_min,
                        axis_overlap_max,
                    )
                    right_start, right_end = cls._region_wavelength_bounds(
                        region,
                        "right",
                        axis_overlap_min,
                        axis_overlap_max,
                    )
                except (TypeError, ValueError, AttributeError):
                    continue
                left_starts.append(min(left_start, left_end))
                left_ends.append(max(left_start, left_end))
                right_starts.append(min(right_start, right_end))
                right_ends.append(max(right_start, right_end))
            if not left_starts or not right_starts:
                left_bounds = (float(np.min(left_waves)), axis_overlap_max)
                right_bounds = (axis_overlap_min, float(np.max(right_waves)))
            else:
                left_bounds = (min(left_starts), max(left_ends))
                right_bounds = (min(right_starts), max(right_ends))

        left_min = max(float(np.min(left_waves)), float(left_bounds[0]))
        left_max = min(float(np.max(left_waves)), float(left_bounds[1]))
        right_min = max(float(np.min(right_waves)), float(right_bounds[0]))
        right_max = min(float(np.max(right_waves)), float(right_bounds[1]))
        overlap_min = max(left_min, right_min, axis_overlap_min)
        overlap_max = min(left_max, right_max, axis_overlap_max)
        if left_min > left_max:
            raise ValueError("Trusted left wavelength range is outside the left OD map")
        if right_min > right_max:
            raise ValueError("Trusted right wavelength range is outside the right OD map")
        if overlap_min > overlap_max:
            raise ValueError("Trusted left/right wavelength ranges do not overlap")
        return {
            "left": (left_min, left_max),
            "right": (right_min, right_max),
            "overlap": (overlap_min, overlap_max),
        }

    @staticmethod
    def _region_wavelength_bounds(
        region: Dict[str, float],
        side: str,
        default_min: float,
        default_max: float,
    ) -> Tuple[float, float]:
        start = float(region.get(f"{side}_wavelength_start", region.get("wavelength_start", default_min)))
        end = float(region.get(f"{side}_wavelength_end", region.get("wavelength_end", default_max)))
        return start, end

    @staticmethod
    def _shift_od_delay_axis(data: np.ndarray, shift_pixels: int) -> np.ndarray:
        shift = int(shift_pixels)
        source = np.asarray(data, dtype=float)
        if shift == 0 or source.ndim != 2 or source.shape[1] == 0:
            return source
        if abs(shift) >= source.shape[1]:
            fill_index = 0 if shift > 0 else source.shape[1] - 1
            return np.repeat(source[:, fill_index:fill_index + 1], source.shape[1], axis=1)

        shifted = np.empty_like(source)
        if shift > 0:
            shifted[:, :shift] = source[:, :1]
            shifted[:, shift:] = source[:, :-shift]
        else:
            offset = abs(shift)
            shifted[:, :-offset] = source[:, offset:]
            shifted[:, -offset:] = source[:, -1:]
        return shifted

    @staticmethod
    def _wavelength_region_mask(
        wavelengths: np.ndarray,
        time_regions: Optional[List[Dict[str, float]]] = None,
        default_min: Optional[float] = None,
        default_max: Optional[float] = None,
        side: Optional[str] = None,
    ) -> np.ndarray:
        waves = np.asarray(wavelengths, dtype=float)
        if waves.size == 0:
            raise ValueError("OD map has no wavelength axis")
        mask = np.zeros(waves.shape, dtype=bool)
        for region in time_regions or []:
            try:
                if side in {"left", "right"}:
                    start = float(region.get(f"{side}_wavelength_start", region.get("wavelength_start")))
                    end = float(region.get(f"{side}_wavelength_end", region.get("wavelength_end")))
                else:
                    starts = [
                        region.get("wavelength_start"),
                        region.get("left_wavelength_start"),
                        region.get("right_wavelength_start"),
                    ]
                    ends = [
                        region.get("wavelength_end"),
                        region.get("left_wavelength_end"),
                        region.get("right_wavelength_end"),
                    ]
                    numeric_starts = [float(item) for item in starts if item is not None]
                    numeric_ends = [float(item) for item in ends if item is not None]
                    start = min(numeric_starts)
                    end = max(numeric_ends)
            except (TypeError, ValueError, AttributeError):
                continue
            lower = min(start, end)
            upper = max(start, end)
            if default_min is not None:
                lower = max(lower, float(default_min))
            if default_max is not None:
                upper = min(upper, float(default_max))
            mask |= (waves >= lower) & (waves <= upper)
        if np.any(mask):
            return mask
        lower = float(default_min) if default_min is not None else float(np.min(waves))
        upper = float(default_max) if default_max is not None else float(np.max(waves))
        return (waves >= lower) & (waves <= upper)

    @staticmethod
    def _delay_region_indices(
        timedelays: np.ndarray,
        time_regions: Optional[List[Dict[str, float]]] = None,
    ) -> np.ndarray:
        delays = np.asarray(timedelays, dtype=float)
        if delays.size == 0:
            raise ValueError("OD map has no delay axis")
        if not time_regions:
            return np.arange(delays.size, dtype=int)

        selected = set()
        for region in time_regions:
            try:
                start = float(region.get("delay_start", region.get("start")))
                end = float(region.get("delay_end", region.get("end")))
            except (TypeError, ValueError, AttributeError):
                continue
            lower = min(start, end)
            upper = max(start, end)
            indices = np.flatnonzero((delays >= lower) & (delays <= upper))
            if indices.size == 0:
                nearest = int(np.argmin(np.abs(delays - ((lower + upper) / 2.0))))
                indices = np.asarray([nearest], dtype=int)
            selected.update(int(item) for item in indices)
        if not selected:
            return np.arange(delays.size, dtype=int)
        return np.asarray(sorted(selected), dtype=int)

    @staticmethod
    def _region_color(index: int) -> str:
        colors = ["#38bdf8", "#f97316", "#22c55e", "#e879f9", "#facc15", "#fb7185"]
        return colors[index % len(colors)]

    @staticmethod
    def _build_ascii_export(data: np.ndarray, info) -> np.ndarray:
        result = np.asarray(data, dtype=float).transpose()
        wavelengths = np.asarray(info.wavelengths, dtype=float)
        final_data = np.vstack((wavelengths, result))
        final_data = final_data.transpose()
        timedelays = np.insert(np.asarray(info.timedelays, dtype=float), 0, 0.0)
        final_data = np.vstack((timedelays, final_data))
        return final_data

    @staticmethod
    def _build_od_dat_table(
        data: np.ndarray,
        wavelengths: np.ndarray,
        timedelays: np.ndarray,
    ) -> np.ndarray:
        payload = np.zeros((len(wavelengths) + 1, len(timedelays) + 1), dtype=float)
        payload[0, 1:] = np.asarray(timedelays, dtype=float)
        payload[1:, 0] = np.asarray(wavelengths, dtype=float)
        payload[1:, 1:] = np.asarray(data, dtype=float)
        return payload

    @classmethod
    def _read_od_dat(cls, file_path: Path) -> Dict[str, np.ndarray]:
        try:
            table = np.loadtxt(str(file_path), dtype=float, ndmin=2)
        except OSError as exc:
            raise ValueError(f"Could not read OD DAT file '{file_path}'") from exc
        except ValueError as exc:
            raise ValueError(f"Could not parse OD DAT file '{file_path}'") from exc

        if table.ndim != 2 or table.shape[0] < 2 or table.shape[1] < 2:
            raise ValueError("OD DAT file must contain a header row, header column and data")

        row_header = np.asarray(table[0, 1:], dtype=float)
        col_header = np.asarray(table[1:, 0], dtype=float)
        body = np.asarray(table[1:, 1:], dtype=float)
        col_header_looks_like_wavelength = cls._axis_looks_like_wavelength(col_header)
        row_header_looks_like_wavelength = cls._axis_looks_like_wavelength(row_header)

        if row_header_looks_like_wavelength and not col_header_looks_like_wavelength:
            wavelengths = row_header
            timedelays = col_header
            data = body.transpose()
        else:
            wavelengths = col_header
            timedelays = row_header
            data = body

        if data.shape != (len(wavelengths), len(timedelays)):
            raise ValueError("OD DAT file axis headers do not match data shape")
        if not cls._is_monotonic(wavelengths):
            raise ValueError("OD DAT wavelength axis must be monotonic")
        return {
            "wavelengths": np.asarray(wavelengths, dtype=float),
            "timedelays": np.asarray(timedelays, dtype=float),
            "data": np.asarray(data, dtype=float),
        }

    @staticmethod
    def _axis_looks_like_wavelength(values: np.ndarray) -> bool:
        finite = np.asarray(values, dtype=float)
        finite = finite[np.isfinite(finite)]
        if finite.size == 0:
            return False
        minimum = float(np.min(finite))
        maximum = float(np.max(finite))
        return 150.0 <= minimum <= 2500.0 and 150.0 <= maximum <= 2500.0

    @staticmethod
    def _is_monotonic(values: np.ndarray) -> bool:
        if len(values) < 2:
            return True
        diffs = np.diff(np.asarray(values, dtype=float))
        return bool(np.all(diffs >= 0) or np.all(diffs <= 0))
