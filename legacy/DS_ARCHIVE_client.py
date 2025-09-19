import sys
from pathlib import Path

app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))

from bin.DS_General_Client import main
from DeviceServers.data.archive.DS_ARCHIVE_Widget import Archive
from gui.Panels import ArchivePanel

layouts = {
    "Main": {"selection": ["manip/general/archive"], "width": 1},
    "Test": {"selection": ["manip/general/archivetest"], "width": 1},
}


if __name__ == "__main__":
    main(ArchivePanel, "ARCHIVE", Archive, "icons//archive.svg", layouts)
