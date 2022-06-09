from dataclasses import dataclass
from threading import Thread
from typing import Dict
from time import sleep
@dataclass
class OrderInfo:
    order_done: bool



a = {1: OrderInfo(False), 2: OrderInfo(True)}


def change(a: Dict[int, OrderInfo]):
    while True:
        for name, order_info in a.items():
            order_info.order_done = False if order_info.order_done else True
        sleep(0.25)

def show(a: Dict[int, OrderInfo]):
    while True:
        for name, order_info in a.items():
            print(f'{name}: {order_info}')
        sleep(0.25)

t1 = Thread(target=change, args=[a])
t2 = Thread(target=show, args=[a])

t1.start()
t2.start()