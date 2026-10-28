"""Relative LabVIEW project URLs use the project FILE as their path base.

Pure path calculation; no filesystem, LabVIEW, network or hardware operations.
Python3.4 compatible.
"""

import ntpath
import posixpath


def project_item_url(project_file, target_file):
    """Return an item URL resolving from project_file to target_file.

    Native LabVIEW resolves ``../same_folder.vi`` beside the project. Standard
    relpath from the containing directory therefore needs one extra ``../``.
    """
    paths = (ntpath if ntpath.splitdrive(project_file)[0] or "\\" in project_file
             else posixpath)
    if (not paths.isabs(project_file) or not paths.isabs(target_file)
            or not project_file.lower().endswith(".lvproj")):
        raise ValueError("Absolute project FILE and target FILE paths required")
    canonical = paths.relpath(target_file, paths.dirname(project_file))
    return "../" + canonical.replace("\\", "/")
