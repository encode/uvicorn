import asyncio
import platform
import sys


def asyncio_setup():

    loop = asyncio.new_event_loop()
    if (
        sys.version_info.major >= 3
        and sys.version_info.minor >= 8
        and platform.system() == "Windows"
    ):
        asyncio.set_event_loop_policy(asyncio.SelectorEventLoop())
    else:
        asyncio.set_event_loop(loop)
