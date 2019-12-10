#
#   Request-reply client in Python
#   Connects REQ socket to tcp://localhost:5559
#   Sends "Hello" to server_p, expects "World" back
#
import zmq

#  Prepare our context and sockets
context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.connect("tcp://127.0.0.1:5559")

#  Do 10 requests, waiting each time for tests_hardware response
for request in range(1,11):
    socket.send(b"Hello")
    message = socket.recv()
    print("Received reply %s [%s]" % (request, message))