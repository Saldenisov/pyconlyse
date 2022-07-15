import zmq
import sys
import gpiozero
from typing import List, Dict, Tuple, Union
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

    def value(self):
        return self.gpiopin.value

    def on(self):
        self.gpiopin.on()

    def off(self):
        self.gpiopin.off()

    def toggle(self):
        self.gpiopin.toggle()


pins: Dict[int, MyPin] = {}
router = None

def main(ip_adress: int):

    def create_sockets():
        context = zmq.Context()
        router = context.socket(zmq.ROUTER)
        router.setsockopt_unicode(zmq.IDENTITY, f'{get_random_string(5)}')
        # POLLER
        poller = zmq.Poller()
        poller.register(router, zmq.POLLIN)
        return router, poller

    def bind(socket: zmq.ROUTER, ip_address: str):
        socket.bind(ip_address)

    def send_msg(msg: str):
        router.send_string(msg)

    def receive_msg(socket: zmq.ROUTER, poller: zmq.Poller, order_id: Dict[str, str]):
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
            id, msg = socket.recv_multipart()
            msg = msg.decode('utf-8')
            msg = eval(msg)
            print(f'Received cmd {msg}')
            order_id[msg['order_id']] = id
            return msg, id
        return -1

    def make_busy(pin_number: int):
        pins[pin_number].active = True

    def make_not_busy(pin_number: int):
        pins[pin_number].active = False

    def toggle(pin_number: int):
        make_busy(pin_number)
        pin = get_pin(pin_number)
        pin.toggle()
        make_not_busy(pin_number)

    def get_pin(pin_number: int) -> MyPin:
        if pin_number not in pins:
            pin = MyPin(pin_number, LED(pin_number))
            pins[pin_number] = pin
        return pins[pin_number]

    def generate_TTL(pin_number: int, number_ttl: int, delay: int, width: int, order_id: Union[str, int]):
        mypin = get_pin(pin_number)
        make_busy(pin_number)
        mypin.ttl_done = 0
        mypin.order_id = order_id
        if number_ttl >=1 and delay > 0 and width >0:
            width = width / 10 ** 6
            delay = delay / 10 ** 6
            print(f'Start to generate TTL with width {width} and dt {delay}.')
            while mypin.active and mypin.ttl_done < number_ttl:
                mypin.on()
                sleep(width)
                mypin.off()
                sleep(delay)
                mypin.ttl_done += 1
            mypin.thread = None
            print('Stopped generating TTL pulses')
            reply = form_reply(mypin)
            send_msg(reply)

            make_not_busy(pin_number)

    def stop_ttl(pin_number: int):
        mypin = get_pin(pin_number)
        mypin.active = False
        reply = form_reply(mypin)
        send_msg(reply)

    def on(pin_number: int):
        mypin = get_pin(pin_number)
        mypin.on()
        reply = form_reply(mypin)
        send_msg(reply)

    def off(pin_number: int):
        mypin = get_pin(pin_number)
        mypin.off()
        reply = form_reply(mypin)
        send_msg(reply)

    def toggle(pin_number: int):
        mypin = get_pin(pin_number)
        mypin.toggle()
        reply = form_reply(mypin)
        send_msg(reply)

    def value(pin_number: int):
        mypin = get_pin(pin_number)
        reply = form_reply(mypin)
        send_msg(reply)

    def form_reply(mypin: MyPin) -> bytes:
        reply = {}
        reply['order_id'] = mypin.order_id
        reply['ttl_done'] = mypin.ttl_done
        reply['state'] = mypin.value()
        reply = str(reply).encode('utf-8')
        return reply

    def get_ttl_accomplished(pin_number: int) -> int:
        mypin = get_pin(pin_number)
        reply = form_reply(mypin)
        send_msg(reply)

    dealer_socket, poller = create_sockets()
    bind(dealer_socket, ip_adress)

    while True:
        msg, id = receive_msg(dealer_socket, poller)
        if msg != -1:
            cmd = msg['cmd']
            mypin = get_pin(cmd['pin_number'])
            if cmd == 'TTL':
                if mypin.thread == None:
                    thr = Thread(target=generate_TTL, kwargs={'pin_number': cmd['pin_number'],
                                                              'delay': cmd['delay'],
                                                              'width': cmd['width'],
                                                              'number_ttl': cmd['number_ttl'],
                                                              'order_id': cmd['order_id'],
                                                              'id': id
                                                              })
                    mypin.thread = thr
                    thr.start()
            elif cmd == 'STOP':
                stop_ttl(pin_number=cmd['pin_number'], id=id)
            elif cmd == 'GET_TTL':
                get_ttl_accomplished(pin_number=cmd['pin_number'], id=id)
            elif cmd == 'TOGGLE':
                toggle(pin_number=cmd['pin_number'], id=id)
            elif cmd == 'ON':
                on(pin_number=cmd['pin_number'], id=id)
            elif cmd == 'OFF':
                off(pin_number=cmd['pin_number'], id=id)
            elif cmd == 'VALUE':
                value(pin_number=cmd['pin_number'], id=id)



if __name__ == "__main__":
    # tcp://129.175.100.128:5555
    ip_address = sys.argv[1]
    main(ip_address)
