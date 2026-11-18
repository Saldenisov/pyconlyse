"""Treatment root policy and local and SMB path resolution."""


def bind(api):
    """Use the owning API module for shared state and dependencies."""
    def _is_within_local_path(path: str, root: str) -> bool:
        """Compare local paths with Windows drive-letter case folding when needed."""
        raw_path = str(path).strip()
        raw_root = str(root).strip()
        if api.re.match(r"^[A-Za-z]:[\\/]", raw_path) or api.re.match(r"^[A-Za-z]:[\\/]", raw_root):
            import ntpath

            normalized_path = ntpath.normcase(ntpath.normpath(raw_path))
            normalized_root = ntpath.normcase(ntpath.normpath(raw_root))
            try:
                return ntpath.commonpath([normalized_path, normalized_root]) == normalized_root
            except ValueError:
                return False

        normalized_path = api.os.path.normcase(api.os.path.normpath(raw_path))
        normalized_root = api.os.path.normcase(api.os.path.normpath(raw_root))
        try:
            return api.os.path.commonpath([normalized_path, normalized_root]) == normalized_root
        except ValueError:
            return False


    def _infer_time_scale_from_path(path: str) -> str:
        match = api.TIME_SCALE_PATH_RE.search(str(path or "").replace("\\", "/"))
        if not match:
            return ""
        return match.group(1).replace("µ", "u").lower()


    def _is_within_allowed_root(path: str) -> bool:
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


    def _stitch_od_roots() -> api.List[str]:
        raw_roots = api.os.environ.get("PYCONLYSE_STITCH_OD_ROOTS")
        roots = raw_roots.split(api.os.pathsep) if raw_roots else list(api.DEFAULT_STITCH_OD_ROOTS)
        return [api._normalize_path(root) for root in roots if str(root).strip()]


    def _is_within_stitch_od_root(path: str) -> bool:
        if api._is_within_allowed_root(path):
            return True
        candidate = api._normalize_path(path)
        for root in api._stitch_od_roots():
            if api.is_smb_path(candidate) or api.is_smb_path(root):
                if api.is_smb_path(candidate) and api.is_smb_path(root):
                    try:
                        if api.smb_is_within(candidate, root):
                            return True
                    except ValueError:
                        continue
            elif api._is_within_local_path(candidate, root):
                return True
        return False


    def _ensure_within_allowed_root(path: str) -> str:
        normalized = api._normalize_path(path)
        if not api._is_within_allowed_root(normalized):
            raise ValueError("Path is outside the allowed treatment root")
        return normalized


    def _ensure_readable_treatment_file(path: str) -> str:
        normalized = api._normalize_path(path)
        if api.is_smb_path(normalized):
            raise ValueError("Network files must be cached before treatment can read them")
        if not (api._is_within_allowed_root(normalized) or api.is_within_cache(normalized)):
            raise ValueError("Path is outside the allowed treatment root and treatment cache")
        if not api.os.path.isfile(normalized):
            raise ValueError("Selected file does not exist")
        return normalized


    def _ensure_readable_od_dat(path: str) -> str:
        normalized = api._normalize_path(path)
        if not api._is_within_stitch_od_root(normalized):
            raise ValueError("Path is outside the allowed treatment or stitch OD root")
        if api._path_suffix(normalized) != ".dat":
            raise ValueError("OD stitch input must be a .dat file")
        if api.is_smb_path(normalized):
            if api._mapped_smb_local_file(normalized):
                return normalized
            if not api.smb_isfile(normalized):
                raise ValueError("Selected OD DAT file does not exist")
            return normalized
        if not api.os.path.isfile(normalized):
            raise ValueError("Selected OD DAT file does not exist")
        return normalized


    def _ensure_writable_output_folder(path: str) -> str:
        normalized = api._normalize_path(path)
        if not api._is_within_stitch_od_root(normalized):
            raise ValueError("Output folder is outside the allowed treatment or stitch OD root")
        if not api._folder_exists(normalized):
            raise ValueError("Output folder does not exist")
        return normalized


    def _mapped_smb_local_file(path: str) -> api.Optional[str]:
        if not api.is_smb_path(path) or not api.is_mapped_smb_path(path):
            return None
        mapped = api.smb_to_local_path(path)
        if mapped and api.os.path.isfile(mapped):
            return api.os.path.abspath(mapped)
        return None


    def _mapped_smb_local_dir(path: str) -> api.Optional[str]:
        if not api.is_smb_path(path) or not api.is_mapped_smb_path(path):
            return None
        mapped = api.smb_to_local_path(path)
        if mapped and api.os.path.isdir(mapped):
            return api.os.path.abspath(mapped)
        return None


    def _default_folder() -> str:
        folder = api._normalize_path(api.get_allowed_root())
        if api.is_smb_path(folder):
            return folder
        if api.os.path.isdir(folder):
            return folder
        return ""


    def _folder_exists(folder: str) -> bool:
        if api.is_smb_path(folder):
            if api._mapped_smb_local_dir(folder):
                return True
            return api.smb_isdir(folder)
        return api.os.path.isdir(folder)


    def _root_exists(root: str) -> bool:
        now = api.monotonic()
        with api._root_exists_cache_lock:
            cached = api._root_exists_cache.get(root)
            if cached and now - cached[1] <= api.ROOT_EXISTS_CACHE_TTL_SECONDS:
                return bool(cached[0])

        if api.is_smb_path(root):
            exists = True
        else:
            exists = api.os.path.isdir(root)

        with api._root_exists_cache_lock:
            api._root_exists_cache[root] = (bool(exists), now)
        return bool(exists)


    def _clear_root_exists_cache(root: api.Optional[str] = None) -> None:
        with api._root_exists_cache_lock:
            if root is None:
                api._root_exists_cache.clear()
            else:
                api._root_exists_cache.pop(root, None)


    def _path_name(path: str) -> str:
        if api.is_smb_path(path):
            return api.smb_name(path)
        return api.Path(path).name


    def _path_suffix(path: str) -> str:
        if api.is_smb_path(path):
            return api.smb_suffix(path)
        return api.Path(path).suffix.lower()

    api._is_within_local_path = _is_within_local_path
    api._infer_time_scale_from_path = _infer_time_scale_from_path
    api._is_within_allowed_root = _is_within_allowed_root
    api._stitch_od_roots = _stitch_od_roots
    api._is_within_stitch_od_root = _is_within_stitch_od_root
    api._ensure_within_allowed_root = _ensure_within_allowed_root
    api._ensure_readable_treatment_file = _ensure_readable_treatment_file
    api._ensure_readable_od_dat = _ensure_readable_od_dat
    api._ensure_writable_output_folder = _ensure_writable_output_folder
    api._mapped_smb_local_file = _mapped_smb_local_file
    api._mapped_smb_local_dir = _mapped_smb_local_dir
    api._default_folder = _default_folder
    api._folder_exists = _folder_exists
    api._root_exists = _root_exists
    api._clear_root_exists_cache = _clear_root_exists_cache
    api._path_name = _path_name
    api._path_suffix = _path_suffix
