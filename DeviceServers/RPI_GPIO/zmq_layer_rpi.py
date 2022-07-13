import zmq
import sys
import gpiozero
from typing import List, Dict, Tuple
from time import sleep
from threading import Thread
POLLING = 0.1
from gpiozero import LED

pins: Dict[int, LED] = {}
pins_threads: Dict[int, Thread]
active_pins: Dict[int, bool] = {}
order_ttl: Dict[str, int] = {}

def main(ip_adress: int):

    def create_sockets(port) -> Tuple[zmq.DEALER, zmq.Poller]:
        context = zmq.Context()
        dealer = context.socket(zmq.DEALER)
        dealer.setsockopt_unicode(zmq.IDENTITY, f'')
        # POLLER
        poller = zmq.Poller()
        poller.register(dealer, zmq.POLLIN)
        return dealer, poller

    def connect(socket: zmq.DEALER, ip_address: str):
        socket.connect(ip_address)

    def send_msg(socket: zmq.DEALER, msg: str):
        pass

    def receive_msg(socket: zmq.DEALER, poller: zmq.Poller) -> List[int, str]:
        """
        cmd[0]:
        1 - generte TTL
        2 - stop generation
        3 - give number of TTL already generated
        4 - toggle
        msg is utf string dict{cmd: str, order_id: str, pin_number: int, etc}
        """
        sockets = dict(poller.poll(1))
        if socket in sockets:
            msg: str = socket.recv_string()
            msg = msg.decode('utf-8')
            msg = eval(msg)
            return msg
        return -1

    def toggle(pin_number: int):
        make_busy(pin_number)
        pin = get_pin(pin_number)
        pin.toggle()
        make_not_busy(pin_number)

    def get_pin(pin_number: int) -> LED:
        if pin_number not in pins:
            pin = LED(pin_number)
            pins[pin_number] = pin
        pin: LED = pins[pin_number]
        return pin

    def make_busy(pin_number: int):
        active_pins[pin_number] = True

    def make_not_busy(pin_number: int):
        active_pins[pin_number] = False

    def generate_TTL(pin_number: int, number_ttl: int, delay: int, width: int):
        pin = get_pin(pin_number)
        make_busy(pin_number)
        if number_ttl >=1 and delay > 0 and width >0:
            width = width / 10 ** 6
            delay = delay / 10 ** 6
            i = 0
            while active_pins[pin_number] and i < number_ttl:
                pin.on()
                sleep(width)
                pin.off()
                sleep(delay)
                i += 1
            del pins_threads[pin_number]
            make_not_busy(pin_number)

    def stop_ttl(pin_number: int) -> int:
        pass

    def get_ttl_accomplished(pin_number: int) -> int:
        pass

    dealer, poller = create_sockets()
    connect(dealer, ip_adress)

    while True:
        msg = receive_msg(dealer, poller)
        cmd = msg['cmd']
        pin_number = cmd['pin_number']
        if cmd == 'TTL':
            if pin_number not in pins_threads:
                thr = Thread(target=generate_TTL, kwargs={'pin_number': cmd['pin_number'],
                                                          'delay': cmd['delay'],
                                                          'width': cmd['width'],
                                                          'number_ttl': cmd['number_ttl'],
                                                          'order_id': cmd['order_id']})
                pins_threads[pin_number] = thr
                thr.start()
        elif cmd == 'STOP':
            stop_ttl(order_id=cmd['order_id'])
        elif cmd == 'GET_TTL':
            get_ttl_accomplished(order_id=cmd['order_id'])
        elif cmd == 'TOGGLE':
            toggle(pin_number=cmd['pin_number'], order_id=cmd['order_id'])


if __name__ == "__main__":
    ip_adress= sys.argv[1]
    main(ip_adress)
