
import zmq
import threading
from time import sleep

class Pub(threading.Thread):

    def __init__(self):
        super().__init__()
        self.context = zmq.Context()
        self.publisher = self.context.socket(zmq.PUB)
        self.publisher.bind("tcp://127.0.0.1:5556")
        self.dealer = self.context.socket(zmq.DEALER)
        self.dealer.setsockopt_unicode(zmq.IDENTITY, 'bloody')
        self.dealer.connect("tcp://127.0.0.1:5555")
        self.p = True
        self.r = True

    def run(self):
        s = 'test'.encode('utf-8')
        from random import randint
        i = 0
        while self.r:
            if self.p:
                i += 1
                f = str(i).encode('utf-8')
                self.publisher.send_multipart([f, s])
                self.dealer.send_multipart([f, s])
                self.dealer.send_multipart([f, s + s])
            sleep(0.1)


class Sub(threading.Thread):
    def __init__(self):
        super().__init__()
        self.context = zmq.Context()
        self.sub = self.context.socket(zmq.SUB)
        self.frontend = self.context.socket(zmq.ROUTER)
        self.frontend.bind("tcp://127.0.0.1:5555")
        self.poller = zmq.Poller()
        self.poller.register(self.sub, zmq.POLLIN)
        self.poller.register(self.frontend, zmq.POLLIN)

        self.sub.setsockopt(zmq.SUBSCRIBE, b"")
        self.sub.setsockopt(zmq.RCVHWM, 1)
        self.sub.connect("tcp://127.0.0.1:5556")
        self.p = True
        self.r = True


    def run(self):
        while self.r:
            if self.p:
                sockets = dict(self.poller.poll())

                if self.sub in sockets:
                    f, msg = self.sub.recv_multipart()
                    print('sub', f, msg)
                if self.frontend in sockets:
                    who, f, s= self.frontend.recv_multipart()
                    print('frontend', who, f, s)


p = Pub()
s = Sub()
p.start()
s.start()

sleep(1)
s.p = False
sleep(1)
p.p = False
s.p = True

