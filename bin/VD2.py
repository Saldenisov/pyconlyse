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
from models.ClientGUIModels import VD2Treatment
from controllers.ClientGUIControllers import VD2TreatmentController
from logs_pack import initialize_logger




def main():
    logger = initialize_logger(app_folder / 'LOG', file_name="VD2Treatment")
    logger.info('Starting VD2Treatment GUI...')
    app = QApplication(sys.argv)
    VD2TreatmentController(VD2Treatment(app_folder))
    app.exec_()


if __name__ == '__main__':
    main()
