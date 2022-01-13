from threading import Thread
from time import sleep


class A(Thread):

    def __init__(self):
        super().__init__()
        self.active = False
        self.pause = False
    def a(self):
        print('Alive')
        sleep(0.5)

    def stop(self):
        self.active = False

    def hold(self):
        self.pause = True

    def unhold(self):
        self.pause = False

    def activate(self):
        self.active = True
        self.start()

    def run(self):
        while self.active:
            if not self.pause:
                self.a()
            else:
                sleep(0.2)


a = A()
a.activate()
a.hold()

sleep(1)
a.unhold()

