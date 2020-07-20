import os
import pathlib
from time import sleep

def treat_com(com: str, commands: dict, messenger, logger, path):
    active = True
    x = com.split(' ')
    com = x[0]
    rest = x[1:]
    if com in commands:
        if com == '-help':
            for key, desription in commands.items():
                print(key + ':\t' + desription)
        elif com == "-start_server":
            try:
                if not messenger.thinker.server_hb:
                    p = str(path / 'server.py')
                    #subprocess.Popen([sys.executable, p],
                                     #shell=True,
                                     #creationflags=subprocess.DETACHED_PROCESS)
                    pyexec = str(pathlib.Path(path.parent.parent / 'python_env\mypy37\Scripts' / 'python.exe'))
                    exc = 'start cmd /K ' +  pyexec + " " + p
                    os.system(exc)
                else:
                    print('Server is already running...')
            except Exception as e:
                print(e)
        elif com == '-stop_server':
            msg = MessageOld(message_type='demand', from_=messenger.device_id, to_='Server_messenger')
            msg['datastructures']['com'] = 'stop_server'
            messenger.add_task_out()
            print('yes')
        elif com == '-start_service':
            pyexec = str(pathlib.Path(path.parent.parent / 'python_env\mypy37\Scripts' / 'python.exe'))
            p = str(path / 'device_start.py')
            exc = f'start cmd /K {pyexec} {p} {rest[0]} {rest[1]}'
            os.system(exc)
        elif com == '-quit':
            answer = input('Unsafe stop, are you sure? Y/N ')
            if answer == 'Y' or answer == 'y':
                active = False
                print('Quiting')
                messenger.stop()
                sleep(.8)
        elif com == '-server_status':
            print('Server status: ' + str(messenger.thinker.server_hb))
    else:
        logger.error('Command is unknown')
    return active
