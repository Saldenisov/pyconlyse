from threading import Thread
from time import sleep


def test1():
    while True:
        i = 10
        sleep(1)
        print(i)


def test2():
    while True:
        i = 20
        sleep(0.25)
        print(i)


a = Thread(target=test1)
b = Thread(target=test2)

a.start()
b.start()