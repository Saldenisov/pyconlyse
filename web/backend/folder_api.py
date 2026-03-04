# folder_api.py
import os

from flask import Blueprint, jsonify, request

folder_api = Blueprint('folder_api', __name__, url_prefix='/api')

# Default root for browsing treatment data. Can be overridden per deployment.
ALLOWED_ROOT = r'E:\\ICP_notebooks'


def get_allowed_root():
    return os.environ.get("PYCONLYSE_ALLOWED_ROOT", ALLOWED_ROOT)

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

    allowed_root = get_allowed_root()

    # Validate that the requested folder is within the configured root
    if not os.path.abspath(folder).startswith(os.path.abspath(allowed_root)):
        return jsonify({"error": "Invalid folder"}), 403

    # Build the tree for the selected folder. Here we include files.
    contents_tree = build_folder_tree(folder, include_files=True)
    return jsonify(contents_tree)
