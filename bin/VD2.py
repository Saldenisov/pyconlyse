"""
sergey.denisov@u-psud.fr
ICP/CNRS UMR8000
01/04/2020
"""


import sys
from pathlib import Path
app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))
from PyQt5.QtWidgets import QApplication
from gui.models import VD2TreatmentModel
from gui.controllers.ClientGUIControllers import VD2TreatmentController
from logs_pack import initialize_logger


def main():
    logger = initialize_logger(app_folder / 'LOG', file_name="VD2Treatment")
    logger.info('Starting VD2Treatment GUI...')
    app = QApplication(sys.argv)
    VD2TreatmentController(VD2TreatmentModel(app_folder, data_folder='D:\\DATA_VD2\\2020\\20200630-RK-940'))
    app.exec_()


if __name__ == '__main__':
    main()
