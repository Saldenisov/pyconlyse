from functools import wraps
from types import MethodType
def add_method(cls):
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            return func(*args, **kwargs)
        setattr(cls, func.__name__, wrapper)
        # Note we are not binding func, but wrapper which accepts self but does exactly the same as func
        return func # returning func means func can still be used normally
    return decorator


class A:
    def __init__(self):
        self.inter = 2
    def t(self):
        return self.inter**2


def test(self):
    print(self.t())


a = A()

a.test = MethodType(test, a)

a.test()


