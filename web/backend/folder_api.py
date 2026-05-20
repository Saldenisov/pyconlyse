import os
import platform
import re
import socket
from pathlib import Path

from flask import Blueprint, jsonify, request

from treatment_network_path import is_smb_path, normalize_smb_path, smb_isdir

folder_api = Blueprint('folder_api', __name__, url_prefix='/api')

MACOS_TREATMENT_ROOT = Path("/dev/DATA/VD2")
MACOS_TREATMENT_ROOT_BASE = Path("/dev/DATA")
MACOS_TREATMENT_ROOT_BASES = [Path("/dev/DATA"), Path("/Volumes")]
WINDOWS_TREATMENT_ROOT = "E:/Data/DATA_VD2"
WINDOWS_TREATMENT_ROOT_BASE = "E:/"
FALLBACK_ALLOWED_ROOT = Path.home() / "TreatmentData"
WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")


def get_default_allowed_root():
    system_name = platform.system().lower()
    if system_name == "windows":
        return WINDOWS_TREATMENT_ROOT
    if system_name == "darwin":
        return str(MACOS_TREATMENT_ROOT)
    return str(FALLBACK_ALLOWED_ROOT)


def get_treatment_root_base():
    return get_treatment_root_bases()[0]


def get_treatment_root_bases():
    env_base = os.environ.get("PYCONLYSE_TREATMENT_ROOT_BASE")
    if env_base:
        return [item for item in env_base.split(os.pathsep) if item]

    system_name = platform.system().lower()
    hostname = socket.gethostname().lower()
    if system_name == "windows" or hostname.startswith("everest"):
        return [WINDOWS_TREATMENT_ROOT_BASE]
    if system_name == "darwin":
        return [str(path) for path in MACOS_TREATMENT_ROOT_BASES]
    return [str(FALLBACK_ALLOWED_ROOT.parent)]


def get_allowed_root():
    return (
        os.environ.get("PYCONLYSE_TREATMENT_ROOT")
        or os.environ.get("PYCONLYSE_ALLOWED_ROOT")
        or get_default_allowed_root()
    )


def _normalize_path(path):
    if is_smb_path(path):
        return normalize_smb_path(path)
    return os.path.abspath(os.path.expanduser(str(path).strip()))


def _looks_like_windows_path(path):
    return bool(WINDOWS_DRIVE_RE.match(str(path).strip()))


def _normalize_for_compare(path, prefer_windows=False):
    raw_path = os.path.expanduser(str(path).strip())
    use_windows = prefer_windows or _looks_like_windows_path(raw_path)
    if use_windows:
        import ntpath

        return ntpath.normcase(ntpath.abspath(raw_path))
    return os.path.normcase(_normalize_path(raw_path))


def _is_within_root(path, allowed_root):
    if is_smb_path(path) or is_smb_path(allowed_root):
        from treatment_network_path import smb_is_within

        if not is_smb_path(path) or not is_smb_path(allowed_root):
            return False
        return smb_is_within(path, allowed_root)

    prefer_windows = _looks_like_windows_path(path) or _looks_like_windows_path(allowed_root)
    try:
        if prefer_windows:
            import ntpath

            normalized_path = _normalize_for_compare(path, prefer_windows=True)
            normalized_root = _normalize_for_compare(allowed_root, prefer_windows=True)
            return ntpath.commonpath([normalized_path, normalized_root]) == normalized_root
        return os.path.commonpath([
            _normalize_for_compare(path),
            _normalize_for_compare(allowed_root),
        ]) == _normalize_for_compare(allowed_root)
    except ValueError:
        return False


def set_allowed_root(root_path):
    normalized = _normalize_path(root_path)
    if is_smb_path(root_path):
        try:
            if not smb_isdir(normalized):
                raise ValueError("Treatment root does not exist")
        except ValueError as exc:
            if "smbprotocol" not in str(exc):
                raise
        os.environ["PYCONLYSE_TREATMENT_ROOT"] = normalized
        os.environ["PYCONLYSE_ALLOWED_ROOT"] = normalized
        return normalized

    root_bases = get_treatment_root_bases()
    if not any(_is_within_root(root_path, root_base) for root_base in root_bases):
        raise ValueError(f"Treatment root must be inside one of: {', '.join(root_bases)}")
    if not os.path.isdir(normalized):
        raise ValueError("Treatment root does not exist")

    os.environ["PYCONLYSE_TREATMENT_ROOT"] = normalized
    os.environ["PYCONLYSE_ALLOWED_ROOT"] = normalized
    return normalized

def build_folder_tree(root_path, include_files=False):
    """
    Recursively builds a tree of directories (and optionally files)
    starting from root_path. Each node is a dictionary with:
      - 'name': Folder or file name
      - 'path': Full path to the item
      - 'isFile': False for directories, True for files (if included)
      - 'children': List of child nodes (only for directories)
    """
    node = {
        "name": os.path.basename(root_path) or root_path,
        "path": root_path,
        "isFile": False,
        "children": []
    }
    try:
        with os.scandir(root_path) as it:
            for entry in it:
                if entry.is_dir():
                    node["children"].append(build_folder_tree(entry.path, include_files))
                elif include_files:
                    # Optionally include files in the tree
                    node["children"].append({
                        "name": entry.name,
                        "path": entry.path,
                        "isFile": True
                    })
    except Exception as e:
        print(f"Error reading directory {root_path}: {e}")
    return node

@folder_api.route('/folder-structure', methods=['GET'])
def get_folder_structure():
    """
    Returns a JSON tree of allowed folders starting at ALLOWED_ROOT.
    Used for folder selection.
    """
    folder_tree = build_folder_tree(get_allowed_root())
    return jsonify(folder_tree)

@folder_api.route('/folder-contents', methods=['GET'])
def get_folder_contents():
    """
    Returns a JSON tree of the contents of the folder specified by the
    'folder' query parameter. Includes files if needed.
    """
    folder = request.args.get('folder')
    if not folder:
        return jsonify({"error": "Folder parameter is missing"}), 400

    allowed_root = _normalize_path(get_allowed_root())
    normalized_folder = _normalize_path(folder)

    # Validate that the requested folder is within the configured root
    if not _is_within_root(normalized_folder, allowed_root):
        return jsonify({"error": "Invalid folder"}), 403

    if not os.path.isdir(normalized_folder):
        return jsonify({"error": "Folder not found"}), 404

    # Build the tree for the selected folder. Here we include files.
    contents_tree = build_folder_tree(normalized_folder, include_files=True)
    return jsonify(contents_tree)
