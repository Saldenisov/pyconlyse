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

    def send_msg(msg: str, id: str):
        # print(f'Sending msg {msg}')
        router.send_multipart([id, msg])

    def receive_msg(socket: zmq.ROUTER, poller: zmq.Poller):
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
            # print(f'Received cmd {msg}')
            return msg, id
        return -1, 0

    def make_busy(pin_number: int):
        pins[pin_number].active = True

    def make_not_busy(pin_number: int):
        pins[pin_number].active = False

    def get_pin(pin_number: int) -> MyPin:
        if pin_number not in pins:
            pin = MyPin(pin_number, LED(pin_number))
            pins[pin_number] = pin
        return pins[pin_number]

    def generate_TTL(pin_number: int, number_ttl: int, delay: int, width: int, order_id: Union[str, int], id: str):
        mypin = get_pin(pin_number)
        make_busy(pin_number)
        mypin.ttl_done = 0
        mypin.order_id = order_id
        if number_ttl >=1 and delay > 0 and width >0:
            width = width / 10 ** 6
            delay = delay / 10 ** 6
            print(f'Start to generate TTL pulses {number_ttl} with width {width} and dt {delay}.')
            print('[', end='')
            i = 1
            while mypin.active and mypin.ttl_done < number_ttl:
                mypin.on()
                sleep(width)
                mypin.off()
                sleep(delay)
                mypin.ttl_done += 1

                if mypin.ttl_done / number_ttl > i * .1:
                    i += 1
                    print("#", end='')

            mypin.thread = None
            if mypin.ttl_done == number_ttl:
                print(']')
            print(f'Stopped generating TTL pulses. Number of pulses: {mypin.ttl_done}')
            reply = form_reply(mypin, 'ttl')
            send_msg(reply, id)
            make_not_busy(pin_number)

    def stop_ttl(pin_number: int, id: str, order_id=""):
        mypin = get_pin(pin_number)
        mypin.active = False
        mypin.order_id = order_id
        reply = form_reply(mypin, 'stop_ttl')
        send_msg(reply, id)

    def on(pin_number: int, id: str, order_id=""):
        mypin = get_pin(pin_number)
        mypin.on()
        mypin.order_id = order_id
        reply = form_reply(mypin, 'on')
        send_msg(reply, id)

    def off(pin_number: int, id: str, order_id=""):
        mypin = get_pin(pin_number)
        mypin.off()
        mypin.order_id = order_id
        reply = form_reply(mypin, 'off')
        send_msg(reply, id)

    def toggle(pin_number: int, id: str, order_id=""):
        mypin = get_pin(pin_number)
        mypin.toggle()
        mypin.order_id = order_id
        reply = form_reply(mypin, 'toggle')
        send_msg(reply, id)

    def value(pin_number: int, id: str, order_id=""):
        mypin = get_pin(pin_number)
        mypin.order_id = order_id
        reply = form_reply(mypin, 'value')
        send_msg(reply, id)

    def get_ttl_accomplished(pin_number: int, id: str, order_id="") -> int:
        mypin = get_pin(pin_number)
        mypin.order_id = order_id
        reply = form_reply(mypin, 'get_ttl')
        send_msg(reply, id)

    def form_reply(mypin: MyPin, cmd='') -> bytes:
        reply = {}
        reply['order_id'] = mypin.order_id
        reply['ttl_done'] = mypin.ttl_done
        reply['state'] = mypin.value()
        reply['cmd'] = cmd
        reply = str(reply).encode('utf-8')
        return reply

    router, poller = create_sockets()
    bind(router, ip_adress)

    while True:
        msg, id = receive_msg(router, poller)
        if msg != -1:
            cmd = msg['cmd']
            if cmd == 'TTL':
                mypin = get_pin(msg['pin_number'])
                if mypin.thread == None:
                    thr = Thread(target=generate_TTL, kwargs={'pin_number': msg['pin_number'],
                                                              'delay': msg['delay'],
                                                              'width': msg['width'],
                                                              'number_ttl': msg['number_ttl'],
                                                              'order_id': msg['order_id'],
                                                              'id': id
                                                              })
                    mypin.thread = thr
                    thr.start()
            elif cmd == 'STOP':
                stop_ttl(pin_number=msg['pin_number'], id=id, order_id=msg['order_id'])
            elif cmd == 'GET_TTL':
                get_ttl_accomplished(pin_number=msg['pin_number'], id=id, order_id=msg['order_id'])
            elif cmd == 'TOGGLE':
                toggle(pin_number=msg['pin_number'], id=id, order_id=msg['order_id'])
            elif cmd == 'ON':
                on(pin_number=msg['pin_number'], id=id, order_id=msg['order_id'])
            elif cmd == 'OFF':
                off(pin_number=msg['pin_number'], id=id, order_id=msg['order_id'])
            elif cmd == 'VALUE':
                value(pin_number=msg['pin_number'], id=id, order_id=msg['order_id'])



if __name__ == "__main__":
    # tcp://129.175.100.128:5555
    ip_address = sys.argv[1]
    main(ip_address)
