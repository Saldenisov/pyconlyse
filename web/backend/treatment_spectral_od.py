"""Estimate VD2 optical density using pre-signal spectral references."""

from collections import OrderedDict
from contextlib import contextmanager

import numpy as np
from scipy.ndimage import gaussian_filter1d

from utilities.dataio import H5Opener


SPECTRAL_SUM = "matched_spectral_sum"
SPECTRAL_INDIVIDUAL = "matched_spectral_individual"
SPECTRAL_MODES = (SPECTRAL_SUM, SPECTRAL_INDIVIDUAL)
REFERENCE_ROWS = 30
MATCH_WINDOW = 20


@contextmanager
def maps(opener, path, info, h5py, include_excluded=False):
    if H5Opener is not None and isinstance(opener, H5Opener):
        with h5py.File(path, "r") as handle:
            raw = handle["raw_data"]
            mask = opener._selection_mask(handle, len(raw))
            indices = np.flatnonzero(mask) if not include_excluded else np.arange(len(raw))
            yield indices, lambda index: opener._reorient_data2d(raw[index], info), handle
        return

    def read(index):
        measurement, error = opener.read_map(path, int(index))
        if not measurement:
            raise ValueError(error or f"Could not read frame {index + 1}")
        data = np.asarray(measurement.data)
        if path.suffix.lower() == ".his" and data.dtype.kind == "i":
            return data.view(data.dtype.str.replace("i", "u"))
        return data

    yield np.arange(info.number_maps), read, None


def calculate(abs_frames, base_frames, noise, mode, log_ratio, frame_stride=None):
    """The ABS frames only receive the common BRUIT subtraction."""
    a_ids, read_abs = abs_frames
    b_ids, read_base = base_frames
    if not len(a_ids) or not len(b_ids):
        raise ValueError("Brightness matching requires active ABS and BASE frames")
    if noise.ndim != 2 or noise.shape[1] <= REFERENCE_ROWS:
        raise ValueError("Spectral correction needs 30 reference rows and later signal rows")

    def reference(image):
        if image.shape != noise.shape:
            raise ValueError("ABS, BASE and BRUIT frame shapes do not match")
        spectrum = (image[:, :REFERENCE_ROWS] - noise[:, :REFERENCE_ROWS]).sum(axis=1)
        return spectrum.sum(), gaussian_filter1d(spectrum, 5, mode="nearest")

    base_references = {index: reference(read_base(index)) for index in b_ids}
    b_ids = np.array([i for i in b_ids if np.isfinite(base_references[i][0])
                      and base_references[i][0] > 0], dtype=int)
    if not len(b_ids):
        raise ValueError("BASE has no positive intensity in the first 30 rows")
    brightness = np.log([base_references[i][0] for i in b_ids])
    if frame_stride is None:
        order = np.argsort(brightness, kind="stable")
        brightness, b_ids = brightness[order], b_ids[order]
    summed_abs = np.zeros_like(noise, dtype=float)
    summed_base = np.zeros_like(summed_abs)
    counts = np.zeros_like(summed_abs, dtype=np.int64)
    cache = OrderedDict()
    for index in a_ids:
        absorption = read_abs(index)
        intensity, spectrum = reference(absorption)
        if not np.isfinite(intensity) or intensity <= 0:
            continue
        target = np.log(intensity)
        if frame_stride is None:
            insertion = np.searchsorted(brightness, target)
            start, stop = max(0, insertion - 1), insertion + 1
        else:
            window = MATCH_WINDOW * frame_stride
            start, stop = np.searchsorted(b_ids, (index - window, index + window + 1))
        candidates = b_ids[start:stop]
        if not len(candidates):
            continue
        order = np.lexsort((np.abs(candidates - index), np.abs(brightness[start:stop] - target)))
        selected = candidates[order[0]]
        if selected not in cache:
            cache[selected] = read_base(selected)
            if len(cache) > 8:
                cache.popitem(last=False)
        cache.move_to_end(selected)
        base_spectrum = base_references[selected][1]
        valid_ref = (spectrum > 0) & (base_spectrum > 0) & np.isfinite(spectrum) & np.isfinite(base_spectrum)
        scale = np.divide(spectrum, base_spectrum, out=np.full_like(spectrum, np.nan), where=valid_ref)
        a = absorption - noise
        b = (cache[selected] - noise) * scale[:, None]
        if mode == SPECTRAL_INDIVIDUAL:
            od = log_ratio(b, a)
            valid = np.isfinite(od)
            np.add(summed_base, od, out=summed_base, where=valid)
        else:
            valid = np.isfinite(a) & np.isfinite(b)
            np.add(summed_abs, a, out=summed_abs, where=valid)
            np.add(summed_base, b, out=summed_base, where=valid)
        counts += valid
    if not counts.any():
        raise ValueError("No usable ABS/BASE matches in the first 30 rows")
    if mode == SPECTRAL_INDIVIDUAL:
        return np.divide(summed_base, counts, out=np.full_like(summed_base, np.nan), where=counts > 0)
    return log_ratio(summed_base, summed_abs)


def paired_frames(indices, handle, first_abs):
    if handle is not None and "beam_on" in handle:
        roles = np.asarray(handle["beam_on"])
        if roles.shape != (len(handle["raw_data"]),):
            raise ValueError("Invalid beam phase labels in paired H5")
        return indices[roles[indices] == 1], indices[roles[indices] == 0]
    original = indices
    if handle is not None and "map_selection" not in handle:
        kept = H5Opener._kept_indices(handle)
        if kept is not None and kept.shape == (len(handle["raw_data"]),):
            original = kept[indices]
    is_abs = original % 2 == (0 if first_abs else 1)
    return indices[is_abs], indices[~is_abs]
