#!/usr/bin/env python3
"""ARCHIVE Client using general DS panel framework"""
import sys
from pathlib import Path

app_folder = Path(__file__).resolve().parents[3]
sys.path.append(str(app_folder))

from gui.DS_General_Client import main
from gui.Panels import ArchivePanel
from DeviceServers.data.archive.DS_ARCHIVE_Widget import Archive

# Layouts from legacy
layouts = {
    "Main": {"selection": ["manip/general/archive"], "width": 1},
    "Test": {"selection": ["manip/general/archivetest"], "width": 1},
}


def start_archive_client(instance: str = "Main", vis_type=None, standalone: bool = True):
    from DeviceServers.shared.DS_Widget import VisType

    if vis_type is None:
        vis_type = VisType.FULL

    return main(
        ArchivePanel,
        "ARCHIVE",
        Archive,
        "bin/icons/archive.svg",
        layouts,
        instance=instance,
        vis_type=vis_type,
        standalone=standalone,
    )


if __name__ == "__main__":
    sys.exit(start_archive_client())


