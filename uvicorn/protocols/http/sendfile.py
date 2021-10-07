import asyncio
import os


def can_sendfile(loop) -> bool:
    """
    Judge loop.sendfile available
    """
    return (
        hasattr(asyncio, "ProactorEventLoop")
        and isinstance(loop, asyncio.ProactorEventLoop)
    ) or (isinstance(loop, asyncio.SelectorEventLoop) and hasattr(os, "sendfile"))
