"""Session state snapshots, validation, and persistence for Data Treatment."""

from copy import deepcopy
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Dict
from typing import Optional
import math
import os


class TreatmentSessionStore:
    def __init__(self, repository=None):
        import treatment_api as api

        self._lock = api.Lock()
        self._repository = repository
        self._sessions: Dict[str, Dict[str, object]] = (
            repository.load_sessions() if repository else {}
        )

    def _persist_locked(self, session_id):
        self._sessions[session_id]["saved_at"] = datetime.now(timezone.utc).isoformat()
        if self._repository:
            self._repository.save_session(session_id, self._sessions[session_id])

    @staticmethod
    def _clone_state(state: Dict[str, object]) -> Dict[str, object]:
        snapshot = dict(state)
        snapshot["paths"] = dict(state["paths"])
        snapshot["path_sources"] = dict(state.get("path_sources") or {})
        snapshot["selection"] = dict(state["selection"])
        return snapshot

    def _get_or_create_state(self, session_id: str) -> Dict[str, object]:
        import treatment_api as api

        state = self._sessions.get(session_id)
        if state is None:
            state = api._default_state()
            self._sessions[session_id] = state
            self._persist_locked(session_id)
        return state

    def snapshot(self, session_id: str) -> Dict[str, object]:
        with self._lock:
            state = self._get_or_create_state(session_id)
            return self._clone_state(state)

    def saved_sessions(self, browser, profile):
        import treatment_api as api

        prefix = f"browser:{api.workspace_identity(browser)}:"
        with self._lock:
            items = [dict(session_id=key, folder=state.get("folder_path", ""),
                          name=state.get("save_file_name") or state.get("folder_path") or "Treatment",
                          updated_at=state.get("saved_at", ""))
                     for key, state in self._sessions.items()
                     if key.startswith(prefix) and api._saved_session_profile(key) == profile
                     and (state.get("paths") or state.get("save_file_name") or state.get("selection")
                          or (state.get("folder_path") and state.get("status_label") != "Treatment session is ready."))]
        return sorted(items, key=lambda item: item["updated_at"], reverse=True)[:40]

    def copy_saved_session(self, source_id, target_id):
        with self._lock:
            source = self._sessions.get(source_id)
            if source is None:
                raise ValueError("Saved treatment session no longer exists")
            source = deepcopy(source)
        return self.restore_if_empty(target_id, source, origin="server snapshot")

    def reset(self, session_id: Optional[str] = None) -> Dict[str, object]:
        import treatment_api as api

        with self._lock:
            if session_id is None:
                self._sessions.clear()
                if self._repository:
                    self._repository.delete_session()
                return self._clone_state(api._default_state())
            self._sessions[session_id] = api._default_state()
            self._persist_locked(session_id)
            return self._clone_state(self._sessions[session_id])

    def restore_if_empty(self, session_id: str, snapshot: Dict[str, object], *, origin="browser backup") -> bool:
        """Import a browser backup only into an untouched, empty server session."""
        import treatment_api as api

        if not isinstance(snapshot, dict):
            raise ValueError("session backup must be an object")
        exp_type = str(snapshot.get("exp_type") or "")
        if exp_type not in api.EXP_TYPES:
            raise ValueError("session backup has an unsupported experiment type")
        selected_data_type = str(snapshot.get("selected_data_type") or "")
        if selected_data_type not in api.REQUIRED_DATA_TYPES[exp_type]:
            raise ValueError("session backup has an invalid selected data type")
        calc_mode = str(snapshot.get("calc_mode") or "")
        if calc_mode not in api.CALC_MODES:
            raise ValueError("session backup has an invalid calculation mode")

        folder = api._ensure_within_allowed_root(str(snapshot.get("folder_path") or ""))
        save_folder = api._ensure_within_allowed_root(str(snapshot.get("save_folder") or folder))
        if not api._folder_exists(folder) or not api._folder_exists(save_folder):
            raise ValueError("session backup folder no longer exists")
        save_file_name = os.path.basename(str(snapshot.get("save_file_name") or "").strip())
        if save_file_name and not save_file_name.lower().endswith(".dat"):
            raise ValueError("session backup save file name must end in .dat")

        paths = {}
        sources = {}
        raw_paths = snapshot.get("paths") or {}
        raw_sources = snapshot.get("path_sources") or {}
        if not isinstance(raw_paths, dict) or not isinstance(raw_sources, dict):
            raise ValueError("session backup paths must be objects")
        for data_type, path in raw_paths.items():
            if data_type not in api.DATA_TYPES:
                raise ValueError("session backup has an invalid input data type")
            paths[data_type] = api._ensure_readable_treatment_file(str(path))
            source = str(raw_sources.get(data_type) or path)
            sources[data_type] = api._ensure_within_allowed_root(source) if source != path else paths[data_type]

        active_data_type = str(snapshot.get("active_data_type") or "")
        if active_data_type not in {"", "OD", "DAT", *api.DATA_TYPES}:
            raise ValueError("session backup has an invalid active data type")
        dat_preview_path = str(snapshot.get("dat_preview_path") or "")
        if dat_preview_path:
            dat_preview_path = api._ensure_readable_treatment_file(dat_preview_path)
            if api._path_suffix(dat_preview_path) != ".dat":
                raise ValueError("session backup preview must be DAT")
        if active_data_type == "DAT" and not dat_preview_path:
            raise ValueError("session backup preview file is missing")
        preview_request = None
        raw_preview = snapshot.get("cleaning_preview_request")
        if isinstance(raw_preview, dict) and str(raw_preview.get("file_path") or "") == paths.get(active_data_type):
            try:
                angle_threshold = float(raw_preview["angle_threshold"])
                surface_threshold = float(raw_preview["surface_threshold"])
                if math.isfinite(angle_threshold) and math.isfinite(surface_threshold):
                    preview_request = {
                        "angle_threshold": angle_threshold,
                        "surface_threshold": surface_threshold,
                        "file_path": paths[active_data_type],
                    }
            except (KeyError, TypeError, ValueError):
                pass
        try:
            map_index = max(0, int(snapshot.get("map_index") or 0))
            raw_selection = snapshot.get("selection") or {}
            if not isinstance(raw_selection, dict):
                raise ValueError("selection must be an object")
            selection = {
                key: int(value) for key, value in raw_selection.items()
                if key in {"x1", "x2", "y1", "y2"} and value is not None
            }
        except (TypeError, ValueError) as exc:
            raise ValueError("session backup has invalid selection values") from exc

        with self._lock:
            current = self._get_or_create_state(session_id)
            if current.get("status_label") != "Treatment session is ready." or current.get("paths"):
                return False
            current.update({
                "exp_type": exp_type,
                "selected_data_type": selected_data_type,
                "active_data_type": active_data_type,
                "dat_preview_path": dat_preview_path,
                "map_index": map_index,
                "selection": selection,
                "calc_mode": calc_mode,
                "first_map_with_electrons": bool(snapshot.get("first_map_with_electrons", True)),
                "folder_path": folder,
                "save_folder": save_folder,
                "save_file_name": save_file_name,
                "paths": paths,
                "path_sources": sources,
                "result_ready": bool(snapshot.get("result_ready", False)),
                "result_map_policy": (
                    "all_raw_maps"
                    if snapshot.get("result_map_policy") == "all_raw_maps"
                    else "selected_maps"
                ),
                "cleaning_preview_request": preview_request,
                "status_label": f"Treatment session restored from {origin}.",
            })
            self._persist_locked(session_id)
            return True

    def update_config(self, session_id: str, payload: Dict[str, object]) -> Dict[str, object]:
        import treatment_api as api

        with self._lock:
            state = self._get_or_create_state(session_id)
            previous_calculation = (
                state["exp_type"], state["selected_data_type"],
                state["calc_mode"], state["first_map_with_electrons"],
            )
            requested_exp_type = str(state["exp_type"])
            if "exp_type" in payload:
                exp_type = str(payload["exp_type"])
                if exp_type not in api.EXP_TYPES:
                    raise ValueError(f"Unsupported exp_type '{exp_type}'")
                state["exp_type"] = exp_type
                requested_exp_type = exp_type

            if "selected_data_type" in payload:
                selected_data_type = str(payload["selected_data_type"])
                if selected_data_type not in api.DATA_TYPES:
                    raise ValueError(
                        f"Unsupported selected_data_type '{selected_data_type}'"
                    )
                if selected_data_type not in api.REQUIRED_DATA_TYPES[requested_exp_type]:
                    raise ValueError(
                        f"selected_data_type '{selected_data_type}' is not valid for exp_type '{requested_exp_type}'"
                    )
                state["selected_data_type"] = selected_data_type
            else:
                required_data_types = api.REQUIRED_DATA_TYPES[requested_exp_type]
                if state["selected_data_type"] not in required_data_types:
                    state["selected_data_type"] = required_data_types[0]

            if "calc_mode" in payload:
                calc_mode = str(payload["calc_mode"])
                if calc_mode not in api.CALC_MODES:
                    raise ValueError(f"Unsupported calc_mode '{calc_mode}'")
                state["calc_mode"] = calc_mode

            if requested_exp_type == "ABS+BASE+NOISE":
                state["calc_mode"] = "averaged"

            if "first_map_with_electrons" in payload:
                state["first_map_with_electrons"] = bool(
                    payload["first_map_with_electrons"]
                )

            if "save_folder" in payload:
                save_folder = api._ensure_within_allowed_root(str(payload["save_folder"]))
                if not api._folder_exists(save_folder):
                    raise ValueError("save_folder does not exist")
                state["save_folder"] = save_folder

            if "save_file_name" in payload:
                save_file_name = os.path.basename(str(payload["save_file_name"]).strip())
                if save_file_name and not save_file_name.lower().endswith(".dat"):
                    save_file_name = f"{Path(save_file_name).stem}.dat"
                state["save_file_name"] = save_file_name

            state["status_label"] = "Treatment session updated."
            if previous_calculation != (
                state["exp_type"], state["selected_data_type"],
                state["calc_mode"], state["first_map_with_electrons"],
            ):
                state["result_ready"] = False
                state["result_map_policy"] = "selected_maps"
                state["cleaning_preview_request"] = None
            self._persist_locked(session_id)

        return self.snapshot(session_id)

    def set_folder(self, session_id: str, folder_path: str) -> Dict[str, object]:
        import treatment_api as api

        folder = api._ensure_within_allowed_root(folder_path)
        if not api._folder_exists(folder):
            raise ValueError("Selected folder does not exist")

        with self._lock:
            state = self._get_or_create_state(session_id)
            state["folder_path"] = folder
            _, save_file_name = api._default_save_target_for_folder(folder)
            state["save_folder"] = folder
            state["save_file_name"] = save_file_name
            state["result_ready"] = False
            state["result_map_policy"] = "selected_maps"
            state["cleaning_preview_request"] = None
            state["status_label"] = f"Folder selected: {folder}"
            self._persist_locked(session_id)

        return self.snapshot(session_id)

    def clear_folder_inputs(self, session_id: str) -> None:
        """Start a folder selection without inheriting a previous sample's roles."""
        with self._lock:
            state = self._get_or_create_state(session_id)
            state.update(paths={}, path_sources={}, active_data_type="", map_index=0,
                         noise_ready=False, result_ready=False, dat_preview_path="",
                         cleaning_preview_request=None, selection={})
            self._persist_locked(session_id)

    def set_data_path(
        self,
        session_id: str,
        data_type: str,
        file_path: str,
        source_path: Optional[str] = None,
    ) -> Dict[str, object]:
        import treatment_api as api

        if data_type not in api.DATA_TYPES:
            raise ValueError(f"Unsupported data_type '{data_type}'")

        normalized_source = api._normalize_path(source_path) if source_path else api._normalize_path(file_path)
        mapped_source = (
            api._mapped_smb_local_file(normalized_source)
            if api.is_smb_path(normalized_source)
            else None
        )
        if mapped_source and os.path.abspath(file_path) == mapped_source:
            normalized = mapped_source
        else:
            normalized = api._ensure_readable_treatment_file(file_path)

        with self._lock:
            state = self._get_or_create_state(session_id)
            state["paths"][data_type] = normalized
            state.setdefault("path_sources", {})[data_type] = normalized_source
            state["active_data_type"] = data_type
            state["map_index"] = 0
            state["result_ready"] = False
            state["result_map_policy"] = "selected_maps"
            state["cleaning_preview_request"] = None
            if not state["save_file_name"]:
                stem = os.path.splitext(os.path.basename(normalized))[0]
                state["save_file_name"] = f"{stem}.dat"
            state["status_label"] = f"{data_type} file selected."
            self._persist_locked(session_id)

        return self.snapshot(session_id)

    def set_browsing_folder(self, session_id: str, folder_path: str) -> Dict[str, object]:
        """Repair browser folder context without resetting active processing state."""
        import treatment_api as api

        folder = api._ensure_within_allowed_root(folder_path)
        if not api._folder_exists(folder):
            raise ValueError("Selected folder does not exist")
        with self._lock:
            state = self._get_or_create_state(session_id)
            state["folder_path"] = folder
            self._persist_locked(session_id)
        return self.snapshot(session_id)

    def mark_result_ready(
        self, session_id: str, ready: bool, map_policy: str = "selected_maps"
    ) -> None:
        with self._lock:
            state = self._get_or_create_state(session_id)
            state["result_ready"] = bool(ready)
            state["result_map_policy"] = (
                "all_raw_maps" if ready and map_policy == "all_raw_maps" else "selected_maps"
            )
            self._persist_locked(session_id)

    def set_cleaning_preview_request(self, session_id: str, request_payload) -> None:
        with self._lock:
            state = self._get_or_create_state(session_id)
            state["cleaning_preview_request"] = dict(request_payload) if request_payload else None
            self._persist_locked(session_id)

    def update_selection(self, session_id: str, payload: Dict[str, object]) -> Dict[str, object]:
        import treatment_api as api

        with self._lock:
            state = self._get_or_create_state(session_id)

            if "active_data_type" in payload:
                active_data_type = str(payload["active_data_type"])
                if active_data_type and active_data_type not in {"OD", "DAT"} and active_data_type not in api.DATA_TYPES:
                    raise ValueError(f"Unsupported active_data_type '{active_data_type}'")
                state["active_data_type"] = active_data_type

            if "map_index" in payload:
                try:
                    map_index = int(payload["map_index"])
                except (TypeError, ValueError):
                    raise ValueError("map_index must be an integer")
                if map_index < 0:
                    raise ValueError("map_index must be zero or positive")
                state["map_index"] = map_index

            if "selection" in payload:
                raw_selection = payload["selection"] or {}
                if not isinstance(raw_selection, dict):
                    raise ValueError("selection must be an object")

                selection = dict(state["selection"])
                for key in ("x1", "x2", "y1", "y2"):
                    if key in raw_selection and raw_selection[key] is not None:
                        try:
                            selection[key] = int(raw_selection[key])
                        except (TypeError, ValueError):
                            raise ValueError(f"{key} must be an integer")
                state["selection"] = selection

            state["status_label"] = "Selection updated."
            self._persist_locked(session_id)

        return self.snapshot(session_id)

    def set_dat_preview(self, session_id, path):
        with self._lock:
            state = self._get_or_create_state(session_id)
            state.update(dat_preview_path=path, active_data_type="DAT", map_index=0, selection={})
            self._persist_locked(session_id)
