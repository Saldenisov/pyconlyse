"""Treatment HDF5 conversion and canonical validation."""


def bind(api):
    """Use the owning API module for shared state and dependencies."""
    def _compressed_h5_reuse_summary(local_path: api.Path, display_path: str, source_size_bytes: int) -> api.Optional[api.Dict[str, object]]:
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


    def _convert_source_to_h5(source_path: str, progress_callback=None) -> api.Dict[str, object]:
        return api._compression_progress_summary(source_path, progress_callback=progress_callback)


    def _convert_source_to_h5_legacy(source_path: str) -> api.Dict[str, object]:
        source_suffix = api._path_suffix(source_path)
        if source_suffix == ".h5":
            if api.is_smb_path(source_path):
                cached_source = api._cache_assignable_source(source_path)
                source_size_bytes = int(cached_source.get("size_bytes") or 0)
                reuse_summary = api._compressed_h5_reuse_summary(
                    api.Path(str(cached_source["cached_path"])),
                    source_path,
                    source_size_bytes,
                )
                if reuse_summary:
                    return reuse_summary
                with api.tempfile.TemporaryDirectory(prefix="pyconlyse_recompress_h5_") as tmp_dir:
                    local_output = api.Path(tmp_dir) / api._path_name(source_path)
                    summary = api.treatment_service.convert_file_to_h5(
                        api.Path(str(cached_source["cached_path"])),
                        local_output,
                    )
                    output_size_bytes = int(local_output.stat().st_size)
                    api.copy_local_file_to_smb_atomic(local_output, source_path)
                if not api.smb_isfile(source_path):
                    raise ValueError(f"Compressed H5 was not created: {source_path}")
            else:
                source = api.Path(source_path).expanduser()
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

        output_name = f"{api.Path(api._path_name(source_path)).stem}.h5"
        if api.is_smb_path(source_path):
            output_path = api.smb_join(api.smb_parent(source_path), output_name)
            if api.smb_isfile(output_path):
                existing_cached = api._cache_assignable_source(output_path)
                existing_size_bytes = int(existing_cached.get("size_bytes") or 0)
                reuse_summary = api._compressed_h5_reuse_summary(
                    api.Path(str(existing_cached["cached_path"])),
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
            with api.tempfile.TemporaryDirectory(prefix="pyconlyse_convert_h5_") as tmp_dir:
                local_output = api.Path(tmp_dir) / output_name
                summary = api.treatment_service.convert_file_to_h5(
                    api.Path(str(cached_source["cached_path"])),
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

        source = api.Path(source_path).expanduser()
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
        parent = api.smb_parent(path)
        for entry in api.smb_listdir(parent):
            if str(entry.get("path")) == path:
                return int(entry.get("size_bytes") or 0)
        return 0


    def _validate_canonical_h5(file_path: api.Path, display_path: api.Optional[str] = None) -> None:
        """Reject incomplete H5 output before a source HIS can be removed."""
        if api.h5py is None:
            raise ValueError("h5py is not available in this Python environment")
        path = api.Path(file_path).expanduser()
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


    def _compression_progress_summary(source_path: str, progress_callback=None) -> api.Dict[str, object]:
        source_suffix = api._path_suffix(source_path)
        if source_suffix not in {".his", ".h5"}:
            raise ValueError("Convert/Compress supports only HIS or H5 files")

        output_name = f"{api.Path(api._path_name(source_path)).stem}.h5"
        output_path = source_path if source_suffix == ".h5" else (
            api.smb_join(api.smb_parent(source_path), output_name)
            if api.is_smb_path(source_path)
            else str(api.Path(source_path).expanduser().with_suffix(".h5"))
        )

        mapped_source = api._mapped_smb_local_file(source_path) if api.is_smb_path(source_path) else None
        if mapped_source:
            source = api.Path(mapped_source)
            mapped_output = api.smb_to_local_path(output_path) if api.is_smb_path(output_path) else None
            if not mapped_output:
                raise ValueError("Mapped SMB output path is not configured")
            output = api.Path(mapped_output)
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
                with api.tempfile.TemporaryDirectory(prefix="pyconlyse_mapped_h5_") as tmp_dir:
                    local_output = api.Path(tmp_dir) / output_name
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
                    api.os.replace(local_output, output)
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
            with api.tempfile.TemporaryDirectory(prefix="pyconlyse_compress_job_") as tmp_dir:
                local_source = api.Path(tmp_dir) / api._path_name(source_path)
                local_output = api.Path(tmp_dir) / output_name
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
            source = api.Path(source_path).expanduser()
            source_size_bytes = int(source.stat().st_size)
            output = api.Path(output_path).expanduser()
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
                with api.tempfile.TemporaryDirectory(prefix="pyconlyse_recompress_h5_", dir=output.parent) as tmp_dir:
                    staged_output = api.Path(tmp_dir) / output.name
                    summary = api.treatment_service.convert_file_to_h5(
                        source, staged_output, progress_callback=conversion_progress,
                    )
                    api._validate_canonical_h5(staged_output, output_path)
                    api.os.replace(staged_output, output)
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

    api._compressed_h5_reuse_summary = _compressed_h5_reuse_summary
    api._convert_source_to_h5 = _convert_source_to_h5
    api._convert_source_to_h5_legacy = _convert_source_to_h5_legacy
    api._smb_size_bytes = _smb_size_bytes
    api._validate_canonical_h5 = _validate_canonical_h5
    api._compression_progress_summary = _compression_progress_summary
