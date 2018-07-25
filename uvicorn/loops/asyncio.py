import asyncio


def asyncio_setup():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop
