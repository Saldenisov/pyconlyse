"""
sergey.denisov@u-psud.fr
LCP/CNRS UMR8000 ELYSE platform
06/08/2019
"""


import sys
from pathlib import Path
from PyQt5.QtWidgets import QApplication
from models.ServerGUIModel import ServerGUIModel
from controllers.ServerGUIController import ServerGUIController
from logs_pack import initialize_logger

app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(Path(__file__).resolve().parents[1]))


def main():
    logger = initialize_logger(app_folder / 'LOG', file_name="ServerGUI")
    logger.info('Starting Server GUI...')
    app = QApplication(sys.argv)
    ServerGUIController(ServerGUIModel(app_folder))
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
