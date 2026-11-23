"""pump probe v0 api files operations."""


def bind(api):
    """Use the owning API module for shared state and dependencies."""
    def _data_root():
        return api.os.environ.get("PYCONLYSE_PUMP_PROBE_DATA_ROOT", api.DEFAULT_DATA_ROOT)


    def _normalize_data_path(path):
        raw_path = str(path or "").strip() or api._data_root()
        if api.is_smb_path(raw_path):
            return api.normalize_smb_path(raw_path)
        return api.os.path.abspath(api.os.path.expanduser(raw_path))


    def _is_data_path_allowed(path):
        root = api._normalize_data_path(api._data_root())
        normalized = api._normalize_data_path(path)
        if api.is_smb_path(root) or api.is_smb_path(normalized):
            return api.is_smb_path(root) and api.is_smb_path(normalized) and api.smb_is_within(normalized, root)
        try:
            return api.os.path.commonpath([normalized, root]) == root
        except ValueError:
            return False


    def _local_listdir(folder):
        entries = []
        with api.os.scandir(folder) as iterator:
            for entry in iterator:
                is_file = entry.is_file()
                entries.append({
                    "name": entry.name,
                    "path": entry.path,
                    "is_dir": entry.is_dir(),
                    "is_file": is_file,
                    "size_bytes": int(entry.stat().st_size) if is_file else 0,
                })
        return entries


    def _list_data_path(path):
        normalized = api._normalize_data_path(path)
        if not api._is_data_path_allowed(normalized):
            raise ValueError("Data path is outside pump-probe data root")
        if api.is_smb_path(normalized):
            return api.smb_listdir(normalized)
        return api._local_listdir(normalized)


    def _parent_data_path(path):
        root = api._normalize_data_path(api._data_root())
        normalized = api._normalize_data_path(path)
        if normalized == root:
            return root
        if api.is_smb_path(normalized):
            parent = api.smb_parent(normalized)
            return parent if api._is_data_path_allowed(parent) else root
        parent = api.os.path.dirname(normalized)
        return parent if api._is_data_path_allowed(parent) else root


    def _safe_folder_name(name):
        text = str(name or "").strip()
        cleaned = "".join(char if char.isalnum() or char in " ._-+()" else "_" for char in text)
        cleaned = cleaned.strip(" .")
        if not cleaned:
            raise ValueError("Folder name is empty")
        return cleaned[:120]


    def _mkdir_data_path(parent, name):
        parent_path = api._normalize_data_path(parent)
        if not api._is_data_path_allowed(parent_path):
            raise ValueError("Parent path is outside pump-probe data root")
        folder_name = api._safe_folder_name(name)
        if api.is_smb_path(parent_path):
            import smbclient

            server, _share, _remote_path = api.split_smb_path(parent_path)
            from treatment_network_path import _register_session

            _register_session(server)
            next_path = api.smb_join(parent_path, folder_name)
            smbclient.makedirs(api.smb_to_unc(next_path), exist_ok=True)
            return next_path
        next_path = api.os.path.join(parent_path, folder_name)
        api.Path(next_path).mkdir(parents=True, exist_ok=True)
        return next_path


    def _read_data_file(path):
        normalized = api._normalize_data_path(path)
        if not api._is_data_path_allowed(normalized):
            raise ValueError("Data file is outside pump-probe data root")
        if api.is_smb_path(normalized):
            import smbclient

            server, _share, _remote_path = api.split_smb_path(normalized)
            from treatment_network_path import _register_session

            _register_session(server)
            with smbclient.open_file(api.smb_to_unc(normalized), mode="rb") as handle:
                return normalized, handle.read()
        with open(normalized, "rb") as handle:
            return normalized, handle.read()


    def _native_run_directory(directory):
        """Return a filesystem path suitable for native HDF5 I/O."""
        target_directory = api._normalize_data_path(directory)
        if not api._is_data_path_allowed(target_directory):
            raise ValueError("Run output path is outside pump-probe data root")
        root = api._normalize_data_path(api._data_root())
        if api.is_smb_path(target_directory):
            target_directory = api.smb_to_local_path(target_directory)
            root = api.smb_to_local_path(root)
            if target_directory is None or root is None:
                return None
        target = api.Path(target_directory).resolve()
        if not target.is_relative_to(api.Path(root).resolve()):
            raise ValueError("Resolved run output path is outside pump-probe data root")
        return target


    def _publish_data_file(directory, source_path):
        """Return the final path; copy only artifacts that were staged elsewhere."""
        target_directory = api._normalize_data_path(directory)
        native_directory = api._native_run_directory(target_directory)
        source = api.Path(source_path)
        target_name = source.name
        if native_directory is not None:
            native_directory.mkdir(parents=True, exist_ok=True)
            target = native_directory / target_name
            if source.resolve() != target:
                api.shutil.copy2(source, target)
            return (api.smb_join(target_directory, target_name) if api.is_smb_path(target_directory)
                    else str(api.Path(target_directory) / target_name))

        import smbclient

        server, _share, _remote_path = api.split_smb_path(target_directory)
        from treatment_network_path import _register_session

        _register_session(server)
        target = api.smb_join(target_directory, target_name)
        with open(source, "rb") as input_handle:
            with smbclient.open_file(api.smb_to_unc(target), mode="wb") as output_handle:
                api.shutil.copyfileobj(input_handle, output_handle)
        return target



    def _data_file_name(path):
        if api.is_smb_path(path):
            return api.unquote(path.rstrip("/").split("/")[-1])
        return api.Path(path).name


    def _data_file_suffix(path):
        return api.Path(api._data_file_name(path)).suffix.lower()


    def pump_probe_data_list():
        try:
            root = api._normalize_data_path(api._data_root())
            path = api._normalize_data_path(api.request.args.get("path") or root)
            entries = api._list_data_path(path)
            entries = sorted(
                entries,
                key=lambda item: (not item.get("is_dir"), str(item.get("name", "")).lower()),
            )
            return api.jsonify({
                "success": True,
                "root": root,
                "path": path,
                "parent": api._parent_data_path(path),
                "entries": entries,
            })
        except Exception as exc:
            return api.jsonify({"success": False, "error": str(exc)}), 400


    def pump_probe_data_create_folder():
        try:
            payload = api.request.get_json(silent=True) or {}
            parent = payload.get("parent") or api._data_root()
            name = payload.get("name") or ""
            path = api._mkdir_data_path(parent, name)
            return api.jsonify({
                "success": True,
                "root": api._normalize_data_path(api._data_root()),
                "path": path,
            })
        except Exception as exc:
            return api.jsonify({"success": False, "error": str(exc)}), 400


    def pump_probe_data_load():
        try:
            payload = api.request.get_json(silent=True) or {}
            path = payload.get("path") or ""
            normalized, file_payload = api._read_data_file(path)
            return api.jsonify(api.load_payload(normalized, file_payload))
        except Exception as exc:
            return api.jsonify({"success": False, "error": str(exc)}), 400


    def pump_probe_data_treat():
        """Replay a correction recipe from source; never write acquisition files."""
        try:
            payload = api.request.get_json(silent=True) or {}
            if payload.get("source_spec") is not None:
                spec = payload["source_spec"]
                sources = api._derived_sources(spec)
                dataset, preview = api.treat_derived_dataset(
                    sources, spec["method"], payload.get("operations", []), payload.get("source_sha256"),
                )
                if payload.get("path") != preview["path"]:
                    raise ValueError("Derived source identity changed; recreate the dataset")
            else:
                normalized, file_payload = api._read_data_file(payload.get("path") or "")
                dataset, preview = api.treat_dataset(
                    normalized, file_payload, payload.get("operations", []), payload.get("source_sha256"),
                )
            return api._treatment_response(dataset, preview, payload.get("format"))
        except Exception as exc:
            return api.jsonify({"success": False, "error": str(exc)}), 400


    def _derived_sources(spec):
        """Resolve every original file within the data root and verify its bytes."""
        if (not isinstance(spec, dict) or set(spec) != {"kind", "method", "sources"}
                or spec["kind"] != "derived" or spec["method"] not in {"average", "merge"}):
            raise ValueError("Invalid derived source specification")
        entries = spec["sources"]
        if not isinstance(entries, list) or not 2 <= len(entries) <= 32:
            raise ValueError("Select 2..32 source datasets")
        sources = []
        for entry in entries:
            if (not isinstance(entry, dict) or set(entry) != {"path", "source_sha256"}
                    or not isinstance(entry["path"], str) or not isinstance(entry["source_sha256"], str)):
                raise ValueError("Each source requires a path and source_sha256")
            normalized, file_payload = api._read_data_file(entry["path"])
            if api.hashlib.sha256(file_payload).hexdigest() != entry["source_sha256"]:
                raise ValueError("Source file changed; reload before deriving or applying corrections")
            sources.append((normalized, file_payload))
        return sources


    def _treatment_response(dataset, preview, output_format):
        if output_format == "dat":
            response = api.Response(api.export_dat(dataset), mimetype="text/tab-separated-values")
            response.headers["Content-Disposition"] = 'attachment; filename="v0-corrected.dat"'
            return response
        if output_format not in {None, "json"}:
            raise ValueError("Unsupported correction output format")
        return api.jsonify(preview)


    def pump_probe_data_derive():
        """Build an explicitly selected multi-file OD dataset without changing RAW."""
        try:
            payload = api.request.get_json(silent=True) or {}
            spec = {"kind": "derived", "method": payload.get("method"), "sources": payload.get("sources")}
            sources = api._derived_sources(spec)
            dataset, preview = api.derive_dataset(sources, spec["method"])
            operations = payload.get("operations", [])
            if not isinstance(operations, list):
                raise ValueError("Recipe must be a list with at most 32 operations")
            if operations:
                dataset, preview = api.treat_derived_dataset(
                    sources, spec["method"], operations, preview["source_sha256"],
                )
            return api._treatment_response(dataset, preview, payload.get("format"))
        except Exception as exc:
            return api.jsonify({"success": False, "error": str(exc)}), 400

    api._data_root = _data_root
    api._normalize_data_path = _normalize_data_path
    api._is_data_path_allowed = _is_data_path_allowed
    api._local_listdir = _local_listdir
    api._list_data_path = _list_data_path
    api._parent_data_path = _parent_data_path
    api._safe_folder_name = _safe_folder_name
    api._mkdir_data_path = _mkdir_data_path
    api._read_data_file = _read_data_file
    api._native_run_directory = _native_run_directory
    api._publish_data_file = _publish_data_file
    api._data_file_name = _data_file_name
    api._data_file_suffix = _data_file_suffix
    api.pump_probe_data_list = pump_probe_data_list
    api.pump_probe_data_create_folder = pump_probe_data_create_folder
    api.pump_probe_data_load = pump_probe_data_load
    api.pump_probe_data_treat = pump_probe_data_treat
    api._derived_sources = _derived_sources
    api._treatment_response = _treatment_response
    api.pump_probe_data_derive = pump_probe_data_derive
