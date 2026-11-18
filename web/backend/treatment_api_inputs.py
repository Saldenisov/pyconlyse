"""Treatment input discovery and measurement naming."""


def bind(api):
    """Use the owning API module for shared state and dependencies."""
    def _file_data_type_candidate(file_name: str, exp_type: str) -> api.Optional[str]:
        stem = api.Path(file_name).stem.upper()
        if stem.startswith("NOISE") or stem.startswith("BRUIT"):
            return "NOISE"
        if exp_type == "ABS+BASE+NOISE":
            if stem.startswith("BASE"):
                return "BASE"
            if stem.startswith("ABS"):
                return "ABS"
        elif exp_type == "HIS+NOISE":
            if stem.startswith("ABS"):
                return "ABS+BASE"
        elif exp_type == "HIS":
            if stem.startswith("ABS"):
                return "ABS+BASE+NOISE"
        return None


    def _candidate_rank(file_path: api.Path) -> tuple:
        suffix = file_path.suffix.lower()
        suffix_rank = {
            ".his": 0,
            ".img": 2,
            ".dat": 3,
            ".h5": 4,
            ".raw": 4,
        }.get(suffix, 99)
        return (suffix_rank, file_path.name.lower())


    def _default_save_target_for_folder(folder: str):
        folder_name = api._path_name(folder)
        save_file_name = f"{folder_name}.dat" if folder_name else "result.dat"
        if api.is_smb_path(folder):
            parent = api.smb_parent(folder)
            return parent or folder, save_file_name
        parent = str(api.Path(folder).expanduser().resolve().parent)
        return parent, save_file_name


    def _dated_save_file_name_for_folder(folder: str, on_date=None) -> str:
        processing_date = on_date or api.datetime.now().astimezone().date()
        folder_name = api._path_name(folder)
        return f"{folder_name}_{processing_date:%Y%m%d}.dat"


    def _folder_contains(parent: str, child: str) -> bool:
        if api.is_smb_path(parent) or api.is_smb_path(child):
            if not (api.is_smb_path(parent) and api.is_smb_path(child)):
                return False
            try:
                return api.smb_is_within(child, parent)
            except ValueError:
                return False
        return api._is_within_local_path(child, parent)


    def _save_folder_for_measurement(session: api.Dict[str, object], measurement_folder: str) -> str:
        """Keep the selected parent (or a manual override), not the measurement folder."""
        configured = str(session.get("save_folder") or "").strip()
        selected = str(session.get("folder_path") or "").strip()
        if configured:
            configured = api._ensure_within_allowed_root(configured)
            if not api._folder_exists(configured):
                raise ValueError("save_folder does not exist")
            manual_override = not selected or api._normalize_path(configured) != api._normalize_path(selected)
            if manual_override or (
                api._normalize_path(configured) != api._normalize_path(measurement_folder)
                and api._folder_contains(configured, measurement_folder)
            ):
                return configured

        parent = (
            api.smb_parent(measurement_folder)
            if api.is_smb_path(measurement_folder)
            else str(api.Path(measurement_folder).parent)
        )
        if parent and api._is_within_allowed_root(parent) and api._folder_exists(parent):
            return api._ensure_within_allowed_root(parent)
        return measurement_folder


    def _candidate_sort_key(path: str) -> tuple:
        suffix = api._path_suffix(path)
        suffix_rank = {
            ".his": 0,
            ".img": 2,
            ".dat": 3,
            ".h5": 4,
            ".raw": 4,
        }.get(suffix, 99)
        return (suffix_rank, api._path_name(path).lower())


    def _folder_input_candidates(folder: str, exp_type: str, convert: bool = False) -> api.Dict[str, api.List[str]]:
        required_data_types = api.REQUIRED_DATA_TYPES.get(exp_type, [])
        candidates: api.Dict[str, api.List[str]] = {data_type: [] for data_type in required_data_types}
        accepted_suffixes = {".his", ".h5"} if convert else set(api.treatment_service.supported_suffixes)

        mapped_folder = api._mapped_smb_local_dir(folder) if api.is_smb_path(folder) else None
        if mapped_folder:
            with api.os.scandir(mapped_folder) as entries:
                for entry in entries:
                    if not entry.is_file():
                        continue
                    file_path = api.smb_join(folder, entry.name)
                    if api._path_suffix(file_path) not in accepted_suffixes:
                        continue
                    data_type = api._file_data_type_candidate(entry.name, exp_type)
                    if data_type in candidates:
                        candidates[data_type].append(file_path)
        elif api.is_smb_path(folder):
            entries = api.smb_listdir(folder)
            for entry in entries:
                if not entry["is_file"]:
                    continue
                file_path = str(entry["path"])
                if api._path_suffix(file_path) not in accepted_suffixes:
                    continue
                data_type = api._file_data_type_candidate(str(entry["name"]), exp_type)
                if data_type in candidates:
                    candidates[data_type].append(file_path)
        else:
            with api.os.scandir(folder) as entries:
                for entry in entries:
                    if not entry.is_file():
                        continue
                    file_path = entry.path
                    if api._path_suffix(file_path) not in accepted_suffixes:
                        continue
                    data_type = api._file_data_type_candidate(entry.name, exp_type)
                    if data_type in candidates:
                        candidates[data_type].append(file_path)

        return candidates


    def _convert_sort_key(path: str) -> tuple:
        suffix = api._path_suffix(path)
        suffix_rank = {".his": 0, ".h5": 1}.get(suffix, 99)
        return (suffix_rank, api._path_name(path).lower())


    def _folder_required_input_types(exp_type: str) -> api.List[str]:
        return [
            data_type
            for data_type in api.REQUIRED_DATA_TYPES.get(exp_type, [])
            if data_type != "NOISE"
        ]


    def _delete_source_his_after_cleaning(saved: api.Dict[str, object]) -> api.Optional[str]:
        source_path = str(saved.get("source_file_path") or saved.get("file_path") or "")
        output_path = str(saved.get("output_path") or "")
        if not source_path or not output_path or api._path_suffix(source_path) != ".his":
            return None
        if api.is_within_cache(source_path):
            return None

        if api.is_smb_path(source_path):
            if not api.is_smb_path(output_path) or not api.smb_isfile(output_path):
                raise ValueError("Cleaned H5 was not created; HIS was not deleted")
            cached_output = api._cache_assignable_source(output_path)
            api._validate_canonical_h5(api.Path(str(cached_output["cached_path"])), output_path)
            api.smb_remove(source_path)
            return source_path

        normalized_source = api._ensure_within_allowed_root(source_path)
        source = api.Path(normalized_source).expanduser()
        output = api.Path(output_path).expanduser()
        api._validate_canonical_h5(output, output_path)
        source.unlink()
        return str(source)


    def _cache_assignable_source(source_path: str) -> api.Dict[str, object]:
        if api.is_smb_path(source_path):
            mapped_file = api._mapped_smb_local_file(source_path)
            if mapped_file:
                stat = api.os.stat(mapped_file)
                return {
                    "source_path": api._normalize_path(source_path),
                    "cached_path": mapped_file,
                    "copied": False,
                    "size_bytes": int(stat.st_size),
                    "cache": {
                        "cache_root": api.get_cache_root(),
                        "limit_bytes": api.get_cache_limit_bytes(),
                        "removed": [],
                        "size_bytes": 0,
                        "local_map": True,
                    },
                }
            if not api.smb_isfile(source_path):
                raise ValueError("Selected file does not exist")
            return api.cache_external_file(
                source_path,
                api.smb_name(source_path),
                lambda target_path: api.copy_smb_file_to_local(source_path, target_path),
            )

        if not api.os.path.isfile(source_path):
            raise ValueError("Selected file does not exist")
        return api.cache_file(source_path)


    def _active_assignable_data_type(session: api.Dict[str, object]) -> str:
        paths = session.get("paths") or {}
        active_data_type = str(session.get("active_data_type") or "").strip()
        if active_data_type in api.DATA_TYPES and paths.get(active_data_type):
            return active_data_type
        for data_type in api.DATA_TYPES:
            if paths.get(data_type):
                return data_type
        return ""


    def _map_selection_status(file_path: str) -> api.Dict[str, object]:
        """Return persisted H5 selection state; never describe runtime preview as applied."""
        status: api.Dict[str, object] = {
            "applied": False,
            "included_count": None,
            "total_count": None,
            "method": None,
        }
        if api.h5py is None or api._path_suffix(file_path) != ".h5" or not api.os.path.isfile(file_path):
            return status
        try:
            with api.h5py.File(file_path, "r") as h5_file:
                raw_data = h5_file.get("raw_data")
                if raw_data is None or len(raw_data.shape) < 1:
                    return status
                total_count = int(raw_data.shape[0])
                status["total_count"] = total_count
                selection_group = h5_file.get("map_selection")
                if selection_group is None or "included" not in selection_group:
                    status["included_count"] = total_count
                    return status
                included = selection_group["included"][:]
                if included.shape != (total_count,):
                    return status
                status["applied"] = True
                status["included_count"] = int(included.astype(bool).sum())
                method = selection_group.attrs.get("method")
                if isinstance(method, bytes):
                    method = method.decode("utf-8", errors="replace")
                status["method"] = str(method) if method is not None else None
                for attribute in ("sam_angle_threshold", "sam_surface_threshold"):
                    if attribute in selection_group.attrs:
                        status[attribute.removeprefix("sam_")] = float(selection_group.attrs[attribute])
        except (OSError, TypeError, ValueError):
            return status
        return status

    api._file_data_type_candidate = _file_data_type_candidate
    api._candidate_rank = _candidate_rank
    api._default_save_target_for_folder = _default_save_target_for_folder
    api._dated_save_file_name_for_folder = _dated_save_file_name_for_folder
    api._folder_contains = _folder_contains
    api._save_folder_for_measurement = _save_folder_for_measurement
    api._candidate_sort_key = _candidate_sort_key
    api._folder_input_candidates = _folder_input_candidates
    api._convert_sort_key = _convert_sort_key
    api._folder_required_input_types = _folder_required_input_types
    api._delete_source_his_after_cleaning = _delete_source_his_after_cleaning
    api._cache_assignable_source = _cache_assignable_source
    api._active_assignable_data_type = _active_assignable_data_type
    api._map_selection_status = _map_selection_status
