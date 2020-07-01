from random import randrange

import zmq

context = zmq.Context()
socket = context.socket(zmq.PUB)
socket.bind("tcp://127.0.0.1:5556")

while True:
    zipcode = randrange(1, 100000)
    temperature = randrange(-80, 135)
    relhumidity = randrange(10, 60)
    # print("%i %i %i" % (zipcode, temperature, relhumidity))
    socket.send_string("%i %i %i" % (zipcode, temperature, relhumidity))