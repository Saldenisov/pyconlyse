"""
CLI for controlling 5V NEWPORT steppers with A9888
"""

from time import sleep

import RPi.GPIO as GPIO  # import RPi.GPIO module

GPIO.setmode(GPIO.BCM)  # choose BCM or BOARD

TTL_pin = 19
DIR_pin = 26
enable_pin = 12
ms1 = 21
ms2 = 20
ms3 = 16
relayIa = 2
relayIb = 3
relayIIa = 17
relayIIb = 27

GPIO.setup(TTL_pin, GPIO.OUT)
GPIO.setup(DIR_pin, GPIO.OUT)
GPIO.setup(enable_pin, GPIO.OUT)
GPIO.setup(ms1, GPIO.OUT)
GPIO.setup(ms2, GPIO.OUT)
GPIO.setup(ms3, GPIO.OUT)
GPIO.setup(relayIa, GPIO.OUT)
GPIO.setup(relayIb, GPIO.OUT)
GPIO.setup(relayIIa, GPIO.OUT)
GPIO.setup(relayIIb, GPIO.OUT)

# On/Off for relay normally closed
On = 0
Off = 1

GPIO.output(TTL_pin, 0)
GPIO.output(DIR_pin, 0)
GPIO.output(enable_pin, 0)

GPIO.output(relayIa, Off)
GPIO.output(relayIb, Off)

GPIO.output(relayIIa, Off)
GPIO.output(relayIIb, Off)


def set_settings(com='Full'):
    steps = [90, 90]
    TTL_width = 10.0  # ms
    delay_TTL = 20  # ms
    settings = {'Full': [[0, 0, 0], TTL_width, steps * 1],
                'Half': [[1, 0, 0], TTL_width / 2, steps * 2],
                'Quarter': [[0, 1, 0], TTL_width / 4, steps * 4],
                'Eight': [[1, 1, 0], TTL_width / 8, steps * 8],
                'Sixteen': [[1, 1, 1], TTL_width / 16, steps * 16], }
    GPIO.output(ms1, settings[com][0][0])
    GPIO.output(ms2, settings[com][0][1])
    GPIO.output(ms3, settings[com][0][2])
    return settings[com][1] / 1000, settings[com][2], delay_TTL


TTL_width, steps, delay_TTL = set_settings('Full')
print("Sleep time is {}; Steps between positions is {}.".format(TTL_width, steps))


def enable_controller():
    GPIO.output(enable_pin, 1)
    sleep(0.05)


def disable_controller():
    GPIO.output(enable_pin, 0)
    sleep(0.05)


def direction(orientation='top'):
    if orientation == 'top':
        GPIO.output(DIR_pin, 1)
    elif orientation == 'bottom':
        GPIO.output(DIR_pin, 0)


def deactivate_all_relay():
    GPIO.output(relayIa, Off)
    GPIO.output(relayIb, Off)
    GPIO.output(relayIIa, Off)
    GPIO.output(relayIIb, Off)

    sleep(0.1)


def activate_relay(n=1):
    if n == 1:
        deactivate_all_relay()
        GPIO.output(relayIa, On)
        GPIO.output(relayIb, On)
    elif n == 2:
        deactivate_all_relay()
        GPIO.output(relayIIa, On)
        GPIO.output(relayIIb, On)

    sleep(0.1)


def moveto(n_steps):
    enable_controller()
    if n_steps >= 0:
        direction('top')
    else:
        direction('bottom')
    for step in range(n_steps):
        GPIO.output(TTL_pin, 1)
        sleep(TTL_width)
        GPIO.output(TTL_pin, 0)
        sleep(delay_TTL)
    disable_controller()


position = [0, 0]
com = ''
try:
    while com != 'stop':
        com = input('Type command (e.g., -help: ')
        com = " ".join(com.split())
        com = str.split(com)

        if '-help' in com:
            print('Type -move 1 max or -move 1 min or -move 1 n_steps; -set_zero')

        elif '-set_zero' in com:
            position = 0
            print('Position is set to ZERO')

        elif '-move' in com:
            try:
                stepper = int(com[1])
                success = True
            except (KeyError, IndexError, ValueError) as e:
                print('While setting number of stepper, error occured {}'.format(e))

            if success:
                try:
                    if com[2] == 'max':
                        where = steps[stepper - 1]
                    elif com[2] == 'min':
                        where = 0

                    else:
                        where = int(com[2])

                    steps_to_go = where - position[stepper - 1]
                    position[stepper - 1] = position[stepper - 1] + steps_to_go

                    activate_relay(stepper)
                    moveto(steps_to_go)

                except (KeyError, IndexError, ValueError) as e:
                    print('While setting where to move, error occured {}'.format(e))


except KeyboardInterrupt:  # trap a CTRL+C keyboard interrupt
    print('Terminated by user')
finally:
    activate_relay(1)
    moveto(-1 * position[0])
    deactivate_all_relay()

    activate_relay(2)
    moveto(-1 * position[1])
    deactivate_all_relay()

    GPIO.cleanup()  # resets all GPIO ports used by this program
    print('Executation is terminated')
