"""Optical-density calculations and HDF5 processing revisions."""

import json
import time

import numpy as np

from avantes_h5 import TEXT, axes, field, nx, process_revision, utc_iso


def valid_counts(block):
    spectra = []
    diagnostics = block["metadata"].get("readout", {})
    for index, channel in enumerate(("ch1", "ch2")):
        counts = block[channel]
        pixels = diagnostics.get(str(index), {}).get("saturated_pixels")
        if pixels:
            counts = np.array(counts, dtype=float, copy=True)
            counts[pixels] = np.nan
        spectra.append(counts)
    return tuple(spectra)


def mean_counts(blocks):
    return tuple(np.mean(channel, axis=0) for channel in zip(*(valid_counts(block) for block in blocks)))


def optical_density(ch1, ch2, reference, dark, wavelengths):
    """Calculate ratio-of-ratios OD on the Ch1 wavelength grid."""
    w1, w2 = wavelengths
    sample1 = np.asarray(ch1, dtype=float) - dark[0]
    sample2 = np.asarray(ch2, dtype=float) - dark[1]
    ref1 = np.asarray(reference[0], dtype=float) - dark[0]
    ref2 = np.asarray(reference[1], dtype=float) - dark[1]
    order = np.argsort(w2)
    # An invalid source pixel must not become valid through interpolation.
    sample2 = np.where(sample2 > 0, sample2, np.nan)
    ref2 = np.where(ref2 > 0, ref2, np.nan)
    sample2 = np.interp(w1, w2[order], sample2[order], left=np.nan, right=np.nan)
    ref2 = np.interp(w1, w2[order], ref2[order], left=np.nan, right=np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        od = (np.log10(ref1) - np.log10(sample1)) + (np.log10(sample2) - np.log10(ref2))
    od[~np.isfinite(od)] = np.nan
    return od


def publish_raw_recalculation(entry, selected, zero, read_blocks, dose_at):
    """Recalculate sample OD and drift from the archived detector counts."""
    dark = mean_counts(read_blocks(selected["background"]))
    baseline = mean_counts(read_blocks(selected[zero]))
    reference = mean_counts(read_blocks(selected["reference"]))
    wavelengths = tuple(entry[f"raw_ch{i}/wavelength"][:] for i in (1, 2))
    acquisition = entry["acquisition"]
    count = int(acquisition.attrs["committed_rows"])
    if count < 1:
        raise ValueError("Record sample spectra before recalculating OD")
    anchors = [entry["blanks"][key] for key in sorted(entry["blanks"])]
    parameters = {role: group.name for role, group in selected.items()}
    parameters.update(zero=zero, input_rows=count,
                      channel_1=entry["raw_ch1/data"].name, channel_2=entry["raw_ch2/data"].name)
    with process_revision(entry, "raw_recalculation", "Gamma OD from raw counts", "1", utc_iso(time.time()),
                          parameters) as (revision, path):
        revision.attrs["default"] = "data"
        data = nx(revision, "data", "NXdata")
        field(data, "time", acquisition["time"][:count], "s")
        data["wavelength"] = entry["od_live/wavelength"]
        od = data.create_dataset("od", shape=(count, len(wavelengths[0])), dtype="f8",
                                 fillvalue=np.nan, compression="gzip", compression_opts=1)
        od.attrs["units"] = "1"
        axes(data, "od", ("time", "wavelength"))
        raw1, raw2 = entry["raw_ch1/data"], entry["raw_ch2/data"]
        metadata = acquisition["metadata_json"].asstr()
        has_valid_od = False
        for start in range(0, count, 128):
            batch = slice(start, min(start + 128, count))
            spectra = [
                optical_density(*valid_counts(dict(ch1=ch1, ch2=ch2, metadata=json.loads(info))),
                                baseline, dark, wavelengths)
                for ch1, ch2, info in zip(raw1[batch], raw2[batch], metadata[batch])
            ]
            has_valid_od |= bool(np.isfinite(spectra).any())
            od[batch] = spectra
        if not has_valid_od:
            raise ValueError("The selected calibration and saved counts produce no valid OD")
    if len(anchors) >= 2:
        anchor_od = np.stack([
            optical_density(*(reference if blank["initial"][()] else mean_counts(read_blocks(blank))),
                            baseline, dark, wavelengths)
            for blank in anchors
        ])
        publish_blank_correction(entry, "reprocessed from raw counts", dose_at,
                                 source=entry.file[f"{path}/data/od"], blank_od=anchor_od)
    return path


def publish_blank_correction(entry, reason, dose_at, *, source=None, blank_od=None):
    anchors = [entry["blanks"][key] for key in sorted(entry["blanks"])]
    if len(anchors) < 2:
        raise ValueError("At least two measured blanks are required for drift correction")
    count = int(entry["acquisition"].attrs["committed_rows"])
    times = entry["acquisition/time"][:count]
    elapsed = np.array([blank["anchor_time"][()] for blank in anchors])
    if blank_od is None:
        blank_od = np.stack([blank["od"][:] for blank in anchors])
    if source is None:
        source = entry["od_live/delta_od"]
    drift = blank_od - blank_od[0]
    parameters = {
        "blank_paths": np.asarray([blank.name for blank in anchors], dtype=TEXT),
        "source": source.name,
        "reason": reason,
        "method": "Piecewise linear interpolation of measured blank OD relative to first blank; no extrapolation",
        "input_rows": count,
    }
    with process_revision(entry, "blank_correction", "Gamma blank interpolation", "1", utc_iso(time.time()),
                          parameters) as (revision, path):
        field(revision, "anchor_time", elapsed, "s")
        field(revision, "anchor_od", blank_od, "1")
        if "irradiation" in entry and np.isfinite(entry["irradiation/dose_rate_set"][()]):
            field(revision, "anchor_dose", [dose_at(entry, value) for value in elapsed], "Gy")
        revision.attrs["default"] = "data"
        data = nx(revision, "data", "NXdata")
        field(data, "time", times, "s")
        if "dose" in entry["acquisition"]:
            field(data, "dose", entry["acquisition/dose"][:count], "Gy")
            data.attrs["dose_indices"] = 0
        data["wavelength"] = entry["od_live/wavelength"]
        fields = {}
        shape = count, blank_od.shape[1]
        for name in ("od", "blank_drift"):
            fields[name] = data.create_dataset(name, shape=shape, dtype="f8", fillvalue=np.nan,
                                               compression="gzip", compression_opts=1)
            fields[name].attrs["units"] = "1"
        axes(data, "od", ("time", "wavelength"), ("blank_drift",))
        for i in range(len(anchors) - 1):
            first = np.searchsorted(times, elapsed[i], side="left" if i == 0 else "right")
            last = np.searchsorted(times, elapsed[i + 1], side="right")
            for start in range(first, last, 128):
                end = min(start + 128, last)
                fraction = ((times[start:end] - elapsed[i]) / (elapsed[i + 1] - elapsed[i]))[:, None]
                interpolated = (1 - fraction) * drift[i] + fraction * drift[i + 1]
                # An exact anchor only depends on its own valid wavelengths.
                interpolated = np.where(fraction == 0, drift[i], interpolated)
                interpolated = np.where(fraction == 1, drift[i + 1], interpolated)
                fields["blank_drift"][start:end] = interpolated
                fields["od"][start:end] = source[start:end] - interpolated
    return path
