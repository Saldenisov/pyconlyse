import time
import zmq
from zmq.devices.monitoredqueuedevice import MonitoredQueue
from zmq.utils.strtypes import asbytes
from multiprocessing import Process
from threading import Thread
import random

frontend_port = 5559
backend_port = 5560
monitor_port = 5562
number_of_workers = 1



def get_local_ip() -> str:
    from socket import gethostbyname, gethostname
    return gethostbyname(gethostname())

def monitordevice(ports):

    monitoringdevice = MonitoredQueue(zmq.XREP, zmq.XREQ, zmq.PUB, asbytes('in'), asbytes('out'))

    local = "tcp://" + get_local_ip()
    monitoringdevice.bind_in(local + ":%d" % ports['frontend_port'])
    monitoringdevice.bind_out(local + ":%d" % ports['backend_port'])
    monitoringdevice.bind_mon(local + ":%d" % ports['monitor_port'])

    monitoringdevice.setsockopt_in(zmq.RCVHWM, 1)
    monitoringdevice.setsockopt_out(zmq.SNDHWM, 1)

    thread = Thread(target=monitoringdevice.start, name='monitordevice')
    thread.start()

    print("Program: Monitoring device has started")

def server(backend_port):
    print("Program: Server connecting to device")
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    local = "tcp://" + get_local_ip()
    socket.connect(local + ":%s" % backend_port)
    server_id = random.randrange(1,10005)
    while True:
        message = socket.recv()
        print("Server: Received - %s" % message)
        socket.send_string("Response from server_p #%s" % server_id)

def client(frontend_port, client_id):
    print("Program: Worker #%s connecting to device" % client_id)
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    local = "tcp://" + get_local_ip()
    socket.connect(local + ":%s" % frontend_port)
    request_num = 1
    while True:
        time.sleep(1)
        socket.send_string("Request #%s from client#%s" % (request_num, client_id))
    #  Get the reply.
        message = socket.recv_multipart()
        print("Client: Received - %s" % message)
        request_num += 1

def monitor():
    print("Starting monitoring process")
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    print("Collecting updates from server_p...")
    local = "tcp://" + get_local_ip()
    socket.connect (local + ":%s" % monitor_port)
    socket.setsockopt_string(zmq.SUBSCRIBE, "")
    while True:
        string = socket.recv_multipart()
        print("Monitoring Client: %s" % string)


ports = {'frontend_port': 5559, 'backend_port': 5560, 'monitor_port': 5562}
monitordevice(ports)
#
# device = MonitoredQueue_device(ports)
# device.init()

server_p = Thread(target=server, args=(backend_port,))
server_p.start()
monitorclient_p = Thread(target=monitor)
monitorclient_p.start()

for client_id in range(number_of_workers):
    Thread(target=client, args=(frontend_port, client_id,)).start()
