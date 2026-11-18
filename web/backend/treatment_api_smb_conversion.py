"""Staged SMB transfers and parallel HDF5 conversion."""


def bind(api):
    """Use the owning API module for shared state and dependencies."""
    def _convert_smb_sources_to_h5_pipeline(
        selected_paths: api.Dict[str, str],
        progress_callback=None,
    ) -> api.Dict[str, api.Dict[str, object]]:
        conversions: api.Dict[str, api.Dict[str, object]] = {}
        prepared: api.Dict[str, api.Dict[str, object]] = {}

        with api.tempfile.TemporaryDirectory(prefix="pyconlyse_folder_smb_convert_") as tmp_dir:
            tmp_path = api.Path(tmp_dir)

            for data_type, source_path in selected_paths.items():
                source_suffix = api._path_suffix(source_path)
                if source_suffix not in {".his", ".h5"}:
                    raise ValueError("Convert/Compress supports only HIS or H5 files")

                output_name = f"{api.Path(api._path_name(source_path)).stem}.h5"
                output_path = (
                    source_path
                    if source_suffix == ".h5"
                    else api.smb_join(api.smb_parent(source_path), output_name)
                )
                mapped_source = api._mapped_smb_local_file(source_path)
                mapped_output = api.smb_to_local_path(output_path) if mapped_source else None
                if mapped_source:
                    local_source = api.Path(mapped_source)
                    source_size_bytes = int(local_source.stat().st_size)
                    output_existed = source_suffix == ".h5" or (
                        bool(mapped_output) and api.Path(str(mapped_output)).is_file()
                    )
                    local_output = (
                        tmp_path / f"{data_type}_compressed_{output_name}"
                        if source_suffix == ".h5"
                        else api.Path(str(mapped_output))
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
                    mapped_output = api.Path(str(item["mapped_output"]))
                    if api.Path(item["local_output"]) != mapped_output:
                        mapped_output.parent.mkdir(parents=True, exist_ok=True)
                        api.os.replace(item["local_output"], mapped_output)
                    if not mapped_output.is_file():
                        raise ValueError(f"Compressed H5 was not created: {item['output_path']}")
                    if item["source_suffix"] == ".his":
                        if progress_callback:
                            progress_callback(data_type, "delete", 0, 0, "Removing source HIS")
                        api.Path(item["local_source"]).unlink()
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

    api._convert_smb_sources_to_h5_pipeline = _convert_smb_sources_to_h5_pipeline
