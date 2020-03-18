import concurrent.futures
from time import sleep
def foo(bar):
    print('hello {}'.format(bar))
    return 'foo'

def boo(bar):
    print('hello {}'.format(bar))
    sleep(2)
    return 'boo'

with concurrent.futures.ThreadPoolExecutor() as executor:
    future = executor.submit(foo, 'world!')
    future2 = executor.submit(boo, 'shit')
    return_value = future.result()
    print(return_value, future2.result())