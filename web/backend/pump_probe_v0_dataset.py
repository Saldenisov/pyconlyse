"""Shot-preserving TRANCON/V0 readers and stateless correction previews."""

import hashlib
import json
from dataclasses import dataclass, field
from io import BytesIO, StringIO
from pathlib import Path
from urllib.parse import unquote
from zipfile import ZipFile

import h5py
import numpy as np

from pump_probe_v0_processing import (
    OD_ALGORITHM, TRANCON_GROUPS, TRANCON_LAYOUT, TRANCON_FLOAT_LAYOUT, V0_LAYOUT, V0_RAW_GROUPS,
    apply_dataset_recipe, calculate_raw_od,
)


@dataclass
class V0Dataset:
    wavelengths: np.ndarray
    delays: np.ndarray
    od: np.ndarray | None
    blocks: list | None = None
    groups: tuple = ()
    layout: str | None = None
    raw_name: str = ""
    algorithm: str = "stored-od"
    channels: list | None = None
    source_row_indices: np.ndarray | None = None
    source_spec: dict | None = None
    source_hash: str | None = None
    contributors: list | None = None
    source_provenance: list | None = None
    segments: list | None = None
    source_datasets: tuple | None = field(default=None, repr=False)
    modified_source_row_indices: list = field(default_factory=list)
    removed_source_row_indices: list = field(default_factory=list)
    treatment_details: list = field(default_factory=list)
    source_wavelengths: np.ndarray = field(init=False, repr=False)
    source_delays: np.ndarray = field(init=False, repr=False)
    source_od: np.ndarray | None = field(init=False, repr=False)

    def __post_init__(self):
        self.wavelengths = np.asarray(self.wavelengths, dtype=np.float64).copy()
        self.delays = np.asarray(self.delays, dtype=np.float64).copy()
        self.od = np.asarray(self.od, dtype=np.float64).copy() if self.od is not None else None
        self.source_wavelengths = self.wavelengths.copy()
        self.source_delays = self.delays.copy()
        self.source_od = self.od.copy() if self.od is not None else None
        for values in (self.source_wavelengths, self.source_delays, self.source_od):
            if values is not None:
                values.setflags(write=False)
        if self.blocks is not None:
            original = []
            for block in self.blocks:
                values = np.array(block, copy=True)
                values.setflags(write=False)
                original.append(values)
            self.blocks = tuple(original)
        self.source_row_indices = (np.arange(len(self.delays), dtype=np.int64)
                                   if self.source_row_indices is None
                                   else np.asarray(self.source_row_indices, dtype=np.int64).copy())


def _file_name(path):
    return unquote(str(path).rstrip("/").split("/")[-1]) if str(path).startswith("smb://") else Path(path).name


def _to_float_list(values):
    # Coordinates retain DBL precision and ordered repeats through JSON.
    return [float(value) for value in values]


def _to_matrix(values, precision=6):
    return [[round(float(value), precision) if np.isfinite(value) else None for value in row]
            for row in values]


def _json_details(value):
    """Display gaps in diagnostics without changing internal OD or replay data."""
    if isinstance(value, dict):
        return {key: _json_details(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [_json_details(item) for item in value]
    if isinstance(value, np.generic):
        value = value.item()
    return None if isinstance(value, float) and not np.isfinite(value) else value


def _read_dat(payload):
    text = payload.decode("utf-8-sig", errors="strict").replace(",", ".")
    data = np.loadtxt(StringIO(text), ndmin=2)
    if data.shape[0] < 2 or data.shape[1] < 2:
        raise ValueError("DAT file does not contain wavelength x delay matrix")
    return V0Dataset(data[1:, 0], data[0, 1:], data[1:, 1:].T)


def _read_trancon_raw(payload):
    lines = payload.decode("utf-8-sig", errors="strict").replace(",", ".").splitlines()
    if not lines or not any(line.strip().startswith("S_") for line in lines[1:]):
        return None
    wavelengths = np.loadtxt(StringIO(lines[0]), ndmin=1)
    delays, blocks, rows = [], [], []
    delay = None
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        if line.startswith("S_"):
            if delay is not None:
                raise ValueError("RAW delay block lacks E_ marker")
            delay, rows = float(line[2:]), []
        elif line.startswith("E_"):
            if delay is None or not rows:
                raise ValueError("Empty or unmatched RAW delay block")
            values = np.loadtxt(StringIO("\n".join(rows)), ndmin=2)
            if values.shape[1] != wavelengths.size or values.shape[0] % 6:
                raise ValueError("RAW dimensions disagree with six-group layout")
            if (not np.isfinite(values).all() or (values < 0).any()
                    or (values > 65535).any() or (values != np.floor(values)).any()):
                raise ValueError("TRANCON RAW counts must be integers in 0..65535")
            blocks.append(values.astype(np.uint16).reshape(6, -1, wavelengths.size))
            delays.append(delay)
            delay, rows = None, []
        else:
            if delay is None:
                raise ValueError("RAW values outside a delay block")
            rows.append(line)
    if delay is not None or not blocks:
        raise ValueError("Incomplete or empty RAW")
    od, _used, _removed = calculate_raw_od(blocks, TRANCON_LAYOUT)
    return V0Dataset(wavelengths, np.asarray(delays), od, blocks,
                     TRANCON_GROUPS, TRANCON_LAYOUT, algorithm=OD_ALGORITHM)


def _read_zip(path, payload):
    with ZipFile(BytesIO(payload)) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith(".raw")]
        if not names:
            raise ValueError("ZIP does not contain .raw file")
        expected = Path(_file_name(path)).stem + ".raw"
        raw_name = next((name for name in names if Path(name).name == expected), names[0])
        raw_payload = archive.read(raw_name)
    dataset = _read_trancon_raw(raw_payload)
    if dataset is None:
        text = raw_payload.decode("utf-8-sig", errors="strict").replace(",", ".")
        values = np.loadtxt(StringIO(text), ndmin=2)
        if values.shape[1] < 2:
            raise ValueError("RAW file does not contain legacy delay x spectra matrix")
        dataset = V0Dataset(np.arange(values.shape[1] - 1), values[:, 0], None,
                            channels=[{"key": "raw", "label": "raw", "values": _to_matrix(values[:, 1:], 2)}])
    dataset.raw_name = raw_name
    return dataset


def _text(value):
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)


def _read_h5(payload):
    with h5py.File(BytesIO(payload), "r") as handle:
        required = {"od", "wavelength_nm", "delay_ps", "raw_data", "raw_group_names", "frame_counts"}
        if not required.issubset(handle.keys()):
            raise ValueError("H5 file is not a V0 pump-probe run with frame counts")
        wavelengths = np.asarray(handle["wavelength_nm"], dtype=np.float64)
        delays = np.asarray(handle["delay_ps"], dtype=np.float64)
        od = np.asarray(handle["od"], dtype=np.float64).T
        raw = handle["raw_data"]
        groups = tuple(_text(value) for value in handle["raw_group_names"])
        counts = np.asarray(handle["frame_counts"])
        if (wavelengths.ndim != 1 or delays.ndim != 1
                or od.shape != (len(delays), len(wavelengths))
                or raw.ndim != 4 or raw.shape[:2] != (len(delays), len(groups))
                or raw.shape[3] != len(wavelengths) or counts.shape != delays.shape
                or not np.isfinite(counts).all() or (counts < 0).any()
                or (counts > raw.shape[2]).any() or (counts != np.floor(counts)).any()):
            raise ValueError("H5 RAW dimensions or frame counts are invalid")
        # Slice actual acquired counts: NaN padding is storage, not a shot mask.
        blocks = [np.asarray(raw[index, :, :int(count), :])
                  for index, count in enumerate(counts)]
        inferred = V0_LAYOUT if groups == V0_RAW_GROUPS else TRANCON_LAYOUT if groups == TRANCON_GROUPS else None
        declared = _text(handle["metadata/raw_layout"][()]) if "metadata/raw_layout" in handle else inferred
        if declared == TRANCON_FLOAT_LAYOUT and groups == TRANCON_GROUPS:
            if raw.dtype != np.dtype("float32"):
                raise ValueError("H5 float32 RAW layout requires float32 storage")
            inferred = declared
        if declared != inferred:
            raise ValueError("H5 declared RAW layout disagrees with group names")
        algorithm = _text(handle["metadata/od_algorithm"][()]) if "metadata/od_algorithm" in handle else "stored-od-unspecified"
    # Stored precalculation has priority, including older log-of-means files.
    return V0Dataset(wavelengths, delays, od, blocks, groups, inferred, algorithm=algorithm)


def read_dataset(path, payload):
    suffix = Path(_file_name(path)).suffix.lower()
    if suffix == ".dat":
        dataset, kind = _read_dat(payload), "od"
    elif suffix == ".zip":
        dataset, kind = _read_zip(path, payload), "raw"
    elif suffix in {".h5", ".hdf5"}:
        dataset, kind = _read_h5(payload), "h5"
    else:
        raise ValueError("Only .dat, .zip, and V0 .h5 files can be loaded")
    if (not np.isfinite(dataset.wavelengths).all() or not np.isfinite(dataset.delays).all()
            or len(dataset.wavelengths) == 0 or len(dataset.delays) == 0):
        raise ValueError("Dataset axes must be nonempty and finite")
    return dataset, kind


def dataset_payload(path, payload, dataset, kind, operations=None, shot_info=None):
    source_counts = [block.shape[1] for block in dataset.blocks] if dataset.blocks is not None else []
    row_map = np.asarray(dataset.source_row_indices, dtype=np.int64)
    if (row_map.shape != dataset.delays.shape or (row_map < 0).any()
            or (row_map >= len(dataset.source_delays)).any()):
        raise ValueError("Dataset source row lineage disagrees with axes")
    counts = [source_counts[int(index)] for index in row_map] if source_counts else []
    channels = dataset.channels or []
    if dataset.blocks is not None:
        channels = []
        for group_index, name in enumerate(dataset.groups):
            values = np.full((len(dataset.delays), len(dataset.wavelengths)), np.nan)
            for index, source_index in enumerate(row_map):
                block = dataset.blocks[int(source_index)]
                if block.shape[1]:
                    values[index] = block[group_index].mean(axis=0)
            channels.append({"key": name, "label": name, "values": _to_matrix(values, 2)})
    elif channels:
        channels = [{**channel, "values": [channel["values"][int(index)] for index in row_map]}
                    for channel in channels]
    capabilities = _capabilities(dataset)
    if dataset.blocks is not None and dataset.layout in {V0_LAYOUT, TRANCON_LAYOUT, TRANCON_FLOAT_LAYOUT}:
        capabilities.append("raw_od")
    if dataset.blocks is not None and dataset.layout in {TRANCON_LAYOUT, TRANCON_FLOAT_LAYOUT}:
        capabilities.append("raw_background")
    response = {
        "success": True, "kind": kind, "file_name": _file_name(path), "path": path,
        "source_sha256": dataset.source_hash or hashlib.sha256(payload).hexdigest(),
        "wavelengths": _to_float_list(dataset.wavelengths),
        "delays": _to_float_list(dataset.delays),
        "channels": channels, "raw_trace_count": max(counts, default=1 if channels else 0),
        "frame_counts": counts, "raw_groups": list(dataset.groups), "raw_layout": dataset.layout,
        "source_row_indices": row_map.tolist(), "source_frame_counts": source_counts,
        "source_delays": _to_float_list(dataset.source_delays),
        "source_wavelengths": _to_float_list(dataset.source_wavelengths),
        "modified_source_row_indices": list(dataset.modified_source_row_indices),
        "modified_row_indices": [i for i, source_index in enumerate(row_map)
                                 if int(source_index) in dataset.modified_source_row_indices],
        "removed_source_row_indices": list(dataset.removed_source_row_indices),
        "raw_lineage": {"unchanged": True, "scope": "original-source" if dataset.blocks is not None else "no-aggregate-raw" if dataset.source_spec else "no-shot-raw",
                        "row_alignment": "source_row_indices", "numeric_equality_to_treated_od": False},
        "od_algorithm": dataset.algorithm, "operations": operations or [],
        "capabilities": capabilities, "shot_selection": shot_info,
        "treatment_details": _json_details(dataset.treatment_details),
    }
    if dataset.source_spec:
        response["source_spec"] = dataset.source_spec
    if dataset.contributors is not None:
        response["contributors"] = [dataset.contributors[int(index)] for index in row_map]
    if dataset.source_provenance is not None:
        response["source_provenance"] = dataset.source_provenance
    if dataset.segments is not None:
        response["segments"] = dataset.segments
    if shot_info is not None:
        response["shot_selection"] = {
            "used_counts": [shot_info["used_counts"][int(index)] for index in row_map],
            "removed_zero_slots": [shot_info["removed_zero_slots"][int(index)] for index in row_map],
            "source_used_counts": list(shot_info["used_counts"]),
            "source_removed_zero_slots": list(shot_info["removed_zero_slots"]),
        }
    response["recipe_fingerprint"] = _fingerprint({
        "source_sha256": response["source_sha256"], "operations": response["operations"],
        "source_row_indices": response["source_row_indices"],
        "modified_source_row_indices": response["modified_source_row_indices"],
    })
    if dataset.raw_name:
        response["raw_name"] = dataset.raw_name
    if dataset.od is not None:
        response["heatmap"] = _to_matrix(dataset.od, 9)
        response["nonfinite_counts"] = {
            "nan": int(np.isnan(dataset.od).sum()), "positive_inf": int(np.isposinf(dataset.od).sum()),
            "negative_inf": int(np.isneginf(dataset.od).sum()),
        }
    return response


def load_payload(path, payload):
    dataset, kind = read_dataset(path, payload)
    return dataset_payload(path, payload, dataset, kind)


def treat_dataset(path, payload, operations, source_sha256):
    if not isinstance(source_sha256, str) or source_sha256 != hashlib.sha256(payload).hexdigest():
        raise ValueError("Source file changed; reload before applying corrections")
    dataset, kind = read_dataset(path, payload)
    return _treat_loaded_dataset(path, payload, dataset, kind, operations)


def _treat_loaded_dataset(path, payload, dataset, kind, operations):
    result = apply_dataset_recipe(dataset.source_od, dataset.blocks, dataset.layout, operations,
                                  dataset.source_wavelengths, dataset.source_delays)
    dataset.od, dataset.wavelengths, dataset.delays = result["od"], result["wavelengths"], result["delays"]
    dataset.source_row_indices = result["source_row_indices"]
    dataset.modified_source_row_indices = result["modified_source_row_indices"]
    dataset.removed_source_row_indices = result["removed_source_row_indices"]
    dataset.treatment_details = result["treatment_details"]
    if result["operations"] and result["operations"][0]["kind"].startswith("raw_"):
        dataset.algorithm = OD_ALGORITHM
    return dataset, dataset_payload(path, payload, dataset, kind,
                                    result["operations"], result["shot_selection"])


def _fingerprint(value):
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _capabilities(dataset):
    if dataset.od is None:
        return []
    rows, columns = dataset.od.shape
    kinds = ["scale", "replace_nonfinite"]
    finite = np.isfinite(dataset.od).all()
    if finite and columns >= 2:
        kinds.append("kinetic_clean")
    if finite and rows >= 2:
        kinds.append("legacy_baseline")
    if finite and max(rows, columns) >= 3:
        kinds.append("savitzky_golay")
    return kinds


def derive_dataset(sources, method):
    """Derive OD from ordered file bytes, retaining contributor identities.

    Average uses first-longest delays and exact first-match lookups. Merge
    concatenates spectral segments and requires identical positional delays.
    Neither operation manufactures shot-level RAW for the aggregate.
    """
    if method not in {"average", "merge"}:
        raise ValueError("Derived method must be average or merge")
    if not isinstance(sources, (list, tuple)) or not 2 <= len(sources) <= 32:
        raise ValueError("Derivation requires 2..32 ordered sources")
    datasets, source_records, provenance = [], [], []
    for source in sources:
        if (not isinstance(source, (tuple, list)) or len(source) != 2
                or not isinstance(source[0], str) or not isinstance(source[1], bytes)):
            raise ValueError("Each source must contain a path and immutable file bytes")
        path, payload = source
        dataset, _kind = read_dataset(path, payload)
        if dataset.od is None:
            raise ValueError("Every derived source must contain an OD map")
        datasets.append(dataset)
        record = {"path": path, "source_sha256": hashlib.sha256(payload).hexdigest()}
        source_records.append(record)
        provenance.append({**record, "wavelengths": _to_float_list(dataset.wavelengths),
                           "delays": _to_float_list(dataset.delays),
                           "frame_counts": [b.shape[1] for b in dataset.blocks] if dataset.blocks is not None else [],
                           "raw_layout": dataset.layout, "raw_preserved_in_original_source": True})
    spec = {"kind": "derived", "method": method, "sources": source_records}
    source_hash = _fingerprint(spec)
    path = "derived:" + source_hash
    contributors, segments = [], None
    if method == "average":
        waves = datasets[0].wavelengths.copy()
        if any(not np.array_equal(d.wavelengths, waves) for d in datasets):
            raise ValueError("Average requires exactly matching ordered wavelength axes")
        reference = max(range(len(datasets)), key=lambda i: len(datasets[i].delays))
        delays = datasets[reference].delays.copy()
        rows = []
        for delay in delays:
            values, used = [], []
            for source_index, dataset in enumerate(datasets):
                matches = np.flatnonzero(dataset.delays == delay)
                if matches.size:
                    row_index = int(matches[0])
                    values.append(dataset.od[row_index])
                    used.append({"source_index": source_index, "source_row_index": row_index,
                                 **source_records[source_index]})
            with np.errstate(invalid="ignore", over="ignore"):
                rows.append(np.asarray(values, dtype=np.float64).mean(axis=0))
            contributors.append(used)
        od = np.asarray(rows, dtype=np.float64)
        algorithm = "exact-delay-arithmetic-mean-v1"
    else:
        delays = datasets[0].delays.copy()
        if any(not np.array_equal(d.delays, delays) for d in datasets):
            raise ValueError("Spectral merge requires exactly matching ordered delay axes")
        waves = np.concatenate([d.wavelengths for d in datasets])
        od = np.concatenate([d.od for d in datasets], axis=1)
        segments, start = [], 0
        for source_index, dataset in enumerate(datasets):
            stop = start + len(dataset.wavelengths)
            segments.append({"source_index": source_index, "start_column": start, "stop_column": stop,
                             **source_records[source_index]})
            start = stop
        contributors = [[{"source_index": i, "source_row_index": row_index,
                          "start_column": segment["start_column"], "stop_column": segment["stop_column"],
                          **source_records[i]} for i, segment in enumerate(segments)]
                        for row_index in range(len(delays))]
        algorithm = "ordered-spectral-concatenation-v1"
    dataset = V0Dataset(waves, delays, od, algorithm=algorithm, source_spec=spec,
                        source_hash=source_hash, contributors=contributors,
                        source_provenance=provenance, segments=segments,
                        source_datasets=tuple(datasets))
    return dataset, dataset_payload(path, None, dataset, "derived")


def treat_derived_dataset(sources, method, operations, source_sha256):
    """Rebuild ordered originals before replay; reject stale contributor bytes."""
    dataset, response = derive_dataset(sources, method)
    if not isinstance(source_sha256, str) or source_sha256 != response["source_sha256"]:
        raise ValueError("Source files changed; reload before applying corrections")
    return _treat_loaded_dataset(response["path"], None, dataset, "derived", operations)


def export_dat(dataset):
    matrix = np.empty((len(dataset.wavelengths) + 1, len(dataset.delays) + 1))
    matrix[0, 0] = 0
    matrix[0, 1:] = dataset.delays
    matrix[1:, 0] = dataset.wavelengths
    matrix[1:, 1:] = dataset.od.T
    output = StringIO()
    np.savetxt(output, matrix, delimiter="\t", fmt="%.17g")
    return output.getvalue()
