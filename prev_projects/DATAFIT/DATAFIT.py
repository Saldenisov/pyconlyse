"""
nothing to say
"""

import sys
from PyQt5.QtWidgets import QApplication
from MODEL import MModel
from CONTROLLER.MController import MController
from LOGGING import initialize_logger


CONFIG = 'C:\\Users\\Sergey Denisov\\Dropbox\\Python\\DATAFIT\\Settings\\'
ROOT = 'C:\\Users\\Sergey Denisov\\Dropbox\\Python\\DATAFIT\\tests_files'


def main():
    initialize_logger(
        'C:\\Users\\Sergey Denisov\\Dropbox\\Python\\DATAFIT\\LOG', "MAIN")

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
