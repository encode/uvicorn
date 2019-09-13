import sys
import asyncio


def asyncio_setup():
    if sys.platform == 'win32' and (sys.version_info.major >= 3 and sys.version_info.minor >= 7):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
