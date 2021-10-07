import asyncio
import os
import sys


def can_sendfile(loop) -> bool:
    """
    Judge loop.sendfile available
    """
    return sys.version_info[:2] >= (3, 7) and (
        (
            hasattr(asyncio, "ProactorEventLoop")
            and isinstance(loop, asyncio.ProactorEventLoop)
        )
        or (isinstance(loop, asyncio.SelectorEventLoop) and hasattr(os, "sendfile"))
    )
