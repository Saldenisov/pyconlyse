"""NeXus base classes and typed datasets used by the Gamma HDF5 format."""

from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

import h5py
import numpy as np


SCHEMA_VERSION = 2
TEXT = h5py.string_dtype(encoding="utf-8")
QUARTZ_CELL_TYPES = ("QZ", "QS")
OD_DESCRIPTION = "Decadic optical density, log10(reference ratio / measured ratio)"


def utc_iso(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat()


def nx(parent, name, cls):
    group = parent.create_group(name)
    group.attrs["NX_class"] = cls
    return group


def field(group, name, value, units=None, long_name=None):
    dataset = group.create_dataset(name, data=value)
    describe(dataset, units, long_name)
    return dataset


def describe(dataset, units=None, long_name=None):
    if units:
        dataset.attrs["units"] = units
    if long_name:
        dataset.attrs["long_name"] = long_name


def appendable(group, name, *, width=None, dtype="f8", fill=np.nan, units=None, long_name=None):
    tail = () if width is None else (width,)
    dataset = group.create_dataset(
        name, shape=(0,) + tail, maxshape=(None,) + tail, chunks=(256,) if width is None else (32, width),
        dtype=dtype, fillvalue=fill,
    )
    describe(dataset, units, long_name)
    return dataset


def axes(group, signal, coordinate_names, auxiliary=()):
    group.attrs["signal"] = signal
    group.attrs["axes"] = np.asarray(coordinate_names, dtype=TEXT)
    if auxiliary:
        group.attrs["auxiliary_signals"] = np.asarray(auxiliary, dtype=TEXT)
    for i, name in enumerate(coordinate_names):
        group.attrs[f"{name}_indices"] = i
        axis = group[name]
        if not axis.is_scale:
            axis.make_scale(name)
        for signal_name in (signal,) + tuple(auxiliary):
            dimension = group[signal_name].dims[i]
            dimension.label = name
            if not dimension.keys():
                dimension.attach_scale(axis)


def optical_volume_ml(diameter_mm, length_mm):
    return np.pi * (diameter_mm / 2) ** 2 * length_mm / 1000


def probe_volume_ml(setup):
    if "probe_volume_ml" in setup:
        return setup["probe_volume_ml"]
    return optical_volume_ml(setup.get("window_diameter_mm", np.nan), setup.get("path_length_mm", np.nan))


def missing_sample_fields(setup):
    missing = []
    for key, label in (("sample_volume_ml", "Measured volume (mL)"),
                       ("window_diameter_mm", "Entrance aperture diameter (mm)"),
                       ("path_length_mm", "Sample optical path (mm)")):
        value = setup.get(key)
        if not isinstance(value, (int, float, np.number)) or not np.isfinite(value) or value <= 0:
            missing.append(label)
    if setup.get("cell_type") not in QUARTZ_CELL_TYPES:
        missing.append("Quartz cell type (QZ or QS)")
    return missing


def missing_reference_fields(setup):
    if setup.get("reference_same_cell", True):
        return []
    missing = []
    length = setup.get("reference_path_length_mm", 0)
    if not isinstance(length, (int, float, np.number)) or not np.isfinite(length) or length <= 0:
        missing.append("Reference optical path (mm)")
    if setup.get("reference_cell_type") not in QUARTZ_CELL_TYPES:
        missing.append("Reference quartz cell type (QZ or QS)")
    return missing


def write_sample_geometry(entry, setup):
    sample = entry["sample"]
    fields = (
        ("window_diameter", float(setup.get("window_diameter_mm", np.nan)), "mm", "Entrance aperture diameter"),
        ("path_length", float(setup.get("path_length_mm", np.nan)), "mm", "Optical path length"),
        ("optical_volume", probe_volume_ml(setup), "mL", "Probe volume entered or calculated from geometry"),
        ("sample_volume", setup.get("sample_volume_ml", np.nan), "mL", "Measured volume of the sample"),
        ("cell_type", setup.get("cell_type", ""), None, "Quartz cell type"),
    )
    for name, value, units, description in fields:
        if name in sample:
            sample[name][()] = value
        else:
            field(sample, name, value, units, description)

    if "reference_same_cell" not in setup:
        return
    if "reference" not in entry:
        reference = nx(entry, "reference", "NXsample")
        reference["window_diameter"] = sample["window_diameter"]
    else:
        reference = entry["reference"]
    same = setup["reference_same_cell"]
    length_key = "path_length_mm" if same else "reference_path_length_mm"
    type_key = "cell_type" if same else "reference_cell_type"
    for name, value, units in (
        ("same_cell_as_sample", same, None),
        ("path_length", float(setup.get(length_key, np.nan)), "mm"),
        ("cell_type", setup.get(type_key, ""), None),
    ):
        if name in reference:
            reference[name][()] = value
        else:
            field(reference, name, value, units)


def init_exposure(entry, setup):
    nx(entry, "sample", "NXsample")
    write_sample_geometry(entry, setup)
    exposure = nx(entry, "irradiation", "NXcollection")
    rate = setup.get("dose_rate_gy_h", np.nan)
    if not np.isnan(rate) and (not np.isfinite(rate) or rate < 0):
        raise ValueError("Dose rate must be finite and nonnegative")
    field(exposure, "dose_rate_set", rate, "Gy/h")
    log = nx(exposure, "state", "NXlog")
    appendable(log, "time", units="s")
    appendable(log, "value", dtype="u1", fill=0)
    log["time"].attrs["start"] = entry["start_time"].asstr()[()]
    for name, value in (("time", setup.get("start_offset_s", 0.0)),
                        ("value", bool(setup.get("irradiating_at_start", False)))):
        log[name].resize(1, axis=0)
        log[name][0] = value
    acq = entry["acquisition"]
    dose = appendable(acq, "dose", units="Gy", long_name="Estimated accumulated absorbed dose")
    dose.resize(acq.attrs["committed_rows"], axis=0)
    entry["od_live/dose"] = dose
    entry["od_live"].attrs["dose_indices"] = 0
    if "lamp_monitor" not in entry:
        entry["lamp_monitor"] = entry["raw_ch2"]


def init_entry(file, wavelengths, serials, started_utc_s, exposure_setup):
    file.attrs.update(default="entry", creator="PyConlyse Gamma-spectrometer", file_time=utc_iso(started_utc_s))
    entry = nx(file, "entry", "NXentry")
    entry.attrs["default"] = "od_live"
    field(entry, "title", "Avantes optical density time series")
    field(entry, "start_time", utc_iso(started_utc_s))
    instrument = nx(entry, "instrument", "NXinstrument")
    field(instrument, "name", "Dual Avantes spectrometer")
    acquisition = nx(entry, "acquisition", "NXcollection")
    acquisition.attrs["committed_rows"] = 0
    time_axis = appendable(acquisition, "time", units="s", long_name="Elapsed time since start of run")
    utc = appendable(acquisition, "time_utc", units="s", long_name="POSIX UTC acquisition start time")
    utc.attrs["epoch"] = "1970-01-01T00:00:00+00:00"
    appendable(acquisition, "metadata_json", dtype=TEXT, fill="{}")

    for i, (wavelength, serial) in enumerate(zip(wavelengths, serials), 1):
        detector = nx(instrument, f"detector_{i}", "NXdetector")
        field(detector, "serial_number", serial)
        field(detector, "wavelength", wavelength, "nm", "Detector's native wavelength calibration")
        appendable(detector, "data", width=len(wavelength), units="counts",
                   long_name="Uncorrected SDK intensity after hardware averaging")
        appendable(detector, "count_time_set", units="s", long_name="Configured integration time per exposure")
        appendable(detector, "averages_set", dtype="i4", fill=-1, long_name="Configured hardware averages")
        appendable(detector, "trigger_mode_set", dtype="i2", fill=-1, long_name="Configured Avantes SDK trigger mode")
        status = appendable(detector, "readout_ok", dtype="i1", fill=-1)
        status.attrs["codes"] = "-1 unknown; 0 failed; 1 retrieved"
        raw = nx(entry, f"raw_ch{i}", "NXdata")
        raw["time"] = time_axis
        raw["wavelength"] = detector["wavelength"]
        raw["data"] = detector["data"]
        axes(raw, "data", ("time", "wavelength"))

    live = nx(entry, "od_live", "NXdata")
    live["time"] = time_axis
    live["wavelength"] = entry["raw_ch1/wavelength"]
    appendable(live, "od", width=len(wavelengths[0]), units="1", long_name=OD_DESCRIPTION)
    appendable(live, "delta_od", width=len(wavelengths[0]), units="1",
               long_name="Live OD relative to Set Zero when acquired, otherwise live OD")
    axes(live, "od", ("time", "wavelength"), ("delta_od",))
    init_exposure(entry, exposure_setup)
    nx(entry, "calibration", "NXcollection")
    nx(entry, "blanks", "NXcollection")
    nx(entry, "processing", "NXcollection")
    events = nx(entry, "events", "NXcollection")
    appendable(events, "metadata_json", dtype=TEXT, fill="{}")
    return entry


def published_processes(entry, kind):
    for name, process in sorted(entry["processing"].items()):
        if not name.startswith("_") and process.attrs.get("kind") == kind:
            yield process


@contextmanager
def process_revision(entry, kind, program, version, date, inputs):
    parent = entry["processing"]
    sequence = max((int(item["sequence_index"][()]) for name, item in parent.items()
                    if not name.startswith("_")), default=0) + 1
    draft = f"_pending_{uuid4().hex}"
    name = f"{sequence:06d}_{kind}"
    process = nx(parent, draft, "NXprocess")
    process.attrs["kind"] = kind
    try:
        field(process, "program", program)
        field(process, "version", version)
        field(process, "date", date)
        field(process, "sequence_index", sequence)
        parameters = nx(process, "parameters", "NXparameters")
        for key, value in inputs.items():
            field(parameters, key, value)
        yield process, f"{parent.name}/{name}"
        entry.file.flush()
        parent.move(draft, name)
    except Exception:
        if draft in parent:
            del parent[draft]
        raise
