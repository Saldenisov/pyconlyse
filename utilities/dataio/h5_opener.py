"""
Created on 05 june 2024

@author: saldenisov
"""

# import logging
import logging
from pathlib import Path
import re
from typing import Union, Tuple
import h5py
import numpy as np

from utilities.dataio.opener import Opener, CriticalInfo
from utilities.datastructures.mes_independent.measurments_dataclass import Measurement
from utilities.errors.myexceptions import NoSuchFileType

module_logger = logging.getLogger(__name__)


class H5Opener(Opener):
    ALLOWED_FILES_TYPES = ['.h5']
    TIME_UNIT_RE = re.compile(r"(?<![A-Za-z])(?:\d+(?:\.\d+)?)\s*(fs|ps|ns|us|µs|ms|s)(?![A-Za-z])", re.IGNORECASE)

    @staticmethod
    def _data_key(h5_file) -> str:
        return "raw_data"

    @staticmethod
    def _kept_indices(h5_file):
        if "metadata" not in h5_file:
            return None
        if "kept_indices" not in h5_file["metadata"].attrs:
            return None
        return np.asarray(h5_file["metadata"].attrs["kept_indices"], dtype=int)

    @staticmethod
    def _selection_mask(h5_file, raw_map_count: int) -> np.ndarray:
        """Return the active-map mask for canonical H5 treatment files.

        Files written before the non-destructive cleaning schema have no
        ``map_selection`` group.  They therefore retain their historical
        behaviour: every map physically present in ``raw_data`` is active.
        """
        if "map_selection" not in h5_file:
            return np.ones(raw_map_count, dtype=bool)
        selection_group = h5_file["map_selection"]
        if "included" not in selection_group:
            return np.ones(raw_map_count, dtype=bool)
        included = np.asarray(selection_group["included"], dtype=bool)
        if included.shape != (raw_map_count,):
            module_logger.warning(
                "H5Opener: ignoring malformed map_selection/included with shape %s",
                included.shape,
            )
            return np.ones(raw_map_count, dtype=bool)
        return included

    @staticmethod
    def _original_measurements(h5_file):
        if "metadata" not in h5_file:
            return None
        if "original_measurements" not in h5_file["metadata"].attrs:
            return None
        return int(h5_file["metadata"].attrs["original_measurements"])

    @staticmethod
    def _as_text(value) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="ignore")
        if hasattr(value, "item"):
            try:
                return H5Opener._as_text(value.item())
            except Exception:
                pass
        return str(value or "")

    @classmethod
    def _time_unit_from_path(cls, file_path: Path) -> str:
        normalized = str(file_path).replace("\\", "/")
        match = cls.TIME_UNIT_RE.search(normalized)
        if not match:
            return ""
        unit = match.group(1).replace("µ", "u").lower()
        return unit

    @classmethod
    def _time_unit_from_metadata(cls, h5_file, file_path: Path) -> str:
        comments = ""
        if "metadata" in h5_file:
            md = h5_file["metadata"]
            for attr_name in ("time_scale", "scaling_yunit", "scaling_yunit_original"):
                if attr_name in md.attrs:
                    value = cls._as_text(md.attrs[attr_name]).strip()
                    if value and value != "??":
                        return value
            if "description" in md.attrs:
                comments = cls._as_text(md.attrs["description"])

        if "ScalingYUnit=" in comments:
            try:
                return comments.split("ScalingYUnit=")[1][1:].split(",")[0].strip().strip('"')[:3]
            except Exception:
                pass

        return cls._time_unit_from_path(file_path) or "??"

    def read_critical_info(self, file_path: Path) -> CriticalInfo:
        """Read axes and basic info from an HDF5 file.

        We are robust to older files that may miss the ``metadata`` group or the
        ``ScalingYUnit=`` tag in the description. In that case we fall back to a
        dummy scaling unit.
        """
        if file_path.suffix in self.ALLOWED_FILES_TYPES:
            with h5py.File(file_path, "r") as f:
                timedelays = np.array(f["timedelays"])
                wavelengths = np.array(f["wavelengths"])
                n_maps = f[self._data_key(f)].shape[0]

                scalingyunit = self._time_unit_from_metadata(f, file_path)

            return CriticalInfo(
                file_path=file_path,
                timedelays_length=len(timedelays),
                wavelengths_length=len(wavelengths),
                timedelays=timedelays,
                wavelengths=wavelengths,
                number_maps=n_maps,
                scaling_yunit=scalingyunit,
            )
        else:
            raise NoSuchFileType(file_path.suffix)

    def _reorient_data2d(self, data: np.ndarray, info: CriticalInfo) -> np.ndarray:
        """Return data with shape (wavelengths, timedelays) based on axis lengths.

        Some H5 files store raw_data as (timedelays, wavelengths), others as
        (wavelengths, timedelays). We detect which is which by comparing the
        2D shape to (len(timedelays), len(wavelengths)) and
        (len(wavelengths), len(timedelays)). If ``data`` is not 2D, we leave it
        untouched and just log, since such files are outside the scope of this
        Treatment GUI.
        """
        if data.ndim != 2:
            module_logger.error(
                "H5Opener: expected 2D data slice but got shape %s; leaving as-is",
                data.shape,
            )
            return data

        nt, nw = data.shape
        expected_t = len(info.timedelays)
        expected_w = len(info.wavelengths)

        if (nt, nw) == (expected_t, expected_w):
            # Stored as (timedelays, wavelengths) → transpose.
            return data.T
        if (nt, nw) == (expected_w, expected_t):
            # Already (wavelengths, timedelays).
            return data

        # Unexpected shape: log and return as-is so caller can decide what to do.
        module_logger.error(
            "H5Opener: unexpected raw_data 2D shape %s for file %s; "
            "expected (%d, %d) or (%d, %d)",
            data.shape,
            info.file_path,
            expected_t,
            expected_w,
            expected_w,
            expected_t,
        )
        return data

    def read_map(self, file_path: Path, map_index=0) -> Union[Measurement, Tuple[bool, str]]:
        """Return a single map with data shaped (wavelengths, timedelays).

        We inspect the raw_data slice shape and transpose only when necessary so
        that all Measurement instances are consistent with HamamatsuFileOpener.
        """
        if file_path not in self.paths:
            res, comments = self.fill_critical_info(file_path)
        else:
            res = True
        if res:
            info: CriticalInfo = self.paths[file_path]
            with h5py.File(file_path, "r") as f:
                data_key = self._data_key(f)
                data = f[data_key][map_index]
                kept_indices = self._kept_indices(f)
                original_measurements = self._original_measurements(f)
                has_map_selection = (
                    "map_selection" in f and "included" in f["map_selection"]
                )
                comments = ""
                if "metadata" in f and "description" in f["metadata"].attrs:
                    comments = self._as_text(f["metadata"].attrs["description"])

            data = self._reorient_data2d(data, info)

            scalingyunit = info.scaling_yunit

            measurement = Measurement(
                type=file_path.suffix,
                comments=comments,
                author="",
                timestamp=file_path.stat().st_mtime,
                data=data,
                wavelengths=info.wavelengths,
                timedelays=info.timedelays,
                time_scale=scalingyunit,
            )
            if (
                kept_indices is not None
                and not has_map_selection
                and map_index < len(kept_indices)
            ):
                measurement.original_index = int(kept_indices[map_index])
            else:
                measurement.original_index = int(map_index)
            if original_measurements is not None:
                measurement.original_measurements = int(original_measurements)
            return (measurement, "")
            return False, comments

    def average_map(self, file_path: Path, call_back_func=None):
        """Average all maps and return (wavelengths, timedelays).

        ``raw_data`` may be stored either as (n_maps, timedelays, wavelengths)
        or (n_maps, wavelengths, timedelays). We detect and transpose as needed.
        """
        if file_path not in self.paths:
            res, comments = self.fill_critical_info(file_path)
        else:
            res = True
        if not res:
            return False

        info: CriticalInfo = self.paths[file_path]
        with h5py.File(file_path, "r") as f:
            data3d = np.array(f[self._data_key(f)])
            selection_mask = self._selection_mask(f, data3d.shape[0])

        data3d = data3d[selection_mask]
        if data3d.shape[0] == 0:
            raise ValueError("H5 map selection excludes every map")

        # Inspect one slice to decide orientation.
        sample = data3d[0]
        self._reorient_data2d(sample, info)

        # Apply the same transformation to the whole stack by checking whether
        # a transpose was needed for the sample.
        nt, nw = sample.shape
        expected_t = len(info.timedelays)
        expected_w = len(info.wavelengths)
        if (nt, nw) == (expected_t, expected_w):
            # need transpose for all slices
            data3d = np.transpose(data3d, (0, 2, 1))

        avg = np.average(data3d, axis=0)
        return avg

    def give_all_maps(
        self,
        file_path,
        include_excluded: bool = False,
    ) -> Union[Measurement, Tuple[bool, str]]:
        """Yield active maps, or every raw map when cleaning needs an audit view.

        ``raw_data`` is deliberately never filtered on disk.  The default view
        honours ``map_selection/included`` so downstream averages and OD
        calculations use the selected maps only.  Cleaning callers pass
        ``include_excluded=True`` to inspect and re-evaluate the full archive.
        """
        res = True
        if file_path not in self.paths:
            res, comments = self.fill_critical_info(file_path)
        if res:
            info: CriticalInfo = self.paths[file_path]
            with h5py.File(file_path, "r") as f:
                data_key = self._data_key(f)
                data3d = np.array(f[data_key])
                kept_indices = self._kept_indices(f)
                original_measurements = self._original_measurements(f)
                selection_mask = self._selection_mask(f, data3d.shape[0])
                has_map_selection = (
                    "map_selection" in f and "included" in f["map_selection"]
                )
                comments = ""
                if "metadata" in f and "description" in f["metadata"].attrs:
                    comments = f["metadata"].attrs["description"]

            indices = np.arange(data3d.shape[0], dtype=int)
            if not include_excluded:
                indices = indices[selection_mask]

            for index in indices:
                data_i = data3d[int(index)]
                data_i = self._reorient_data2d(data_i, info)
                measurement = Measurement(
                    type=file_path.suffix,
                    comments=comments,
                    author="",
                    timestamp=file_path.stat().st_mtime,
                    data=data_i,
                    wavelengths=info.wavelengths,
                    timedelays=info.timedelays,
                    time_scale=info.scaling_yunit,
                )
                if (
                    kept_indices is not None
                    and not has_map_selection
                    and index < len(kept_indices)
                ):
                    measurement.original_index = int(kept_indices[index])
                else:
                    measurement.original_index = int(index)
                if original_measurements is not None:
                    measurement.original_measurements = int(original_measurements)
                yield measurement
        else:
            return res, comments
