param = {'MS_for_A4988': {'friendly_name': 'MS_for_A4988', 'pins': {1: 1, 2: 1, 3: 1}},
            '1_A4988': {'friendly_name': 'xuy', 'pins': {4: 0}},
            '2_A4988': {'friendly_name': 'xuy', 'pins': {5: 0}},
            '3_A4988': {'friendly_name': 'xuy', 'pins': {6: 0}},
            '4_A4988': {'friendly_name': 'xuy', 'pins': {7: 0}},
            '5_A4988': {'friendly_name': 'xuy', 'pins': {8: 0}},
            '1_DM542': {'friendly_name': 'xuy', 'pins': {9: 0}},
            '2_DM542': {'friendly_name': 'xuy', 'pins': {'A': 0}},
            '3_DM542': {'friendly_name': 'xuy', 'pins': {'B': 0}},
         }
import time
# connect to numato
import telnetlib
from time import sleep
HOST = "10.20.30.204"
user = 'admin'
password = 'elyse'

tn = telnetlib.Telnet(HOST, port=23)
tn.open(HOST, port=23)
user = user.encode('ascii') + b"\r\n"
tn.read_until(b"User Name: ")
tn.write(user)
password = password.encode('ascii') + b"\r\n"
tn.read_until(b"Password: ")
tn.write(password)
# sleep(1)
# print(tn.read_very_eager().decode('ascii'))
# cmd1 = 'gpio get 0'.encode('ascii') + b"\r\n"
# tn.write(cmd1)
# sleep(1)
# cmd2 = 'gpio read 0'.encode('ascii') + b"\r\n"
# tn.write(cmd2)
# sleep(1)
# print(tn.read_very_eager().decode('ascii'))

def form_cmd(pin_n, value):
    cmd = ''
    if value == 1:
        cmd = f'gpio set {pin_n}'
    elif value == 0:
        cmd = f'gpio clear {pin_n}'
    else:
        raise Exception('Incorrect value')
    return cmd.encode('ascii') + b'\r\n'

def send_to_numato(cmd):
    # print(cmd)
    tn.write(cmd)

def set_pin(pin_n, value):
    print(f'Pin_n: {pin_n}, value: {value}')
    print('Sending to Numato....')
    send_to_numato(form_cmd(pin_n, value))
    # code
    print('Checking if set.')


for device_name, parameters in param.items():
    for pin_n, value in parameters['pins'].items():
        set_pin(pin_n, value)

a = time.time()
for i in range(3000):
    # sleep(0.1)
    if i%2 == 0:
        value = 0
    else:
        value = 1

    send_to_numato(form_cmd(1, value))
tn.read_eager()
for i in range(2100):
    # sleep(0.1)
    if i%2 == 0:
        value = 0
    else:
        value = 1

    send_to_numato(form_cmd(1, value))

b = time.time()
print(f'Time elapsed: {b - a}')