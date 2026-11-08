import logging
import os
import re
import sys
import tempfile
from pathlib import Path
from threading import Lock
from types import SimpleNamespace
from typing import Dict, List, Optional, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from treatment_cleaning import TreatmentCleaning
from treatment_conversion import TreatmentConversion, h5py
from treatment_od_stitching import TreatmentODStitching
from treatment_network_path import (
    copy_local_file_to_smb_atomic,
    is_smb_path,
    smb_join,
    smb_parent,
)
from utilities.dataio import (
    OPENER_ACCRODANCE,
    ASCIIOpener,
    H5Opener,
    HamamatsuFileOpener,
    OpenersTypes,
)

module_logger = logging.getLogger(__name__)


class TreatmentDataService(TreatmentCleaning, TreatmentConversion, TreatmentODStitching):
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

    def get_skana_result(self, session_id: str):
        """Copy the full calculated OD already in RAM; never reopen an input file."""
        with self._lock:
            runtime = self._runtimes.get(session_id)
            if not runtime or runtime.get('result') is None or runtime.get('result_info') is None:
                return None
            data = np.asarray(runtime['result'])
            if data.size > 2_000_000:
                raise ValueError('OD exceeds 2 million cells; select or compress before SK-Ana analysis.')
            info = runtime['result_info']
            return SimpleNamespace(data=np.array(data, dtype=float, copy=True),
                wavelengths=np.array(info.wavelengths, dtype=float, copy=True),
                timedelays=np.array(info.timedelays, dtype=float, copy=True),
                time_scale=getattr(info, 'scaling_yunit', '') or '??',
                signal_unit='OD', source='Calculated OD')

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
            "sample": self._finite_list(sample),
            "wavelengths": self._downsample_1d(np.asarray(measurement.wavelengths)).tolist(),
            "timedelays": self._downsample_1d(np.asarray(measurement.timedelays)).tolist(),
            "time_scale": measurement.time_scale,
            **self._finite_statistics(data),
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
            preview_state = session_state
            if active_data_type == "DAT" and session_state.get("dat_preview_path"):
                preview_state = {**session_state, "paths": {"DAT": session_state["dat_preview_path"]}}
            resolved_active_data_type, file_path = self._resolve_active_path(preview_state)
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

        kinetics = self._finite_mean(data[x1:x2], axis=0)
        spectrum = self._finite_mean(data[:, y1:y2], axis=1)
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
        if session_state.get("dat_preview_path"):
            assigned_data_types = ["DAT", *assigned_data_types]

        return {
            "selection_ready": True,
            "active_data_type": resolved_active_data_type,
            "assigned_data_types": assigned_data_types,
            "map_index": map_index,
            "file_info": file_info,
            "heatmap": {
                "z": self._finite_list(heatmap_sample),
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
                "y": self._finite_list(kinetics),
                "time_scale": time_scale,
            },
            "spectrum": {
                "x": wavelengths.tolist(),
                "y": self._finite_list(spectrum),
            },
        }

    def export_selection_average(
        self,
        session_state: Dict[str, object],
        user_type: str,
        ranges_text: str,
    ) -> Dict[str, object]:
        preview_state = session_state
        if session_state.get("active_data_type") == "DAT" and session_state.get("dat_preview_path"):
            preview_state = {**session_state, "paths": {"DAT": session_state["dat_preview_path"]}}
        active_data_type, file_path = self._resolve_active_path(preview_state)
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
            "sample": self._finite_list(self._downsample_2d(data)),
            "file_info": self._format_file_info(source_path, info, data.shape),
            **self._finite_statistics(data),
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
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    suffix=".dat",
                    delete=False,
                ) as temp_file:
                    temp_path = Path(temp_file.name)
                    np.savetxt(temp_file, payload, delimiter="\t", fmt="%.4f")
                    temp_file.flush()
                    os.fsync(temp_file.fileno())
                bytes_written = copy_local_file_to_smb_atomic(temp_path, save_path)
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
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".dat",
                prefix=f".{save_file_name}.",
                dir=save_folder,
                delete=False,
            ) as temp_file:
                temp_path = Path(temp_file.name)
                np.savetxt(temp_file, payload, delimiter="\t", fmt="%.4f")
                temp_file.flush()
                os.fsync(temp_file.fileno())
            os.replace(temp_path, save_path)
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
        return {
            "save_path": str(save_path),
            "rows": int(payload.shape[0]),
            "cols": int(payload.shape[1]),
            "bytes": int(save_path.stat().st_size),
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

        include_excluded = bool(session_state.get("include_excluded_maps", False))

        def average(opener, path):
            if include_excluded and H5Opener is not None and isinstance(opener, H5Opener):
                return opener.average_map(path, include_excluded=True)
            return opener.average_map(path)

        abs_data = np.asarray(average(abs_opener, abs_path), dtype=float)
        base_data = np.asarray(average(base_opener, base_path), dtype=float)
        noise_data = np.asarray(average(noise_opener, noise_path), dtype=float)

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
            valid_maps = np.zeros_like(result, dtype=int)
            for abs_data, base_data in pair_data:
                numerator = base_data if noise_data is None else base_data - noise_data
                denominator = abs_data if noise_data is None else abs_data - noise_data
                od = self._safe_log10_ratio(numerator, denominator)
                valid = np.isfinite(od)
                np.add(result, od, out=result, where=valid)
                valid_maps += valid
            return np.divide(result, valid_maps, out=np.full_like(result, np.nan), where=valid_maps > 0)

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

        valid = (np.isfinite(numerator) & np.isfinite(denominator)
                 & (numerator > 0) & (denominator > 0))
        od = np.full(numerator.shape, np.nan)
        od[valid] = np.log10(numerator[valid]) - np.log10(denominator[valid])
        return od

    @staticmethod
    def _finite_list(data: np.ndarray) -> list:
        return np.where(np.isfinite(data), data, None).tolist()

    @staticmethod
    def _finite_statistics(data: np.ndarray) -> Dict[str, object]:
        finite = data[np.isfinite(data)]
        return {
            "min": float(finite.min()) if finite.size else None,
            "max": float(finite.max()) if finite.size else None,
            "mean": float(finite.mean()) if finite.size else None,
            "valid_pixels": int(finite.size),
            "invalid_pixels": int(data.size - finite.size),
        }

    @staticmethod
    def _finite_mean(data: np.ndarray, axis: int) -> np.ndarray:
        valid = np.isfinite(data)
        counts = valid.sum(axis=axis)
        sums = np.sum(data, axis=axis, where=valid)
        return np.divide(sums, counts, out=np.full_like(sums, np.nan), where=counts > 0)

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

    @staticmethod
    def _build_ascii_export(data: np.ndarray, info) -> np.ndarray:
        result = np.asarray(data, dtype=float).transpose()
        wavelengths = np.asarray(info.wavelengths, dtype=float)
        final_data = np.vstack((wavelengths, result))
        final_data = final_data.transpose()
        timedelays = np.insert(np.asarray(info.timedelays, dtype=float), 0, 0.0)
        final_data = np.vstack((timedelays, final_data))
        return final_data
