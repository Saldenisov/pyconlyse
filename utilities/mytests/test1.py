import zmq
from time import sleep

context = zmq.Context()
dealer1 = context.socket(zmq.DEALER)
dealer1.setsockopt_unicode(zmq.IDENTITY, "dealer")
dealer1.connect('tcp://129.175.100.70:5556')

dealer2 = context.socket(zmq.DEALER)
dealer2.setsockopt_unicode(zmq.IDENTITY, "dealer")
dealer2.connect('tcp://129.175.100.70:5557')


poller = zmq.Poller()
poller.register(dealer1, zmq.POLLIN)
poller.register(dealer2, zmq.POLLIN)


i = 0
while True:
    sleep(1)
    i += 1
    dealer1.send(f'Dealer1:{i}'.encode('utf-8'))
    dealer2.send(f'XXX2:{i}'.encode('utf-8'))