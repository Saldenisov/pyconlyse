import gpiozero
from gpiozero.pins.pigpio import PiGPIOFactory
from gpiozero import LED, PWMLED


ip = '129.175.100.171'
n = 26
factory = PiGPIOFactory(host=ip)

pin = LED(n, pin_factory=factory)

import time


total = []
repeat = 100

pulse_width = 2
time_wait = 4

# a = time.time()
# pin.blink(on_time=1, off_time=0, n=1, background=False)
#
# print(f'Blink time of {repeat} repeat is {time.time() - a}')

start = time.time()
for i in range(repeat):
    a = time.time()
    pin.toggle()
    b = time.time()
    total.append(b - a)

print(f'Time: {sum(total) / repeat * 1000}')