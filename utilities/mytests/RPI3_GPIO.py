from gpiozero.pins.pigpio import PiGPIOFactory
from gpiozero import LED


factory = PiGPIOFactory(host='10.20.30')

pin1 = LED(pin='1', pin_factory=factory)

for i in range(1000):
    print(f'{i}')
    pin1.on()
    pin1.off()