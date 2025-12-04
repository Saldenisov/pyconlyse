"""
Created on 05 june 2024

@author: saldenisov
"""

# import logging
import logging
from functools import lru_cache
from pathlib import Path
from typing import Union, Tuple
import h5py
import numpy as np

from gui.controllers.openers.Opener import Opener, CriticalInfo
from utilities.datastructures.mes_independent.measurments_dataclass import Measurement
from utilities.myfunc import error_logger
from utilities.errors.myexceptions import NoSuchFileType

module_logger = logging.getLogger(__name__)


class H5Opener(Opener):
    ALLOWED_FILES_TYPES = ['.h5']

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
                n_maps = f["raw_data"].shape[0]

                comments = ""
                if "metadata" in f:
                    md = f["metadata"]
                    if "description" in md.attrs:
                        comments = md.attrs["description"]

            scalingyunit = "??"
            if "ScalingYUnit=" in comments:
                try:
                    scalingyunit = comments.split("ScalingYUnit=")[1][1:3]
                except Exception:
                    pass

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
            file_path,
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
                data = f["raw_data"][map_index]
                comments = ""
                if "metadata" in f and "description" in f["metadata"].attrs:
                    comments = f["metadata"].attrs["description"]

            data = self._reorient_data2d(data, info)

            scalingyunit = info.scaling_yunit
            if "ScalingYUnit=" in comments:
                try:
                    scalingyunit = comments.split("ScalingYUnit=")[1][1:3]
                except Exception:
                    pass

            return (
                Measurement(
                    type=file_path.suffix,
                    comments=comments,
                    author="",
                    timestamp=file_path.stat().st_mtime,
                    data=data,
                    wavelengths=info.wavelengths,
                    timedelays=info.timedelays,
                    time_scale=scalingyunit,
                ),
                "",
            )
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
            data3d = np.array(f["raw_data"])

        # Inspect one slice to decide orientation.
        sample = data3d[0]
        sample_reoriented = self._reorient_data2d(sample, info)

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

    def give_all_maps(self, file_path) -> Union[Measurement, Tuple[bool, str]]:
        """Yield maps with data shaped (wavelengths, timedelays)."""
        res = True
        if file_path not in self.paths:
            res, comments = self.fill_critical_info(file_path)
        if res:
            info: CriticalInfo = self.paths[file_path]
            with h5py.File(file_path, "r") as f:
                data3d = np.array(f["raw_data"])
                comments = ""
                if "metadata" in f and "description" in f["metadata"].attrs:
                    comments = f["metadata"].attrs["description"]

            for data_i in data3d:
                data_i = self._reorient_data2d(data_i, info)
                yield Measurement(
                    type=file_path.suffix,
                    comments=comments,
                    author="",
                    timestamp=file_path.stat().st_mtime,
                    data=data_i,
                    wavelengths=info.wavelengths,
                    timedelays=info.timedelays,
                    time_scale=info.scaling_yunit,
                )
        else:
            return res, comments
