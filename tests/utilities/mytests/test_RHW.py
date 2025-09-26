import zmq
adr = 'tcp://127.0.0.1:6001'
context = zmq.Context()
pub = context.socket(zmq.PUB)
pub.setsockopt_unicode(zmq.IDENTITY, 'publisher')
pub.bind(adr)
sub = context.socket(zmq.SUB)
poller = zmq.Poller()
poller.register(sub, zmq.POLLIN)
sub.setsockopt(zmq.SUBSCRIBE, b"")
sub.set_hwm(1)
#sub.setsockopt(zmq.RCVHWM, 1)
sub.connect(adr)

from threading import Thread
from time import sleep

def send_pub(pub):
    i = 0
    while True:
        i += 1
        pub.send_multipart([b'msg', str(i).encode('utf-8')])
        print(f'publishing msg_i = {i}')
        sleep(0.3)

t = Thread(target=send_pub, args=[pub])
t.start()

n = 0
sleeped = False
while True:
    n += 1
    print(f'n={n}')
    if n > 10 and not sleeped:
        sleeped = True
        print('sleeping')
        sleep(1)
    sockets = dict(poller.poll(300))
    if sub in sockets:
        data = sub.recv_multipart()
        print(f'recived {data}')