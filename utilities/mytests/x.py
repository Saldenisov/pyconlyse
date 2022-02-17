import numato_gpio as gpio

my_device_id = '12345678'
a = gpio.discover()
dev = gpio.devices[my_device_id]

dev.setup(1, gpio.OUT)


# configure port 4 as output apnd set it to high
#dev.setup(4, gpio.OUT)
#dev.write(4, 1)

# configure port 27 as input and print its logic level
#dev.setup(27, gpio.IN)
#print(dev.read(27))

# configure port 2 as input and print its ADC value
#dev.setup(2, gpio.IN)
#print(dev.adc_read(2))

# configure port 14 as input and setup notification on logic level changes
#dev.setup(14, gpio.IN)
#def callback(port, level):
#    print("{edge:7s} edge detected on port {port} "
 #       "-> new logic level is {level}".format(
 #       edge="Rising" if level else "Falling",
 #       port=port,
 #       level="high" if level else "low")
 #   )

# dev.add_event_detect(14, callback, gpio.BOTH)
dev.notify = True