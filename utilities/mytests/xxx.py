from functools import wraps



dev = False
class A:

    @decor(dev=dev)
    def f(self):
        print('Dev is set to false')


a = A()
a.f()