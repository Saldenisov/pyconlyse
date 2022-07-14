import zmq
import sys
import gpiozero
from typing import List, Dict, Tuple
from time import sleep
from threading import Thread
POLLING = 0.1
from gpiozero import LED
from dataclasses import dataclass

import random
import string

def get_random_string(length):
    # choose from all lowercase letter
    letters = string.ascii_lowercase
    result_str = ''.join(random.choice(letters) for i in range(length))
    return result_str

@dataclass
class MyPin:
    pin_number: int
    gpiopin: LED
    ttl_done: int = 0
    active: bool = False
    thread: Thread = None
    order_id: str = ''

pins: Dict[int, MyPin] = {}
dealer_socket = None


def main(ip_adress: int):

    def create_sockets():
        context = zmq.Context()
        dealer = context.socket(zmq.DEALER)
        dealer.setsockopt_unicode(zmq.IDENTITY, f'{get_random_string(5)}')
        # POLLER
        poller = zmq.Poller()
        poller.register(dealer, zmq.POLLIN)
        return dealer, poller

    def connect(socket: zmq.DEALER, ip_address: str):
        socket.connect(ip_address)

    def send_msg(msg: str):
        dealer_socket.send_string(msg)

    def receive_msg(socket: zmq.DEALER, poller: zmq.Poller):
        """
        cmd[0]:
        1 - TTL
        2 - STOP
        3 - GET_TTL
        4 - TOGGLE
        msg is utf string dict{cmd: str, order_id: str, pin_number: int, etc}
        """
        msg = {}
        sockets = dict(poller.poll(1))
        if socket in sockets:
            msg: str = socket.recv_string()
            msg = msg.encode('utf-8')
            msg = eval(msg)
            return msg
        return -1

    def make_busy(pin_number: int):
        pins[pin_number].active = True

    def make_not_busy(pin_number: int):
        pins[pin_number].active = False

    def toggle(pin_number: int):
        make_busy(pin_number)
        pin = get_pin(pin_number)
        pin.gpiopin.toggle()
        make_not_busy(pin_number)

    def get_pin(pin_number: int) -> MyPin:
        if pin_number not in pins:
            pins[pin_number] = MyPin(pin_number, LED(pin_number))
        return pins[pin_number]

    def generate_TTL(pin_number: int, number_ttl: int, delay: int, width: int):
        mypin = get_pin(pin_number)
        make_busy(pin_number)
        if number_ttl >=1 and delay > 0 and width >0:
            width = width / 10 ** 6
            delay = delay / 10 ** 6
            while mypin.active and mypin.ttl_done < number_ttl:
                mypin.gpiopin.on()
                sleep(width)
                mypin.gpiopin.off()
                sleep(delay)
                mypin.ttl_done += 1
            mypin.thread = None
            reply = form_reply(mypin)
            send_msg(reply)
            mypin.ttl_done = 0
            mypin.order_id = ''
            make_not_busy(pin_number)

    def stop_ttl(pin_number: int) -> int:
        mypin = get_pin(pin_number)
        mypin.active = False
        reply = form_reply(mypin)
        send_msg(reply)

    def form_reply(mypin: MyPin) -> bytes:
        reply = {}
        reply['order_id'] = mypin.order_id
        reply['ttl_done'] = mypin.ttl_done
        reply = str(reply).encode('utf-8')
        return reply

    def get_ttl_accomplished(pin_number: int) -> int:
        mypin = get_pin(pin_number)
        reply = form_reply(mypin)
        send_msg(reply)

    dealer_socket, poller = create_sockets()
    connect(dealer_socket, ip_adress)

    while True:
        msg = receive_msg(dealer_socket, poller)
        if msg != -1:
            cmd = msg['cmd']
            mypin = get_pin(cmd['pin_number'])
            if cmd == 'TTL':
                if mypin.thread == None:
                    thr = Thread(target=generate_TTL, kwargs={'pin_number': cmd['pin_number'],
                                                              'delay': cmd['delay'],
                                                              'width': cmd['width'],
                                                              'number_ttl': cmd['number_ttl'],
                                                              'order_id': cmd['order_id']
                                                              })
                    mypin.thread = thr
                    thr.start()
            elif cmd == 'STOP':
                stop_ttl(order_id=cmd['pin_number'])
            elif cmd == 'GET_TTL':
                get_ttl_accomplished(order_id=cmd['pin_number'])
            elif cmd == 'TOGGLE':
                toggle(pin_number=cmd['pin_number'])




if __name__ == "__main__":
    # tcp://129.175.100.128:5555
    ip_address = sys.argv[1]
    main(ip_address)
