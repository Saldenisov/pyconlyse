"""
nothing to say
"""

import sys
from PyQt5.QtWidgets import QApplication
from prev_projects.DATAFIT.MODEL import MModel
from prev_projects.DATAFIT.CONTROLLER.MController import MController
from prev_projects.DATAFIT.LOGGING import initialize_logger


CONFIG = 'C:\\dev\\pyconlyse\\prev_projects\\DATAFIT\\Settings\\'
ROOT = 'C:\\dev\\pyconlyse\\prev_projects\\DATAFIT\\tests_files'


def main():
    initialize_logger(
        '/utilities/prev_projects\\DATAFIT\\LOG', "MAIN")

    app = QApplication(sys.argv)

    # main model creation
    try:
        model = MModel(root=ROOT,
                       config_path=CONFIG,
                       developping=True)
    except:
        print('Shutting down...')

    # create controller and send reference on the model
    else:
        MController(model)

        app.exec()


if __name__ == '__main__':
    sys.exit(main())
