'''
stepmotors widget is designed to control real delay lines
though communcation with devices widget using
ethernet as tests_hardware main communication line.
sergey.denisov@u-psud.fr
LCP/CNRS UMR8000 ELYSE platform
05/01/2019
'''

import sys
from pathlib import Path
app_folder = str(Path(__file__).resolve().parents[1])
sys.path.append(app_folder)

from PyQt5.QtWidgets import QApplication
from models.ClientGUIModels import StepMotorsModel
from controllers.ClientGUIControllers import StepMotorsController
from logs_pack import initialize_logger


def main():
    path = Path(__file__).resolve()
    logger = initialize_logger(path.parent / 'LOG', file_name="StepMotors")
    logger.info('Starting Step motors widget')
    app = QApplication(sys.argv)
    StepMotorsController(StepMotorsModel(Path(app_folder)))
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
