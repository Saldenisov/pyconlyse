"""OD map stitching and heatmap sampling for the treatment service."""

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np


class TreatmentODStitching:
    """Operations shared by the treatment service's OD stitching and previews."""

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
