"""HDF5 compression, SMB transfer, and conversion job tracking."""

from pathlib import Path
from typing import Dict
from typing import Optional
import os
import tempfile


def _compressed_h5_reuse_summary(local_path: Path, display_path: str, source_size_bytes: int) -> Optional[Dict[str, object]]:
    import treatment_api as api

    if api.h5py is None:
        return None
    try:
        with api.h5py.File(local_path, "r") as h5_file:
            if "raw_data" not in h5_file:
                return None
            raw_data = h5_file["raw_data"]
            if raw_data.compression != "gzip":
                return None
            compression_level = raw_data.compression_opts
    except (AttributeError, OSError, TypeError):
        return None

    output_size_bytes = int(source_size_bytes or local_path.stat().st_size)
    return {
        "source_path": display_path,
        "output_path": display_path,
        "converted": False,
        "overwritten": False,
        "deleted_source": False,
        "reused_compressed": True,
        "compression": "gzip",
        "compression_level": compression_level,
        "source_size_bytes": output_size_bytes,
        "output_size_bytes": output_size_bytes,
        "space_change_bytes": 0,
        "space_change_percent": 0.0,
    }


def _convert_source_to_h5(source_path: str, progress_callback=None) -> Dict[str, object]:
    import treatment_api as api

    return api._compression_progress_summary(source_path, progress_callback=progress_callback)


def _convert_folder_source_worker(data_type: str, source_path: str, progress_queue):
    import treatment_api as api

    def report(*args):
        if progress_queue is not None:
            progress_queue.put((data_type, *args))

    return api._convert_source_to_h5(
        source_path,
        progress_callback=report if progress_queue is not None else None,
    )


def _convert_staged_h5_worker(data_type: str, source_path: str, output_path: str, progress_queue):
    import treatment_api as api

    summary = api.treatment_service.convert_file_to_h5(
        Path(source_path),
        Path(output_path),
        progress_callback=api._cpu_progress_callback(data_type, progress_queue),
    )
    output = Path(output_path)
    if not output.is_file():
        raise ValueError(f"Compressed H5 was not created: {output}")
    summary["output_size_bytes"] = int(output.stat().st_size)
    return summary


def _convert_smb_sources_to_h5_pipeline(
    selected_paths: Dict[str, str],
    progress_callback=None,
) -> Dict[str, Dict[str, object]]:
    import treatment_api as api

    conversions: Dict[str, Dict[str, object]] = {}
    prepared: Dict[str, Dict[str, object]] = {}

    with tempfile.TemporaryDirectory(prefix="pyconlyse_folder_smb_convert_") as tmp_dir:
        tmp_path = Path(tmp_dir)

        for data_type, source_path in selected_paths.items():
            source_suffix = api._path_suffix(source_path)
            if source_suffix not in {".his", ".h5"}:
                raise ValueError("Convert/Compress supports only HIS or H5 files")

            output_name = f"{Path(api._path_name(source_path)).stem}.h5"
            output_path = (
                source_path
                if source_suffix == ".h5"
                else api.smb_join(api.smb_parent(source_path), output_name)
            )
            mapped_source = api._mapped_smb_local_file(source_path)
            mapped_output = api.smb_to_local_path(output_path) if mapped_source else None
            if mapped_source:
                local_source = Path(mapped_source)
                source_size_bytes = int(local_source.stat().st_size)
                output_existed = source_suffix == ".h5" or (
                    bool(mapped_output) and Path(str(mapped_output)).is_file()
                )
                local_output = (
                    tmp_path / f"{data_type}_compressed_{output_name}"
                    if source_suffix == ".h5"
                    else Path(str(mapped_output))
                )
                if output_existed and source_suffix == ".his" and progress_callback:
                    progress_callback(
                        data_type,
                        "replace",
                        0,
                        0,
                        "Existing H5 will be replaced from HIS",
                    )
            else:
                source_size_bytes = api._smb_size_bytes(source_path)
                output_existed = source_suffix == ".h5" or (
                    source_suffix == ".his" and api.smb_isfile(output_path)
                )
                local_source = tmp_path / f"{data_type}_{api._path_name(source_path)}"
                local_output = tmp_path / f"{data_type}_{output_name}"
                if local_output == local_source:
                    local_output = tmp_path / f"{data_type}_compressed_{output_name}"

                if output_existed and source_suffix == ".his" and progress_callback:
                    progress_callback(
                        data_type,
                        "replace",
                        0,
                        0,
                        "Existing H5 will be replaced from HIS",
                    )
                if progress_callback:
                    progress_callback(
                        data_type,
                        "download",
                        0,
                        source_size_bytes,
                        "Reading source file from SMB",
                    )
                api.copy_smb_file_to_local(
                    source_path,
                    local_source,
                    progress_callback=(
                        lambda current, dt=data_type, total=source_size_bytes: progress_callback(
                            dt,
                            "download",
                            current,
                            total,
                            "Reading source file from SMB",
                        )
                        if progress_callback
                        else None
                    ),
                )

            if source_suffix == ".h5":
                reuse_summary = api._compressed_h5_reuse_summary(
                    local_source,
                    source_path,
                    source_size_bytes,
                )
                if reuse_summary:
                    if progress_callback:
                        progress_callback(
                            data_type,
                            "complete",
                            source_size_bytes,
                            source_size_bytes,
                            "H5 is already gzip compressed",
                        )
                    conversions[data_type] = reuse_summary
                    continue

            prepared[data_type] = {
                "source_path": source_path,
                "source_suffix": source_suffix,
                "source_size_bytes": source_size_bytes,
                "output_path": output_path,
                    "output_existed": output_existed,
                    "local_source": local_source,
                    "local_output": local_output,
                    "mapped_output": mapped_output,
                }

        if prepared:
            if progress_callback:
                for data_type in prepared:
                    progress_callback(data_type, "convert", 0, 0, "Compressing local H5 with gzip level 4")

            def report_conversion(data_type, current, total):
                progress_callback(
                    data_type,
                    "convert",
                    current,
                    total,
                    f"Compressing map {current}/{total} with gzip level 4",
                )

            def complete_conversion(data_type, summary):
                item = prepared[data_type]
                source_size_bytes = int(item["source_size_bytes"])
                output_size_bytes = int(summary.get("output_size_bytes") or 0)
                space_change_bytes = output_size_bytes - source_size_bytes
                summary.update({
                    "source_path": str(item["source_path"]),
                    "output_path": str(item["output_path"]),
                    "converted": True,
                    "overwritten": bool(item["output_existed"]),
                    "deleted_source": item["source_suffix"] == ".his",
                    "source_size_bytes": source_size_bytes,
                    "output_size_bytes": output_size_bytes,
                    "space_change_bytes": space_change_bytes,
                    "space_change_percent": (
                        round((space_change_bytes / source_size_bytes) * 100, 2)
                        if source_size_bytes else 0.0
                    ),
                })
                conversions[data_type] = summary

            api._run_parallel_cpu_jobs(
                {
                    data_type: (str(item["local_source"]), str(item["local_output"]))
                    for data_type, item in prepared.items()
                },
                api._convert_staged_h5_worker,
                on_progress=report_conversion if progress_callback else None,
                on_complete=complete_conversion,
            )

        for data_type, item in prepared.items():
            conversion = conversions[data_type]
            output_size_bytes = int(conversion.get("output_size_bytes") or 0)
            if item.get("mapped_output"):
                mapped_output = Path(str(item["mapped_output"]))
                if Path(item["local_output"]) != mapped_output:
                    mapped_output.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(item["local_output"], mapped_output)
                if not mapped_output.is_file():
                    raise ValueError(f"Compressed H5 was not created: {item['output_path']}")
                if item["source_suffix"] == ".his":
                    if progress_callback:
                        progress_callback(data_type, "delete", 0, 0, "Removing source HIS")
                    Path(item["local_source"]).unlink()
                continue

            if progress_callback:
                progress_callback(
                    data_type,
                    "upload",
                    0,
                    output_size_bytes,
                    "Writing compressed H5 to SMB",
                )
            api.copy_local_file_to_smb_atomic(
                item["local_output"],
                str(item["output_path"]),
                progress_callback=(
                    lambda current, dt=data_type, total=output_size_bytes: progress_callback(
                        dt,
                        "upload",
                        current,
                        total,
                        "Writing compressed H5 to SMB",
                    )
                    if progress_callback
                    else None
                ),
            )
            if not api.smb_isfile(str(item["output_path"])):
                raise ValueError(f"Compressed H5 was not created: {item['output_path']}")
            if item["source_suffix"] == ".his":
                if progress_callback:
                    progress_callback(data_type, "delete", 0, 0, "Removing source HIS")
                api.smb_remove(str(item["source_path"]))

    return conversions


def _convert_source_to_h5_legacy(source_path: str) -> Dict[str, object]:
    import treatment_api as api

    source_suffix = api._path_suffix(source_path)
    if source_suffix == ".h5":
        if api.is_smb_path(source_path):
            cached_source = api._cache_assignable_source(source_path)
            source_size_bytes = int(cached_source.get("size_bytes") or 0)
            reuse_summary = api._compressed_h5_reuse_summary(
                Path(str(cached_source["cached_path"])),
                source_path,
                source_size_bytes,
            )
            if reuse_summary:
                return reuse_summary
            with tempfile.TemporaryDirectory(prefix="pyconlyse_recompress_h5_") as tmp_dir:
                local_output = Path(tmp_dir) / api._path_name(source_path)
                summary = api.treatment_service.convert_file_to_h5(
                    Path(str(cached_source["cached_path"])),
                    local_output,
                )
                output_size_bytes = int(local_output.stat().st_size)
                api.copy_local_file_to_smb_atomic(local_output, source_path)
            if not api.smb_isfile(source_path):
                raise ValueError(f"Compressed H5 was not created: {source_path}")
        else:
            source = Path(source_path).expanduser()
            source_size_bytes = int(source.stat().st_size)
            reuse_summary = api._compressed_h5_reuse_summary(source, str(source), source_size_bytes)
            if reuse_summary:
                return reuse_summary
            summary = api.treatment_service.convert_file_to_h5(source, source)
            if not source.is_file():
                raise ValueError(f"Compressed H5 was not created: {source}")
            output_size_bytes = int(source.stat().st_size)

        space_change_bytes = output_size_bytes - source_size_bytes
        summary.update({
            "source_path": source_path,
            "output_path": source_path,
            "converted": True,
            "overwritten": True,
            "deleted_source": False,
            "source_size_bytes": source_size_bytes,
            "output_size_bytes": output_size_bytes,
            "space_change_bytes": space_change_bytes,
            "space_change_percent": (
                round((space_change_bytes / source_size_bytes) * 100, 2)
                if source_size_bytes
                else 0.0
            ),
        })
        return summary
    if source_suffix != ".his":
        raise ValueError("Set/Convert supports only HIS to H5 conversion or existing H5 files")

    output_name = f"{Path(api._path_name(source_path)).stem}.h5"
    if api.is_smb_path(source_path):
        output_path = api.smb_join(api.smb_parent(source_path), output_name)
        if api.smb_isfile(output_path):
            existing_cached = api._cache_assignable_source(output_path)
            existing_size_bytes = int(existing_cached.get("size_bytes") or 0)
            reuse_summary = api._compressed_h5_reuse_summary(
                Path(str(existing_cached["cached_path"])),
                output_path,
                existing_size_bytes,
            )
            if reuse_summary:
                api.smb_remove(source_path)
                reuse_summary.update({
                    "source_path": source_path,
                    "deleted_source": True,
                    "reused_existing_output": True,
                })
                return reuse_summary
        cached_source = api._cache_assignable_source(source_path)
        source_size_bytes = int(cached_source.get("size_bytes") or 0)
        with tempfile.TemporaryDirectory(prefix="pyconlyse_convert_h5_") as tmp_dir:
            local_output = Path(tmp_dir) / output_name
            summary = api.treatment_service.convert_file_to_h5(
                Path(str(cached_source["cached_path"])),
                local_output,
            )
            output_size_bytes = int(local_output.stat().st_size)
            api.copy_local_file_to_smb_atomic(local_output, output_path)
        if not api.smb_isfile(output_path):
            raise ValueError(f"Converted H5 was not created: {output_path}")
        api.smb_remove(source_path)
        space_change_bytes = output_size_bytes - source_size_bytes
        summary.update({
            "source_path": source_path,
            "output_path": output_path,
            "converted": True,
            "deleted_source": True,
            "source_size_bytes": source_size_bytes,
            "output_size_bytes": output_size_bytes,
            "space_change_bytes": space_change_bytes,
            "space_change_percent": (
                round((space_change_bytes / source_size_bytes) * 100, 2)
                if source_size_bytes
                else 0.0
            ),
        })
        return summary

    source = Path(source_path).expanduser()
    source_size_bytes = int(source.stat().st_size)
    output_path = source.with_suffix(".h5")
    if output_path.is_file():
        reuse_summary = api._compressed_h5_reuse_summary(
            output_path,
            str(output_path),
            int(output_path.stat().st_size),
        )
        if reuse_summary:
            source.unlink()
            reuse_summary.update({
                "source_path": str(source),
                "deleted_source": True,
                "reused_existing_output": True,
            })
            return reuse_summary
    summary = api.treatment_service.convert_file_to_h5(source, output_path)
    if not output_path.is_file():
        raise ValueError(f"Converted H5 was not created: {output_path}")
    output_size_bytes = int(output_path.stat().st_size)
    source.unlink()
    space_change_bytes = output_size_bytes - source_size_bytes
    summary.update({
        "source_path": str(source),
        "output_path": str(output_path),
        "converted": True,
        "deleted_source": True,
        "source_size_bytes": source_size_bytes,
        "output_size_bytes": output_size_bytes,
        "space_change_bytes": space_change_bytes,
        "space_change_percent": (
            round((space_change_bytes / source_size_bytes) * 100, 2)
            if source_size_bytes
            else 0.0
        ),
    })
    return summary


def _smb_size_bytes(path: str) -> int:
    import treatment_api as api

    parent = api.smb_parent(path)
    for entry in api.smb_listdir(parent):
        if str(entry.get("path")) == path:
            return int(entry.get("size_bytes") or 0)
    return 0


def _compression_job_snapshot(job_id: str) -> Dict[str, object]:
    import treatment_api as api

    with api._compression_jobs_lock:
        return dict(api._compression_jobs.get(job_id) or {})


def _folder_set_job_snapshot(job_id: str) -> Dict[str, object]:
    import treatment_api as api

    with api._folder_set_jobs_lock:
        return dict(api._folder_set_jobs.get(job_id) or {})


def _update_compression_job(job_id: str, **updates) -> None:
    import treatment_api as api

    with api._compression_jobs_lock:
        job = api._compression_jobs.setdefault(job_id, {})
        job.update(updates)
        job["updated_at"] = api.monotonic()


def _update_folder_set_job(job_id: str, **updates) -> None:
    import treatment_api as api

    with api._folder_set_jobs_lock:
        job = api._folder_set_jobs.setdefault(job_id, {})
        job.update(updates)
        job["updated_at"] = api.monotonic()


def _validate_canonical_h5(file_path: Path, display_path: Optional[str] = None) -> None:
    """Reject incomplete H5 output before a source HIS can be removed."""
    import treatment_api as api

    if api.h5py is None:
        raise ValueError("h5py is not available in this Python environment")
    path = Path(file_path).expanduser()
    label = display_path or str(path)
    if not path.is_file():
        raise ValueError(f"Compressed H5 was not created: {label}")
    try:
        with api.h5py.File(path, "r") as h5_file:
            required = ("raw_data", "wavelengths", "timedelays", "map_selection")
            missing = [name for name in required if name not in h5_file]
            if missing or "included" not in h5_file["map_selection"]:
                raise ValueError(
                    "H5 output is missing required datasets: "
                    f"{', '.join(missing + ([] if 'map_selection' in missing else ['map_selection/included']))}"
                )
            raw_data = h5_file["raw_data"]
            wavelengths = h5_file["wavelengths"]
            timedelays = h5_file["timedelays"]
            included = h5_file["map_selection"]["included"]
            if raw_data.ndim != 3 or raw_data.shape[0] < 1:
                raise ValueError("H5 raw_data must contain one or more 2D maps")
            if wavelengths.ndim != 1 or timedelays.ndim != 1:
                raise ValueError("H5 wavelength and delay axes must be one-dimensional")
            if raw_data.shape[1:] != (wavelengths.shape[0], timedelays.shape[0]):
                raise ValueError("H5 raw_data shape does not match wavelength and delay axes")
            if included.shape != (raw_data.shape[0],):
                raise ValueError("H5 map_selection/included does not match raw_data")
            if raw_data.compression != "gzip":
                raise ValueError("H5 raw_data must use gzip compression")
    except (OSError, TypeError, ValueError) as exc:
        raise ValueError(f"Compressed H5 verification failed for {label}: {exc}") from exc


def _compression_progress_summary(source_path: str, progress_callback=None) -> Dict[str, object]:
    import treatment_api as api

    source_suffix = api._path_suffix(source_path)
    if source_suffix not in {".his", ".h5"}:
        raise ValueError("Convert/Compress supports only HIS or H5 files")

    output_name = f"{Path(api._path_name(source_path)).stem}.h5"
    output_path = source_path if source_suffix == ".h5" else (
        api.smb_join(api.smb_parent(source_path), output_name)
        if api.is_smb_path(source_path)
        else str(Path(source_path).expanduser().with_suffix(".h5"))
    )

    mapped_source = api._mapped_smb_local_file(source_path) if api.is_smb_path(source_path) else None
    if mapped_source:
        source = Path(mapped_source)
        mapped_output = api.smb_to_local_path(output_path) if api.is_smb_path(output_path) else None
        if not mapped_output:
            raise ValueError("Mapped SMB output path is not configured")
        output = Path(mapped_output)
        source_size_bytes = int(source.stat().st_size)
        output_existed = source_suffix == ".h5" or output.is_file()
        if source_suffix == ".h5":
            reuse_summary = api._compressed_h5_reuse_summary(source, source_path, source_size_bytes)
            if reuse_summary:
                if progress_callback:
                    progress_callback("complete", source_size_bytes, source_size_bytes, "H5 is already gzip compressed")
                return reuse_summary

        if output_existed and source_suffix == ".his" and progress_callback:
            progress_callback("replace", 0, 0, "Existing H5 will be replaced from HIS")
        if progress_callback:
            progress_callback("convert", 0, source_size_bytes, "Compressing local mapped H5 with gzip level 4")

        if source_suffix == ".h5":
            with tempfile.TemporaryDirectory(prefix="pyconlyse_mapped_h5_") as tmp_dir:
                local_output = Path(tmp_dir) / output_name
                summary = api.treatment_service.convert_file_to_h5(
                    source,
                    local_output,
                    progress_callback=(
                        lambda current, total: progress_callback(
                            "convert",
                            current,
                            total,
                            f"Compressing map {current}/{total} with gzip level 4",
                        )
                        if progress_callback
                        else None
                    ),
                )
                if not local_output.is_file():
                    raise ValueError(f"Compressed H5 was not created: {output_path}")
                output.parent.mkdir(parents=True, exist_ok=True)
                os.replace(local_output, output)
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            summary = api.treatment_service.convert_file_to_h5(
                source,
                output,
                progress_callback=(
                    lambda current, total: progress_callback(
                        "convert",
                        current,
                        total,
                        f"Compressing map {current}/{total} with gzip level 4",
                    )
                    if progress_callback
                    else None
                ),
            )
            if not output.is_file():
                raise ValueError(f"Compressed H5 was not created: {output_path}")
            if source_suffix == ".his":
                api._validate_canonical_h5(output, output_path)
                if progress_callback:
                    progress_callback("delete", 0, 0, "Removing source HIS")
                source.unlink()

        output_size_bytes = int(output.stat().st_size)
    elif api.is_smb_path(source_path):
        source_size_bytes = api._smb_size_bytes(source_path)
        output_existed = source_suffix == ".h5" or (
            source_suffix == ".his" and api.smb_isfile(output_path)
        )
        with tempfile.TemporaryDirectory(prefix="pyconlyse_compress_job_") as tmp_dir:
            local_source = Path(tmp_dir) / api._path_name(source_path)
            local_output = Path(tmp_dir) / output_name
            if output_existed and source_suffix == ".his" and progress_callback:
                progress_callback("replace", 0, 0, "Existing H5 will be replaced from HIS")
            if progress_callback:
                progress_callback("download", 0, source_size_bytes, "Reading source file from SMB")
            api.copy_smb_file_to_local(
                source_path,
                local_source,
                progress_callback=(
                    lambda current: progress_callback(
                        "download",
                        current,
                        source_size_bytes,
                        "Reading source file from SMB",
                    )
                    if progress_callback
                    else None
                ),
            )
            if source_suffix == ".h5":
                reuse_summary = api._compressed_h5_reuse_summary(
                    local_source,
                    source_path,
                    source_size_bytes,
                )
                if reuse_summary:
                    if progress_callback:
                        progress_callback("complete", source_size_bytes, source_size_bytes, "H5 is already gzip compressed")
                    return reuse_summary

            if progress_callback:
                progress_callback("convert", 0, 0, "Compressing local H5 with gzip level 4")
            summary = api.treatment_service.convert_file_to_h5(
                local_source,
                local_output,
                progress_callback=(
                    lambda current, total: progress_callback(
                        "convert",
                        current,
                        total,
                        f"Compressing map {current}/{total} with gzip level 4",
                    )
                    if progress_callback
                    else None
                ),
            )
            output_size_bytes = int(local_output.stat().st_size)
            if source_suffix == ".his":
                api._validate_canonical_h5(local_output, output_path)

            if progress_callback:
                progress_callback("upload", 0, output_size_bytes, "Writing compressed H5 to SMB")
            api.copy_local_file_to_smb_atomic(
                local_output,
                output_path,
                progress_callback=(
                    lambda current: progress_callback(
                        "upload",
                        current,
                        output_size_bytes,
                        "Writing compressed H5 to SMB",
                    )
                    if progress_callback
                    else None
                ),
            )

        if not api.smb_isfile(output_path):
            raise ValueError(f"Compressed H5 was not created: {output_path}")
        if source_suffix == ".his":
            if progress_callback:
                progress_callback("delete", 0, 0, "Removing source HIS")
            api.smb_remove(source_path)
    else:
        source = Path(source_path).expanduser()
        source_size_bytes = int(source.stat().st_size)
        output = Path(output_path).expanduser()
        output_existed = source_suffix == ".h5" or output.is_file()
        if source_suffix == ".h5":
            reuse_summary = api._compressed_h5_reuse_summary(source, str(source), source_size_bytes)
            if reuse_summary:
                if progress_callback:
                    progress_callback("complete", source_size_bytes, source_size_bytes, "H5 is already gzip compressed")
                return reuse_summary
        if output_existed and source_suffix == ".his" and progress_callback:
            progress_callback("replace", 0, 0, "Existing H5 will be replaced from HIS")
        if progress_callback:
            progress_callback("convert", 0, source_size_bytes, "Compressing local H5 with gzip level 4")
        conversion_progress = (
            lambda current, total: progress_callback(
                "convert",
                current,
                total,
                f"Compressing map {current}/{total} with gzip level 4",
            )
            if progress_callback
            else None
        )
        if source_suffix == ".h5":
            with tempfile.TemporaryDirectory(prefix="pyconlyse_recompress_h5_", dir=output.parent) as tmp_dir:
                staged_output = Path(tmp_dir) / output.name
                summary = api.treatment_service.convert_file_to_h5(
                    source, staged_output, progress_callback=conversion_progress,
                )
                api._validate_canonical_h5(staged_output, output_path)
                os.replace(staged_output, output)
        else:
            summary = api.treatment_service.convert_file_to_h5(
                source, output, progress_callback=conversion_progress,
            )
        if not output.is_file():
            raise ValueError(f"Compressed H5 was not created: {output}")
        output_size_bytes = int(output.stat().st_size)
        if source_suffix == ".his":
            api._validate_canonical_h5(output, output_path)
            if progress_callback:
                progress_callback("delete", 0, 0, "Removing source HIS")
            source.unlink()

    space_change_bytes = output_size_bytes - source_size_bytes
    summary.update({
        "source_path": source_path,
        "output_path": output_path,
        "converted": True,
        "overwritten": output_existed,
        "deleted_source": source_suffix == ".his",
        "source_size_bytes": source_size_bytes,
        "output_size_bytes": output_size_bytes,
        "space_change_bytes": space_change_bytes,
        "space_change_percent": (
            round((space_change_bytes / source_size_bytes) * 100, 2)
            if source_size_bytes
            else 0.0
        ),
    })
    return summary


def _run_compression_job(job_id: str, session_id: str, source_path: str) -> None:
    import treatment_api as api

    def progress(phase: str, current: int, total: int, message: str) -> None:
        api._update_compression_job(
            job_id,
            phase=phase,
            current_bytes=int(current or 0),
            total_bytes=int(total or 0),
            message=message,
        )

    try:
        progress("start", 0, 0, "Starting Convert/Compress")
        conversion = api._compression_progress_summary(source_path, progress_callback=progress)
        api._update_compression_job(
            job_id,
            status="complete",
            phase="complete",
            current_bytes=int(conversion.get("output_size_bytes") or 0),
            total_bytes=int(conversion.get("output_size_bytes") or 0),
            message="Convert/Compress complete",
            conversion=conversion,
            payload={**api._session_payload(session_id), "conversion": conversion},
        )
    except ValueError as exc:
        api._update_compression_job(
            job_id,
            status="error",
            phase="error",
            message=str(exc),
            error=str(exc),
        )
