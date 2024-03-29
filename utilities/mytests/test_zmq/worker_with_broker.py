#
#   Request-reply service in Python
#   Connects REP socket to tcp://localhost:5560
#   Expects "Hello" from client, replies with "World"
#
from time import sleep

import zmq

context = zmq.Context()
socket = context.socket(zmq.REP)
socket.connect("tcp://127.0.0.1:5560")

while True:
    message = socket.recv()
    print("Received request: %s" % message)
    sleep(2)
    socket.send(b"World")