"""
01/04/2020
sergey.denisov@u-psud.fr
ICP/CNRS UMR8000
"""
import sys
from pathlib import Path

from PyQt5.QtWidgets import QApplication
from gui.models.ClientGUIModels import TreatmentModel
from gui.controllers.TreatmentController import TreatmentController
from logs_pack import initialize_logger

app_folder = Path(__file__).resolve().parents[1]


def main():
    logger = initialize_logger(app_folder / 'LOG', file_name="Treatment")
    logger.info('Starting Treatment GUI...')
    app = QApplication(sys.argv)
    TreatmentController(TreatmentModel(app_folder,
                                       data_folder='E:\\20240527_GdFAzo\\9701_water_600_x0'))
    app.exec_()


if __name__ == '__main__':
    main()
