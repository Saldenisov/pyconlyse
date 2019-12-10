'''
Hardware server_p programm is tests_hardware CUI.
It allows to control multiple devices from GUI client applications

sergey.denisov@u-psud.fr
LCP/CNRS UMR8000 ELYSE platform
17/01/2019
'''

import sys
import logging
from pathlib import Path
app_folder = str(Path(__file__).resolve().parents[1])
sys.path.append(app_folder)

from bin.useful import treat_com
from time import sleep
from logs_pack import initialize_logger
from utilities import save_parameters
from communication import ServerCLILogic, ClientMessenger


COMMANDS = {'-help': 'help',
            '-start_server': 'starts server_p execution in separate terminal',
            '-server_status': 'gives information on server_p status',
            '-server_clients': 'gives the number of clients connected to server_p',
            '-stop_server': 'stops server_p execution, warning clients about this event',
            '-add_hardware': 'the .py file should be passed in the command, e.g., -add_hardware script.py',
            '-start_service': """to start service type '-start_service service_name DB_file_name options'""",
            '-quit': 'stop execution'}


addresses = {'server_frontend': 'tcp://127.0.0.1:5554',
             'server_pub': 'tcp://127.0.0.1:5555',
             'publisher': 'tcp://127.0.0.1:5556'}


def init():
    path = Path(__file__).resolve()
    initialize_logger(path.parent / 'LOG', file_name="ServerCLI")
    logger = logging.getLogger("ServerCLI")
    logger.info('ServerCLI is starting...')
    messenger = ClientMessenger(name='ServerCLI_messenger',
                                parent=None,
                                addresses=addresses,
                                thinker_class=ServerCLILogic)
    messenger.subscribe_sub()
    messenger.connect()
    messenger.start()
    com_treat = save_parameters(commands=COMMANDS,
                                messenger=messenger,
                                logger=logger,
                                path=path.parent)(treat_com)
    sleep(0.51)
    return com_treat, logger


def main(Cmds: list):
    active = True
    com_treat, logger = init()
    if Cmds:
        cmds = Cmds
    else:
        cmds = ['-start_service DL_emulate DL_DB.db']
    while active:
        if cmds:
            com = cmds.pop(0)
            print(com)
        else:
            com = input('Type command (e.g., -help): ')
        active = com_treat(com=com)
        sleep(0.2)


if __name__ == "__main__":
    main(sys.argv[1:])