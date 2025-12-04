"""
01/04/2020
sergey.denisov@u-psud.fr
ICP/CNRS UMR8000
"""
import sys
from pathlib import Path

app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))

from PyQt5.QtWidgets import QApplication

from gui.models.ClientGUIModels import TreatmentModel
from gui.controllers.TreatmentController import TreatmentController
from gui.treatment_config import get_data_folder
from logs_pack import initialize_logger


def main():
    logger = initialize_logger(app_folder / 'LOG', file_name="Treatment")
    logger.info('Starting Treatment GUI...')

    data_folder = get_data_folder()
    logger.info(f"Using data folder: {data_folder}")

    app = QApplication(sys.argv)
    TreatmentController(TreatmentModel(app_folder, data_folder=data_folder))

    app.exec_()


if __name__ == '__main__':
    main()
