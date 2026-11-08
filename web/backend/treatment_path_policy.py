"""Treatment input paths, output selection, and allowed-root policy."""

from datetime import datetime
from pathlib import Path
from typing import Dict
from typing import List
from typing import Optional
import os
import re


def _is_within_local_path(path: str, root: str) -> bool:
    """Compare local paths with Windows drive-letter case folding when needed."""
    raw_path = str(path).strip()
    raw_root = str(root).strip()
    if re.match(r"^[A-Za-z]:[\\/]", raw_path) or re.match(r"^[A-Za-z]:[\\/]", raw_root):
        import ntpath

        normalized_path = ntpath.normcase(ntpath.normpath(raw_path))
        normalized_root = ntpath.normcase(ntpath.normpath(raw_root))
        try:
            return ntpath.commonpath([normalized_path, normalized_root]) == normalized_root
        except ValueError:
            return False

    normalized_path = os.path.normcase(os.path.normpath(raw_path))
    normalized_root = os.path.normcase(os.path.normpath(raw_root))
    try:
        return os.path.commonpath([normalized_path, normalized_root]) == normalized_root
    except ValueError:
        return False


def _infer_time_scale_from_path(path: str) -> str:
    import treatment_api as api

    match = api.TIME_SCALE_PATH_RE.search(str(path or "").replace("\\", "/"))
    if not match:
        return ""
    return match.group(1).replace("µ", "u").lower()


def _is_within_allowed_root(path: str) -> bool:
    import treatment_api as api

    allowed_root = api._normalize_path(api.get_allowed_root())
    candidate = api._normalize_path(path)
    if api.is_smb_path(candidate) or api.is_smb_path(allowed_root):
        if not api.is_smb_path(candidate) or not api.is_smb_path(allowed_root):
            return False
        try:
            return api.smb_is_within(candidate, allowed_root)
        except ValueError:
            return False

    return api._is_within_local_path(candidate, allowed_root)


def _ensure_within_allowed_root(path: str) -> str:
    import treatment_api as api

    normalized = api._normalize_path(path)
    if not api._is_within_allowed_root(normalized):
        raise ValueError("Path is outside the allowed treatment root")
    return normalized


def _ensure_readable_treatment_file(path: str) -> str:
    import treatment_api as api

    normalized = api._normalize_path(path)
    if api.is_smb_path(normalized):
        raise ValueError("Network files must be cached before treatment can read them")
    if not (api._is_within_allowed_root(normalized) or api.is_within_cache(normalized)):
        raise ValueError("Path is outside the allowed treatment root and treatment cache")
    if not os.path.isfile(normalized):
        raise ValueError("Selected file does not exist")
    return normalized


def _ensure_writable_output_folder(path: str) -> str:
    import treatment_api as api

    normalized = api._normalize_path(path)
    if not api._is_within_stitch_od_root(normalized):
        raise ValueError("Output folder is outside the allowed treatment or stitch OD root")
    if not api._folder_exists(normalized):
        raise ValueError("Output folder does not exist")
    return normalized


def _mapped_smb_local_file(path: str) -> Optional[str]:
    import treatment_api as api

    if not api.is_smb_path(path) or not api.is_mapped_smb_path(path):
        return None
    mapped = api.smb_to_local_path(path)
    if mapped and os.path.isfile(mapped):
        return os.path.abspath(mapped)
    return None


def _mapped_smb_local_dir(path: str) -> Optional[str]:
    import treatment_api as api

    if not api.is_smb_path(path) or not api.is_mapped_smb_path(path):
        return None
    mapped = api.smb_to_local_path(path)
    if mapped and os.path.isdir(mapped):
        return os.path.abspath(mapped)
    return None


def _default_folder() -> str:
    import treatment_api as api

    folder = api._normalize_path(api.get_allowed_root())
    if api.is_smb_path(folder):
        return folder
    if os.path.isdir(folder):
        return folder
    return ""


def _folder_exists(folder: str) -> bool:
    import treatment_api as api

    if api.is_smb_path(folder):
        if api._mapped_smb_local_dir(folder):
            return True
        return api.smb_isdir(folder)
    return os.path.isdir(folder)


def _root_exists(root: str) -> bool:
    import treatment_api as api

    now = api.monotonic()
    with api._root_exists_cache_lock:
        cached = api._root_exists_cache.get(root)
        if cached and now - cached[1] <= api.ROOT_EXISTS_CACHE_TTL_SECONDS:
            return bool(cached[0])

    if api.is_smb_path(root):
        exists = True
    else:
        exists = os.path.isdir(root)

    with api._root_exists_cache_lock:
        api._root_exists_cache[root] = (bool(exists), now)
    return bool(exists)


def _clear_root_exists_cache(root: Optional[str] = None) -> None:
    import treatment_api as api

    with api._root_exists_cache_lock:
        if root is None:
            api._root_exists_cache.clear()
        else:
            api._root_exists_cache.pop(root, None)


def _default_state() -> Dict[str, object]:
    import treatment_api as api

    folder = api._default_folder()
    default_exp_type = api.EXP_TYPES[1]
    default_required = api.REQUIRED_DATA_TYPES[default_exp_type]
    return {
        "exp_type": default_exp_type,
        "selected_data_type": default_required[0],
        "active_data_type": "",
        "dat_preview_path": "",
        "map_index": 0,
        "selection": {},
        "calc_mode": api.CALC_MODES[0],
        "first_map_with_electrons": True,
        "folder_path": folder,
        "save_folder": folder,
        "save_file_name": "",
        "paths": {},
        "path_sources": {},
        "status_label": "Treatment session is ready.",
        "noise_ready": False,
        "result_ready": False,
        "result_map_policy": "selected_maps",
        "result_shape": None,
        "result_source_path": "",
        "cleaning_preview_request": None,
    }


def _file_data_type_candidate(file_name: str, exp_type: str) -> Optional[str]:
    stem = Path(file_name).stem.upper()
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


def _candidate_rank(file_path: Path) -> tuple:
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
    import treatment_api as api

    folder_name = api._path_name(folder)
    save_file_name = f"{folder_name}.dat" if folder_name else "result.dat"
    if api.is_smb_path(folder):
        parent = api.smb_parent(folder)
        return parent or folder, save_file_name
    parent = str(Path(folder).expanduser().resolve().parent)
    return parent, save_file_name


def _dated_save_file_name_for_folder(folder: str, on_date=None) -> str:
    import treatment_api as api

    processing_date = on_date or datetime.now().astimezone().date()
    folder_name = api._path_name(folder)
    return f"{folder_name}_{processing_date:%Y%m%d}.dat"


def _folder_contains(parent: str, child: str) -> bool:
    import treatment_api as api

    if api.is_smb_path(parent) or api.is_smb_path(child):
        if not (api.is_smb_path(parent) and api.is_smb_path(child)):
            return False
        try:
            return api.smb_is_within(child, parent)
        except ValueError:
            return False
    return api._is_within_local_path(child, parent)


def _save_folder_for_measurement(session: Dict[str, object], measurement_folder: str) -> str:
    """Keep the selected parent (or a manual override), not the measurement folder."""
    import treatment_api as api

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
        else str(Path(measurement_folder).parent)
    )
    if parent and api._is_within_allowed_root(parent) and api._folder_exists(parent):
        return api._ensure_within_allowed_root(parent)
    return measurement_folder


def _path_name(path: str) -> str:
    import treatment_api as api

    if api.is_smb_path(path):
        return api.smb_name(path)
    return Path(path).name


def _path_suffix(path: str) -> str:
    import treatment_api as api

    if api.is_smb_path(path):
        return api.smb_suffix(path)
    return Path(path).suffix.lower()


def _candidate_sort_key(path: str) -> tuple:
    import treatment_api as api

    suffix = api._path_suffix(path)
    suffix_rank = {
        ".his": 0,
        ".img": 2,
        ".dat": 3,
        ".h5": 4,
        ".raw": 4,
    }.get(suffix, 99)
    return (suffix_rank, api._path_name(path).lower())


def _folder_input_candidates(folder: str, exp_type: str, convert: bool = False) -> Dict[str, List[str]]:
    import treatment_api as api

    required_data_types = api.REQUIRED_DATA_TYPES.get(exp_type, [])
    candidates: Dict[str, List[str]] = {data_type: [] for data_type in required_data_types}
    accepted_suffixes = {".his", ".h5"} if convert else set(api.treatment_service.supported_suffixes)

    mapped_folder = api._mapped_smb_local_dir(folder) if api.is_smb_path(folder) else None
    if mapped_folder:
        with os.scandir(mapped_folder) as entries:
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
        with os.scandir(folder) as entries:
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
    import treatment_api as api

    suffix = api._path_suffix(path)
    suffix_rank = {".his": 0, ".h5": 1}.get(suffix, 99)
    return (suffix_rank, api._path_name(path).lower())


def _folder_required_input_types(exp_type: str) -> List[str]:
    import treatment_api as api

    return [
        data_type
        for data_type in api.REQUIRED_DATA_TYPES.get(exp_type, [])
        if data_type != "NOISE"
    ]
