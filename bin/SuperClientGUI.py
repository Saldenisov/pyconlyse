"""
This is Client Terminus.
It is the main client GUI for establishing connections between client and devices
sergey.denisov@u-psud.fr
LCP/CNRS UMR8000
ELYSE platform
14/11/2019
"""

import sys
from pathlib import Path
app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))

from PyQt5.QtWidgets import QApplication

from gui.models.ClientGUIModels import SuperUserGUIModel
from gui.controllers.ClientGUIControllers import SuperClientGUIcontroller
from logs_pack import initialize_logger


def main():
    logger = initialize_logger(app_folder/ 'LOG', file_name="SuperUserGUI")
    logger.info('Starting SuperUser GUI')
    app = QApplication(sys.argv)
    SuperClientGUIcontroller(SuperUserGUIModel(app_folder))
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
