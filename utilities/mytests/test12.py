import zmq
import random
import sys
import time
from threading import Thread

def server():
    port = "5556"
    if len(sys.argv) > 1:
        port = sys.argv[1]
        int(port)

    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.bind("tcp://127.0.0.1:%s" % port)

    while True:
        socket.send(b'hi')
        time.sleep(.2)

def client():
    import sys
    import zmq

    port = "5556"
    # Socket to talk to server_p
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    #socket.setsockopt_unicode(zmq.SUBSCRIBE, "")

    print("Collecting updates from weather server_p...")
    socket.connect("tcp://127.0.0.1:%s" % port)

    # Process 5 updates
    total_value = 0
    for update_nbr in range(5):
        string = socket.recv()
        print(string)

    # print("Average messagedata value for topic '%s' was %dF" % (topicfilter, total_value / update_nbr))

t1 = Thread(target=server,name='s')
t2 = Thread(target=client,name='c')

t1.start()
t2.start()