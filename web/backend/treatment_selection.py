"""Treatment selection previews, averaged exports and bounds."""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np


class TreatmentSelection:
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
        paths = session_state.get("paths") or {}
        sources = session_state.get("path_sources") or {}
        reference_source = None
        if resolved_active_data_type == "ABS":
            reference_source = sources.get("ABS") or paths.get("ABS")
        elif resolved_active_data_type == "ABS+BASE":
            if H5Opener is not None and isinstance(opener, H5Opener):
                with h5py.File(file_path, "r") as handle:
                    abs_ids, _ = paired_frames(np.array([map_index]), handle,
                                              session_state.get("first_map_with_electrons", True))
                    is_abs = bool(len(abs_ids))
            else:
                is_abs = map_index % 2 == (0 if session_state.get("first_map_with_electrons", True) else 1)
            if is_abs:
                reference_source = sources.get("ABS+BASE") or paths.get("ABS+BASE")
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
            "spectral_reference_source": reference_source,
            "spectral_reference": session_state.get("spectral_reference"),
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
