import asyncio

import uvloop


def uvloop_setup(**_) -> None:
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
