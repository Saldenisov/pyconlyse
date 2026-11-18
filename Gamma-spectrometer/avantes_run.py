"""Disk format and OD calculations for the standalone Gamma spectrometer."""

import json
from contextlib import contextmanager, nullcontext, suppress
import errno
from pathlib import Path
import time

import h5py
import numpy as np


from avantes_h5 import (
    SCHEMA_VERSION, TEXT, append_record, appendable, axes, field, init_entry, init_exposure, nx,
    missing_reference_fields, missing_sample_fields, publish_group, published_processes,
    utc_iso, write_sample_geometry,
)

from avantes_processing import (
    mean_counts, optical_density, publish_blank_correction, publish_raw_recalculation, valid_counts,
)



OD_DATASETS = ("od_raw", "od_delta", "od_corrected", "od_reprocessed")
CALIBRATION_ROLES = ("background", "empty", "reference")


@contextmanager
def _new_run_file(path):
    # Acquire the path exclusively. Never clean up a file we failed to open.
    file = h5py.File(path, "x")
    try:
        with file:
            yield file
    except Exception:
        with suppress(OSError):
            path.unlink()
        raise


def _open_run_for_write(path):
    """Allow a concurrent reader to release its lock before a write."""
    for delay in (0.05, 0.1, 0.2, 0.4, 0.8):
        try:
            return h5py.File(path, "r+")
        except OSError as exc:
            if exc.errno not in (errno.EAGAIN, errno.EWOULDBLOCK) and "Win32 GetLastError() = 33" not in str(exc):
                raise
            time.sleep(delay)
    return h5py.File(path, "r+")


class AvantesRun:
    """Read Avantes HDF5 runs and append to the NeXus-based version 2 format."""

    def __init__(self, path):
        self.path = Path(path)

    @classmethod
    def create(cls, path, wavelengths, serials, started_utc_s, settings, calibration):
        run = cls(path)
        with _new_run_file(run.path) as file:
            cls._initialize_file(file, wavelengths, serials, started_utc_s, settings, calibration)
        return run

    @classmethod
    def _initialize_file(cls, file, wavelengths, serials, started_utc_s, settings, calibration):
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
        return entry

    def begin_capture(self, role, repeats, blocks_per_repeat):
        if repeats < 1 or blocks_per_repeat < 1:
            raise ValueError("A spectral capture requires at least one block and one repeat")
        with _open_run_for_write(self.path) as file:
            entry = self._writable_entry(file)
            if "calibration_captures" not in entry:
                nx(entry, "calibration_captures", "NXcollection")
            captures = entry["calibration_captures"]
            sequence = max((int(key) for key in captures if key.isdecimal()), default=-1) + 1
            name = f"{sequence:08d}"
            with publish_group(captures, name, "NXcollection") as capture:
                capture.attrs.update(role=role, capture_id=name, repeats=repeats, blocks_per_repeat=blocks_per_repeat,
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
        with _open_run_for_write(self.path) as file:
            capture = self._writable_entry(file)[f"calibration_captures/{name}"]
            index = int(capture.attrs["committed_blocks"])
            repeat, in_repeat = divmod(index, int(capture.attrs["blocks_per_repeat"]))
            if capture.attrs["complete"] or repeat >= capture.attrs["repeats"]:
                raise ValueError("The spectral capture already has every requested block")
            meta = dict(block["metadata"], repeat_index=repeat, block_in_repeat=in_repeat)
            values = dict(block_index=index, repeat_index=repeat, block_in_repeat=in_repeat,
                          time_utc=meta["utc_s"], ch1_counts=block["ch1"], ch2_counts=block["ch2"],
                          metadata_json=json.dumps(meta))
            append_record(index, ((capture[key], value) for key, value in values.items()),
                          commit=(capture, "committed_blocks"))
            return index + 1

    def append_preview_block(self, block):
        with _open_run_for_write(self.path) as file:
            entry = self._writable_entry(file)
            if "preview_captures" not in entry:
                with publish_group(entry, "preview_captures", "NXcollection") as preview:
                    preview.attrs["committed_blocks"] = 0
                    appendable(preview, "time_utc", units="s")
                    appendable(preview, "metadata_json", dtype=TEXT, fill="{}")
                    for channel in (1, 2):
                        wavelength = entry[f"raw_ch{channel}/wavelength"]
                        counts = appendable(preview, f"ch{channel}_counts", width=len(wavelength), units="counts")
                        counts.dims[1].attach_scale(wavelength)
            preview = entry["preview_captures"]
            metadata = block["metadata"]
            append_record(
                int(preview.attrs["committed_blocks"]),
                ((preview["time_utc"], metadata["utc_s"]),
                 (preview["metadata_json"], json.dumps(metadata)),
                 (preview["ch1_counts"], block["ch1"]),
                 (preview["ch2_counts"], block["ch2"])),
                commit=(preview, "committed_blocks"),
            )

    def finish_capture(self, name):
        with _open_run_for_write(self.path) as file:
            entry = self._writable_entry(file)
            capture = entry[f"calibration_captures/{name}"]
            if capture.attrs["committed_blocks"] != capture.attrs["repeats"] * capture.attrs["blocks_per_repeat"]:
                raise ValueError("Incomplete spectral capture")
            role = capture.attrs["role"]
            blocks = self._read_blocks(capture)
            if len(blocks) != capture.attrs["committed_blocks"]:
                raise ValueError("A spectral capture dataset is shorter than its committed record count")
            if capture.attrs["complete"]:
                return blocks
            if role in {"background", "empty", "reference"}:
                calibration = entry["calibration"]
                previous = calibration.get(role)
                replacing = previous is not None and previous.id != capture.id
                if replacing and not file.attrs.get("calibration_pending", False):
                    raise ValueError("Calibration is locked once sample collection starts")
                archive = self._archive_replaced_zeros(entry, role) if replacing else nullcontext()
                with archive:
                    try:
                        if replacing:
                            del calibration[role]
                        if role not in calibration:
                            calibration[role] = capture
                        capture.attrs.modify("complete", True)
                    except Exception:
                        with suppress(OSError, RuntimeError, ValueError):
                            if role in calibration and calibration[role].id == capture.id:
                                del calibration[role]
                            if previous is not None and role not in calibration:
                                calibration[role] = previous
                            capture.attrs.modify("complete", False)
                        raise
            else:
                capture.attrs.modify("complete", True)
            return blocks

    @staticmethod
    @contextmanager
    def _archive_replaced_zeros(entry, role):
        """Retain earlier zero selections and the provisional drift anchor."""
        zero_roles = ("empty", "reference") if role in {"background", "empty"} else ("reference",)
        zeros = entry.get("calibration_zeros")
        to_archive = [f"calibration_zeros/{key}" for key in zero_roles if zeros is not None and key in zeros]
        anchor = entry.get("blanks/00000000")
        if anchor is not None and "initial" in anchor and bool(anchor["initial"][()]):
            to_archive.append("blanks/00000000")
        initial_blank = entry.get("calibration/initial_blank")
        moved = []
        try:
            if to_archive:
                if "calibration_zero_history" not in entry:
                    nx(entry, "calibration_zero_history", "NXcollection")
                history = entry["calibration_zero_history"]
                for source in to_archive:
                    label = "initial_anchor" if source.startswith("blanks/") else source.rsplit("/", 1)[-1]
                    destination = f"calibration_zero_history/{len(history):08d}_{label}"
                    entry.move(source, destination)
                    moved.append((source, destination))
            if initial_blank is not None:
                del entry["calibration/initial_blank"]
            yield
        except Exception:
            for source, destination in reversed(moved):
                with suppress(OSError, RuntimeError, ValueError):
                    entry.move(destination, source)
            if initial_blank is not None and "calibration/initial_blank" not in entry:
                with suppress(OSError, RuntimeError, ValueError):
                    entry["calibration/initial_blank"] = initial_blank
            raise

    def set_preparation_zero(self, role, od):
        with _open_run_for_write(self.path) as file:
            entry = self._writable_entry(file)
            calibration = entry["calibration"]
            source = calibration[role]
            zeros = entry.require_group("calibration_zeros")
            if role == "reference":
                self._ensure_reference_anchor(entry, od)
            if role in zeros and not self._zero_complete(zeros[role]):
                del zeros[role]
            if role not in zeros:
                with publish_group(zeros, role, "NXdata") as zero:
                    zero["wavelength"] = entry["raw_ch1/wavelength"]
                    field(zero, "od", od, "1")
                    field(zero, "selected_utc", time.time(), "s")
                    zero["spectra"] = source
                    axes(zero, "od", ("wavelength",))

    @classmethod
    def _ensure_reference_anchor(cls, entry, od):
        calibration = entry["calibration"]
        source = calibration["reference"]
        if not len(entry["blanks"]):
            cls._store_blank(entry, 0, cls._read_blocks(source), od, True)
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
            return self._has_preparation_zero(file["entry"], role) if "entry" in file else False

    @staticmethod
    def _zero_complete(zero):
        return zero is not None and all(key in zero for key in ("wavelength", "od", "selected_utc", "spectra"))

    @classmethod
    def _has_preparation_zero(cls, entry, role):
        if not cls._zero_complete(entry.get(f"calibration_zeros/{role}")):
            return False
        if role == "reference":
            anchor = entry.get("blanks/00000000")
            return ("calibration/initial_blank" in entry and anchor is not None
                    and "initial" in anchor and bool(anchor["initial"][()]))
        return True

    def exposure_config(self):
        with h5py.File(self.path, "r") as file:
            return json.loads(file.attrs["settings_json"]).get("exposure", {})

    def set_prepared_exposure(self, setup):
        with _open_run_for_write(self.path) as file:
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
        with _open_run_for_write(self.path) as file:
            entry = self._writable_entry(file)
            if not file.attrs.get("calibration_pending", False):
                return float(file.attrs["started_utc_s"])
            calibration = entry["calibration"]
            if not set(CALIBRATION_ROLES).issubset(calibration):
                raise ValueError("Measure Background, Empty and Reference before starting acquisition")
            dark = mean_counts(self._read_blocks(calibration["background"]))
            reference = mean_counts(self._read_blocks(calibration["reference"]))
            wavelengths = tuple(entry[f"raw_ch{i}/wavelength"][:] for i in (1, 2))
            initial_od = optical_density(*reference, reference, dark, wavelengths)
            if not np.isfinite(initial_od).any():
                raise ValueError("Reference has no valid OD after background subtraction")
            setup = dict(exposure_setup, start_offset_s=offset)
            rate = setup.get("dose_rate_gy_h", np.nan)
            if not np.isnan(rate) and (not np.isfinite(rate) or rate < 0):
                raise ValueError("Dose rate must be finite and nonnegative")
            self._ensure_reference_anchor(entry, initial_od)
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
        committed = int(group.attrs.get("committed_blocks", len(group["metadata_json"])))
        return [
            dict(ch1=ch1, ch2=ch2, metadata=json.loads(metadata))
            for ch1, ch2, metadata in zip(group["ch1_counts"][:committed], group["ch2_counts"][:committed],
                                          group["metadata_json"][:committed])
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

    def settings(self):
        with h5py.File(self.path, "r") as file:
            self._version(file)
            return json.loads(file.attrs["settings_json"])

    @staticmethod
    def suggest_continuation_path(path):
        candidate = path.with_name(f"{path.stem}_continued.h5")
        index = 2
        while candidate.exists():
            candidate = path.with_name(f"{path.stem}_continued_{index}.h5")
            index += 1
        return candidate

    def create_continuation_checkpoint(self, destination):
        """Keep calibration and reference anchors in an independent, small HDF5."""
        wavelengths, serials, epoch, _ = self.info()
        settings = self.settings()
        calibration = self.calibration_blocks()
        with h5py.File(self.path, "r") as original, _new_run_file(Path(destination)) as file:
            source = original["entry"]
            entry = self._initialize_file(file, wavelengths, serials, epoch, settings, calibration)
            for _, blank in sorted(source["blanks"].items()):
                self._store_blank(entry, blank["anchor_time"][()], self._read_blocks(blank),
                                  blank["od"][:], bool(blank["initial"][()]))
            old_state = source["irradiation/state"]
            new_state = entry["irradiation/state"]
            count = self._irradiation_log_length(old_state)
            for key in ("time", "value"):
                new_state[key].resize(count, axis=0)
                new_state[key][:] = old_state[key][:count]
            new_state.attrs.modify("committed_rows", count)
            entry["irradiation"].attrs["dose_unknown_after_s"] = self._resume_cutoff(source)
            file.attrs["calibration_pending"] = False

    @staticmethod
    def _resume_cutoff(entry):
        acq = entry["acquisition"]
        count = int(acq.attrs["committed_rows"])
        if count < 0 or any(len(dataset) < count for _, dataset in AvantesRun._row_fields(entry)):
            raise ValueError("A measurement dataset is shorter than its committed row count")
        if count:
            elapsed = acq["time"][count - 1]
            prior_cutoff = entry["irradiation"].attrs.get("dose_unknown_after_s", elapsed)
            return min(elapsed, prior_cutoff)
        return entry["irradiation"].attrs.get("dose_unknown_after_s", 0.0)

    def validate_continuation(self):
        with _open_run_for_write(self.path) as file:
            entry = self._writable_entry(file)
            if file.attrs.get("calibration_pending", False):
                raise ValueError("The acquisition has not completed calibration")
            self._resume_cutoff(entry)
            if not {"background", "reference"}.issubset(entry["calibration"]):
                raise ValueError("The acquisition is missing calibration counts")

    def latest_reference_utc(self):
        with h5py.File(self.path, "r") as file:
            if self._version(file) == SCHEMA_VERSION:
                blanks = file["entry/blanks"]
                if len(blanks):
                    latest = blanks[sorted(blanks)[-1]]
                    if "capture_time_utc" in latest:
                        value = float(latest["capture_time_utc"][()])
                        if np.isfinite(value):
                            return value
                reference = file.get("entry/calibration/reference")
            else:
                reference = file.get("calibration/reference")
            if reference is None:
                return None
            times = [block["metadata"].get("utc_s", np.nan) for block in self._read_blocks(reference)]
            finite = [float(value) for value in times if value is not None and np.isfinite(value)]
            return max(finite, default=None)

    def begin_collection_segment(self, utc_s):
        """Index a new segment and expose completed spectra as same-file HDF5 views."""
        with _open_run_for_write(self.path) as file:
            entry = self._writable_entry(file)
            acquisition = entry["acquisition"]
            stop = int(acquisition.attrs["committed_rows"])
            segments = entry.require_group("acquisition_segments")
            segments.attrs["NX_class"] = "NXcollection"
            names = sorted(name for name in segments if name.isdecimal())
            first = int(segments[names[-1]]["stop_row"][()]) if names else 0
            if first == stop:
                return None
            if not 0 <= first < stop:
                raise ValueError("Invalid acquisition segment bounds")
            name = f"{int(names[-1]) + 1 if names else 0:08d}"
            with publish_group(segments, name, "NXcollection") as archive:
                field(archive, "first_row", first)
                field(archive, "stop_row", stop)
                field(archive, "archived_utc", utc_s, "s")
                archive["source_acquisition"] = acquisition
                for key, source in (
                    ("time", acquisition["time"]), ("time_utc", acquisition["time_utc"]),
                    ("ch1_counts", entry["raw_ch1/data"]), ("ch2_counts", entry["raw_ch2/data"]),
                    ("od", entry["od_live/od"]), ("delta_od", entry["od_live/delta_od"]),
                ):
                    layout = h5py.VirtualLayout(shape=(stop - first, *source.shape[1:]), dtype=source.dtype)
                    layout[:] = h5py.VirtualSource(".", source.name, shape=source.shape)[first:stop]
                    archived = archive.create_virtual_dataset(key, layout, fillvalue=np.nan)
                    if "units" in source.attrs:
                        archived.attrs["units"] = source.attrs["units"]
                for channel in (1, 2):
                    archive[f"wavelength_ch{channel}"] = entry[f"raw_ch{channel}/wavelength"]
            return name

    def record_interruption(self, utc_s, *, event="automatic_resume", **details):
        with _open_run_for_write(self.path) as file:
            entry = self._writable_entry(file)
            cutoff = self._resume_cutoff(entry)
            entry["irradiation"].attrs["dose_unknown_after_s"] = cutoff
        self.append_event(event, utc_s, last_known_dose_elapsed_s=float(cutoff),
                          **details)

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
        with _open_run_for_write(self.path) as file:
            entry = self._writable_entry(file)
            acq = entry["acquisition"]
            index = int(acq.attrs["committed_rows"])
            if not np.isfinite(time_s) or (index and time_s < acq["time"][index - 1]):
                raise ValueError("Measurement timestamps must be finite and nondecreasing")
            values = dict(time=time_s, time_utc=utc_s, ch1_data=ch1, ch2_data=ch2, od=od_raw, delta_od=od_delta,
                          metadata_json=json.dumps(metadata), **self._typed_detector_fields(metadata))
            if "dose" in acq:
                values["dose"] = self._dose(entry, time_s) if np.isfinite(utc_s) else np.nan
            append_record(index, ((dataset, values[name]) for name, dataset in self._row_fields(entry)),
                          commit=(acq, "committed_rows"))
            return index + 1

    @staticmethod
    def _dose(entry, elapsed):
        irradiation = entry["irradiation"]
        rate = irradiation["dose_rate_set"][()]
        if not np.isfinite(rate) or elapsed > irradiation.attrs.get("dose_unknown_after_s", np.inf):
            return np.nan
        return AvantesRun._irradiation_seconds(irradiation["state"], elapsed) * rate / 3600

    @staticmethod
    def _irradiation_seconds(state, elapsed):
        time_points = state["time"][:AvantesRun._irradiation_log_length(state)]
        end = np.searchsorted(time_points, elapsed, side="right")
        if end == 0:
            return np.nan
        durations = np.diff(np.append(time_points[:end], elapsed))
        return np.dot(durations, state["value"][:end])

    @staticmethod
    def _irradiation_log_length(state):
        count = min(len(state["time"]), len(state["value"]))
        return min(int(state.attrs.get("committed_rows", count)), count)

    def irradiation_state(self):
        with h5py.File(self.path, "r") as file:
            irradiation = file.get("entry/irradiation")
            if irradiation is None:
                return np.nan, False
            state = irradiation["state"]
            count = self._irradiation_log_length(state)
            return irradiation["dose_rate_set"][()], bool(count and state["value"][count - 1])

    def dose_timeline_interrupted(self):
        with h5py.File(self.path, "r") as file:
            irradiation = file.get("entry/irradiation")
            return irradiation is not None and "dose_unknown_after_s" in irradiation.attrs

    def sample_volumes(self):
        with h5py.File(self.path, "r") as file:
            sample = file.get("entry/sample")
            if sample is None:
                return np.nan, np.nan
            return sample["optical_volume"][()], sample["sample_volume"][()]

    def mark_irradiation(self, enabled, utc_s):
        """Log the operator's observation of the external irradiation state."""
        with _open_run_for_write(self.path) as file:
            entry = self._writable_entry(file)
            if "irradiation" not in entry:
                init_exposure(entry, {})
            log = entry["irradiation/state"]
            elapsed = utc_s - file.attrs["started_utc_s"]
            count = self._irradiation_log_length(log)
            if not np.isfinite(elapsed) or (count and elapsed < log["time"][count - 1]):
                raise ValueError("Irradiation events must be in chronological order")
            if not count or bool(log["value"][count - 1]) != bool(enabled):
                append_record(count, ((log["time"], elapsed), (log["value"], bool(enabled))),
                              commit=(log, "committed_rows"))

    def append_event(self, event, utc_s, **details):
        encoded = json.dumps(dict(event=event, utc_s=utc_s, **details))
        with _open_run_for_write(self.path) as file:
            events = self._writable_entry(file)["events/metadata_json"]
            append_record(len(events), ((events, encoded),))

    def add_blank(self, time_s, blocks, od, *, initial=False):
        """Record an independent blank OD spectrum and publish a new correction."""
        with _open_run_for_write(self.path) as file:
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
        with _open_run_for_write(self.path) as file:
            return self._correct(self._writable_entry(file), reason="user requested")

    @staticmethod
    def _calibration_input(entry, role, capture_id):
        if role not in CALIBRATION_ROLES:
            raise ValueError(f"Unknown calibration role: {role}")
        if capture_id is None:
            return entry["calibration"][role]
        if not capture_id.isdecimal():
            raise ValueError("Invalid calibration capture ID")
        capture = entry[f"calibration_captures/{capture_id}"]
        if capture.attrs["role"] != role or not capture.attrs["complete"]:
            raise ValueError(f"Capture {capture_id} is not a completed {role}")
        return capture

    def calibration_options(self):
        with h5py.File(self.path, "r") as file:
            entry = self._writable_entry(file)
            captures = entry.get("calibration_captures", {})
            options = {}
            for role in CALIBRATION_ROLES:
                active = entry["calibration"].get(role)
                choices = []
                if active is not None:
                    label = "Active capture"
                    if "capture_id" in active.attrs:
                        label += f" #{active.attrs['capture_id']}"
                    choices.append((label, None))
                for name in sorted(captures, reverse=True):
                    capture = captures[name]
                    if (name.isdecimal() and capture.attrs.get("role") == role and capture.attrs.get("complete")
                            and (active is None or capture.id != active.id)):
                        choices.append((f"Capture #{name} · {len(capture['ch1_counts'])} blocks", name))
                options[role] = choices
            return options

    def preview_calibration(self, role, selections, zero):
        with h5py.File(self.path, "r") as file:
            entry = self._writable_entry(file)
            selected = self._calibration_input(entry, role, selections.get(role))
            blocks = self._read_blocks(selected)
            wavelengths = tuple(entry[f"raw_ch{i}/wavelength"][:] for i in (1, 2))
            counts = mean_counts(blocks)
            od = None
            if role != "background" and zero is not None:
                baseline = mean_counts(self._read_blocks(self._calibration_input(entry, zero, selections.get(zero))))
                dark = mean_counts(self._read_blocks(self._calibration_input(entry, "background", selections.get("background"))))
                od = optical_density(*counts, baseline, dark, wavelengths)
            return wavelengths, counts, od

    def reprocess_raw(self, selections=None, zero="reference"):
        """Derive OD from archived detector counts with independently selected calibration inputs."""
        if zero not in {"empty", "reference"}:
            raise ValueError("Choose Empty or Reference as the OD baseline")
        selections = selections or {}
        with _open_run_for_write(self.path) as file:
            entry = self._writable_entry(file)
            selected = {}
            for role in CALIBRATION_ROLES:
                if role != "empty" or role == zero or role in entry["calibration"]:
                    selected[role] = self._calibration_input(entry, role, selections.get(role))
            return publish_raw_recalculation(entry, selected, zero, self._read_blocks, self._dose)

    @staticmethod
    def _correct(entry, reason, *, source=None, blank_od=None):
        return publish_blank_correction(entry, reason, AvantesRun._dose, source=source, blank_od=blank_od)

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
                elif dataset == "od_reprocessed":
                    latest = next(reversed(list(published_processes(entry, "raw_recalculation"))), None)
                    signal = latest["data/od"] if latest is not None else None
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
            upgraded = type(self)(destination)
            settings = json.loads(old.attrs["settings_json"])
            calibration = self.calibration_blocks()
            with _new_run_file(upgraded.path) as new:
                entry = self._initialize_file(new, wavelengths, serials, epoch, settings, calibration)
                if "calibration_pending" in new.attrs:
                    new.attrs.modify("calibration_pending", False)
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
