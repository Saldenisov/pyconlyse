#!/usr/bin/env python3
import sys
from pathlib import Path

from PyQt5 import QtWidgets
from PyQt5.QtGui import QIcon
from taurus.qt.qtgui.application import TaurusApplication

app_folder = Path(__file__).resolve().parents[2]
sys.path.append(str(app_folder))

from DeviceServers.cameras.andor.DS_ANDOR_CCD_Widget import ANDOR_CCD
from DeviceServers.shared.DS_Widget import VisType
from DeviceServers.spectrographs.andor.DS_ANDOR_SPECTROGRAPH_Widget import (
    ANDOR_SPECTROGRAPH,
)

layouts = {
    "V0": {
        "camera": ["manip/CR/ANDOR_CCD1"],
        "spectrographs": ["manip/CR/ANDOR_SHAMROCK1", "manip/CR/ANDOR_KYMERA1"],
    }
}


class SpectroscopyWorkbench(QtWidgets.QWidget):
    def __init__(self, instance: str, vis_type: VisType = VisType.FULL):
        super().__init__()
        self.setWindowTitle(f"Spectroscopy - {instance}")
        self.setWindowIcon(QIcon("bin/icons/spectrometer.png"))
        self.vis_type = vis_type
        self.instance = instance
        self.config = layouts[instance]

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(
            QtWidgets.QLabel(
                "Andor spectroscopy workbench: Newton CCD together with Shamrock/Kymera control."
            )
        )

        camera_box = QtWidgets.QGroupBox("CCD")
        camera_layout = QtWidgets.QVBoxLayout(camera_box)
        for device_name in self.config.get("camera", []):
            camera_layout.addWidget(ANDOR_CCD(device_name, self, vis_type))
        layout.addWidget(camera_box)

        spectro_box = QtWidgets.QGroupBox("Spectrographs")
        spectro_layout = QtWidgets.QVBoxLayout(spectro_box)
        for device_name in self.config.get("spectrographs", []):
            spectro_layout.addWidget(ANDOR_SPECTROGRAPH(device_name, self, vis_type))
        layout.addWidget(spectro_box)

        layout.addStretch()


def start_spectroscopy_client(
    instance: str = "V0",
    vis_type=None,
    standalone: bool = True,
):
    if vis_type is None:
        vis_type = VisType.FULL

    if standalone:
        app = TaurusApplication(sys.argv, cmd_line_parser=None)

    panel = SpectroscopyWorkbench(instance=instance, vis_type=vis_type)
    panel.show()

    if standalone:
        sys.exit(app.exec_())
    return panel


if __name__ == "__main__":
    vis_type = VisType.FULL
    if len(sys.argv) >= 3:
        try:
            vis_type = VisType(sys.argv[2])
        except ValueError:
            vis_type = VisType.FULL
    instance = sys.argv[1] if len(sys.argv) >= 2 else "V0"
    start_spectroscopy_client(instance=instance, vis_type=vis_type, standalone=True)
