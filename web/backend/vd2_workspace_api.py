"""Software-only folder navigation and saved VD2 form settings."""
import os
from pathlib import Path

from flask import jsonify, request
from browser_workspace_state import BrowserWorkspaceStates, WorkspaceConflict, workspace_identity


def workspace_repository():
    return BrowserWorkspaceStates(os.environ.get("PYCONLYSE_WORKSPACE_STATE_DB") or
                                  os.environ.get("PYCONLYSE_EXPERIMENT_STATE_DB") or
                                  str(Path.home() / ".pyconlyse" / "experiment_preparation.sqlite3"))


def browser_identity():
    return workspace_identity(request.headers.get("X-Workspace-Browser"))


def install_workspace_routes(blueprint):
    @blueprint.route("/workspace", methods=["GET", "POST"])
    def vd2_workspace():
        try:
            browser = browser_identity()
            window = workspace_identity(request.headers.get("X-Workspace-Window"))
            repo = workspace_repository()
            if request.method == "GET":
                saved = repo.get(browser, window)
            else:
                payload = request.get_json(silent=True)
                if not isinstance(payload, dict) or set(payload) != {"settings", "revision"}:
                    raise ValueError("Settings and revision are required")
                saved = repo.save(browser, window, payload["settings"], payload["revision"])
            return jsonify(success=True, workspace=saved, persistence="sqlite",
                           features=["manifest_browser", "project_history", "quoted_paths"])
        except WorkspaceConflict as exc:
            return jsonify(success=False, error=str(exc)), 409
        except ValueError as exc:
            return jsonify(success=False, error=str(exc)), 400

    @blueprint.get("/workspace/history")
    def vd2_workspace_history():
        try:
            return jsonify(success=True, workspaces=workspace_repository().history(browser_identity()))
        except ValueError as exc:
            return jsonify(success=False, error=str(exc)), 400

    @blueprint.get("/protocol/folders")
    def vd2_project_folders():
        # Use the existing Treatment root boundary. List one level only; never
        # recursively scan the data drive or create/modify a directory.
        from folder_api import get_allowed_root
        from treatment_api import _ensure_within_allowed_root
        try:
            root = Path(get_allowed_root()).resolve()
            folder = Path(_ensure_within_allowed_root(request.args.get("folder") or str(root))).resolve()
            if not folder.is_relative_to(root):
                raise ValueError("Folder is outside the allowed data root")
            if not folder.is_dir():
                return jsonify(success=False, error="Folder does not exist", root=str(root)), 404
            folders = []
            files = []
            include_json = request.args.get("kind") == "manifest"
            truncated = False
            with os.scandir(folder) as entries:
                for entry in entries:
                    if entry.is_dir() and Path(entry.path).resolve().is_relative_to(root):
                        if len(folders) + len(files) == 1000:
                            truncated = True
                            break
                        folders.append(dict(name=entry.name, path=entry.path))
                    elif include_json and entry.is_file() and entry.name.lower().endswith('.json') and Path(entry.path).resolve().is_relative_to(root):
                        if len(folders) + len(files) == 1000:
                            truncated = True
                            break
                        files.append(dict(name=entry.name, path=entry.path))
            return jsonify(success=True, folder=str(folder), root=str(root),
                           parent=str(folder.parent) if folder != root else None,
                           folders=sorted(folders, key=lambda item: item["name"].casefold()),
                           files=sorted(files, key=lambda item: item["name"].casefold()), truncated=truncated)
        except (OSError, ValueError) as exc:
            return jsonify(success=False, error=str(exc)), 400
