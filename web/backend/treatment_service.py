import logging
import sys
from pathlib import Path
from threading import Lock
from typing import Dict, Optional, Tuple

import numpy as np

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

        self._noise_average = None
        self._result = None
        self._result_info = None
        self._result_source_path = None

    @property
    def supported_suffixes(self):
        return tuple(sorted(OPENER_ACCRODANCE.keys()))

    def reset_runtime(self):
        with self._lock:
            self._noise_average = None
            self._result = None
            self._result_info = None
            self._result_source_path = None

    def runtime_status(self):
        with self._lock:
            result_shape = tuple(self._result.shape) if self._result is not None else None
            result_source = (
                str(self._result_source_path) if self._result_source_path is not None else ""
            )
            return {
                "noise_ready": self._noise_average is not None,
                "result_ready": self._result is not None,
                "result_shape": result_shape,
                "result_source_path": result_source,
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

    def average_noise(self, session_state: Dict[str, object]) -> Dict[str, object]:
        noise_path = self._require_path(session_state, "NOISE")
        opener, info = self._get_opener_and_info(noise_path)
        noise_average = np.asarray(opener.average_map(noise_path))

        with self._lock:
            self._noise_average = noise_average

        return {
            "noise_ready": True,
            "shape": list(noise_average.shape),
            "sample": self._downsample_2d(noise_average).tolist(),
            "file_info": self._format_file_info(noise_path, info, noise_average.shape),
        }

    def calc_abs(self, session_state: Dict[str, object]) -> Dict[str, object]:
        exp_type = session_state.get("exp_type")
        if exp_type == "ABS+BASE+NOISE":
            data, info, source_path = self._calc_abs_base_noise(session_state)
        elif exp_type == "HIS+NOISE":
            data, info, source_path = self._calc_his_noise(session_state)
        elif exp_type == "HIS":
            raise ValueError("HIS mode is not implemented yet in web treatment")
        else:
            raise ValueError(f"Unsupported experiment type '{exp_type}'")

        with self._lock:
            self._result = data
            self._result_info = info
            self._result_source_path = source_path

        return {
            "result_ready": True,
            "shape": list(data.shape),
            "sample": self._downsample_2d(data).tolist(),
            "file_info": self._format_file_info(source_path, info, data.shape),
            "min": float(np.min(data)),
            "max": float(np.max(data)),
            "mean": float(np.mean(data)),
        }

    def save_result(self, session_state: Dict[str, object]) -> Dict[str, object]:
        with self._lock:
            if self._result is None or self._result_info is None:
                raise ValueError("No calculated result is available to save")
            data = np.array(self._result, copy=True)
            info = self._result_info

        save_folder = Path(str(session_state.get("save_folder") or "")).expanduser()
        save_file_name = Path(str(session_state.get("save_file_name") or "")).name
        if not save_folder:
            raise ValueError("save_folder is not configured")
        if not save_file_name:
            raise ValueError("save_file_name is not configured")

        save_path = save_folder / save_file_name
        payload = self._build_ascii_export(data, info)
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

    def _calc_his_noise(
        self, session_state: Dict[str, object]
    ) -> Tuple[np.ndarray, object, Path]:
        data_path = self._require_path(session_state, "ABS+BASE")
        opener, info = self._get_opener_and_info(data_path)
        if not hasattr(opener, "give_pair_maps"):
            raise ValueError("Selected file type does not support paired HIS maps")

        with self._lock:
            noise_average = None if self._noise_average is None else np.array(self._noise_average, copy=True)

        if noise_average is None:
            noise_summary = self.average_noise(session_state)
            noise_average = np.asarray(noise_summary["sample"])
            with self._lock:
                noise_average = np.array(self._noise_average, copy=True)

        first_map_with_electrons = bool(session_state.get("first_map_with_electrons", True))
        calc_mode = str(session_state.get("calc_mode", "individual"))

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

        if calc_mode == "individual":
            result = np.zeros_like(pair_data[0][0], dtype=float)
            treated_maps = 0
            for abs_data, base_data in pair_data:
                result += self._safe_log10_ratio(
                    base_data - noise_average, abs_data - noise_average
                )
                treated_maps += 1
            result = result / treated_maps
        elif calc_mode == "averaged":
            abs_data = np.mean(np.stack([pair[0] for pair in pair_data]), axis=0)
            base_data = np.mean(np.stack([pair[1] for pair in pair_data]), axis=0)
            result = self._safe_log10_ratio(base_data - noise_average, abs_data - noise_average)
        else:
            raise ValueError(f"Unsupported calculation mode '{calc_mode}'")

        return result, info, data_path

    def _get_opener_and_info(self, file_path: Path):
        opener = self._get_opener(file_path)
        success, comments = opener.fill_critical_info(file_path)
        if not success:
            raise ValueError(comments or f"Could not read file '{file_path}'")
        return opener, opener.paths[file_path]

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

    @staticmethod
    def _format_file_info(file_path: Path, info, data_shape) -> Dict[str, object]:
        return {
            "file_path": str(file_path),
            "suffix": file_path.suffix.lower(),
            "number_maps": int(info.number_maps),
            "timedelays_length": int(info.timedelays_length),
            "wavelengths_length": int(info.wavelengths_length),
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
