import threading

class StoppableThread(threading.Thread):
    """Thread class with tests_hardware stop() method. The thread itself has to check
    regularly for the stopped() condition."""

    def __init__(self, target):
        super(StoppableThread, self).__init__(target=target)
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def stopped(self):
        return self._stop_event.is_set()
from time import sleep

def f():

    while True:
        print('yes')
        sleep(0.5)

a = StoppableThread(target=f)

a.start()

sleep(3)
a.stop()

