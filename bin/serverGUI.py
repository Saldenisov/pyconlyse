"""
sergey.denisov@u-psud.fr
LCP/CNRS UMR8000 ELYSE platform
06/08/2019
"""
import sys
from pathlib import Path
from PyQt5.QtWidgets import QApplication
from gui.models import ServerGUIModel
from gui.controllers import ServerGUIController
from logs_pack import initialize_logger

app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))


def main():
    logger = initialize_logger(app_folder / 'LOG', file_name="ServerGUI")
    logger.info('Starting Server GUI...')
    app = QApplication(sys.argv)
    model = ServerGUIModel(app_folder)
    ServerGUIController(model)
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
