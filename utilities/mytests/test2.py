import zmq


context = zmq.Context()
router1 = context.socket(zmq.ROUTER)
router2 = context.socket(zmq.ROUTER)
router1.bind('tcp://129.175.100.70:5556')
router2.bind('tcp://129.175.100.70:5557')

poller = zmq.Poller()
poller.register(router1, zmq.POLLIN)
poller.register(router2, zmq.POLLIN)

i = 0
while True:
    sockets = dict(poller.poll(1000))
    if router1 in sockets:
        print(router1.recv_multipart())
    if router2 in sockets:
        print(router2.recv_multipart())



