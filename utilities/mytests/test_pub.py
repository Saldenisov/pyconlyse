import zmq
adr = 'tcp://127.0.0.1:6001'
context = zmq.Context()
pub = context.socket(zmq.PUB)
pub.setsockopt_unicode(zmq.IDENTITY, 'publisher')
pub.bind(adr)
sub = context.socket(zmq.SUB)
poller = zmq.Poller()
poller.register(sub, zmq.POLLIN)
sub.connect(adr)
sub.setsockopt(zmq.SUBSCRIBE, b"")
sub.setsockopt(zmq.RCVHWM, 10)

from threading import Thread
from time import sleep

def send_pub(pub):
    i = 0
    while True:
        i += 1
        pub.send_multipart([b'msg', str(i).encode('utf-8')])
        #print(f'publishing msg_i = {i}')
        sleep(0.05)

t = Thread(target=send_pub, args=[pub])
t.start()

n = 0
removed = False
added = False
while True:
    n += 1
    print(f'n={n}')
    if n > 100 and not removed:
        removed = True
        print('removing sub')
        poller.unregister(sub)
        sub.close()
        sub = None
    if n < 500:
        sleep(0.01)
    if n > 500 and not added:
        added = True
        sub = context.socket(zmq.SUB)
        poller.register(sub, zmq.POLLIN)
        sub.connect(adr)
        sub.setsockopt(zmq.SUBSCRIBE, b"")
        sub.setsockopt(zmq.RCVHWM, 10)
    sockets = dict(poller.poll(1))
    if sub in sockets:
        data = sub.recv_multipart()
        print(f'recived {data}')