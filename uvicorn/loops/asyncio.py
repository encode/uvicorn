import asyncio
import platform
import selectors
import sys
from asyncio import AbstractEventLoop


def asyncio_setup() -> None:
    loop: AbstractEventLoop
    if (
        sys.version_info.major >= 3
        and sys.version_info.minor >= 8
        and platform.system() == "Windows"
    ):
        selector = selectors.SelectSelector()
        loop = asyncio.SelectorEventLoop(selector)
        asyncio.set_event_loop(loop)
    else:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
