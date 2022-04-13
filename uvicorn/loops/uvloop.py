import asyncio

import uvloop


def uvloop_setup() -> None:
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
