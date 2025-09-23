from taurus import Device

rpi_name = 'manip/v0/rpi3_gpio_v0'
dir = 27

dev = Device(rpi_name)
dev.set_pin_state([dir, 0])
print(dev.get_pin_state(dir))

from time import sleep

dt = 0.000001


for i in range(1000):
    dev.set_pin_state([dir, 1])
    sleep(dt)
    dev.set_pin_state([dir, 0])
    sleep(dt*3)
