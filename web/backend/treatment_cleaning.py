"""SAM cleaning and recovery of previously removed measurements."""

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, List, Optional, Tuple

import numpy as np

from treatment_conversion import h5py
from treatment_network_path import copy_local_file_to_smb_atomic, is_smb_path, smb_join, smb_parent
from utilities.dataio import H5Opener


class TreatmentCleaning:
    """Cleaning operations that share the treatment service runtime."""

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
        deleted_data, deleted_indices, _deleted_records = TreatmentCleaning._existing_deleted_payload(path)
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
            TreatmentCleaning._write_map_selection(
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
