import asyncio


def asyncio_setup() -> None:  # pragma: no cover
    loop: asyncio.AbstractEventLoop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
