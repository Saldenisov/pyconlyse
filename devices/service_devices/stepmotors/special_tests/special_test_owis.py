import ctypes
from pathlib import Path
from threading import Thread
dll_path = str(Path("C:\dev\pyconlyse\devices\service_devices\stepmotors\DLL\ps90.dll"))
PS90_DLL = ctypes.WinDLL(dll_path)


def error_OWIS_ps90(code: int, type: int, user_def=''):
    errors_connections = {0: 'no error', -1: 'function error', -2: 'invalid serial com_port (com_port is not found)',
                  -3: 'access react_denied  (com_port is busy)', -4: 'access react_denied  (com_port is busy)',
                  -5: 'no response from control unit', -7: 'control unit with the specified serial number is not found',
                  -8: 'no connection to modbus/tcp', -9: 'no connection to tcp/ip socket'}
    errors_functions = {0: 'no error', -1: 'function error', -2: 'communication error', -3: 'syntax error',
                            -4: 'axis is in wrong state', -9: 'OWISid chip is not found',
                            -10: 'OWISid parameter is empty (not defined)'}
    if code > 0 or (code not in errors_connections or code not in errors_functions):
        return "Wrong code number"
    elif type not in [0, 1]:
        return "Wrong type of error"
    else:
        if code != 0:
            return errors_connections[code] if type == 0 else errors_functions[code]
        else:
            return user_def


def connect_simple_ps90(control_unit: int, ser_num=""):
    control_unit = ctypes.c_long(control_unit)
    #ser_num = ctypes.c_char_p(ser_num)
    res = PS90_DLL.PS90_SimpleConnect(control_unit, "") * -1  # *-1 is according official documentation
    return True if res == 0 else False, error_OWIS_ps90(res, 0)


def disconnect_ps90(control_unit: int):
    control_unit = ctypes.c_long(control_unit)
    res = PS90_DLL.PS90_Disconnect(control_unit)
    return True if res == 0 else False, error_OWIS_ps90(res, 1)


def _get_read_error_ps90(control_unit: int) -> int:
    if not isinstance(control_unit, ctypes.c_long):
        control_unit = ctypes.c_long(control_unit)
    res = PS90_DLL.PS90_GetReadError(control_unit)
    return res


def get_pos_ex_ps90(control_unit: int, axis: int):
    control_unit = ctypes.c_long(control_unit)
    pitch = 1
    axis = ctypes.c_long(axis)
    res = PS90_DLL.PS90_GetPosition(control_unit, axis) / 10000 * pitch
    error = _get_read_error_ps90(control_unit)
    if error != 0:
        res = False
    return res, error_OWIS_ps90(error, 1)


def motor_init_ps90(control_unit: int, axis: int):
    control_unit = ctypes.c_long(control_unit)
    axis = ctypes.c_long(axis)
    res = PS90_DLL.PS90_MotorInit(control_unit, axis)
    return True if res == 0 else False, error_OWIS_ps90(res, 1, f'Motor of axis {axis} is initialized')


def set_target_ex_ps90(control_unit: int, axis: int, value: float):
    control_unit = ctypes.c_long(control_unit)
    pitch = 1
    axis = ctypes.c_long(axis)
    value = ctypes.c_double(value / pitch)
    res = PS90_DLL.PS90_SetTargetEx(control_unit, axis, value)
    return True if res == 0 else False, error_OWIS_ps90(res, 1)


def go_target_ps90(control_unit: int, axis: int):
    control_unit = ctypes.c_long(control_unit)
    axis = ctypes.c_long(axis)
    res = PS90_DLL.PS90_GoTarget(control_unit, axis)
    return True if res == 0 else False, error_OWIS_ps90(res, 1)


res_connect = connect_simple_ps90(1)
print(f'Connect simple: {res_connect}')

res_motor_init = motor_init_ps90(1, axis=1)
print(f'Motor init axis=1: {res_motor_init}')

from random import uniform
from time import sleep
t_sleep = .12

def work_func():
    for i in range(50):
        go_to = round(uniform(0, 10), 2)
        res_set_target = set_target_ex_ps90(1, 1, go_to)
        if res_set_target[0]:
            res_go_to = go_target_ps90(1, 1)
            print(f'Round {i} - Setting target to {go_to}: {res_set_target} - Go_to: {res_go_to}')
            for j in range(10):
                print('Checking position...')
                res = get_pos_ex_ps90(1, 1)
                if res[0] == go_to:
                    break
                sleep(t_sleep)
        else:
            res_go_to = (False, 'Set target did not work')

def dummy_func():
    while True:
        print('Dummy func working')
        i = 89 ** 5
        sleep(0.05)


work_thread = Thread(target=work_func)
dummy_thread = Thread(target=dummy_func)

work_thread.start()
dummy_thread.start()

sleep(100)

res_disconnect = disconnect_ps90(1)
print(f'Disconnect: {res_connect}')



