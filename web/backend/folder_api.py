# folder_api.py
from flask import Blueprint, jsonify
import os

folder_api = Blueprint('folder_api', __name__, url_prefix='/api')

# Define the allowed root folder (only allow browsing within E:\)
ALLOWED_ROOT = r'E:\\ICP_notebooks'

def build_folder_tree(root_path):
    """
    Recursively builds a tree of directories starting from root_path.
    Each node in the tree is represented as a dictionary with:
      - 'name': Folder name
      - 'path': Full path to the folder
      - 'isFile': False for directories
      - 'children': List of child directory nodes
    """
    tree = {
        "name": os.path.basename(root_path) or root_path,
        "path": root_path,
        "isFile": False,
        "children": []
    }
    try:
        with os.scandir(root_path) as it:
            for entry in it:
                if entry.is_dir():
                    # Recursively build the tree for subdirectories.
                    tree["children"].append(build_folder_tree(entry.path))
    except Exception as e:
        # Log the error or handle it as needed.
        print(f"Error reading directory {root_path}: {e}")
    return tree

@folder_api.route('/folder-structure', methods=['GET'])
def get_folder_structure():
    """
    GET endpoint that returns a JSON tree of allowed folders starting at E:\
    """
    folder_tree = build_folder_tree(ALLOWED_ROOT)
    return jsonify(folder_tree)
