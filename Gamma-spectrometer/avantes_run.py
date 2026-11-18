"""Disk format and OD calculations for the standalone Gamma spectrometer."""

import json
from pathlib import Path
import time

import h5py
import numpy as np


from avantes_h5 import (
    SCHEMA_VERSION, TEXT, appendable, axes, field, init_entry, init_exposure, nx,
    missing_reference_fields, missing_sample_fields, process_revision, published_processes, utc_iso, write_sample_geometry,
)


OD_DATASETS = ("od_raw", "od_delta", "od_corrected")


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


class AvantesRun:
    """Read Avantes HDF5 runs and append to the NeXus-based version 2 format."""

    def __init__(self, path):
        self.path = Path(path)

    @classmethod
    def create(cls, path, wavelengths, serials, started_utc_s, settings, calibration):
        run = cls(path)
        with h5py.File(run.path, "x") as file:
            file.attrs.update(
                format="avantes-gamma", version=SCHEMA_VERSION, started_utc_s=started_utc_s,
                settings_json=json.dumps(settings), serials_json=json.dumps(serials),
            )
            entry = init_entry(file, wavelengths, serials, started_utc_s, settings.get("exposure", {}))
            if "sample_name" in settings:
                file.attrs["calibration_pending"] = True
                entry["title"][()] = settings["sample_name"]
                field(entry["sample"], "name", settings["sample_name"])
                field(entry["sample"], "description", settings.get("sample_comment", ""))
            for role, blocks in calibration.items():
                if blocks:
                    cls._write_blocks(entry, entry["calibration"], role, blocks)
        return run

    def begin_capture(self, role, repeats, blocks_per_repeat):
        with h5py.File(self.path, "r+") as file:
            entry = self._writable_entry(file)
            if "calibration_captures" not in entry:
                nx(entry, "calibration_captures", "NXcollection")
            captures = entry["calibration_captures"]
            name = f"{len(captures):08d}"
            capture = nx(captures, name, "NXcollection")
            capture.attrs.update(role=role, repeats=repeats, blocks_per_repeat=blocks_per_repeat,
                                 committed_blocks=0, complete=False)
            for key in ("block_index", "repeat_index", "block_in_repeat"):
                appendable(capture, key, dtype="i8", fill=-1)
            capture["block_index"].make_scale("block_index")
            appendable(capture, "time_utc", units="s")
            appendable(capture, "metadata_json", dtype=TEXT, fill="{}")
            for i in (1, 2):
                wavelength = entry[f"raw_ch{i}/wavelength"]
                data = appendable(capture, f"ch{i}_counts", width=len(wavelength), units="counts")
                data.dims[0].attach_scale(capture["block_index"])
                data.dims[1].attach_scale(wavelength)
            return name

    def append_capture_block(self, name, block):
        with h5py.File(self.path, "r+") as file:
            capture = self._writable_entry(file)[f"calibration_captures/{name}"]
            index = int(capture.attrs["committed_blocks"])
            repeat, in_repeat = divmod(index, int(capture.attrs["blocks_per_repeat"]))
            meta = dict(block["metadata"], repeat_index=repeat, block_in_repeat=in_repeat)
            values = dict(block_index=index, repeat_index=repeat, block_in_repeat=in_repeat,
                          time_utc=meta["utc_s"], ch1_counts=block["ch1"], ch2_counts=block["ch2"],
                          metadata_json=json.dumps(meta))
            for key, value in values.items():
                data = capture[key]
                data.resize(index + 1, axis=0)
                data[index] = data.fillvalue if value is None else value
            file.flush()
            capture.attrs.modify("committed_blocks", index + 1)
            return index + 1

    def finish_capture(self, name):
        with h5py.File(self.path, "r+") as file:
            entry = self._writable_entry(file)
            capture = entry[f"calibration_captures/{name}"]
            if capture.attrs["committed_blocks"] != capture.attrs["repeats"] * capture.attrs["blocks_per_repeat"]:
                raise ValueError("Incomplete spectral capture")
            role = capture.attrs["role"]
            capture.attrs.modify("complete", True)
            if role != "blank":
                calibration = entry["calibration"]
                if role in calibration and calibration[role].id != capture.id:
                    raise ValueError(f"{role.title()} was already selected in this run")
                if role not in calibration:
                    calibration[role] = capture
            return self._read_blocks(capture)

    def set_preparation_zero(self, role, od):
        with h5py.File(self.path, "r+") as file:
            entry = self._writable_entry(file)
            calibration = entry["calibration"]
            source = calibration[role]
            zeros = entry.require_group("calibration_zeros")
            if role not in zeros:
                zero = nx(zeros, role, "NXdata")
                zero["wavelength"] = entry["raw_ch1/wavelength"]
                field(zero, "od", od, "1")
                field(zero, "selected_utc", time.time(), "s")
                zero["spectra"] = source
                axes(zero, "od", ("wavelength",))
            if role == "reference":
                if not len(entry["blanks"]):
                    self._store_blank(entry, 0, self._read_blocks(source), od, True)
                if "initial_blank" not in calibration:
                    calibration["initial_blank"] = source

    def preparation_info(self):
        with h5py.File(self.path, "r") as file:
            entry = file.get("entry")
            pending = bool(file.attrs.get("calibration_pending", False))
            comment = entry["sample/description"].asstr()[()] if entry is not None and "sample/description" in entry else ""
            return pending, comment

    def has_preparation_zero(self, role):
        with h5py.File(self.path, "r") as file:
            return f"entry/calibration_zeros/{role}" in file

    def exposure_config(self):
        with h5py.File(self.path, "r") as file:
            return json.loads(file.attrs["settings_json"]).get("exposure", {})

    def set_prepared_exposure(self, setup):
        with h5py.File(self.path, "r+") as file:
            entry = self._writable_entry(file)
            if not file.attrs.get("calibration_pending", False):
                raise ValueError("Sample metadata is locked once sample collection starts")
            settings = json.loads(file.attrs["settings_json"])
            settings["exposure"] = setup
            write_sample_geometry(entry, setup)
            file.attrs["settings_json"] = json.dumps(settings)

    def sample_metadata(self):
        with h5py.File(self.path, "r") as file:
            sample = file.get("entry/sample")
            if sample is None:
                return {}
            metadata = {}
            for key, name in (("sample_volume_ml", "sample_volume"), ("window_diameter_mm", "window_diameter"),
                              ("path_length_mm", "path_length")):
                if name in sample:
                    metadata[key] = float(sample[name][()])
            if "cell_type" in sample:
                metadata["cell_type"] = sample["cell_type"].asstr()[()]
            reference = file.get("entry/reference")
            if reference is not None:
                metadata["reference_same_cell"] = bool(reference["same_cell_as_sample"][()])
                metadata["reference_path_length_mm"] = float(reference["path_length"][()])
                metadata["reference_cell_type"] = reference["cell_type"].asstr()[()]
            return metadata

    def start_prepared_collection(self, epoch, exposure_setup, offset=0.0):
        missing = missing_sample_fields(exposure_setup) + missing_reference_fields(exposure_setup)
        if missing:
            raise ValueError("Complete sample metadata: " + ", ".join(missing))
        with h5py.File(self.path, "r+") as file:
            entry = self._writable_entry(file)
            if not file.attrs.get("calibration_pending", False):
                return float(file.attrs["started_utc_s"])
            if "initial_blank" not in entry["calibration"]:
                raise ValueError("Set Reference Zero before starting acquisition")
            setup = dict(exposure_setup, start_offset_s=offset)
            rate = setup.get("dose_rate_gy_h", np.nan)
            if not np.isnan(rate) and (not np.isfinite(rate) or rate < 0):
                raise ValueError("Dose rate must be finite and nonnegative")
            file.attrs["started_utc_s"] = epoch
            entry["start_time"][()] = utc_iso(epoch)
            entry["irradiation/state/time"].attrs["start"] = utc_iso(epoch)
            entry["irradiation/state/time"][0] = offset
            entry["irradiation/state/value"][0] = bool(setup.get("irradiating_at_start", False))
            entry["irradiation/dose_rate_set"][()] = rate
            write_sample_geometry(entry, setup)
            settings = json.loads(file.attrs["settings_json"])
            settings["exposure"] = setup
            file.attrs["settings_json"] = json.dumps(settings)
            entry["blanks/00000000/anchor_time"][()] = offset
            file.flush()
            file.attrs["calibration_pending"] = False
            return epoch

    def latest_reference_drift(self):
        with h5py.File(self.path, "r") as file:
            blanks = file.get("entry/blanks")
            if blanks is None or len(blanks) < 2:
                return None
            names = sorted(blanks)
            return blanks[names[-1]]["od"][:] - blanks[names[0]]["od"][:]

    def irradiation_seconds(self, elapsed):
        with h5py.File(self.path, "r") as file:
            return self._irradiation_seconds(file["entry/irradiation/state"], elapsed)

    @staticmethod
    def _version(file):
        version = file.attrs.get("version")
        if file.attrs.get("format") != "avantes-gamma" or version not in (1, SCHEMA_VERSION):
            raise ValueError("Unsupported Avantes HDF5 format")
        return int(version)

    @classmethod
    def _writable_entry(cls, file):
        if cls._version(file) != SCHEMA_VERSION:
            raise ValueError("Upgrade the version 1 file to a separate version 2 file before writing")
        return file["entry"]

    def schema_version(self):
        with h5py.File(self.path, "r") as file:
            return self._version(file)

    @staticmethod
    def _write_blocks(entry, parent, role, blocks):
        group = nx(parent, role, "NXcollection")
        block_axis = field(group, "block_index", np.arange(len(blocks), dtype=np.int64))
        block_axis.make_scale("block_index")
        field(group, "time_utc", [b["metadata"].get("utc_s", np.nan) for b in blocks],
              "s", "POSIX UTC acquisition start time")
        for i in (1, 2):
            dataset = field(group, f"ch{i}_counts", np.stack([block[f"ch{i}"] for block in blocks]),
                            "counts", "Uncorrected SDK intensity after hardware averaging")
            dataset.dims[0].attach_scale(block_axis)
            dataset.dims[1].attach_scale(entry[f"raw_ch{i}/wavelength"])
        group.create_dataset("metadata_json", data=[json.dumps(block["metadata"]) for block in blocks], dtype=TEXT)
        return group

    @staticmethod
    def _read_blocks(group):
        return [
            dict(ch1=ch1, ch2=ch2, metadata=json.loads(metadata))
            for ch1, ch2, metadata in zip(group["ch1_counts"][:], group["ch2_counts"][:], group["metadata_json"][:])
        ]

    def info(self):
        with h5py.File(self.path, "r") as file:
            if self._version(file) == 1:
                wavelengths = tuple(file[f"wavelength_nm/ch{i}"][:] for i in (1, 2))
                acquisition = file["measurements"]
            else:
                wavelengths = tuple(file[f"entry/raw_ch{i}/wavelength"][:] for i in (1, 2))
                acquisition = file["entry/acquisition"]
            return (
                wavelengths, json.loads(file.attrs["serials_json"]), float(file.attrs["started_utc_s"]),
                int(acquisition.attrs["committed_rows"]),
            )

    def calibration(self):
        return {role: mean_counts(blocks) for role, blocks in self.calibration_blocks().items()}

    def calibration_blocks(self):
        with h5py.File(self.path, "r") as file:
            parent = file["calibration" if self._version(file) == 1 else "entry/calibration"]
            return {role: self._read_blocks(group) for role, group in parent.items()}

    def detector_setup(self):
        with h5py.File(self.path, "r") as file:
            saved = json.loads(file.attrs["settings_json"])["spectrometers"]
            return [saved["1"], saved["2"]]

    @staticmethod
    def _row_fields(entry):
        acq = entry["acquisition"]
        for name in ("time", "time_utc", "metadata_json"):
            yield name, acq[name]
        if "dose" in acq:
            yield "dose", acq["dose"]
        for i in (1, 2):
            for name in ("data", "count_time_set", "averages_set", "trigger_mode_set", "readout_ok"):
                yield f"ch{i}_{name}", entry[f"instrument/detector_{i}/{name}"]
        for name in ("od", "delta_od"):
            yield name, entry[f"od_live/{name}"]

    @staticmethod
    def _typed_detector_fields(metadata):
        fields = {}
        channels = metadata.get("channels", ())
        readout_ok = metadata.get("channel_ok", ())
        for i in range(2):
            settings = channels[i] if i < len(channels) else {}
            fields.update({
                f"ch{i+1}_count_time_set": settings.get("integration_ms", np.nan) / 1000,
                f"ch{i+1}_averages_set": settings.get("averages", -1),
                f"ch{i+1}_trigger_mode_set": settings.get("trigger_mode", -1),
                f"ch{i+1}_readout_ok": int(readout_ok[i]) if i < len(readout_ok) else -1,
            })
        return fields

    def append(self, time_s, utc_s, ch1, ch2, od_raw, od_delta, metadata):
        """Publish a row only after both counts and the live OD have been written."""
        with h5py.File(self.path, "r+") as file:
            entry = self._writable_entry(file)
            acq = entry["acquisition"]
            index = int(acq.attrs["committed_rows"])
            if not np.isfinite(time_s) or (index and time_s < acq["time"][index - 1]):
                raise ValueError("Measurement timestamps must be finite and nondecreasing")
            values = dict(time=time_s, time_utc=utc_s, ch1_data=ch1, ch2_data=ch2, od=od_raw, delta_od=od_delta,
                          metadata_json=json.dumps(metadata), **self._typed_detector_fields(metadata))
            if "dose" in acq:
                values["dose"] = self._dose(entry, time_s) if np.isfinite(utc_s) else np.nan
            for name, dataset in self._row_fields(entry):
                dataset.resize(index + 1, axis=0)
                value = values[name]
                dataset[index] = dataset.fillvalue if value is None else value
            file.flush()
            acq.attrs.modify("committed_rows", index + 1)
            return index + 1

    @staticmethod
    def _dose(entry, elapsed):
        irradiation = entry["irradiation"]
        rate = irradiation["dose_rate_set"][()]
        if not np.isfinite(rate):
            return np.nan
        return AvantesRun._irradiation_seconds(irradiation["state"], elapsed) * rate / 3600

    @staticmethod
    def _irradiation_seconds(state, elapsed):
        time_points = state["time"][:]
        end = np.searchsorted(time_points, elapsed, side="right")
        if end == 0:
            return np.nan
        durations = np.diff(np.append(time_points[:end], elapsed))
        return np.dot(durations, state["value"][:end])

    def irradiation_state(self):
        with h5py.File(self.path, "r") as file:
            irradiation = file.get("entry/irradiation")
            if irradiation is None:
                return np.nan, False
            return irradiation["dose_rate_set"][()], bool(irradiation["state/value"][-1])

    def sample_volumes(self):
        with h5py.File(self.path, "r") as file:
            sample = file.get("entry/sample")
            if sample is None:
                return np.nan, np.nan
            return sample["optical_volume"][()], sample["sample_volume"][()]

    def mark_irradiation(self, enabled, utc_s):
        """Log the operator's observation of the external irradiation state."""
        with h5py.File(self.path, "r+") as file:
            entry = self._writable_entry(file)
            if "irradiation" not in entry:
                init_exposure(entry, {})
            log = entry["irradiation/state"]
            elapsed = utc_s - file.attrs["started_utc_s"]
            if not np.isfinite(elapsed) or elapsed < log["time"][-1]:
                raise ValueError("Irradiation events must be in chronological order")
            if bool(log["value"][-1]) != bool(enabled):
                index = len(log["time"])
                for name, value in (("time", elapsed), ("value", bool(enabled))):
                    log[name].resize(index + 1, axis=0)
                    log[name][index] = value

    def append_event(self, event, utc_s, **details):
        with h5py.File(self.path, "r+") as file:
            events = self._writable_entry(file)["events/metadata_json"]
            events.resize(len(events) + 1, axis=0)
            events[-1] = json.dumps(dict(event=event, utc_s=utc_s, **details))

    def add_blank(self, time_s, blocks, od, *, initial=False):
        """Record an independent blank OD spectrum and publish a new correction."""
        with h5py.File(self.path, "r+") as file:
            entry = self._writable_entry(file)
            self._store_blank(entry, time_s, blocks, od, initial)
            if len(entry["blanks"]) < 2:
                return False
            self._correct(entry, reason="blank captured")
            return True

    @classmethod
    def _store_blank(cls, entry, time_s, blocks, od, initial):
        blanks = entry["blanks"]
        names = sorted(blanks)
        if not np.isfinite(time_s) or (names and time_s <= blanks[names[-1]]["anchor_time"][()]):
            raise ValueError("Blank must follow the previous anchor")
        name = f"{len(names):08d}"
        try:
            blank = cls._write_blocks(entry, blanks, name, blocks)
            field(blank, "od", od, "1", "Optical density against the original run reference")
            blank["wavelength"] = entry["od_live/wavelength"]
            spectrum = nx(blank, "spectrum", "NXdata")
            spectrum["od"] = blank["od"]
            spectrum["wavelength"] = blank["wavelength"]
            axes(spectrum, "od", ("wavelength",))
            field(blank, "anchor_time", time_s, "s", "Time used for interpolation")
            field(blank, "capture_time_utc", blocks[0]["metadata"]["utc_s"], "s",
                  "POSIX UTC time at capture")
            field(blank, "initial", initial)
            schedule = blocks[0]["metadata"].get("blank_schedule")
            if schedule:
                field(blank, "requested_delay", schedule["delay_minutes"] * 60, "s")
                field(blank, "request_time_utc", schedule["requested_utc_s"], "s")
                field(blank, "scheduled_time_utc", schedule["due_utc_s"], "s")
                field(blank, "automatic_capture", schedule["auto_capture"])
        except Exception:
            if name in blanks:
                del blanks[name]
            raise

    def recalculate(self):
        with h5py.File(self.path, "r+") as file:
            return self._correct(self._writable_entry(file), reason="user requested")

    @staticmethod
    def _correct(entry, reason):
        anchors = [entry["blanks"][key] for key in sorted(entry["blanks"])]
        if len(anchors) < 2:
            raise ValueError("At least two measured blanks are required for drift correction")
        count = int(entry["acquisition"].attrs["committed_rows"])
        times = entry["acquisition/time"][:count]
        elapsed = np.array([blank["anchor_time"][()] for blank in anchors])
        blank_od = np.stack([blank["od"][:] for blank in anchors])
        drift = blank_od - blank_od[0]
        parameters = {
            "blank_paths": np.asarray([blank.name for blank in anchors], dtype=TEXT),
            "source": entry["od_live/delta_od"].name,
            "reason": reason,
            "method": "Piecewise linear interpolation of measured blank OD relative to first blank; no extrapolation",
            "input_rows": count,
        }
        with process_revision(entry, "blank_correction", "Gamma blank interpolation", "1", utc_iso(time.time()),
                              parameters) as (revision, path):
            field(revision, "anchor_time", elapsed, "s")
            field(revision, "anchor_od", blank_od, "1")
            if "irradiation" in entry and np.isfinite(entry["irradiation/dose_rate_set"][()]):
                field(revision, "anchor_dose", [AvantesRun._dose(entry, value) for value in elapsed], "Gy")
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
            source = entry["od_live/delta_od"]
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

    def view(self, dataset="od_delta", time_range=None, limit=500):
        if dataset not in (*OD_DATASETS, "od_vs_blank", "blank_drift"):
            raise ValueError(f"Unknown OD dataset: {dataset}")
        with h5py.File(self.path, "r") as file:
            if self._version(file) == 1:
                rows = file["measurements"]
                times = rows["time_s"][:int(rows.attrs["committed_rows"])]
                wavelengths = file["wavelength_nm/ch1"][:]
                initial = file["blanks"].get("00000000")
                basis = initial["od_raw"][:] if initial is not None and initial.attrs["initial"] else None
                signal = rows.get("od_raw" if dataset == "od_vs_blank" else dataset)
            else:
                entry = file["entry"]
                rows = entry["acquisition"]
                times = rows["time"][:int(rows.attrs["committed_rows"])]
                wavelengths = entry["od_live/wavelength"][:]
                initial = entry["blanks"].get("00000000")
                basis = initial["od"][:] if initial is not None and initial["initial"][()] else None
                if dataset in {"od_corrected", "blank_drift"}:
                    latest = next(reversed(list(published_processes(entry, "blank_correction"))), None)
                    name = "od" if dataset == "od_corrected" else "blank_drift"
                    signal = latest[f"data/{name}"] if latest is not None else None
                else:
                    signal = entry["od_live/delta_od" if dataset == "od_delta" else "od_live/od"]
            first, last = 0, len(times)
            if time_range is not None:
                first = int(np.searchsorted(times, time_range[0], side="left"))
                last = int(np.searchsorted(times, time_range[1], side="right"))
            stride = max(1, (last - first + limit - 1) // limit)
            first += (last - first - 1) % stride if last > first else 0
            selection = slice(first, last, stride)
            selected_times = times[selection]
            values = np.full((len(selected_times), len(wavelengths)), np.nan)
            if signal is not None and first < len(signal):
                available = signal[selection]
                values[:len(available)] = available
            if dataset == "od_vs_blank":
                values[:] = values - basis if basis is not None else np.nan
            return wavelengths, values, selected_times

    def upgrade(self, destination):
        """Copy a version 1 run to a new version 2 file, preserving the source."""
        wavelengths, serials, epoch, count = self.info()
        with h5py.File(self.path, "r") as old:
            if self._version(old) != 1:
                raise ValueError("Only version 1 files need upgrading")
            upgraded = self.create(destination, wavelengths, serials, epoch,
                                   json.loads(old.attrs["settings_json"]), self.calibration_blocks())
            with h5py.File(upgraded.path, "r+") as new:
                entry = new["entry"]
                old_rows = old["measurements"]
                legacy_names = {
                    "time": "time_s", "time_utc": "utc_s", "metadata_json": "metadata_json",
                    "ch1_data": "ch1_counts", "ch2_data": "ch2_counts", "od": "od_raw", "delta_od": "od_delta",
                }
                fields = dict(self._row_fields(entry))
                for dataset in fields.values():
                    dataset.resize(count, axis=0)
                for start in range(0, count, 128):
                    selection = slice(start, min(start + 128, count))
                    for name, old_name in legacy_names.items():
                        fields[name][selection] = old_rows[old_name][selection]
                    metadata = [self._typed_detector_fields(json.loads(value))
                                for value in old_rows["metadata_json"][selection]]
                    for name, dataset in fields.items():
                        if name not in legacy_names and name != "dose":
                            dataset[selection] = [row[name] for row in metadata]
                entry["acquisition"].attrs.modify("committed_rows", count)
                events = entry["events/metadata_json"]
                events.resize(len(old["events_json"]) + 1, axis=0)
                events[:-1] = old["events_json"][:]
                events[-1] = json.dumps(dict(event="upgraded", source=self.path.name, utc_s=time.time()))
                for key in sorted(old["blanks"]):
                    blank = old["blanks"][key]
                    self._store_blank(entry, blank.attrs["time_s"], self._read_blocks(blank),
                                      blank["od_raw"][:], bool(blank.attrs["initial"]))
                if len(entry["blanks"]) >= 2:
                    self._correct(entry, reason="imported from schema 1")
        return upgraded
