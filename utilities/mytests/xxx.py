from time import sleep
from concurrent.futures import ThreadPoolExecutor
class A:
    def __init__(self):
        self.a = 10
        self._main_executor = ThreadPoolExecutor(max_workers=10)

    def add_to_executor(self, func, **kwargs):
        # used for slow methods and functions
        self._main_executor.submit(func, **kwargs)

    def _exec_mes_every_n_sec(self, f=None, flag=False, delay=1, n_max=2, specififc={}):
        print("_exec_mes_every_n_se")
        i = 0
        if delay > 5:
            delay = 5
        from time import sleep
        while self.flag and i <= n_max:
            i += 1
            print(i)
            f(**specififc)
            sleep(delay)

    def f(self, b=0, **kwargs):
        print(f'func f {b}')


    def test(self, **kwargs):
        #self._exec_mes_every_n_sec(f=self.f, flag=True, delay=1, n_max=2, specififc=kwargs)
        self.add_to_executor(self._exec_mes_every_n_sec, f=self.f, flag=self.flag, delay=1, n_max=2, specififc=kwargs)


a = A()
a.flag = True
a.test(b=1000, flag=True)
sleep(1.5)
a.flag = False





