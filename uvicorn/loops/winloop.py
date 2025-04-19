import asyncio

import winloop


def winloop_setup(use_subprocess: bool = False) -> None:
    asyncio.set_event_loop_policy(winloop.EventLoopPolicy())
