from functools import wraps


def dll_lock(dll_containing_class):
    def decorator_function(func):
        @wraps(func)
        def inner(*args, **kwargs):
            dll_containing_class.lock = True
            res = func(*args, **kwargs)
            dll_containing_class.lock = False
            return res
        return inner
    return decorator_function


class A:
    def __init__(self):
        self.lock = 10

a = A()

@dll_lock(a)
def f(c):
    print(c)


f(10)
print(a.lock)
