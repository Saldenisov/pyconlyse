import json
import logging
import os
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
from treatment_h5_conversion import TreatmentH5Conversion, h5py
from treatment_od_stitching import TreatmentODStitching
from treatment_selection import TreatmentSelection
from treatment_spectral_od import SPECTRAL_MODES, calculate as spectral_od, maps as spectral_maps, paired_frames, reference_window
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


class TreatmentDataService(
    TreatmentODStitching,
    TreatmentSelection,
    TreatmentCleaning,
    TreatmentH5Conversion,
):
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
        base_opener, base_info = self._get_opener_and_info(base_path)
        noise_opener, noise_info = self._get_opener_and_info(noise_path)

        include_excluded = bool(session_state.get("include_excluded_maps", False))
        mode = session_state.get("calc_mode")
        if mode in SPECTRAL_MODES:
            source = (session_state.get("path_sources") or {}).get("ABS") or str(abs_path)
            window = reference_window(session_state.get("spectral_reference"), source)
            for key in ("wavelengths", "timedelays"):
                if any(not np.array_equal(getattr(abs_info, key), getattr(other, key))
                       for other in (base_info, noise_info)):
                    raise ValueError("ABS, BASE and BRUIT axes do not match")
            with (spectral_maps(abs_opener, abs_path, abs_info, h5py, include_excluded) as (a_ids, a_read, _),
                  spectral_maps(base_opener, base_path, base_info, h5py, include_excluded) as (b_ids, b_read, _)):
                noise = self._spectral_noise(noise_path, include_excluded, abs_info)
                result = spectral_od((a_ids, a_read), (b_ids, b_read), noise, mode, self._safe_log10_ratio, window)
            return result, abs_info, abs_path

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

    def _spectral_noise(self, path, include_excluded, signal_info):
        opener, info = self._get_opener_and_info(path)
        if any(not np.array_equal(getattr(info, key), getattr(signal_info, key))
               for key in ("wavelengths", "timedelays")):
            raise ValueError("BRUIT axes do not match the paired data")
        with spectral_maps(opener, path, info, h5py, include_excluded) as (indices, read, _):
            return self._average_spectral_frames(indices, read)

    @staticmethod
    def _average_spectral_frames(indices, read):
        if not len(indices):
            raise ValueError("No active frames in the selected phase")
        total = np.array(read(indices[0]), dtype=float)
        for index in indices[1:]:
            total += read(index)
        return total / len(indices)

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
        mode = session_state.get("calc_mode")
        if mode in SPECTRAL_MODES or (
            mode == "averaged" and H5Opener is not None and isinstance(opener, H5Opener)
        ):
            include_excluded = bool(session_state.get("include_excluded_maps", False))
            with spectral_maps(opener, data_path, info, h5py, include_excluded) as (indices, read, handle):
                if handle is not None and "beam_on" in handle and "background" in handle:
                    noise = np.asarray(handle["background"], dtype=float)
                else:
                    noise = self._spectral_noise(self._require_path(session_state, "NOISE"), include_excluded, info)
                first_abs = bool(session_state.get("first_map_with_electrons", True))
                abs_ids, base_ids = paired_frames(indices, handle, first_abs)
                if mode == "averaged":
                    absorption = self._average_spectral_frames(abs_ids, read) - noise
                    base = self._average_spectral_frames(base_ids, read) - noise
                    result = self._safe_log10_ratio(base, absorption)
                else:
                    source = (session_state.get("path_sources") or {}).get("ABS+BASE") or str(data_path)
                    window = reference_window(session_state.get("spectral_reference"), source)
                    result = spectral_od((abs_ids, read), (base_ids, read), noise, mode,
                                         self._safe_log10_ratio, window, frame_stride=2)
            return result, info, data_path
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
