"""
CLI for controlling 5V NEWPORT steppers with A9888
in reality 12V is supplied, thus is really important to
disable controller and switch off for doulbe protection
so current does not run during waiting time

4 axis are controlled at this moment with this peace of code

"""
import RPi.GPIO as GPIO  # import RPi.GPIO module

from time import sleep


GPIO.setmode(GPIO.BCM)  # choose BCM or BOARD

TTL_pin = 19
DIR_pin = 26
enable_pin = 12
ms1 = 21
ms2 = 20
ms3 = 16
relayIa = 2 #orange
relayIb = 3 #red
relayIIa = 17 #brown hz
relayIIb = 27 #green
relayIIIa = 22 #yellow
relayIIIb = 10 #gray
relayIVa = 9 #blue
relayIVb = 11 #green

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
GPIO.setup(relayIIIa, GPIO.OUT)
GPIO.setup(relayIIIb, GPIO.OUT)
GPIO.setup(relayIVa, GPIO.OUT)
GPIO.setup(relayIVb, GPIO.OUT)

#On/Off for relay normally closed
On = 0
Off = 1

GPIO.output(TTL_pin, 0)
GPIO.output(DIR_pin, 0)
GPIO.output(enable_pin, 0)


GPIO.output(relayIa, Off)
GPIO.output(relayIb, Off)

GPIO.output(relayIIa, Off)
GPIO.output(relayIIb, Off)

GPIO.output(relayIIIa, Off)
GPIO.output(relayIIIb, Off)

GPIO.output(relayIVa, Off)
GPIO.output(relayIVb, Off)


def set_settings(com='Full'):
    steps = [(90,0), (90,0), (90,0), (90,0)],
    TTL_width = {1: 30./1000,
                 2: 3./1000,
                 3: 5./1000,
                 4: 5./1000}  # s
    delay_TTL = {1: 5./1000, 
                 2: 1./1000,
                 3: 5./1000,
                 4: 5./1000}  # s
    settings = {'Full': [[0, 0, 0], 1],
                'Half': [[1, 0, 0],  2],
                'Quarter': [[0, 1, 0],  4],
                'Eight': [[1, 1, 0], 8],
                'Sixteen': [[1, 1, 1], 16]}
    GPIO.output(ms1, settings[com][0][0])
    GPIO.output(ms2, settings[com][0][1])
    GPIO.output(ms3, settings[com][0][2])
    return  settings[com][1], TTL_width,  delay_TTL, steps



coef,  TTL_width, delay_TTL, steps = set_settings('Sixteen')
print("Sleep time is {}; Steps between positions is {}.".format(TTL_width, steps))


def enable_controller():
    GPIO.output(enable_pin, 0)
    sleep(0.05)


def disable_controller():
    GPIO.output(enable_pin, 1)
    sleep(0.05)


def direction(orientation='top'):
    if orientation == 'top':
        GPIO.output(DIR_pin, 1)
    elif orientation == 'bottom':
        GPIO.output(DIR_pin, 0)
    sleep(0.05)


def deactivate_all_relay():
    GPIO.output(relayIa, Off)
    GPIO.output(relayIb, Off)
    GPIO.output(relayIIa, Off)
    GPIO.output(relayIIb, Off)
    GPIO.output(relayIIIa, Off)
    GPIO.output(relayIIIb, Off)
    GPIO.output(relayIVa, Off)
    GPIO.output(relayIVb, Off)
    sleep(0.1)


def activate_relay(n):
    if n == 1:
        deactivate_all_relay()
        GPIO.output(relayIa, On)
        GPIO.output(relayIb, On)
    elif n == 2:
        deactivate_all_relay()
        GPIO.output(relayIIa, On)
        GPIO.output(relayIIb, On)
    elif n == 3:
        deactivate_all_relay()
        GPIO.output(relayIIIa, On)
        GPIO.output(relayIIIb, On)
    elif n == 4:
        deactivate_all_relay()
        GPIO.output(relayIVa, On)
        GPIO.output(relayIVb, On)
    sleep(0.1)


def moveto(n_steps, axis):
    enable_controller()
    activate_relay(axis)	
    if n_steps >=0:
        direction('top')
    else:
        direction('bottom')
    width = TTL_width[axis] / coef
    delay = delay_TTL[axis] / coef
    for step in range(abs(n_steps * coef)):
        GPIO.output(TTL_pin, 1)
        sleep(width)
        GPIO.output(TTL_pin, 0)
        sleep(delay)
    sleep(0.3)
    disable_controller()
    deactivate_all_relay()

positions = [0, 0, 0, 0]
com = []

try:
    while 'stop' not in com:
        com = input('Type command (e.g., help): ')
        com = " ".join(com.split())
        com = str.split(com)
        
        if 'help' in com:
            print('Type move 1 max or move 1 min or move 1 n_steps; set_zero 1')

        elif 'set_zero' in com:
            try:
                axis = int(com[1])
                if axis <= 0:
                    raise ValueError
                positions[axis-1] = 0
            except (KeyError, IndexError, ValueError) as e:
                print('Wrong axis is passed')
            print('Position {}'.format(positions))
        elif 'move' in com:  
            try:
                stepper = int(com[1])
                success = True
            except (KeyError, IndexError, ValueError) as e:
                print('While setting number of stepper, error occured {}'.format(e))

            if success:
                try:
                    if com[2] == 'max':
                        where = steps[stepper-1][0]
                    elif com[2] == 'min':
                        where = 0
                    else:
                        where = int(com[2])

                    steps_to_go = where - positions[stepper-1]
                    positions[stepper-1] = positions[stepper-1] + steps_to_go

                    moveto(steps_to_go, stepper)

                except (KeyError, IndexError, ValueError) as e:
                    print('While setting where to move, error occured {}'.format(e))
            print('move is done')
        elif 'pos' in com:
            print('Positions {}'.format(positions))


except KeyboardInterrupt:  # trap a CTRL+C keyboard interrupt
    print('Terminated by user')
finally:
    for axis in range(4):
        if positions[axis] != 0:        
            activate_relay(axis + 1)
            moveto(-1*positions[axis], axis+1)
            deactivate_all_relay()

    deactivate_all_relay()	
    GPIO.cleanup()  # resets all GPIO ports used by this program
    print('Executation is terminated')

