import time
import asyncio
from concurrent.futures import ProcessPoolExecutor

def cpu_bound_worker(x, y):
    print("in worker")
    time.sleep(3)
    return x +y

@asyncio.coroutine
def some_coroutine():
    yield from asyncio.sleep(1)
    print("done with coro")

@asyncio.coroutine
def main():
    loop = asyncio.get_event_loop()
    loop.set_default_executor(ProcessPoolExecutor())
    asyncio.async(some_coroutine())
    out = yield from loop.run_in_executor(None, cpu_bound_worker, 3, 4)
    print("got {}".format(out))

loop = asyncio.get_event_loop()
loop.run_until_complete(main())


