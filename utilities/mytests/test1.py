from gpiozero import LED
from time import sleep

from gpiozero.pins.pigpio import PiGPIOFactory

factory = PiGPIOFactory(host='129.175.100.171')

control_pin = LED(4, pin_factory=factory)

def change_state():
    control_pin.on()
    sleep(1)
    control_pin.off()

while True:
    command = input('Click any button to change state.')
    change_state()
