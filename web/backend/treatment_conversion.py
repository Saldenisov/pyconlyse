"""Canonical HDF5 conversion for treatment inputs."""

import json
from pathlib import Path
from typing import Dict

import numpy as np

from utilities.dataio import H5Opener

try:
    import h5py
except ImportError:  # pragma: no cover - optional runtime dependency
    h5py = None
else:
    if not hasattr(h5py, "File"):  # pragma: no cover - broken namespace install
        h5py = None

class TreatmentConversion:
    """File conversion operations of TreatmentDataService."""

    def convert_file_to_h5(self, source_path: Path, output_path: Path, progress_callback=None) -> Dict[str, object]:
        if h5py is None:
            raise ValueError("h5py is not available in this Python environment")

        source = Path(source_path).expanduser()
        if not source.is_file():
            raise ValueError("Selected file does not exist")
        target = Path(output_path).expanduser()

        opener, info = self._get_opener_and_info(source)
        if not hasattr(opener, "give_all_maps"):
            raise ValueError("Selected file type does not support H5 conversion")

        if isinstance(opener, H5Opener) and source.resolve() == target.resolve():
            with h5py.File(source, "r") as h5_file:
                is_canonical_h5 = (
                    "raw_data" in h5_file
                    and "map_selection" in h5_file
                    and "included" in h5_file["map_selection"]
                )
                raw_map_count = (
                    int(h5_file["raw_data"].shape[0]) if "raw_data" in h5_file else 0
                )
            if is_canonical_h5:
                return {
                    "source_path": str(source),
                    "output_path": str(target),
                    "original_measurements": raw_map_count,
                    "compression": "gzip",
                    "compression_level": 4,
                }

        if all(
            hasattr(info, attr)
            for attr in (
                "bytes_per_point",
                "data_pos",
                "timedelays_length",
                "wavelengths_length",
                "number_maps",
            )
        ):
            return self._convert_hamamatsu_file_to_h5(source, output_path, info, progress_callback)

        selection_mask = None
        selection_records = []
        selection_method = "all"
        selection_angle_threshold = None
        selection_surface_threshold = None
        if isinstance(opener, H5Opener):
            with h5py.File(source, "r") as h5_file:
                raw_map_count = int(h5_file["raw_data"].shape[0])
                candidate_mask = H5Opener._selection_mask(h5_file, raw_map_count)
                if "map_selection" in h5_file and "included" in h5_file["map_selection"]:
                    selection_mask = candidate_mask
                    selection_group = h5_file["map_selection"]
                    selection_method = str(selection_group.attrs.get("method", "all"))
                    if "sam_angle_threshold" in selection_group.attrs:
                        selection_angle_threshold = float(
                            selection_group.attrs["sam_angle_threshold"]
                        )
                    if "sam_surface_threshold" in selection_group.attrs:
                        selection_surface_threshold = float(
                            selection_group.attrs["sam_surface_threshold"]
                        )
                    records_json = selection_group.attrs.get("records_json", "[]")
                    if isinstance(records_json, bytes):
                        records_json = records_json.decode("utf-8", errors="ignore")
                    try:
                        selection_records = json.loads(str(records_json))
                    except (TypeError, ValueError):
                        selection_records = []
            measurements = iter(opener.give_all_maps(source, include_excluded=True))
        else:
            measurements = iter(opener.give_all_maps(source))
        first_measurement = next(measurements, None)
        if first_measurement is None:
            raise ValueError("No measurements were found in the selected file")

        first_map = np.asarray(first_measurement.data, dtype=float)
        expected_measurements = int(getattr(info, "number_maps", 0) or 0) or 1
        target.parent.mkdir(parents=True, exist_ok=True)

        with h5py.File(target, "w") as h5_file:
            metadata_group = h5_file.create_group("metadata")
            h5_file.create_dataset("timedelays", data=np.asarray(info.timedelays, dtype=float))
            h5_file.create_dataset("wavelengths", data=np.asarray(info.wavelengths, dtype=float))
            raw_dataset = h5_file.create_dataset(
                "raw_data",
                shape=(expected_measurements,) + tuple(first_map.shape),
                dtype=float,
                compression="gzip",
                compression_opts=4,
            )
            raw_dataset[0] = first_map
            if progress_callback:
                progress_callback(1, expected_measurements)
            written_measurements = 1
            for index, measurement in enumerate(measurements, start=1):
                raw_dataset[index] = np.asarray(measurement.data, dtype=float)
                written_measurements = index + 1
                if progress_callback:
                    progress_callback(written_measurements, expected_measurements)
            self._write_map_selection(
                h5_file,
                selection_mask
                if selection_mask is not None
                else np.ones(written_measurements, dtype=bool),
                records=selection_records,
                method=selection_method,
                angle_threshold=selection_angle_threshold,
                surface_threshold=selection_surface_threshold,
            )
            description = getattr(info, "header", "") or ""
            time_scale = getattr(info, "scaling_yunit", "") or ""
            metadata_group.attrs["description"] = str(description).replace("\0", "").encode("utf-8")
            metadata_group.attrs["source_file"] = str(source)
            metadata_group.attrs["original_measurements"] = int(written_measurements)
            metadata_group.attrs["converted_without_cleaning"] = selection_mask is None
            metadata_group.attrs["h5_schema_version"] = 2
            metadata_group.attrs["compression"] = "gzip"
            metadata_group.attrs["compression_level"] = 4
            metadata_group.attrs["time_scale"] = str(time_scale)
            metadata_group.attrs["scaling_yunit"] = str(time_scale)

        return {
            "source_path": str(source),
            "output_path": str(target),
            "original_measurements": int(written_measurements),
            "compression": "gzip",
            "compression_level": 4,
        }

    def _convert_hamamatsu_file_to_h5(self, source: Path, output_path: Path, info, progress_callback=None) -> Dict[str, object]:
        number_type_by_size = {
            1: np.int8,
            2: np.int16,
            4: np.int32,
        }
        number_type = number_type_by_size.get(int(info.bytes_per_point))
        if number_type is None:
            raise ValueError(f"Unsupported Hamamatsu bytes_per_point: {info.bytes_per_point}")

        number_maps = int(info.number_maps or 1)
        timedelays_length = int(info.timedelays_length)
        wavelengths_length = int(info.wavelengths_length)
        size_data_bytes = int(info.bytes_per_point) * timedelays_length * wavelengths_length
        target = Path(output_path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)

        with h5py.File(target, "w") as h5_file:
            metadata_group = h5_file.create_group("metadata")
            h5_file.create_dataset("timedelays", data=np.asarray(info.timedelays, dtype=float))
            h5_file.create_dataset("wavelengths", data=np.asarray(info.wavelengths, dtype=float))
            raw_dataset = h5_file.create_dataset(
                "raw_data",
                shape=(number_maps, wavelengths_length, timedelays_length),
                chunks=(1, min(wavelengths_length, 128), min(timedelays_length, 128)),
                dtype=float,
                compression="gzip",
                compression_opts=4,
            )
            with open(source, "rb") as file_handle:
                for map_index in range(number_maps):
                    offset = int(info.data_pos) + 64 * map_index + map_index * size_data_bytes
                    file_handle.seek(offset, 0)
                    raw = file_handle.read(size_data_bytes)
                    if len(raw) != size_data_bytes:
                        raise ValueError(
                            f"Could not read full HIS map {map_index + 1}/{number_maps} from {source}"
                        )
                    data = np.frombuffer(raw, dtype=number_type).reshape(
                        timedelays_length,
                        wavelengths_length,
                    ).transpose()
                    raw_dataset[map_index] = data
                    if progress_callback:
                        progress_callback(map_index + 1, number_maps)

            self._write_map_selection(
                h5_file,
                np.ones(number_maps, dtype=bool),
            )

            description = getattr(info, "header", "") or ""
            time_scale = getattr(info, "scaling_yunit", "") or ""
            metadata_group.attrs["description"] = str(description).replace("\0", "").encode("utf-8")
            metadata_group.attrs["source_file"] = str(source)
            metadata_group.attrs["original_measurements"] = number_maps
            metadata_group.attrs["converted_without_cleaning"] = True
            metadata_group.attrs["h5_schema_version"] = 2
            metadata_group.attrs["compression"] = "gzip"
            metadata_group.attrs["compression_level"] = 4
            metadata_group.attrs["time_scale"] = str(time_scale)
            metadata_group.attrs["scaling_yunit"] = str(time_scale)

        return {
            "source_path": str(source),
            "output_path": str(target),
            "original_measurements": number_maps,
            "compression": "gzip",
            "compression_level": 4,
        }
