"""Readers for legacy V0 optical-density and raw-spectrum files."""

from io import BytesIO, TextIOWrapper
from pathlib import Path
from urllib.parse import unquote
from zipfile import ZipFile

import h5py
import numpy as np


def _file_name(path):
    return unquote(str(path).rstrip("/").split("/")[-1]) if str(path).startswith("smb://") else Path(path).name


def _file_stem(path):
    return Path(_file_name(path)).stem


def _to_float_list(values, precision=6):
    return [round(float(value), precision) for value in values]


def _to_matrix(values, precision=6):
    return [
        [round(float(value), precision) if np.isfinite(value) else None for value in row]
        for row in values
    ]


def parse_dat_payload(path, payload):
    text = payload.decode("utf-8-sig", errors="replace").replace(",", ".")
    data = np.loadtxt(BytesIO(text.encode("utf-8")))
    if data.ndim != 2 or data.shape[0] < 2 or data.shape[1] < 2:
        raise ValueError("DAT file does not contain wavelength x delay matrix")
    wavelengths = data[1:, 0]
    delays = data[0, 1:]
    heatmap = data[1:, 1:].T
    return {
        "success": True,
        "kind": "od",
        "file_name": _file_name(path),
        "path": path,
        "wavelengths": _to_float_list(wavelengths, 5),
        "delays": _to_float_list(delays, 5),
        "heatmap": _to_matrix(heatmap, 6),
    }


def _parse_new_raw(raw_handle):
    reader = TextIOWrapper(raw_handle, encoding="utf-8-sig", errors="replace")
    first_line = reader.readline()
    wavelengths = np.fromstring(first_line, dtype=np.single, sep="\t")
    if len(wavelengths) > 1024 or len(wavelengths) == 0:
        return None

    delays = []
    blocks = []
    block_rows = []
    current_delay = None
    for line in reader:
        stripped = line.strip()
        if stripped.startswith("S_"):
            current_delay = float(stripped[2:].replace(",", "."))
            block_rows = []
        elif stripped.startswith("E_"):
            if current_delay is not None and block_rows:
                delays.append(current_delay)
                blocks.append(np.array(block_rows, dtype=np.uint16))
            block_rows = []
            current_delay = None
        elif len(stripped) > 10:
            block_rows.append(np.fromstring(stripped, dtype=np.uint16, sep="\t"))

    if current_delay is not None and block_rows:
        delays.append(current_delay)
        blocks.append(np.array(block_rows, dtype=np.uint16))
    if not blocks:
        return None

    channel_names = ["BG1", "Ir1", "Is1", "BG2", "Ir2", "Is2"]
    channels = {name: [] for name in channel_names}
    raw_trace_count = 0
    for block in blocks:
        if block.ndim != 2 or block.shape[0] < 6:
            continue
        if block.shape[0] % 3 == 0:
            split_groups = np.array_split(block, 3)
            if all(group.shape[0] >= 2 for group in split_groups):
                bg1, bg2 = np.array_split(split_groups[0], 2)
                ir1, is1 = np.array_split(split_groups[1], 2)
                ir2, is2 = np.array_split(split_groups[2], 2)
                grouped = [bg1, ir1, is1, bg2, ir2, is2]
            else:
                grouped = np.array_split(block, 6)
        else:
            grouped = np.array_split(block, 6)
        raw_trace_count = max(raw_trace_count, max(group.shape[0] for group in grouped))
        for name, group in zip(channel_names, grouped):
            channels[name].append(group.mean(axis=0))

    if not any(channels[name] for name in channel_names):
        return None

    return {
        "wavelengths": wavelengths,
        "delays": np.array(delays, dtype=np.single),
        "channels": [
            {
                "key": name,
                "label": name,
                "values": np.array(channels[name], dtype=np.single),
            }
            for name in channel_names
            if channels[name]
        ],
        "raw_trace_count": raw_trace_count,
    }


def _parse_legacy_raw(raw_handle):
    raw_text = raw_handle.read()
    if isinstance(raw_text, bytes):
        raw_text = raw_text.decode("utf-8-sig", errors="replace")
    raw_text = raw_text.replace(",", ".")
    data = np.loadtxt(BytesIO(raw_text.encode("utf-8")))
    if data.ndim != 2 or data.shape[1] < 2:
        raise ValueError("RAW file does not contain legacy delay x spectra matrix")
    return {
        "wavelengths": np.arange(data.shape[1] - 1, dtype=np.single),
        "delays": data[:, 0].astype(np.single),
        "channels": [{
            "key": "raw",
            "label": "raw",
            "values": data[:, 1:].astype(np.single),
        }],
        "raw_trace_count": 1,
    }


def parse_zip_payload(path, payload):
    with ZipFile(BytesIO(payload)) as archive:
        raw_names = [name for name in archive.namelist() if name.lower().endswith(".raw")]
        if not raw_names:
            raise ValueError("ZIP does not contain .raw file")
        expected = f"{_file_stem(path)}.raw"
        raw_name = next((name for name in raw_names if Path(name).name == expected), raw_names[0])
        with archive.open(raw_name) as raw_handle:
            parsed = _parse_new_raw(raw_handle)
        if parsed is None:
            with archive.open(raw_name) as raw_handle:
                parsed = _parse_legacy_raw(raw_handle)

    return {
        "success": True,
        "kind": "raw",
        "file_name": _file_name(path),
        "path": path,
        "raw_name": raw_name,
        "wavelengths": _to_float_list(parsed["wavelengths"], 5),
        "delays": _to_float_list(parsed["delays"], 5),
        "channels": [
            {
                "key": channel["key"],
                "label": channel["label"],
                "values": _to_matrix(channel["values"], 2),
            }
            for channel in parsed["channels"]
        ],
        "raw_trace_count": int(parsed["raw_trace_count"]),
    }


def parse_h5_payload(path, payload):
    """Load V0 HDF5 output for OD-map and raw-group viewing."""
    with h5py.File(BytesIO(payload), "r") as h5_file:
        required = {"od", "wavelength_nm", "delay_ps", "raw_data", "raw_group_names"}
        if not required.issubset(h5_file.keys()):
            raise ValueError("H5 file is not a V0 pump-probe run")
        wavelengths = np.asarray(h5_file["wavelength_nm"], dtype=np.float32)
        delays = np.asarray(h5_file["delay_ps"], dtype=np.float32)
        od = np.asarray(h5_file["od"], dtype=np.float32).T
        raw_data = np.asarray(h5_file["raw_data"], dtype=np.float32)
        frame_counts = np.asarray(h5_file.get("frame_counts", []), dtype=np.int32)
        group_names = [
            value.decode("utf-8") if isinstance(value, bytes) else str(value)
            for value in h5_file["raw_group_names"]
        ]

    channels = []
    raw_trace_count = 0
    for group_index, group_name in enumerate(group_names):
        channel = np.full((len(delays), len(wavelengths)), np.nan, dtype=np.float32)
        for delay_index, count in enumerate(frame_counts):
            if count > 0:
                channel[delay_index] = np.nanmean(raw_data[delay_index, group_index, :int(count)], axis=0)
                raw_trace_count = max(raw_trace_count, int(count))
        channels.append({
            "key": group_name,
            "label": group_name,
            "values": _to_matrix(channel, 2),
        })

    return {
        "success": True,
        "kind": "h5",
        "file_name": _file_name(path),
        "path": path,
        "wavelengths": _to_float_list(wavelengths, 5),
        "delays": _to_float_list(delays, 5),
        "heatmap": _to_matrix(od, 6),
        "channels": channels,
        "raw_trace_count": raw_trace_count,
    }
