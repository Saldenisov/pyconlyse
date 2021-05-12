"""
nothing to say
"""

import sys

from PyQt5.QtWidgets import QApplication
from CONTROLLER.MController import MController
from LOGGING import initialize_logger
from MODEL import MModel

CONFIG = 'C:\\dev\\pyconlyse\\utilities\\prev_projects\\DATAFIT\\Settings\\'
ROOT = 'C:\\dev\\pyconlyse\\utilities\\prev_projects\\DATAFIT\\tests_files'


def main():
    initialize_logger('C:\\dev\\pyconlyse\\utilities\\prev_projects\\DATAFIT\\LOG', "MAIN")

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
