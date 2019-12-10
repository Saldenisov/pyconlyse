import asyncio


async def async_generator():
    n = 1
    i = 0
    while n == 1:
        await asyncio.sleep(1)
        yield i*i
        i += 1

async def main():
    async for i in async_generator():
        print(i)


loop = asyncio.get_event_loop()
try:
    loop.run_until_complete(main())
finally:
    loop.run_until_complete(loop.shutdown_asyncgens())  # see: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.AbstractEventLoop.shutdown_asyncgens
    loop.close()