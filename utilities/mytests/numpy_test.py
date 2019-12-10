import numpy as np
import time

def timing(f):
    def wrap(*args):
        time1 = time.time()
        ret = f(*args)
        time2 = time.time()
        print('{:s} function took {:.3f} ms'.format(f.__name__, (time2-time1)*1000.0))

        return ret
    return wrap

@timing
def test_func(n):
    ar = np.random.rand(n, 1)
    ar[ar < 0.5] = 100.0
    return ar

a = test_func(10**5)

